#!/usr/bin/env python3
"""
Extract credit-card transactions from PDF statements into JSON.

This script uses pdfplumber's page.extract_table() API because many card
statements are printed as visually tabular PDFs rather than embedded data files.
PDF table extraction is layout-sensitive, so the TABLE_SETTINGS block below is
intentionally easy to edit for a specific bank or statement family.

Usage:
    python parse_credit_card_statement.py statement.pdf
    python parse_credit_card_statement.py Statement_*.pdf -o transactions.json

Install dependency:
    pip install pdfplumber
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

try:
    import pdfplumber
except ModuleNotFoundError:
    pdfplumber = None


# pdfplumber table extraction settings.
#
# These values work well for many statements, but PDF extraction is rarely
# one-size-fits-all. If your columns are merged, split incorrectly, or missing:
#
# - Try vertical_strategy="lines" if the statement has visible vertical ruling
#   lines between columns. Use "text" when there are no lines and columns are
#   implied only by aligned text.
# - Try horizontal_strategy="lines" if the statement has horizontal row rules.
#   Use "text" when rows are separated only by whitespace.
# - Increase snap_tolerance / join_tolerance when nearly-aligned ruling lines
#   are not being treated as the same line.
# - Increase text_x_tolerance when words or amounts are split into separate
#   cells. Decrease it when neighboring columns get merged.
# - Increase intersection_tolerance when table lines visibly intersect but
#   pdfplumber does not recognize cell corners.
# - For especially difficult statements, inspect a page with:
#       page.to_image().debug_tablefinder(TABLE_SETTINGS).save("debug.png")
#   That overlay shows where pdfplumber thinks rows, columns, and cells are.
TABLE_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "intersection_tolerance": 5,
    "text_x_tolerance": 2,
    "text_y_tolerance": 3,
}


# Structured merchant keyword mapping. Keys are output categories; values are
# lowercase merchant substrings matched against normalized descriptions.
CATEGORY_MAPPING: dict[str, list[str]] = {
    "Credit Card Payments": [
        "autopay",
        "capital one mobile pymt",
        "automatic payment",
    ],
    "Groceries": [
        "trader joe",
        "wholefoods",
        "whole foods",
        "instacart",
        "jewel osco",
        "mariano",
        "costco",
        "aldi",
        "target",
        "patel brothers",
        "amazon grocery",
        "food mart",
    ],
    "Dining & Cafes": [
        "starbucks",
        "dunkin",
        "uber eats",
        "doordash",
        "sweetgreen",
        "mcdonalds",
        "grubhub",
        "kanela",
        "rivers and roads",
        "vaca",
        "sushi",
        "good eating",
        "taco",
        "cafe",
        "falafelnew",
        "bakerynew",
        "mediterranean",
        "veggie",
        "mango",
        "elephant",
        "wraps",
        "siena",
        "pizza",
        "maman",
        "thai",
        "coffee",
        "kitchen",
    ],
    "Transportation": [
        "uber",
        "lyft",
        "cta",
        "metra",
        "path",
        "mta",
        "sunoco",
        "park",
        "ventra",
        "shell",
        "bp",
        "exxon",
        "7-eleven",
        "spothero",
    ],
    "Utilities & Telecom": [
        "comed",
        "peoples gas",
        "at&t",
        "verizon",
        "t-mobile",
        "xfinity",
        "comcast",
    ],
    "Subscriptions": [
        "netflix",
        "spotify",
        "apple.com/bill",
        "amazon prime",
        "hulu",
        "nytimes",
        "adobe",
    ],
    "Shopping & Retail": [
        "amazon.com",
        "amazon pay",
        "amazon mktp",
        "amazon reta",
        "anthropologie",
        "nike",
        "apple store",
        "nordstrom",
        "zara",
        "home depot",
        "lowes",
        "ikea",
    ],
    "Health & Fitness": [
        "cvs",
        "walgreens",
        "equinox",
        "ffc",
        "planet fit",
        "northwestern med",
        "salon",
        "ent",
    ],
    "Pet Care": [
        "chewy",
        "petco",
        "petsmart",
        "vet",
        "barkbox",
        "krisers",
        "rover",
        "thefarmersdog.com",
    ],
    "Travel & Leisure": [
        "united air",
        "american air",
        "delta",
        "airbnb",
        "marriott",
        "hilton",
        "expedia",
        "travel",
        "etihad",
    ],
}


DATE_PATTERN = re.compile(
    r"^(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|[A-Z][a-z]{2}\s+\d{1,2})$"
)
AMOUNT_PATTERN = re.compile(r"-?\s*\(?\$?\s*\d[\d,]*(?:\.\d{2})?\)?")
DATE_TEXT = r"(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|[A-Z][a-z]{2}\s+\d{1,2})"
TEXT_TRANSACTION_PATTERN = re.compile(
    rf"^(?P<trans_date>{DATE_TEXT})\s+"
    rf"(?P<post_date>{DATE_TEXT})\s+"
    rf"(?P<description>.+?)\s+"
    rf"(?P<amount>-?\s*\(?\$?\s*\d[\d,]*\.\d{{2}}\)?(?:\s*(?:CR|Credit))?)$",
    flags=re.IGNORECASE,
)
CITI_DATE_TEXT = r"\d{1,2}/\d{1,2}"
CITI_TRANSACTION_PATTERN = re.compile(
    rf"^(?P<sale_date>{CITI_DATE_TEXT})"
    rf"(?:\s+(?P<post_date>{CITI_DATE_TEXT}))?\s+"
    rf"(?P<description>.+?)\s+"
    rf"(?P<amount>-?\$?\s*\d[\d,]*\.\d{{2}})"
    rf"(?:\s+.*)?$",
    flags=re.IGNORECASE,
)


NON_TRANSACTION_PATTERNS = [
    r"\bpage\s+\d+\b",
    r"\bcontinued\b",
    r"\btotal\b",
    r"\bsummary\b",
    r"\bbalance\b",
    r"\binterest\b",
    r"\bfees?\s+charged\b",
    r"\badditional\s+information\b",
    r"\bminimum\s+payment\b",
    r"\bnew\s+balance\b",
    r"\bprevious\s+balance\b",
    r"\btransactions?\s+continued\b",
    r"#\d{4}:\s+(?:payments,\s+credits\s+and\s+adjustments|transactions)\b",
]


SUPPLEMENTAL_DETAIL_PATTERNS = [
    # Foreign-currency detail lines often follow the USD transaction amount:
    #   $884.00
    #   INR
    #   89.473684211 Exchange Rate
    # These are useful audit details, but they are not separate transactions.
    r"^\$?\s*\d[\d,]*\.\d{2}$",
    r"^[A-Z]{3}$",
    r"^[A-Z ]+\s+RUPEE$",
    r"^\d{1,2}/\d{1,2}\s+[A-Z ]+\s+RUPEE$",
    r"^\d+(?:\.\d+)?\s+Exchange\s+Rate$",
    r"^\d[\d,]*\.\d{2}\s+X\s+\d+(?:\.\d+)?\s+\(EXCHG\s+RATE\)$",
    r"^Order\s+Number\b",
]


HEADER_TERMS = {
    "date",
    "transaction date",
    "post date",
    "posting date",
    "description",
    "merchant",
    "amount",
    "debits",
    "credits",
}


TEXT_TRANSACTION_HEADER_PATTERN = re.compile(
    r"\bTrans\s+Date\b.*\bPost\s+Date\b.*\bDescription\b.*\bAmount\b",
    flags=re.IGNORECASE,
)
CITI_TRANSACTION_HEADER_PATTERN = re.compile(
    r"^(?:Sale\s+Post|Trans\.\s+Post)(?:\s+Date|\s+\$|\s*$)",
    flags=re.IGNORECASE,
)
CHASE_TRANSACTION_HEADER_PATTERN = re.compile(
    r"^Transaction\s+Merchant\s+Name\s+or\s+Transaction\s+Description\s+\$?\s*Amount$",
    flags=re.IGNORECASE,
)
TRANSACTION_SECTION_HEADER_PATTERN = re.compile(
    rf"(?:{TEXT_TRANSACTION_HEADER_PATTERN.pattern})|(?:{CITI_TRANSACTION_HEADER_PATTERN.pattern})|(?:{CHASE_TRANSACTION_HEADER_PATTERN.pattern})",
    flags=re.IGNORECASE,
)
TRANSACTION_SECTION_START_PATTERN = re.compile(
    r"^(?:Payments,\s+Credits\s+and\s+Adjustments|Standard\s+Purchases(?:,?\s+cont'd)?|PAYMENTS\s+AND\s+OTHER\s+CREDITS|PURCHASE)\b",
    flags=re.IGNORECASE,
)
TRANSACTION_SECTION_END_PATTERN = re.compile(
    r"^(?:TOTAL\s+(?:FEES|INTEREST)|Total\s+(?:fees|interest)|Interest\s+charge|Annual\s+Percentage|Days\s+in\s+billing|2026\s+totals|FOR\s+THE\s+CHARGE|Your\s+is\s+the\s+annual)",
    flags=re.IGNORECASE,
)


@dataclass
class Transaction:
    date: str
    description: str
    amount: float
    category: str
    page: int
    card_source: str = "Unknown Card"


def clean_cell(value: object) -> str:
    """Normalize whitespace and convert missing PDF cells to empty strings."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def clean_row(row: Sequence[object]) -> list[str]:
    """Return a whitespace-normalized row without dropping positional cells."""
    return [clean_cell(cell) for cell in row]


