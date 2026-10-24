"""Reads a sales CSV, imports it into SQLite and generates the report."""

import argparse
import os
import sys

from src.database import create_database, insert_sales, InvalidCSVError
from src.analyzer import generate_report
from src.csv_generator import generate_sample_csv

PROJECT_FOLDER = os.path.dirname(os.path.abspath(__file__))


def positive(text: str) -> int:
    number = int(text)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def read_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Imports a sales CSV into SQLite and generates a report.",
    )
    parser.add_argument("--csv", default=os.path.join(PROJECT_FOLDER, "data", "sales.csv"),
                        help="input CSV file (default: data/sales.csv)")
    parser.add_argument("--output", default=os.path.join(PROJECT_FOLDER, "output"),
                        help="folder where the report is saved (default: output/)")
    parser.add_argument("--json", action="store_true",
                        help="also saves the stats to output/report.json")
    parser.add_argument("--html", action="store_true",
                        help="also saves a page with charts to output/report.html")
    parser.add_argument("--generate", type=positive, metavar="N",
                        help="generates a sample CSV with N sales before analyzing")
    parser.add_argument("--seed", type=int,
                        help="seed for the sample CSV (same value = same data)")
    return parser.parse_args(argv)


def show(path: str) -> str:
    """Path to print: relative when it's inside the current folder, so the
    output doesn't fill up with long absolute paths."""
    full = os.path.abspath(path)
    try:
        relative = os.path.relpath(full)
    except ValueError:  # another drive on Windows
        return full
    return full if relative.startswith("..") else relative


def main(argv=None) -> int:
    # On Windows, with the output redirected to a file (python main.py > log.txt),
    # Python uses cp1252 and breaks on the chart's █
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = read_args(argv)

    print("=" * 55)
    print("  SALES DATA ANALYZER")
    print("=" * 55)

    csv_file = args.csv
    csv_folder = os.path.dirname(os.path.abspath(csv_file))
    db_file = os.path.join(csv_folder, "sales.db")

    os.makedirs(csv_folder, exist_ok=True)
    os.makedirs(args.output, exist_ok=True)

    if args.generate or not os.path.exists(csv_file):
        quantity = args.generate or 200
        print(f"\n[1/4] Generating a sample CSV with {quantity} sales...")
        generate_sample_csv(csv_file, quantity, seed=args.seed)
        print(f"      CSV created at: {show(csv_file)}")
    else:
        print(f"\n[1/4] Using existing CSV: {show(csv_file)}")

    print("\n[2/4] Creating the SQLite database...")
    conn = create_database(db_file)
    print(f"      Database created at: {show(db_file)}")

    try:
        print("\n[3/4] Importing the CSV data into the database...")
        try:
            result = insert_sales(conn, csv_file)
        except InvalidCSVError as error:
            print(f"      Error: {error}")
            print("      Expected columns: date, product, category, quantity, price, seller, region")
            return 1

        print(f"      {result.inserted} records imported.")
        if result.rejected:
            print(f"      {len(result.rejected)} line(s) skipped:")
            for number, reason in result.rejected[:10]:
                print(f"        line {number}: {reason}")
            if len(result.rejected) > 10:
                print(f"        ... and {len(result.rejected) - 10} more")

        print("\n[4/4] Generating the report...")
        report_file = os.path.join(args.output, "report.txt")
        json_file = os.path.join(args.output, "report.json") if args.json else None
        html_file = os.path.join(args.output, "report.html") if args.html else None
        generate_report(conn, report_file, json_file, html_file)
        print(f"      Report saved to: {show(report_file)}")
        if json_file:
            print(f"      JSON saved to: {show(json_file)}")
        if html_file:
            print(f"      HTML saved to: {show(html_file)} (open it in the browser)")
    finally:
        conn.close()

    print("\n" + "=" * 55)
    print("  Done!")
    print("=" * 55)
    return 0


if __name__ == "__main__":
    sys.exit(main())
