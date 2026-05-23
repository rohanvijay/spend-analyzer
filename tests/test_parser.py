import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parse_credit_card_statement import (  # noqa: E402
    categorize,
    parse_citi_transaction_line,
    parse_statement_text_transactions,
    parse_text_transaction_line,
    parse_text_transactions,
)


class TextTransactionParsingTests(unittest.TestCase):
    def test_payment_row_with_dash_amount_is_negative(self):
        transaction = parse_text_transaction_line(
            "Jan 19 Jan 19 CAPITAL ONE AUTOPAY PYMT - $422.71",
            page_number=3,
        )

        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.date, "Jan 19")
        self.assertEqual(transaction.description, "CAPITAL ONE AUTOPAY PYMT")
        self.assertEqual(transaction.amount, -422.71)

    def test_purchase_row_with_foreign_amount_detail(self):
        transactions = parse_text_transactions(
            "\n".join(
                [
                    "Trans Date Post Date Description Amount",
                    "Dec 26 Dec 27 RAZ*BlinkitFaridabad HA $3.56",
                    "$319.00",
                    "INR",
                    "89.606741573 Exchange Rate",
                ]
            ),
            page_number=3,
        )

        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0].description, "RAZ*BlinkitFaridabad HA")
        self.assertEqual(transactions[0].amount, 3.56)

    def test_multiline_travel_details_are_kept_with_transaction(self):
        transactions = parse_text_transactions(
            "\n".join(
                [
                    "Trans Date Post Date Description Amount",
                    "Dec 25 Dec 26 booking40813209835444646-5587089FL $82.89",
                    "PSGR: Vijayvargiya Rohan P",
                    "ORIG: ORD, DEST: ZRH, S/O: X, CARRIER: LX, SVC: Y",
                ]
            ),
            page_number=3,
        )

        self.assertEqual(len(transactions), 1)
        self.assertEqual(
            transactions[0].description,
            "booking40813209835444646-5587089FL PSGR: Vijayvargiya Rohan P "
            "ORIG: ORD, DEST: ZRH, S/O: X, CARRIER: LX, SVC: Y",
        )

    def test_statement_summary_before_header_is_ignored(self):
        transactions = parse_text_transactions(
            "\n".join(
                [
                    "Dec 26, 2025 - Jan 25, 2026 | 31 days in Billing Cycle",
                    "Payment Due Date Previous Balance $422.71",
                    "Trans Date Post Date Description Amount",
                    "Jan 4 Jan 5 DD *DOORDASH THEINDIANDOORDASH.COMCA $51.37",
                ]
            ),
            page_number=1,
        )

        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0].date, "Jan 4")
        self.assertEqual(transactions[0].amount, 51.37)

    def test_account_totals_do_not_leak_into_description(self):
        transactions = parse_text_transactions(
            "\n".join(
                [
                    "Trans Date Post Date Description Amount",
                    "Jan 9 Jan 12 AMAZON PAY INDIA PRIVATEWWW.AMAZON.IN $8.59",
                    "ROHAN PRAMOD VIJAYVARGIYA #8356: Total Transactions $443.75",
                    "Trans Date Post Date Description Amount",
                    "Dec 24 Dec 26 Dripnova Private LimiteIndore $15.47",
                ]
            ),
            page_number=4,
        )

        self.assertEqual([transaction.amount for transaction in transactions], [8.59, 15.47])
        self.assertEqual(
            transactions[0].description,
            "AMAZON PAY INDIA PRIVATEWWW.AMAZON.IN",
        )

    def test_account_section_heading_does_not_leak_into_description(self):
        transactions = parse_text_transactions(
            "\n".join(
                [
                    "Trans Date Post Date Description Amount",
                    "Jan 19 Jan 19 CAPITAL ONE AUTOPAY PYMT - $422.71",
                    "ROHAN PRAMOD VIJAYVARGIYA #8356: Transactions",
                    "Trans Date Post Date Description Amount",
                    "Dec 25 Dec 26 RAZ*IndiGoGurgaon HA $9.88",
                ]
            ),
            page_number=3,
        )

        self.assertEqual(len(transactions), 2)
        self.assertEqual(transactions[0].description, "CAPITAL ONE AUTOPAY PYMT")
        self.assertEqual(transactions[0].amount, -422.71)