def clean_description(description: str) -> str:
    """Normalize description whitespace and remove amount-sign leftovers."""
    return re.sub(r"\s+-\s*$", "", clean_cell(description))


def looks_like_header(row: Sequence[str]) -> bool:
    """Detect repeated table headers that can appear on every statement page."""
    if any(TRANSACTION_SECTION_HEADER_PATTERN.search(cell) for cell in row):
        return True

    lowered_cells = {cell.lower() for cell in row if cell}
    joined = " ".join(lowered_cells)
    header_hits = sum(term in lowered_cells or term in joined for term in HEADER_TERMS)
    return header_hits >= 2


def looks_like_transaction_section_header(line: str) -> bool:
    """Detect the copied-text transaction table heading."""
    return bool(TRANSACTION_SECTION_HEADER_PATTERN.search(clean_cell(line)))


def looks_like_transaction_section_start(line: str) -> bool:
    """Detect Citi section labels that precede transaction rows."""
    return bool(TRANSACTION_SECTION_START_PATTERN.search(clean_cell(line)))


def looks_like_transaction_section_end(line: str) -> bool:
    """Detect statement footer/rewards sections after transaction rows."""
    return bool(TRANSACTION_SECTION_END_PATTERN.search(clean_cell(line)))


def looks_like_non_transaction(row: Sequence[str]) -> bool:
    """Reject page furniture, subtotal lines, and other statement boilerplate."""
    non_empty = [cell for cell in row if cell]
    if not non_empty:
        return True

    joined = " ".join(non_empty).lower()
    if looks_like_header(row):
        return True

    if any(re.search(pattern, joined, flags=re.IGNORECASE) for pattern in NON_TRANSACTION_PATTERNS):
        # Avoid filtering a real transaction solely because its merchant name
        # contains a word like "total"; require the line not to look like a
        # normal date + amount transaction.
        has_date = any(DATE_PATTERN.search(cell) for cell in non_empty)
        has_amount = any(AMOUNT_PATTERN.search(cell) for cell in non_empty)
        if not (has_date and has_amount):
            return True

    # Rows with only one very short cell are almost always page labels or
    # formatting artifacts from the PDF table finder.
    return len(non_empty) == 1 and len(non_empty[0]) < 6


