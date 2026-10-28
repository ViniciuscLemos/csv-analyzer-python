# Sales CSV Analyzer

![Tests](https://github.com/ViniciuscLemos/csv-analyzer-python/actions/workflows/tests.yml/badge.svg)

A Python program that reads a sales CSV, loads the data into a SQLite database and generates a report with the queries written in SQL.

You don't need to install anything besides Python (3.10+).

## Running

```bash
python main.py
```

If there's no CSV at `data/sales.csv`, it generates one with 200 made-up sales. The report goes to `output/report.txt` and also shows up in the terminal.

The report has:
- total revenue and average ticket
- sales by category and by region
- the best-selling products
- the seller ranking
- a simple text chart with the revenue for each month

Options:

```bash
python main.py --csv my_sales.csv          # use another file
python main.py --generate 1000 --seed 42   # generate a new CSV
python main.py --json                      # also save it as JSON
python main.py --html                      # also save a page with charts
python main.py --top 10                    # top 10 products instead of 5
python main.py --from 2024-06-01 --to 2024-06-30   # only one period
python main.py --category books            # only one category
python main.py --seller "ana lima"          # only one seller (case doesn't matter)
```

## What the report looks like

A run with 200 generated sales (`python main.py --generate 200 --seed 3`):

<p>
  <img src="docs/screenshot-run.png" alt="Importing the CSV and the start of the report" width="49%">
  <img src="docs/screenshot-report.png" alt="Seller ranking, sales by region and the monthly chart" width="49%">
</p>

With `--html` the same report also goes to `output/report.html`, a single page with the charts (plain HTML and CSS, no library, so it opens offline). It follows the system's dark mode too.

![The HTML report with revenue by month, category, region and the rankings](docs/screenshot-html.png)

## CSV format

```
date,product,category,quantity,price,seller,region
2024-03-10,Laptop,Electronics,1,2500.00,Ana Lima,Southeast
```

The date has to be in the `YYYY-MM-DD` format, and the price can be written with a dot or a comma, with a currency symbol in front (`$1,234.50`, `R$ 1.234,50`) or without. The separator can be a comma, a semicolon (that is how Excel saves the file in some languages) or a tab. If a row is wrong, the program skips it and tells you which one and why. Completely empty lines (Excel likes to leave a few `,,,,,,` at the end) are just ignored.

## Tests

```bash
python -m unittest discover -s tests
```

## Files

```
main.py
src/database.py        creates the database and imports the CSV
src/analyzer.py        queries and building the report
src/csv_generator.py   generates the sample data
src/html_report.py     the HTML version of the report
```
