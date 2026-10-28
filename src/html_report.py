"""The same report as report.txt, as a single HTML page with charts.

Plain HTML and CSS, without any library: the bars are divs with the width
(or height) as a percentage, so the file opens in any browser, even offline.
"""

from datetime import datetime
from html import escape

from src.analyzer import _month_name, format_money

STYLE = """
:root {
  color-scheme: light dark;
  --bg: #f5f7fb; --card: #fff; --text: #1e293b; --muted: #64748b; --line: #e2e8f0;
  --accent: #2563eb; --soft: #e8eefc;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #0f172a; --card: #1e293b; --text: #e2e8f0; --muted: #94a3b8; --line: #334155;
          --accent: #60a5fa; --soft: #1e3a5f; }
}
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); }
main { max-width: 1040px; margin: 0 auto; padding: 32px 16px 48px; }
h1 { margin: 0; font-size: 1.7rem; }
h2 { margin: 0 0 14px; font-size: 1.05rem; }
.muted { color: var(--muted); }
header { margin-bottom: 22px; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 14px; }
.kpi, .card { background: var(--card); border-radius: 14px; padding: 16px 18px; box-shadow: 0 1px 3px rgba(15, 23, 42, .08); }
.kpi span { display: block; font-size: .85rem; color: var(--muted); }
.kpi strong { display: block; font-size: 1.45rem; margin-top: 4px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.card { margin-bottom: 14px; }
.wide { grid-column: 1 / -1; }
.months { display: flex; align-items: flex-end; gap: 8px; height: 220px; padding-top: 10px; }
.month { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; gap: 6px; min-width: 0; }
.month .col { width: 100%; max-width: 46px; background: var(--accent); border-radius: 6px 6px 0 0; }
.month small { font-size: .72rem; color: var(--muted); white-space: nowrap; }
.month .value { font-size: .68rem; color: var(--muted); }
.bars { list-style: none; margin: 0; padding: 0; }
.bars li { margin-bottom: 11px; }
.bars .label { display: flex; justify-content: space-between; gap: 10px; font-size: .9rem; margin-bottom: 4px; }
.track { height: 9px; background: var(--soft); border-radius: 99px; overflow: hidden; }
.track div { height: 100%; background: var(--accent); border-radius: 99px; }
table { width: 100%; border-collapse: collapse; font-size: .9rem; }
th, td { padding: 8px 6px; text-align: left; border-bottom: 1px solid var(--line); }
th { font-size: .75rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); font-weight: 600; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
tr:last-child td { border-bottom: none; }
footer { text-align: center; font-size: .85rem; margin-top: 18px; }
@media (max-width: 720px) { .grid { grid-template-columns: 1fr; } .month .value { display: none; } }
"""


def _percent(value: float, biggest: float) -> float:
    return round(100 * value / biggest, 1) if biggest else 0


def _change(month: dict) -> str:
    if month["change"] is None:
        return ""
    return f" ({month['change']:+.0f}% from the month before)"


def _bars(rows: list[dict], label: str, value: str, extra=None) -> str:
    biggest = max((r[value] for r in rows), default=0)
    items = []
    for r in rows:
        right = format_money(r[value]) + (f" · {extra(r)}" if extra else "")
        items.append(
            f'<li><div class="label"><span>{escape(str(r[label]))}</span>'
            f'<span class="muted">{right}</span></div>'
            f'<div class="track"><div style="width:{_percent(r[value], biggest)}%"></div></div></li>'
        )
    return f'<ul class="bars">{"".join(items)}</ul>'


def format_html(stats: dict) -> str:
    summary = stats["summary"]
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    head = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Sales report</title><style>{STYLE}</style></head><body><main>"
    )

    if summary["total_sales"] == 0:
        return head + "<h1>Sales report</h1><p class='muted'>No sales found in the file.</p></main></body></html>"

    kpis = [
        ("Total revenue", format_money(summary["total_revenue"])),
        ("Sales", str(summary["total_sales"])),
        ("Average ticket", format_money(summary["average_ticket"])),
        ("Biggest sale", format_money(summary["biggest_sale"])),
    ]
    kpi_html = "".join(f'<div class="kpi"><span>{name}</span><strong>{value}</strong></div>' for name, value in kpis)

    biggest_month = max(m["revenue"] for m in stats["monthly"])
    months_html = "".join(
        f'<div class="month" title="{_month_name(m["month"])}: {format_money(m["revenue"])}{_change(m)}">'
        f'<span class="value">{format_money(m["revenue"] / 1000)}k</span>'
        f'<div class="col" style="height:{max(_percent(m["revenue"], biggest_month), 1)}%"></div>'
        f'<small>{_month_name(m["month"])}</small></div>'
        for m in stats["monthly"]
    )

    sellers_rows = "".join(
        f'<tr><td>{escape(s["seller"])}</td><td class="num">{s["sales"]}</td>'
        f'<td class="num">{format_money(s["revenue"])}</td><td class="num">{s["share"]:.1f}%</td></tr>'
        for s in stats["sellers"]
    )

    products_rows = "".join(
        f'<tr><td>{i}. {escape(p["product"])}</td><td class="num">{p["units"]}</td>'
        f'<td class="num">{format_money(p["revenue"])}</td></tr>'
        for i, p in enumerate(stats["top_products"], start=1)
    )

    return (
        head
        + "<header><h1>Sales report</h1>"
        + f'<p class="muted">{summary["first_sale"]} to {summary["last_sale"]} · generated on {generated}</p></header>'
        + f'<section class="kpis">{kpi_html}</section>'
        + f'<section class="card"><h2>Revenue by month</h2><div class="months">{months_html}</div></section>'
        + '<div class="grid">'
        + '<section class="card"><h2>Revenue by category</h2>'
        + _bars(stats["categories"], "category", "revenue", lambda c: f'{c["sales"]} sales')
        + "</section>"
        + '<section class="card"><h2>Revenue by region</h2>'
        + _bars(stats["regions"], "region", "revenue", lambda r: f'{r["sales"]} sales')
        + "</section>"
        + '<section class="card"><h2>Seller ranking</h2><table><thead><tr><th>Seller</th>'
        + '<th class="num">Sales</th><th class="num">Revenue</th><th class="num">Share</th></tr></thead>'
        + f"<tbody>{sellers_rows}</tbody></table></section>"
        + '<section class="card"><h2>Top ' + str(len(stats["top_products"])) + ' products (by units)</h2><table><thead><tr><th>Product</th>'
        + '<th class="num">Units</th><th class="num">Revenue</th></tr></thead>'
        + f"<tbody>{products_rows}</tbody></table></section>"
        + "</div>"
        + '<footer class="muted">Made with csv-analyzer-python</footer>'
        + "</main></body></html>"
    )