def parse_amount(raw_amount: str) -> float:
    """
    Convert statement amount text into a signed float.

    Handles examples like "$1,234.56", "-$12.99", "($45.00)", and
    "1,234.56 CR". Parentheses, leading minus signs, or credit markers are
    treated as negative values.
    """
    text = raw_amount.strip()
    if not text:
        raise ValueError("empty amount")

    is_negative = bool(
        text.startswith("-")
        or text.startswith("(")
        or text.endswith(")")
        or re.search(r"\b(?:cr|credit)\b", text, flags=re.IGNORECASE)
    )

    cleaned = re.sub(r"[^0-9.]", "", text)
    if not cleaned:
        raise ValueError(f"amount has no digits: {raw_amount!r}")

    amount = float(cleaned)
    return -amount if is_negative else amount


def normalize_for_matching(value: str) -> str:
    """Normalize text for case-insensitive substring merchant matching."""
    return re.sub(r"\s+", " ", value.lower()).strip()


def categorize(description: str, rules: dict[str, list[str]] = CATEGORY_MAPPING) -> str:
    """Assign the first matching merchant category, else Other."""
    normalized_description = normalize_for_matching(description)
    for category, keywords in rules.items():
        if any(normalize_for_matching(keyword) in normalized_description for keyword in keywords):
            return category
    return "Other"