class CategorizationTests(unittest.TestCase):
    def test_categorize_lowercases_before_matching(self):
        self.assertEqual(categorize("STARBUCKS #12345 CHICAGO IL"), "Dining & Cafes")

    def test_categorize_matches_substrings(self):
        self.assertEqual(categorize("WALGREENS #2340312-467-0485IL"), "Health & Fitness")

    def test_categorize_new_requested_merchants(self):
        examples = {
            "CAPITAL ONE AUTOPAY PYMT": "Credit Card Payments",
            "CAPITAL ONE MOBILE PYMT": "Credit Card Payments",
            "AUTOMATIC PAYMENT - THANK YOU": "Credit Card Payments",
            "FALAFELNew CHICAGO IL": "Dining & Cafes",
            "BAKERYNEW 1562 NEW YORK NY": "Dining & Cafes",
            "MEDITERRANEAN GRILL CHICAGO IL": "Dining & Cafes",
            "MAMAN KING STREET NEW YORK NY": "Dining & Cafes",
            "THAI KITCHEN CHICAGO IL": "Dining & Cafes",
            "Amazon Grocery Subscri 888-280-4331 WA": "Groceries",
            "FOOD MART 24 CHICAGO IL": "Groceries",
            "AMAZON PAY INDIA PRIVATE WWW.AMAZON.IN": "Shopping & Retail",
            "PATH TRAIN FARE NY": "Transportation",
            "MTA*NYCT PAYGO NEW YORK NY": "Transportation",
            "VENTRA MOBILE APP CHICAGO IL": "Transportation",
            "THEFARMERSDOG.COM SUBSCRIPTION": "Pet Care",
            "SALON 1800 CHICAGO IL": "Health & Fitness",
            "CHICAGO ENT CHICAGO IL": "Health & Fitness",
        }

        for description, category in examples.items():
            with self.subTest(description=description):
                self.assertEqual(categorize(description), category)

    def test_categorize_uses_other_fallback(self):
        self.assertEqual(categorize("UNKNOWN MERCHANT CHICAGO IL"), "Other")


