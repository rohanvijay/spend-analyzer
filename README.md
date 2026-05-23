# Spend Analyzer

A local personal expense dashboard for parsing credit-card statement PDFs into structured transaction data, then exploring spend trends in a React dashboard.

The app is currently branded as **Rohan & Manisha's Expense Tracker** and is designed to run locally so sensitive statement PDFs and transaction exports do not need to leave the machine.

## What It Does

- Parses statement PDFs from multiple card issuers into normalized JSON.
- Categorizes transactions with a structured merchant keyword mapping.
- Renders a dark-mode React dashboard with spending metrics, charts, and a scannable transaction table.
- Supports filtering transactions by month, category, card source, and live description search.
- Keeps financial source files and generated transaction data out of git by default.

## Supported Statement Sources

The parser currently supports statement text layouts from:

- Capital One
- Citi Costco card
- Citi Double Cash card
- Chase Amazon card

The card source is inferred from the PDF's parent folder name. For example, PDFs under `Statements/Chase Amazon Card/` produce transactions with `card_source: "Chase Amazon Card"`.

## Project Structure

```text
.
├── parse_credit_card_statement.py   # PDF parser and categorization logic
├── transactions.json                # Generated local data file, ignored by git
├── tests/
│   └── test_parser.py               # Parser and categorization tests
├── src/
│   ├── App.jsx                      # React dashboard
│   ├── main.jsx                     # React entry point
│   └── index.css                    # Tailwind styles
├── package.json                     # Frontend scripts and dependencies
├── tailwind.config.js
├── vite.config.js
└── .gitignore
```

PDF statements are expected under a local `Statements/` folder, but PDFs are intentionally ignored by git.

## Data Schema

The generated transaction JSON uses this shape:

```json
{
  "id": "tx-000001",
  "date": "05/18",
  "description": "SQ *SINYA MEDITERRANEAN Chicago IL",
  "amount": 37.1,
  "category": "Dining & Cafes",
  "page": 3,
  "card_source": "Citi Costco card"
}
```

The dashboard consumes `transactions.json` directly from the project root.

## Privacy Notes

The repository is configured to avoid committing sensitive local data:

- `transactions.json` is ignored.
- Statement PDFs under `Statements/**/*.pdf` are ignored.
- Local dependencies and build artifacts are ignored.

Before pushing to GitHub, confirm with:

```bash
git status --short
```

## Setup

### Python Parser

Create or activate a Python environment, then install the PDF parser dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pdfplumber
```

### Frontend

Install frontend dependencies:

```bash
npm install
```

If `npm` is installed through Homebrew on this machine, the full path may be:

```bash
/opt/homebrew/bin/npm install
```

## Generate Transactions

Parse every PDF under the local `Statements/` folder:

```bash
.venv/bin/python parse_credit_card_statement.py Statements -o transactions.json
```

Parse one specific PDF:

```bash
.venv/bin/python parse_credit_card_statement.py "Statements/CapitalOne/Statement_042026_8356.pdf" -o transactions.json
```

The parser recursively expands directories, so adding new PDFs under issuer/card folders is enough for the next generation run.

## Run The Dashboard

Start the local dev server:

```bash
npm run dev -- --port 5173
```

Or, with the Homebrew npm path:

```bash
/opt/homebrew/bin/npm run dev -- --port 5173
```

Open:

```text
http://127.0.0.1:5173/
```

## Build

Create a production build:

```bash
npm run build
```

Preview the production build locally:

```bash
npm run preview
```

## Tests

Run parser tests:

```bash
.venv/bin/python -m unittest tests/test_parser.py
```

The tests cover representative copied-text rows from Capital One, Citi, and Chase statement layouts, plus merchant categorization behavior.

## Categorization

Transaction categories are controlled by `CATEGORY_MAPPING` in `parse_credit_card_statement.py`.

Matching is:

- Case-insensitive
- Substring-based
- Ordered by category insertion order
- Fallbacks to `Other` when no keyword matches

To add a new merchant mapping:

1. Add the lowercase keyword to the right category in `CATEGORY_MAPPING`.
2. Add a representative test row in `tests/test_parser.py`.
3. Run tests.
4. Regenerate `transactions.json`.

Example:

```python
"Groceries": [
    "trader joe",
    "food mart",
]
```

## Dashboard Features

The React dashboard includes:

- Total monthly or selected-period spend
- Budget progress card
- Active cards breakdown
- Recharts area chart for monthly spend trend
- Recharts donut chart for category mix
- Financial transaction table with:
  - Date
  - Description
  - Card Source
  - Category badge
  - Amount
  - Live description search
  - Month filter
  - Category filter
  - Card source filter
  - Sticky header and scroll wrapper

## GitHub Workflow

This project is safe to commit without statement PDFs or generated transaction exports.

Initial local commit has already been created. To connect to GitHub after creating an empty repository:

```bash
git remote add origin https://github.com/rohanvijay/spend-analyzer.git
git branch -M main
git push -u origin main
```

Use a different repo URL if the GitHub repository has a different name.