def find_date(cells: Sequence[str]) -> tuple[int, str] | None:
    """Find the first cell that looks like a transaction or posting date."""
    for index, cell in enumerate(cells):
        if DATE_PATTERN.match(cell):
            return index, cell
    return None


def find_amount(cells: Sequence[str]) -> tuple[int, str] | None:
    """
    Find the right-most amount-looking cell.

    Transaction amounts are typically the final column. Searching from the
    right avoids accidentally treating a date fragment or reference number as
    the amount when extraction creates extra cells.
    """
    for index in range(len(cells) - 1, -1, -1):
        cell = cells[index]
        if AMOUNT_PATTERN.fullmatch(cell) or AMOUNT_PATTERN.search(cell):
            return index, cell
    return None


def parse_transaction_row(
    row: Sequence[str],
    page_number: int,
    card_source: str = "Unknown Card",
) -> Transaction | None:
    """Extract date, description, amount, and category from one table row."""
    if looks_like_non_transaction(row):
        return None

    cells = [cell for cell in row if cell]
    joined_cells = " ".join(cells)
    transaction = parse_citi_transaction_line(joined_cells, page_number, card_source)
    if transaction is None:
        transaction = parse_text_transaction_line(joined_cells, page_number, card_source)
    if transaction is not None:
        return transaction

    date_match = find_date(cells)
    amount_match = find_amount(cells)
    if date_match is None or amount_match is None:
        return None

    date_index, date_text = date_match
    amount_index, amount_text = amount_match
    if amount_index == date_index:
        return None

    description_parts = [
        cell
        for index, cell in enumerate(cells)
        if index not in {date_index, amount_index}
    ]
    raw_description = " ".join(description_parts)
    if re.search(r"\s+-\s*$", raw_description):
        amount_text = f"-{amount_text}"

    description = clean_description(raw_description)
    if not description:
        return None

    try:
        amount = parse_amount(amount_text)
    except ValueError:
        return None

    return Transaction(
        date=date_text,
        description=description,
        amount=amount,
        category=categorize(description),
        page=page_number,
        card_source=card_source,
    )


def parse_text_transaction_line(
    line: str,
    page_number: int,
    card_source: str = "Unknown Card",
) -> Transaction | None:
    """
    Parse a raw text line where columns are separated only by spaces.

    This handles copied/extracted lines such as:
        Dec 25 Dec 26 booking40813209835444646-5587089FL $82.89

    The first date is treated as the transaction date, the second date is the
    posting date, and the right-most currency value is the statement amount.
    """
    cleaned = clean_cell(line)
    match = TEXT_TRANSACTION_PATTERN.match(cleaned)
    if not match:
        return None

    description = clean_description(match.group("description"))
    try:
        amount = parse_amount(match.group("amount"))
    except ValueError:
        return None

    return Transaction(
        date=match.group("trans_date"),
        description=description,
        amount=amount,
        category=categorize(description),
        page=page_number,
        card_source=card_source,
    )


