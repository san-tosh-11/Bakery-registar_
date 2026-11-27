# EXPLAIN.md — Know your project (for the Project Expo)

Every team member may be asked about **working, implementation, code and output**. Read this top to bottom once and you can answer any of them.

---

## 1. One-line description
> "A bakery order register in Python. Staff enter orders, the program validates every input, calculates the money automatically, saves to JSON and CSV, warns about overdue pickups, and shows everything through a Streamlit interface."

## 2. The big idea: logic and screen are separate

```
   app.py (Streamlit screen)  ─┐
                               ├──►  core/  (all real work)  ──►  data/orders.json + orders.csv
   main.py (terminal menu)    ─┘
```

* `core/` = the **brain** (maths, rules, saving). It knows nothing about screens.
* `app.py` and `main.py` = two **faces** that call the same brain.
* Benefit: one set of rules, tested once (101 unit tests), used by both interfaces.

## 3. What each file does

| File | Role | Key things to say |
| :--- | :--- | :--- |
| `core/models.py` | Data + money maths | `BakeryOrder` is a **dataclass**. `recompute_finances()` calculates subtotal → discount → tax → total → balance and sets Paid/Partial/Unpaid. `is_overdue()` and `is_due_within_hours()` drive the warnings. Enums (`OrderStatus`, `PaymentStatus`, `BakeryCategory`) prevent typos. |
| `core/validator.py` | Defensive validation | One function per field. Each returns *valid or not* plus a cleaned value or an error message. Uses **regular expressions** (regex) for name / phone / email / date, and range checks for numbers. |
| `core/persistence.py` | Saving & loading | `StorageManager` writes **JSON and CSV**. **Atomic write**: write to `.tmp` then replace, so a crash can't half-write the file. **Recovery**: corrupted file → backed up → fresh file created. |
| `core/analytics.py` | Dashboard numbers | `generate_summary()` loops over all orders once and returns revenue, cash collected, outstanding, fulfilment rate, category totals, top items, overdue/imminent lists and warnings. |
| `core/importer.py` | Bulk CSV import | Maps different column names (`qty`, `Quantity`, `count` …) to standard ones, validates each row with the same validators, logs **every** error with row number, column, value and reason. |
| `core/exporter.py` | Reports | Writes Markdown, plain-text audit and CSV into `reports/`. |
| `app.py` | Streamlit UI | See section 4. |
| `main.py` | Terminal UI | Menu loop with `input()` / `print()`. Option **W** launches the Streamlit UI. |

## 4. How `app.py` works (Streamlit in 60 seconds)

1. **Streamlit re-runs the whole script from top to bottom on every click or keystroke.**
2. Anything that must survive a re-run is stored in **`st.session_state`** (a dictionary). We keep the loaded `orders` list and the storage manager there.
3. `init_state()` loads orders from disk once. After any change we call `save_orders()` which writes JSON + CSV.
4. The page uses sidebar navigation. Each destination is drawn by one function:
   `render_dashboard`, `render_orders`, `render_new_order`, `render_update`, `render_import`, `render_export`.
5. UI elements are Python calls: `st.text_input`, `st.selectbox`, `st.metric`, `st.dataframe`, `st.bar_chart`, `st.button`, and `st.radio` for sidebar navigation. **No HTML/CSS.**
6. `st.rerun()` forces a fresh run after saving; `flash()` keeps the success message across that rerun.

### New Order tab — the most important flow
```
user types → check_field() calls the validator → red error shown immediately
          → when qty/price/discount/tax are valid, a temporary BakeryOrder computes the live total
          → Save button enabled only when every field is valid
          → click Save → BakeryOrder created → appended to list → save_orders() → form cleared
```
The total is **not** recalculated in `app.py`; it reuses `BakeryOrder` so the formula exists in only one place.

## 5. Worked example (be ready to do this live)
Quantity 2 × $40.00 = **$80.00** subtotal · discount 0 % · tax 5 % → tax **$4.00** · total **$84.00**
Advance **$42.00** → balance **$42.00** → status **Partial**. Pay the $42.00 → balance **$0.00** → **Paid**.

## 6. Questions you may be asked

**Why Streamlit?** Pure Python, so the interface is written in the same language as the project, and it was one of the two options allowed (NiceGUI or Streamlit). No HTML/CSS needed.

**Where is the data stored?** `data/orders.json` and `data/orders.csv`, both updated on every change.

**What if the JSON file is corrupted?** `persistence.py` catches the error, copies the bad file to `*.corrupt_<timestamp>.bak`, creates a clean file, and the program keeps running.

**What is an atomic write?** Write the new data to a temporary file first, then replace the real file in one step. If the program dies mid-write, the old file is still intact.

**How do you stop wrong input?** Validators in `core/validator.py` run on every field (regex + range checks). In the UI the Save button stays disabled until all fields pass; in the terminal, `prompt_validated_input` loops until the input is valid.

**How is the payment status decided?** After every change, `recompute_finances()` checks: balance 0 → Paid; some money paid → Partial; otherwise Unpaid.

**What counts as overdue?** Pickup time has passed and the order is not Completed or Cancelled. "Due soon" means pickup within the next 24 hours.

**What happens on bulk import with bad rows?** Valid rows are kept, bad rows are rejected, and each problem is listed with row, column, rejected value and reason. Only valid rows are added, and duplicate order IDs are skipped.

**How is the code tested?** `python -m unittest tests/test_bakery.py -v` runs 101 tests covering models, validators, persistence, analytics, import, export and end-to-end flows.

**What is a dataclass?** A Python class where the fields are declared once and `__init__`, `__repr__` etc. are generated automatically. `BakeryOrder` is one.

**Difference between `main.py` and `app.py`?** Same logic, different interface: `main.py` is text menus, `app.py` is the graphical Streamlit interface.

## 7. Run checklist for tomorrow
- [ ] `pip install streamlit` done on the laptop you will demo on (needs internet once).
- [ ] `python -m streamlit run app.py` opens the page on http://localhost:8501.
- [ ] In the sidebar, open **Demo data tools** and click **Reload 42 sample orders** so dates are fresh and the warnings show.
- [ ] Do a full dry run of the demo script in `README.md`.
- [ ] Bring: printed project documentation, Letz project report showing the score, DTI prototype components.
- [ ] Full uniform with blazer and formal shoes.
