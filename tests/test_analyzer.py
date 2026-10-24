import csv
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.analyzer import calculate_stats, format_money, format_report  # noqa: E402
from src.database import InvalidCSVError, create_database, insert_sales  # noqa: E402
from src.csv_generator import generate_sample_csv  # noqa: E402
from src.html_report import format_html  # noqa: E402
import main  # noqa: E402

HEADER = ["date", "product", "category", "quantity", "price", "seller", "region"]


class FolderTestCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.csv = os.path.join(self.folder.name, "sales.csv")

    def tearDown(self):
        self.folder.cleanup()

    def write_csv(self, rows, header=HEADER):
        with open(self.csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)


class TestFormatMoney(unittest.TestCase):
    def test_dollar_format(self):
        self.assertEqual(format_money(1234.5), "$1,234.50")
        self.assertEqual(format_money(0), "$0.00")
        self.assertEqual(format_money(1_000_000), "$1,000,000.00")


class TestImport(FolderTestCase):
    def test_imports_valid_rows(self):
        self.write_csv([
            ["2024-01-10", "Coffee", "Food", "2", "10.50", "Ana", "South"],
            ["2024-02-01", "Honey", "Food", "1", "20,00", "Bruno", "North"],
        ])
        conn = create_database(":memory:")
        result = insert_sales(conn, self.csv)
        self.assertEqual(result.inserted, 2)
        self.assertEqual(result.rejected, [])
        total = conn.execute("SELECT SUM(total) FROM sales").fetchone()[0]
        self.assertAlmostEqual(total, 41.0)

    def test_rejects_invalid_rows_without_stopping(self):
        self.write_csv([
            ["2024-01-10", "Coffee", "Food", "2", "10", "Ana", "South"],
            ["10/01/2024", "Coffee", "Food", "2", "10", "Ana", "South"],   # wrong date
            ["2024-01-10", "Coffee", "Food", "two", "10", "Ana", "South"],  # quantity
            ["2024-01-10", "Coffee", "Food", "0", "10", "Ana", "South"],   # zero quantity
            ["2024-01-10", "", "Food", "1", "10", "Ana", "South"],         # empty product
        ])
        conn = create_database(":memory:")
        result = insert_sales(conn, self.csv)
        self.assertEqual(result.inserted, 1)
        self.assertEqual([n for n, _ in result.rejected], [3, 4, 5, 6])

    def test_csv_with_semicolons(self):
        with open(self.csv, "w", newline="", encoding="utf-8-sig") as f:
            f.write(";".join(HEADER) + "\n")
            f.write("2024-01-10;Coffee;Food;2;10,50;Ana;South\n")
        conn = create_database(":memory:")
        result = insert_sales(conn, self.csv)
        self.assertEqual(result.inserted, 1)
        total = conn.execute("SELECT SUM(total) FROM sales").fetchone()[0]
        self.assertAlmostEqual(total, 21.0)

    def test_price_with_currency_symbol(self):
        self.write_csv([
            ["2024-01-10", "Coffee", "Food", "1", "$10.50", "Ana", "South"],
            ["2024-01-11", "Coffee", "Food", "1", "R$ 9,50", "Ana", "South"],
        ])
        conn = create_database(":memory:")
        self.assertEqual(insert_sales(conn, self.csv).inserted, 2)
        total = conn.execute("SELECT SUM(total) FROM sales").fetchone()[0]
        self.assertAlmostEqual(total, 20.0)

    def test_missing_columns(self):
        self.write_csv([["2024-01-10", "Coffee"]], header=["date", "product"])
        conn = create_database(":memory:")
        with self.assertRaises(InvalidCSVError):
            insert_sales(conn, self.csv)

    def test_reimport_replaces_data(self):
        self.write_csv([["2024-01-10", "Coffee", "Food", "1", "10", "Ana", "South"]])
        conn = create_database(":memory:")
        insert_sales(conn, self.csv)
        insert_sales(conn, self.csv)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0], 1)