def parse_citi_transaction_line(
    line: str,
    page_number: int,
    card_source: str = "Unknown Card",
) -> Transaction | None:
    """
    Parse Citi copied-text rows.

    Citi statements use rows such as:
        05/03 05/04 Netflix.com 408-5403700 CA $8.99
        05/06 SQ *THE GOOD EATING CO. Chicago IL $16.13

    Some extracted rows include rewards/sidebar text after the amount, so this
    parser captures the first statement amount after the merchant description.
    """
    cleaned = clean_cell(line)
    match = CITI_TRANSACTION_PATTERN.match(cleaned)
    if not match:
        return None

    description = clean_description(match.group("description"))
    if looks_like_non_transaction([description]):
        return None

    try:
        amount = parse_amount(match.group("amount"))
    except ValueError:
        return None

    return Transaction(
        date=match.group("sale_date"),
        description=description,
        amount=amount,
        category=categorize(description),
        page=page_number,
        card_source=card_source,
    )


def is_supplemental_detail_line(line: str) -> bool:
    """Return True for foreign amount/currency/exchange-rate detail rows."""
    cleaned = clean_cell(line)
    return any(
        re.match(pattern, cleaned, flags=re.IGNORECASE)
        for pattern in SUPPLEMENTAL_DETAIL_PATTERNS
    )


def finalize_text_transaction(
    transaction: Transaction | None,
    continuation_lines: list[str],
) -> Transaction | None:
    """Attach continuation text to the pending raw-text transaction."""
    if transaction is None:
        return None

    if continuation_lines:
        description = " ".join([transaction.description, *continuation_lines])
        transaction.description = clean_cell(description)
        transaction.category = categorize(transaction.description)

    return transaction


def parse_text_transactions(text: str, page_number: int) -> list[Transaction]:
    """
    Parse transactions from page.extract_text() output.

    Use this when a bank statement copies like plain lines instead of clean
    table cells. A new transaction starts with "Trans Date Post Date ... Amount"
    spacing, while following passenger/route lines are folded into the previous
    transaction description until the next transaction start is found.
    """
    transactions: list[Transaction] = []
    pending: Transaction | None = None
    continuation_lines: list[str] = []
    in_transaction_section = False

    def append_pending() -> None:
        nonlocal pending, continuation_lines
        completed = finalize_text_transaction(pending, continuation_lines)
        if completed is not None:
            transactions.append(completed)
        pending = None
        continuation_lines = []

    for raw_line in text.splitlines():
        line = clean_cell(raw_line)
        if not line:
            continue

        if looks_like_transaction_section_header(line):
            append_pending()
            in_transaction_section = True
            continue

        if not in_transaction_section:
            continue

        current = parse_text_transaction_line(line, page_number)
        if current is not None:
            append_pending()
            pending = current
            continue

        if pending is None:
            continue

        if is_supplemental_detail_line(line):
            continue

        if looks_like_header([line]) or looks_like_non_transaction([line]):
            append_pending()
            continue

        # Lines like "PSGR: ..." and "ORIG: ..., DEST: ..." are continuation
        # details for the current transaction. Keeping them in the description
        # makes merchant matching/auditing more complete without creating extra
        # transaction records.
        continuation_lines.append(line)

    append_pending()
    return transactions


def parse_statement_text_transactions(
    text: str,
    page_number: int,
    card_source: str = "Unknown Card",
) -> list[Transaction]:
    """
    Parse transaction rows from supported copied-text statement layouts.

    Supports Capital One rows with transaction/post dates and Citi rows with
    sale/post dates. Citi pages frequently interleave rewards copy in the right
    column, so transaction sections end aggressively at totals/footer labels.
    """
    transactions: list[Transaction] = []
    pending: Transaction | None = None
    continuation_lines: list[str] = []
    in_transaction_section = False

    def append_pending() -> None:
        nonlocal pending, continuation_lines
        completed = finalize_text_transaction(pending, continuation_lines)
        if completed is not None:
            transactions.append(completed)
        pending = None
        continuation_lines = []

    for raw_line in text.splitlines():
        line = clean_cell(raw_line)
        if not line:
            continue

        if looks_like_transaction_section_header(line) or looks_like_transaction_section_start(line):
            append_pending()
            in_transaction_section = True
            continue

        if not in_transaction_section:
            continue

        if looks_like_transaction_section_end(line):
            append_pending()
            in_transaction_section = False
            continue

        current = parse_citi_transaction_line(line, page_number, card_source)
        if current is None:
            current = parse_text_transaction_line(line, page_number, card_source)

        if current is not None:
            append_pending()
            pending = current
            continue

        if pending is None:
            continue

        if is_supplemental_detail_line(line):
            continue

        if looks_like_header([line]) or looks_like_non_transaction([line]):
            append_pending()
            continue

        continuation_lines.append(line)

    append_pending()
    return transactions


