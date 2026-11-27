# 🍰 Artisan Crust & Crumb — Bakery Order Register
**Project #87 · Small Business & Retail · Python + Streamlit**

A bakery order tracker that removes manual calculation errors, validates every input, saves data safely to JSON and CSV, warns about overdue pickups, imports legacy CSV files and exports reports.

It has two front-ends sharing the same logic (`core/`):

| Interface | File | Run with |
| :--- | :--- | :--- |
| **Graphical UI (Streamlit)** | `app.py` | `python -m streamlit run app.py` |
| Terminal menu | `main.py` | `python main.py` |

No HTML or CSS is used anywhere. Every screen element is a Python call.

---

## Setup

```bash
pip install streamlit          # only needed for the graphical UI
python -m streamlit run app.py # opens http://localhost:8501
```

Windows: double-click `start_gui.bat` (GUI) or `start_cli.bat` (terminal).
The `core/` package and `main.py` need only the Python 3.10+ standard library.

Run the tests:
```bash
python -m unittest tests/test_bakery.py -v     # 101 tests
```

---

## Features (Streamlit sidebar workspace)

The redesigned interface uses Streamlit native components with a built-in dark charcoal theme and warm-gold accent. Navigation is in the sidebar; no custom HTML or CSS is used.


| Tab | What it does |
| :--- | :--- |
| 📊 **Dashboard** | KPI cards (orders, revenue, cash collected, outstanding, fulfilment rate), overdue / due-in-24h warnings, charts, top-selling items |
| 📋 **Orders** | Search by customer / ID / item / phone / flavour; filter by category, payment, status, timing; inspect any order |
| ➕ **New Order** | Live validation under each field, live Subtotal / Discount / Tax / Total, Save unlocks only when everything is valid |
| ✏️ **Update Order** | Record payment (balance and Paid/Partial/Unpaid update automatically), change status, reschedule pickup, delete |
| 📥 **Bulk Import** | Upload a CSV; every row validated; row-by-row error log; append only the valid rows |
| 📤 **Export Reports** | Markdown executive report, plain-text audit ledger, CSV — with download buttons |

---

## Project structure

```
├── app.py                 # Streamlit graphical interface (UI only)
├── main.py                # Terminal menu interface
├── core/
│   ├── models.py          # BakeryOrder + finance maths + enums
│   ├── validator.py       # Input validation rules
│   ├── persistence.py     # JSON + CSV save/load, atomic writes, corruption recovery
│   ├── analytics.py       # KPIs and threshold warnings
│   ├── importer.py        # Bulk CSV import with error log
│   └── exporter.py        # Markdown / TXT / CSV reports
├── data/                  # orders.json / orders.csv (live), sample_orders.*, test_invalid_import.csv
├── reports/               # generated exports
├── scripts/seed_sample_data.py   # regenerates the 42 sample orders
├── tests/test_bakery.py   # 101 unit tests
└── EXPLAIN.md             # how everything works, in plain language
```

---

## Business rules

**Finance** (`core/models.py`)
```
Subtotal   = Quantity × Unit price
Discount   = Subtotal × Discount %
Taxable    = Subtotal − Discount
Tax        = Taxable × Tax %
Total      = Taxable + Tax
Balance    = Total − Advance paid
Payment status:  Balance = 0 → Paid | Advance > 0 → Partial | else Unpaid
```

**Validation** (`core/validator.py`)

| Field | Rule |
| :--- | :--- |
| Customer name | 2–50 chars; letters, spaces, `' . -` |
| Phone | 7–15 digits; optional leading `+`; spaces, hyphens, brackets allowed |
| Email | Optional; must look like `name@domain.com` |
| Item name | 2–80 characters |
| Quantity | Whole number 1–500 |
| Unit price | $0.50 – $5,000.00 |
| Discount / Tax | 0–75 % / 0–30 % |
| Advance paid | ≥ 0 and ≤ order total |
| Pickup date | `YYYY-MM-DD` or `YYYY-MM-DD HH:MM`; not in the past; within 365 days |

**Persistence** — every change is written to `data/orders.json` and `data/orders.csv` through a temporary file, then swapped in (atomic write). If a file is corrupted, it is backed up as `*.corrupt_<time>.bak` and a clean one is created.

---

## Bulk-import demo (`data/test_invalid_import.csv`)

| CSV row | Result | Reason |
| :-: | :-: | :--- |
| 2 | ✅ accepted | valid |
| 3 | ❌ | phone `123` too short; quantity `-5` |
| 4 | ❌ | empty name; date `tomorrow afternoon` invalid |
| 5 | ❌ | advance $500 exceeds order total $25 |
| 6 | ❌ | price `FREE_SAMPLE` is not a number |

---

## 3-minute demo script

1. `python -m streamlit run app.py` → **Dashboard**: point at KPIs and the red overdue warning.
2. **New Order**: type bad values (name `123`, phone `abc`, quantity `-2`) and show the live red errors and the disabled Save button. Then enter *Eleanor Smith*, *Vanilla Sponge Cake*, qty 2, price 40, advance 42 → Total **$84.00**, balance **$42.00**, status **Partial** → Save.
3. **Update Order** → pick the new order → *Record payment* → balance **$0.00**, status **Paid**.
4. **Bulk Import** → *Use the sample flawed file* → *Validate CSV* → show the error log.
5. **Export Reports** → generate and download the Markdown report.
6. Run `python main.py` to show the same data in the terminal version (shared storage).
