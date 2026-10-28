import json
import sqlite3
from datetime import datetime

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def format_money(value: float) -> str:
    # 1234.5 -> "$1,234.50"
    return f"${value:,.2f}"


def _title(text: str) -> str:
    line = "-" * 55
    return f"\n{line}\n  {text}\n{line}"


def _rows(cursor, fields):
    return [dict(zip(fields, r)) for r in cursor.fetchall()]


def calculate_stats(conn: sqlite3.Connection, top: int = 5) -> dict:
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*)                    AS total_sales,
            COALESCE(SUM(total), 0)     AS total_revenue,
            COALESCE(AVG(total), 0)     AS average_ticket,
            COALESCE(MAX(total), 0)     AS biggest_sale,
            COALESCE(MIN(total), 0)     AS smallest_sale,
            MIN(date)                   AS first_sale,
            MAX(date)                   AS last_sale,
            COALESCE(SUM(quantity), 0)  AS units_sold
        FROM sales
    """)
    columns = [c[0] for c in cursor.description]
    summary = dict(zip(columns, cursor.fetchone()))

    cursor.execute("""
        SELECT date, SUM(total) AS revenue
        FROM sales
        GROUP BY date
        ORDER BY revenue DESC, date
        LIMIT 1
    """)
    best = cursor.fetchone()
    summary["best_day"] = {"date": best[0], "revenue": best[1]} if best else None

    cursor.execute("""
        SELECT category, COUNT(*), SUM(total), AVG(price)
        FROM sales
        GROUP BY category
        ORDER BY SUM(total) DESC
    """)
    categories = _rows(cursor, ("category", "sales", "revenue", "average_price"))

    cursor.execute("""
        SELECT product, SUM(quantity) AS units, SUM(total) AS revenue
        FROM sales
        GROUP BY product
        ORDER BY units DESC, revenue DESC
        LIMIT ?
    """, (top,))
    products = _rows(cursor, ("product", "units", "revenue"))

    cursor.execute("""
        SELECT
            seller,
            COUNT(*),
            SUM(total) AS revenue,
            100.0 * SUM(total) / (SELECT SUM(total) FROM sales)
        FROM sales
        GROUP BY seller
        ORDER BY revenue DESC
    """)
    sellers = _rows(cursor, ("seller", "sales", "revenue", "share"))

    cursor.execute("""
        SELECT region, COUNT(*), SUM(total) AS revenue, AVG(total)
        FROM sales
        GROUP BY region
        ORDER BY revenue DESC
    """)
    regions = _rows(cursor, ("region", "sales", "revenue", "average_ticket"))

    cursor.execute("""
        SELECT strftime('%Y-%m', date) AS month, COUNT(*), SUM(total)
        FROM sales
        GROUP BY month
        ORDER BY month
    """)
    months = _rows(cursor, ("month", "sales", "revenue"))
    # compared with the month right before; a gap in the data (no sales at all) also gives None
    previous = None
    for m in months:
        follows = previous and _next_month(previous["month"]) == m["month"]
        m["change"] = (100 * (m["revenue"] - previous["revenue"]) / previous["revenue"]
                       if follows and previous["revenue"] else None)
        previous = m

    # %w gives 0 for Sunday; turned into Monday first, the way people read a week
    cursor.execute("""
        SELECT (CAST(strftime('%w', date) AS INTEGER) + 6) % 7 AS day, COUNT(*), SUM(total)
        FROM sales
        GROUP BY day
        ORDER BY day
    """)
    weekdays = [{**w, "day": WEEKDAYS[w["day"]]}
                for w in _rows(cursor, ("day", "sales", "revenue"))]

    return {
        "summary": summary,
        "categories": categories,
        "top_products": products,
        "sellers": sellers,
        "regions": regions,
        "monthly": months,
        "weekdays": weekdays,
    }


def _next_month(year_month: str) -> str:
    year, month = map(int, year_month.split("-"))
    return f"{year + month // 12}-{month % 12 + 1:02d}"


def _month_name(year_month: str) -> str:
    year, month = year_month.split("-")
    return f"{MONTHS[int(month) - 1]}/{year}"


def format_report(stats: dict) -> str:
    lines = [
        "=" * 55,
        "  SALES REPORT",
        f"  Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 55,
    ]

    summary = stats["summary"]
    if summary["total_sales"] == 0:
        lines.append("\n  No sales found in the file.")
        lines.append("\n" + "=" * 55)
        return "\n".join(lines)

    lines.append(_title("OVERVIEW"))
    lines.append(f"  Period:             {summary['first_sale']} to {summary['last_sale']}")
    lines.append(f"  Total sales:        {summary['total_sales']}")
    lines.append(f"  Total revenue:      {format_money(summary['total_revenue'])}")
    lines.append(f"  Average ticket:     {format_money(summary['average_ticket'])}")
    lines.append(f"  Biggest sale:       {format_money(summary['biggest_sale'])}")
    lines.append(f"  Smallest sale:      {format_money(summary['smallest_sale'])}")
    lines.append(f"  Units sold:         {summary['units_sold']}")
    best = summary["best_day"]
    lines.append(f"  Best day:           {best['date']} ({format_money(best['revenue'])})")

    lines.append(_title("SALES BY CATEGORY"))
    lines.append(f"  {'Category':<15} {'Sales':>7} {'Revenue':>16} {'Avg Price':>14}")
    lines.append("  " + "-" * 53)
    for c in stats["categories"]:
        lines.append(f"  {c['category']:<15} {c['sales']:>7} {format_money(c['revenue']):>16} "
                     f"{format_money(c['average_price']):>14}")

    lines.append(_title(f"TOP {len(stats['top_products'])} PRODUCTS (by units)"))
    for i, p in enumerate(stats["top_products"], start=1):
        lines.append(f"  {i}. {p['product']:<26} {p['units']:>4} un. - {format_money(p['revenue'])}")

    lines.append(_title("SELLER RANKING"))
    lines.append(f"  {'Seller':<15} {'Sales':>7} {'Revenue':>16} {'Share':>7}")
    lines.append("  " + "-" * 48)
    for s in stats["sellers"]:
        share = f"{s['share']:.1f}%"
        lines.append(f"  {s['seller']:<15} {s['sales']:>7} {format_money(s['revenue']):>16} "
                     f"{share:>7}")

    lines.append(_title("SALES BY REGION"))
    for r in stats["regions"]:
        lines.append(f"  {r['region']:<15} {format_money(r['revenue']):>16}  ({r['sales']} sales, "
                     f"avg {format_money(r['average_ticket'])})")

    lines.append(_title("MONTHLY TREND"))
    biggest = max(m["revenue"] for m in stats["monthly"])
    for m in stats["monthly"]:
        # a month with few sales gets at least 1 block, otherwise it looks like nothing was sold
        bar = "█" * max(1, round(20 * m["revenue"] / biggest)) if biggest and m["revenue"] > 0 else ""
        change = f"{m['change']:+.0f}%" if m["change"] is not None else ""
        lines.append(f"  {_month_name(m['month']):<9} {format_money(m['revenue']):>16} {change:>6}  {bar}")

    lines.append(_title("SALES BY WEEKDAY"))
    for w in stats["weekdays"]:
        lines.append(f"  {w['day']:<10} {format_money(w['revenue']):>16}  ({w['sales']} sales)")

    lines.append("\n" + "=" * 55)
    return "\n".join(lines)


def generate_report(conn: sqlite3.Connection, output_path: str, json_path: str | None = None,
                    html_path: str | None = None, top: int = 5) -> dict:
    stats = calculate_stats(conn, top)
    content = format_report(stats)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    if json_path:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

    if html_path:
        # imported here because html_report imports helpers from this file
        from src.html_report import format_html
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(format_html(stats))

    print(content)
    return stats