def table_transactions_from_page(
    page: object,
    page_number: int,
    table_settings: dict[str, object],
    card_source: str = "Unknown Card",
) -> list[Transaction]:
    """Extract transactions from the largest detected table on one page."""
    transactions: list[Transaction] = []

    # extract_table() returns the largest detected table on the page.
    # If your bank prints multiple transaction tables on one page, swap this
    # for extract_tables(settings) and iterate over every table.
    table = page.extract_table(table_settings)
    if not table:
        return transactions

    for raw_row in table:
        row = clean_row(raw_row)
        transaction = parse_transaction_row(row, page_number, card_source)
        if transaction is not None:
            transactions.append(transaction)

    return transactions


def extract_transactions(
    pdf_path: Path,
    table_settings: dict[str, object] | None = None,
) -> list[Transaction]:
    """Loop through all PDF pages and collect parsed transaction rows."""
    if pdfplumber is None:
        raise RuntimeError(
            "pdfplumber is required to read PDF statements. Install it with: "
            "pip install pdfplumber"
        )

    settings = table_settings or TABLE_SETTINGS
    card_source = pdf_path.parent.name if pdf_path.parent.name != "." else pdf_path.stem
    transactions: list[Transaction] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            # Raw text parsing is a fallback and a repair path for statements
            # that copy like this:
            #   Trans Date Post Date Description Amount
            #   Dec 25 Dec 26 merchant text $82.89
            #   PSGR: ...
            #   ORIG: ...
            # In that layout, extract_table() may capture only the first line
            # of a multi-line transaction. If raw text finds at least as many
            # transactions, prefer it because it preserves continuation detail.
            text = page.extract_text() or ""
            text_transactions = parse_statement_text_transactions(text, page_number, card_source)
            if text_transactions:
                transactions.extend(text_transactions)

            # Restrict table parsing to pages that clearly contain transaction
            # sections. Otherwise, statement summary rows can mimic a transaction
            # because they contain dates and currency amounts.
            elif TRANSACTION_SECTION_HEADER_PATTERN.search(text):
                table_transactions = table_transactions_from_page(page, page_number, settings, card_source)
                transactions.extend(table_transactions)

    return transactions


def transactions_to_json(transactions: Iterable[Transaction]) -> str:
    """Serialize transactions as a clean JSON array."""
    payload = [
        {"id": f"tx-{index:06d}", **asdict(transaction)}
        for index, transaction in enumerate(transactions, start=1)
    ]
    return json.dumps(payload, indent=2, ensure_ascii=False)


def expand_pdf_paths(paths: Iterable[Path]) -> list[Path]:
    """Expand file and directory inputs into a stable list of PDF paths."""
    pdf_paths: list[Path] = []
    for path in paths:
        if path.is_dir():
            pdf_paths.extend(sorted(path.rglob("*.pdf")))
        else:
            pdf_paths.append(path)

    return pdf_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract credit-card PDF statement transactions to JSON."
    )
    parser.add_argument(
        "pdf",
        type=Path,
        nargs="+",
        help="Path to one or more credit-card statement PDFs or directories containing PDFs.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional JSON output path. Defaults to printing JSON to stdout.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    transactions: list[Transaction] = []
    for pdf_path in expand_pdf_paths(args.pdf):
        transactions.extend(extract_transactions(pdf_path))
    json_output = transactions_to_json(transactions)

    if args.output:
        args.output.write_text(json_output + "\n", encoding="utf-8")
    else:
        print(json_output)


if __name__ == "__main__":
    main()