class TestStats(FolderTestCase):
    def setUp(self):
        super().setUp()
        self.write_csv([
            ["2024-01-10", "Coffee", "Food", "2", "10", "Ana", "South"],     # 20
            ["2024-01-20", "Book", "Books", "1", "50", "Ana", "North"],      # 50
            ["2024-02-05", "Coffee", "Food", "3", "10", "Bruno", "South"],   # 30
        ])
        self.conn = create_database(":memory:")
        insert_sales(self.conn, self.csv)

    def test_summary(self):
        summary = calculate_stats(self.conn)["summary"]
        self.assertEqual(summary["total_sales"], 3)
        self.assertAlmostEqual(summary["total_revenue"], 100)
        self.assertAlmostEqual(summary["biggest_sale"], 50)
        self.assertEqual(summary["first_sale"], "2024-01-10")

    def test_groupings(self):
        stats = calculate_stats(self.conn)
        self.assertEqual(stats["top_products"][0]["product"], "Coffee")
        self.assertEqual(stats["top_products"][0]["units"], 5)
        ana = next(s for s in stats["sellers"] if s["seller"] == "Ana")
        self.assertAlmostEqual(ana["share"], 70.0)
        self.assertEqual([m["month"] for m in stats["monthly"]], ["2024-01", "2024-02"])

    def test_text_report(self):
        text = format_report(calculate_stats(self.conn))
        self.assertIn("$100.00", text)
        self.assertIn("MONTHLY TREND", text)
        self.assertIn("Jan/2024", text)

    def test_month_with_few_sales_shows_in_chart(self):
        self.write_csv([
            ["2024-01-10", "Laptop", "Electronics", "1", "5000", "Ana", "South"],
            ["2024-02-10", "Pen", "Stationery", "1", "2", "Ana", "South"],
        ])
        conn = create_database(":memory:")
        insert_sales(conn, self.csv)
        text = format_report(calculate_stats(conn))
        feb_line = next(line for line in text.splitlines() if line.strip().startswith("Feb/2024"))
        self.assertTrue(feb_line.endswith("█"))

    def test_empty_database_does_not_break(self):
        conn = create_database(":memory:")
        text = format_report(calculate_stats(conn))
        self.assertIn("No sales", text)
        self.assertIn("No sales", format_html(calculate_stats(conn)))

    def test_html_escapes_names(self):
        self.write_csv([["2024-01-10", "<b>Pen</b>", "Office", "1", "2", "Ana & Bia", "South"]])
        conn = create_database(":memory:")
        insert_sales(conn, self.csv)
        page = format_html(calculate_stats(conn))
        self.assertIn("&lt;b&gt;Pen&lt;/b&gt;", page)
        self.assertIn("Ana &amp; Bia", page)
        self.assertNotIn("<b>Pen</b>", page)


class TestGenerator(FolderTestCase):
    def test_seed_reproduces_same_file(self):
        other = os.path.join(self.folder.name, "other.csv")
        generate_sample_csv(self.csv, 30, seed=7)
        generate_sample_csv(other, 30, seed=7)
        with open(self.csv, encoding="utf-8") as a, open(other, encoding="utf-8") as b:
            self.assertEqual(a.read(), b.read())


class TestMain(FolderTestCase):
    def test_full_run(self):
        output = os.path.join(self.folder.name, "out")
        with redirect_stdout(StringIO()):
            code = main.main(["--csv", self.csv, "--output", output, "--generate", "50", "--seed", "1", "--json", "--html"])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(os.path.join(output, "report.txt")))
        with open(os.path.join(output, "report.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["summary"]["total_sales"], 50)
        with open(os.path.join(output, "report.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertIn("<title>Sales report</title>", page)
        self.assertIn("Revenue by month", page)

    def test_invalid_csv_returns_error(self):
        self.write_csv([["x"]], header=["wrong_column"])
        with redirect_stdout(StringIO()):
            code = main.main(["--csv", self.csv, "--output", self.folder.name])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