class CitiTransactionParsingTests(unittest.TestCase):
    def test_citi_row_with_sale_and_post_date(self):
        transaction = parse_citi_transaction_line(
            "05/03 05/04 Netflix.com 408-5403700 CA $8.99",
            page_number=3,
            card_source="Citi double cash back card",
        )

        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.date, "05/03")
        self.assertEqual(transaction.description, "Netflix.com 408-5403700 CA")
        self.assertEqual(transaction.amount, 8.99)
        self.assertEqual(transaction.category, "Subscriptions")
        self.assertEqual(transaction.card_source, "Citi double cash back card")

    def test_citi_row_with_sale_date_only(self):
        transaction = parse_citi_transaction_line(
            "05/06 SQ *THE GOOD EATING CO. Chicago IL $16.13",
            page_number=3,
        )

        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.date, "05/06")
        self.assertEqual(transaction.description, "SQ *THE GOOD EATING CO. Chicago IL")
        self.assertEqual(transaction.amount, 16.13)
        self.assertEqual(transaction.category, "Dining & Cafes")

    def test_citi_parser_ignores_rewards_copy_after_amount(self):
        transaction = parse_citi_transaction_line(
            "01/25 SQ *MOVE ALONG COFFEE CHICAGO IL $19.29 appear on your statement.",
            page_number=3,
        )

        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.description, "SQ *MOVE ALONG COFFEE CHICAGO IL")
        self.assertEqual(transaction.amount, 19.29)

    def test_citi_parser_uses_first_amount_when_rewards_text_has_amount(self):
        transactions = parse_statement_text_transactions(
            "\n".join(
                [
                    "Sale Post",
                    "Standard Purchases Earned this period ................................... +$6.84",
                    "11/25 02/18 REVERSE QATAR AIR 0002130973024WASHING $9,873.38 Year to Date : $18.61",
                ]
            ),
            page_number=3,
            card_source="Citi Costco card",
        )

        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0].description, "REVERSE QATAR AIR 0002130973024WASHING")
        self.assertEqual(transactions[0].amount, 9873.38)

    def test_citi_statement_sections_parse_and_stop_at_totals(self):
        transactions = parse_statement_text_transactions(
            "\n".join(
                [
                    "Sale Post",
                    "Payments, Credits and Adjustments",
                    "05/12 05/12 Amazon.com Amzn.com/billWA -$4.55",
                    "ROHAN VIJAYVARGIYA",
                    "Standard Purchases",
                    "05/03 05/04 Netflix.com 408-5403700 CA $8.99",
                    "05/06 SQ *THE GOOD EATING CO. Chicago IL $16.13",
                    "Total fees charged in this billing period $0.00",
                    "05/06 05/07 AMAZON RETA* SHOULD NOT PARSE $6.90",
                ]
            ),
            page_number=3,
            card_source="Citi double cash back card",
        )

        self.assertEqual(len(transactions), 3)
        self.assertEqual([transaction.amount for transaction in transactions], [-4.55, 8.99, 16.13])
        self.assertTrue(all(transaction.card_source == "Citi double cash back card" for transaction in transactions))


class ChaseTransactionParsingTests(unittest.TestCase):
    def test_chase_statement_sections_parse_single_date_rows(self):
        transactions = parse_statement_text_transactions(
            "\n".join(
                [
                    "Date of",
                    "Transaction Merchant Name or Transaction Description $ Amount",
                    "PAYMENTS AND OTHER CREDITS",
                    "01/01 AMAZON PAY INDIA PRIVATE WWW.AMAZON.IN -13.33",
                    "01/02 INDIAN RUPEE",
                    "1,199.90 X 0.011109259 (EXCHG RATE)",
                    "01/16 AMAZON MKTPLACE PMTS Amzn.com/bill WA -14.32",
                    "Order Number 112-3248222-2593813",
                    "PURCHASE",
                    "12/25 AMAZON PAY INDIA PRIVATE WWW.AMAZON.IN 73.25",
                    "12/26 INDIAN RUPEE",
                    "6,557.00 X 0.011171267 (EXCHG RATE)",
                    "01/04 Amazon.com*TT7UA3TW3 Amzn.com/bill WA 40.53",
                    "Order Number 112-9884104-1773007",
                    "01/03 Amazon Grocery Subscri 888-280-4331 WA 9.99",
                    "2026 Totals Year-to-Date",
                    "Total fees charged in 2026 $0.00",
                ]
            ),
            page_number=3,
            card_source="Chase Amazon Card",
        )

        self.assertEqual(len(transactions), 5)
        self.assertEqual(
            [transaction.description for transaction in transactions],
            [
                "AMAZON PAY INDIA PRIVATE WWW.AMAZON.IN",
                "AMAZON MKTPLACE PMTS Amzn.com/bill WA",
                "AMAZON PAY INDIA PRIVATE WWW.AMAZON.IN",
                "Amazon.com*TT7UA3TW3 Amzn.com/bill WA",
                "Amazon Grocery Subscri 888-280-4331 WA",
            ],
        )
        self.assertEqual([transaction.amount for transaction in transactions], [-13.33, -14.32, 73.25, 40.53, 9.99])
        self.assertTrue(all(transaction.card_source == "Chase Amazon Card" for transaction in transactions))
        self.assertEqual(transactions[-1].category, "Groceries")


if __name__ == "__main__":
    unittest.main()
