import sqlite3
import csv
from dataclasses import dataclass, field
from datetime import datetime

REQUIRED_COLUMNS = ("date", "product", "category", "quantity", "price", "seller", "region")


class InvalidCSVError(ValueError):
    """CSV without the expected columns."""


@dataclass
class ImportResult:
    inserted: int = 0
    rejected: list[tuple[int, str]] = field(default_factory=list)  # (line, reason)


def create_database(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            product     TEXT NOT NULL,
            category    TEXT NOT NULL,
            quantity    INTEGER NOT NULL CHECK (quantity > 0),
            price       REAL NOT NULL CHECK (price >= 0),
            total       REAL GENERATED ALWAYS AS (quantity * price) STORED,
            seller      TEXT NOT NULL,
            region      TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _parse_price(text: str) -> float:
    # accepts 10.5 and 10,5, and a currency symbol in front ($10.50, R$ 10,50)
    text = text.strip().lstrip("R$€£ ")
    if "," in text and "." in text:
        # with both, the last one is the decimal: 1,234.56 or 1.234,56
        thousands = "," if text.rfind(".") > text.rfind(",") else "."
        text = text.replace(thousands, "")
    return float(text.replace(",", "."))


def _validate_row(row: dict) -> tuple:
    for column in REQUIRED_COLUMNS:
        if not (row.get(column) or "").strip():
            raise ValueError(f"field '{column}' is empty")

    date = row["date"].strip()
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"date '{date}' is not in the YYYY-MM-DD format") from None

    try:
        quantity = int(row["quantity"])
    except ValueError:
        raise ValueError(f"quantity '{row['quantity']}' is not a whole number") from None
    if quantity <= 0:
        raise ValueError("quantity must be greater than zero")

    try:
        price = _parse_price(row["price"])
    except ValueError:
        raise ValueError(f"price '{row['price']}' is not a number") from None
    if price < 0:
        raise ValueError("price can't be negative")

    # "Ana  Lima" and "Ana Lima" should be the same seller in the groupings
    def text(column):
        return " ".join(row[column].split())

    return (date, text("product"), text("category"), quantity, price, text("seller"), text("region"))


def insert_sales(conn: sqlite3.Connection, csv_path: str) -> ImportResult:
    """Imports the CSV. Rows with problems are skipped and end up in `rejected`."""
    result = ImportResult()
    valid = []

    # utf-8-sig because of the BOM Excel puts at the start of the file
    with open(csv_path, newline='', encoding='utf-8-sig') as file:
        # Excel in some languages (Portuguese, for example) saves the CSV with ; instead of a comma
        header = file.readline()
        file.seek(0)
        # and a copy from a spreadsheet pasted into a file comes with tabs
        delimiter = max((",", ";", "\t"), key=header.count)
        reader = csv.DictReader(file, delimiter=delimiter)

        columns = {c.strip() for c in (reader.fieldnames or [])}
        missing = [c for c in REQUIRED_COLUMNS if c not in columns]
        if missing:
            raise InvalidCSVError(f"Missing columns in the CSV: {', '.join(missing)}")

        for number, row in enumerate(reader, start=2):  # line 1 is the header
            row = {(k or "").strip(): v for k, v in row.items()}
            # Excel leaves lines like ",,,,,," at the end; that's not a broken sale
            if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
                continue
            try:
                valid.append(_validate_row(row))
            except ValueError as error:
                result.rejected.append((number, str(error)))

    with conn:
        conn.execute("DELETE FROM sales")
        conn.executemany("""
            INSERT INTO sales (date, product, category, quantity, price, seller, region)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, valid)

    result.inserted = len(valid)
    return result


def keep_period(conn: sqlite3.Connection, start: str | None = None, end: str | None = None) -> int:
    """Deletes the sales outside start..end (both included). Returns how many went away."""
    with conn:
        removed = conn.execute(
            "DELETE FROM sales WHERE date < COALESCE(?, date) OR date > COALESCE(?, date)",
            (start, end),
        ).rowcount
    return removed
