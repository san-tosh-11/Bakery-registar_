"""
app.py
Bakery Order Register - Streamlit user interface (Project #87).

HOW TO RUN:
    pip install streamlit
    streamlit run app.py

HOW THIS FILE IS ORGANISED (useful for explaining it in the Expo):
    This file contains ONLY the screen (UI). All real work is done by the
    modules in the `core/` package, which are shared with the terminal version (main.py):

        core/models.py       -> BakeryOrder + finance maths (subtotal, discount, tax, total, balance)
        core/validator.py    -> defensive input checks (name, phone, price, dates ...)
        core/persistence.py  -> saves / loads orders in JSON + CSV (with corruption recovery)
        core/analytics.py    -> KPIs, overdue / due-soon alerts
        core/importer.py     -> bulk CSV import with row-by-row error log
        core/exporter.py     -> Markdown / TXT audit / CSV reports

    Streamlit re-runs this whole script from top to bottom every time the user
    clicks or types something. Data that must survive between re-runs is kept
    in `st.session_state` (a dictionary that lives as long as the browser tab).

    No HTML or CSS is written anywhere - every element is a Python call (st.xxx).
"""

import os
import sys
from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

# Make sure `core/` can be imported no matter where streamlit is started from
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.models import BakeryOrder, BakeryCategory, OrderStatus, PaymentStatus
from core.validator import (
    validate_customer_name,
    validate_customer_phone,
    validate_customer_email,
    validate_item_name,
    validate_quantity,
    validate_unit_price,
    validate_discount_percent,
    validate_tax_percent,
    validate_advance_paid,
    validate_pickup_date,
)
from core.persistence import StorageManager
from core.analytics import AnalyticsEngine
from core.exporter import ReportExporter
from core.importer import BulkDatasetImporter

SAMPLE_JSON = os.path.join(ROOT_DIR, "data", "sample_orders.json")
FLAWED_CSV = os.path.join(ROOT_DIR, "data", "test_invalid_import.csv")

# set_page_config must be the very first Streamlit call
st.set_page_config(page_title="Bakery Order Register", page_icon="🍰", layout="wide")


# ----------------------------------------------------------------------------
# 1. STATE: load orders once per browser session
# ----------------------------------------------------------------------------
def init_state() -> None:
    """Loads saved orders from disk the first time the page opens."""
    if "storage" in st.session_state:
        return
    storage = StorageManager()
    orders = storage.load_orders()
    if not orders and os.path.exists(SAMPLE_JSON):
        # Empty register -> start with the 42 sample orders (same as the terminal app)
        orders = StorageManager(json_path=SAMPLE_JSON).load_orders_json()
        storage.sync_all(orders)
    st.session_state.storage = storage
    st.session_state.orders = orders
    st.session_state.form_id = 0          # changing this clears the New Order form
    st.session_state.flash = None         # message shown after a save
    st.session_state.import_result = None
    st.session_state.last_export = None


def save_orders() -> None:
    """Writes the current order list to BOTH orders.json and orders.csv."""
    st.session_state.storage.sync_all(st.session_state.orders)


def flash(message: str) -> None:
    """Remember a success message to show after the page re-runs."""
    st.session_state.flash = message


# ----------------------------------------------------------------------------
# 2. SMALL HELPERS
# ----------------------------------------------------------------------------
def unpack(result):
    """
    The validators in core/validator.py return tuples of different shapes:
        (ok, cleaned_value)               e.g. validate_customer_name
        (ok, cleaned_value, error_text)   e.g. validate_quantity
    This turns both into one shape: (ok, value, error_text).
    """
    if len(result) == 3:
        return result
    ok, value_or_msg = result
    return (True, value_or_msg, "") if ok else (False, None, value_or_msg)


def check_field(label: str, raw: str, validator, required: bool = True):
    """
    Runs one validator and shows the red error text under the field.
    Returns (ok, cleaned_value). Empty required fields are 'not ok' but stay
    silent, so the form does not shout at the user before they start typing.
    """
    if not raw.strip():
        return (not required), ""
    ok, value, message = unpack(validator(raw))
    if not ok:
        st.error(f"{label}: {message}", icon="⚠️")
    return ok, value


def orders_to_dataframe(orders) -> pd.DataFrame:
    """Converts BakeryOrder objects into a table (DataFrame) for display."""
    rows = []
    for o in orders:
        if o.is_overdue():
            timing = "OVERDUE"
        elif o.is_due_within_hours(24):
            timing = "Due < 24h"
        else:
            timing = ""
        rows.append({
            "Order ID": o.order_id,
            "Customer": o.customer_name,
            "Phone": o.customer_phone,
            "Category": o.item_category,
            "Item": o.item_name,
            "Qty": o.quantity,
            "Total ($)": o.total_price,
            "Paid ($)": o.advance_paid,
            "Balance ($)": o.balance_due,
            "Pickup": o.pickup_date,
            "Payment": o.payment_status,
            "Status": o.order_status,
            "Timing": timing,
        })
    return pd.DataFrame(rows)


def next_order_id(orders) -> str:
    """Next sequential ID, e.g. ORD-2026-1043 (same rule as the terminal app)."""
    highest = 1000
    for o in orders:
        if o.order_id.startswith("ORD-"):
            try:
                highest = max(highest, int(o.order_id.split("-")[-1]))
            except ValueError:
                pass
    return f"ORD-2026-{highest + 1}"


def pickup_string(d: date, t: time) -> str:
    return f"{d:%Y-%m-%d} {t:%H:%M}"


# ----------------------------------------------------------------------------
# 3. TAB: DASHBOARD  (executive summary + threshold warnings)
# ----------------------------------------------------------------------------
def render_dashboard() -> None:
    orders = st.session_state.orders
    summary = AnalyticsEngine.generate_summary(orders)

    st.subheader("Your bakery at a glance")
    st.caption("A live overview of orders, payments and fulfilment activity.")

    # Operational alerts are kept prominent so urgent pickups are not missed.
    if summary["overdue_count"]:
        st.error(f"🚨 {summary['overdue_count']} order(s) are overdue for pickup. Review them in Orders.")
    if summary["imminent_count"]:
        st.warning(f"⏰ {summary['imminent_count']} order(s) are due within the next 24 hours.")
    for warning in summary["warnings"]:
        if warning.startswith("FINANCIAL"):
            st.warning(warning)

    # Bordered KPI cards use Streamlit's native layout and metric widgets.
    metrics = [
        ("Total orders", f"{summary['total_orders']:,}", "📦"),
        ("Gross revenue", f"${summary['gross_revenue']:,.2f}", "💰"),
        ("Cash collected", f"${summary['cash_collected']:,.2f}", "💳"),
        ("Outstanding", f"${summary['outstanding_balance']:,.2f}", "🧾"),
    ]
    cols = st.columns(4)
    for col, (label, value, icon) in zip(cols, metrics):
        with col:
            with st.container(border=True):
                st.caption(f"{icon}  {label}")
                st.markdown(f"### {value}")
    with st.container(border=True):
        st.caption("🎯 Fulfilment rate")
        st.metric("Orders completed", f"{summary['fulfillment_rate']}%")

    if not orders:
        st.info("Your register is empty. Select **New Order** from the sidebar to add the first order.")
        return

    st.divider()
    st.subheader("Business analytics")
    left, middle, right = st.columns(3)
    with left:
        with st.container(border=True):
            st.markdown("**Revenue by category**")
            cat = pd.DataFrame(
                {"Revenue ($)": {k: v["revenue"] for k, v in summary["category_breakdown"].items()}}
            )
            st.bar_chart(cat, use_container_width=True)
    with middle:
        with st.container(border=True):
            st.markdown("**Payment status**")
            st.bar_chart(pd.DataFrame({"Orders": summary["payment_breakdown"]}), use_container_width=True)
    with right:
        with st.container(border=True):
            st.markdown("**Order status**")
            st.bar_chart(pd.DataFrame({"Orders": summary["status_breakdown"]}), use_container_width=True)

    st.divider()
    a, b = st.columns([1, 1.5])
    with a:
        with st.container(border=True):
            st.markdown("**🏆 Top selling items**")
            top = pd.DataFrame(summary["top_items"]).rename(
                columns={"name": "Item", "units": "Units sold"})
            if not top.empty:
                st.dataframe(top, hide_index=True, use_container_width=True)
            else:
                st.caption("No sales data available yet.")
    with b:
        with st.container(border=True):
            st.markdown("**⏳ Overdue orders**")
            if summary["overdue_orders"]:
                st.dataframe(pd.DataFrame(summary["overdue_orders"]), hide_index=True, use_container_width=True)
            else:
                st.success("No overdue orders. Your pickup schedule is clear.")


# ----------------------------------------------------------------------------
# 4. TAB: ORDERS  (view + search + filter)
# ----------------------------------------------------------------------------
def render_orders() -> None:
    orders = st.session_state.orders
    if not orders:
        st.info("No orders recorded yet.")
        return

    f1, f2, f3, f4, f5 = st.columns([2, 2, 1.5, 1.5, 1.5])
    keyword = f1.text_input("Search", placeholder="customer, ID, item, phone, flavour ...").strip().lower()
    cats = f2.multiselect("Category", [c.value for c in BakeryCategory])
    pays = f3.multiselect("Payment", [p.value for p in PaymentStatus])
    stats = f4.multiselect("Status", [s.value for s in OrderStatus])
    timing = f5.selectbox("Timing", ["All", "Overdue", "Due within 24h"])

    def matches(o: BakeryOrder) -> bool:
        if keyword and not any(keyword in text.lower() for text in (
                o.order_id, o.customer_name, o.item_name, o.customer_phone, o.flavor_notes)):
            return False
        if cats and o.item_category not in cats:
            return False
        if pays and o.payment_status not in pays:
            return False
        if stats and o.order_status not in stats:
            return False
        if timing == "Overdue" and not o.is_overdue():
            return False
        if timing == "Due within 24h" and not o.is_due_within_hours(24):
            return False
        return True

    filtered = [o for o in orders if matches(o)]
    st.caption(f"Showing {len(filtered)} of {len(orders)} orders")
    if not filtered:
        st.warning("No orders match these filters.")
        return

    with st.container(border=True):
        st.dataframe(orders_to_dataframe(filtered), hide_index=True, use_container_width=True)

    # Full details of one order
    chosen = st.selectbox("Inspect an order", [o.order_id for o in filtered])
    o = next(x for x in filtered if x.order_id == chosen)
    d1, d2, d3 = st.columns(3)
    with d1:
        st.markdown(f"**Customer:** {o.customer_name}")
        st.markdown(f"**Phone:** {o.customer_phone}")
        st.markdown(f"**Email:** {o.customer_email or 'N/A'}")
        st.markdown(f"**Item:** {o.item_name} ({o.item_category})")
        st.markdown(f"**Notes:** {o.flavor_notes or 'Standard'}")
    with d2:
        st.markdown(f"**Quantity x Price:** {o.quantity} x ${o.unit_price:.2f}")
        st.markdown(f"**Subtotal:** ${o.subtotal:.2f}")
        st.markdown(f"**Discount / Tax:** {o.discount_percent}% / {o.tax_percent}%")
        st.markdown(f"**Total:** ${o.total_price:.2f}")
        st.markdown(f"**Paid / Balance:** ${o.advance_paid:.2f} / ${o.balance_due:.2f}")
    with d3:
        st.markdown(f"**Payment status:** {o.payment_status}")
        st.markdown(f"**Order status:** {o.order_status}")
        st.markdown(f"**Placed on:** {o.order_date}")
        st.markdown(f"**Pickup:** {o.pickup_date}" + ("  - OVERDUE" if o.is_overdue() else ""))
        st.markdown(f"**Instructions:** {o.special_instructions or 'None'}")


# ----------------------------------------------------------------------------
# 5. TAB: NEW ORDER  (live validation + live price calculation)
# ----------------------------------------------------------------------------
def render_new_order() -> None:
    orders = st.session_state.orders
    fid = st.session_state.form_id          # suffix for widget keys -> lets us reset the form
    order_id = next_order_id(orders)
    st.subheader(f"New order  -  {order_id}")
    st.caption("Every field is checked by core/validator.py as you type. "
               "The Save button unlocks only when everything is valid.")

    # --- Customer ---
    st.markdown("#### 01 · Customer details")
    col1, col2, col3 = st.columns(3)
    name_raw = col1.text_input("Customer name *", key=f"name_{fid}")
    phone_raw = col2.text_input("Customer phone *", key=f"phone_{fid}", placeholder="+91 98765 43210")
    email_raw = col3.text_input("Email (optional)", key=f"email_{fid}")
    with col1:
        ok_name, name = check_field("Name", name_raw, validate_customer_name)
    with col2:
        ok_phone, phone = check_field("Phone", phone_raw, validate_customer_phone)
    with col3:
        ok_email, email = check_field(
            "Email", email_raw, lambda s: validate_customer_email(s, required=False), required=False)

    st.divider()
    # --- Item ---
    st.markdown("#### 02 · Bakery item")
    col1, col2, col3 = st.columns(3)
    category = col1.selectbox("Category", [c.value for c in BakeryCategory], key=f"cat_{fid}")
    item_raw = col2.text_input("Item name *", key=f"item_{fid}")
    notes = col3.text_input("Flavour / dietary / inscription", key=f"notes_{fid}")
    with col2:
        ok_item, item = check_field("Item", item_raw, validate_item_name)

    st.divider()
    # --- Pricing ---
    st.markdown("#### 03 · Pricing and payment")
    col1, col2, col3, col4 = st.columns(4)
    qty_raw = col1.text_input("Quantity (1-500) *", value="1", key=f"qty_{fid}")
    price_raw = col2.text_input("Unit price ($0.50-$5000) *", key=f"price_{fid}")
    disc_raw = col3.text_input("Discount % (0-75)", value="0", key=f"disc_{fid}")
    tax_raw = col4.text_input("Tax % (0-30)", value="5", key=f"tax_{fid}")
    with col1:
        ok_qty, qty = check_field("Quantity", qty_raw, validate_quantity)
    with col2:
        ok_price, price = check_field("Price", price_raw, validate_unit_price)
    with col3:
        ok_disc, disc = check_field("Discount", disc_raw, validate_discount_percent, required=False)
    with col4:
        ok_tax, tax = check_field("Tax", tax_raw, validate_tax_percent, required=False)
    disc = disc or 0.0
    tax = tax or 0.0

    # --- Live total: reuse BakeryOrder so the maths lives in ONE place (core/models.py) ---
    est_total = None
    if ok_qty and ok_price and ok_disc and ok_tax and qty_raw.strip() and price_raw.strip():
        preview = BakeryOrder(
            order_id="PREVIEW", customer_name="Preview", customer_phone="0000000",
            item_category=category, item_name="Preview", quantity=qty, unit_price=price,
            pickup_date="2026-01-01", discount_percent=disc, tax_percent=tax)
        est_total = preview.total_price
        m1, m2, m3 = st.columns(3)
        m1.metric("Subtotal", f"${preview.subtotal:.2f}")
        m2.metric("Discount / Tax", f"{disc}% / {tax}%")
        m3.metric("Total", f"${est_total:.2f}")

    st.divider()
    # --- Advance payment (needs the total to check against) ---
    st.markdown("#### 04 · Pickup and instructions")
    col1, col2, col3 = st.columns(3)
    advance_raw = col1.text_input("Advance paid ($)", value="0", key=f"adv_{fid}")
    pickup_date = col2.date_input(
        "Pickup date", value=date.today() + timedelta(days=1),
        min_value=date.today(), max_value=date.today() + timedelta(days=365), key=f"pdate_{fid}")
    pickup_time = col3.time_input("Pickup time", value=time(10, 0), key=f"ptime_{fid}")

    ok_adv, advance = True, 0.0
    with col1:
        if advance_raw.strip():
            ok_adv, advance, msg = unpack(validate_advance_paid(advance_raw, est_total))
            if not ok_adv:
                st.error(f"Advance: {msg}", icon="⚠️")
        advance = advance or 0.0
    with col3:
        ok_pick, pickup, pick_msg = validate_pickup_date(pickup_string(pickup_date, pickup_time))
        if not ok_pick:
            st.error(f"Pickup: {pick_msg}", icon="⚠️")

    instructions = st.text_input("Special storage / packaging instructions", key=f"instr_{fid}")

    all_ok = all([ok_name, ok_phone, ok_email, ok_item, ok_qty, ok_price,
                  ok_disc, ok_tax, ok_adv, ok_pick]) \
        and name_raw.strip() and phone_raw.strip() and item_raw.strip() and price_raw.strip()

    if not all_ok:
        st.info("Fill in all required (*) fields correctly to enable saving.")
    if st.button("💾 Save order", type="primary", disabled=not all_ok):
        new_order = BakeryOrder(
            order_id=order_id, customer_name=name, customer_phone=phone, customer_email=email,
            item_category=category, item_name=item, quantity=qty, unit_price=price,
            discount_percent=disc, tax_percent=tax, advance_paid=advance,
            pickup_date=pickup, flavor_notes=notes.strip(),
            special_instructions=instructions.strip(), order_status=OrderStatus.PENDING.value)
        orders.append(new_order)
        save_orders()
        st.session_state.form_id += 1          # clears the form on the next run
        flash(f"Order {order_id} saved to JSON and CSV. Total ${new_order.total_price:.2f}, "
              f"balance due ${new_order.balance_due:.2f} ({new_order.payment_status}).")
        st.rerun()


# ----------------------------------------------------------------------------
# 6. TAB: UPDATE ORDER  (payments, status, pickup date, delete)
# ----------------------------------------------------------------------------
def render_update() -> None:
    orders = st.session_state.orders
    if not orders:
        st.info("No orders to update.")
        return

    labels = {o.order_id: f"{o.order_id}  -  {o.customer_name}  -  {o.item_name}" for o in orders}
    chosen = st.selectbox("Select order", list(labels), format_func=lambda i: labels[i])
    order = next(o for o in orders if o.order_id == chosen)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total", f"${order.total_price:.2f}")
    m2.metric("Paid", f"${order.advance_paid:.2f}")
    m3.metric("Balance due", f"${order.balance_due:.2f}")
    m4.metric("Payment status", order.payment_status)

    left, middle, right = st.columns(3)

    with left:
        st.markdown("**💳 Record a payment**")
        if order.balance_due <= 0:
            st.success("Fully paid.")
        else:
            amount = st.number_input(
                "Amount ($)", min_value=0.01, max_value=float(order.balance_due),
                value=float(order.balance_due), step=1.0, key=f"pay_{chosen}")
            if st.button("Record payment"):
                paid = order.record_additional_payment(amount)   # also refreshes payment status
                save_orders()
                flash(f"Recorded ${paid:.2f} for {chosen}. Balance is now ${order.balance_due:.2f} "
                      f"({order.payment_status}).")
                st.rerun()

    with middle:
        st.markdown("**⚙️ Change order status**")
        statuses = [s.value for s in OrderStatus]
        new_status = st.selectbox("Status", statuses, index=statuses.index(order.order_status),
                                  key=f"status_{chosen}")
        if st.button("Update status"):
            order.order_status = new_status
            save_orders()
            flash(f"{chosen} is now '{new_status}'.")
            st.rerun()

    with right:
        st.markdown("**🗓️ Reschedule pickup**")
        new_date = st.date_input("New date", value=date.today() + timedelta(days=1),
                                 min_value=date.today(), key=f"rd_{chosen}")
        new_time = st.time_input("New time", value=time(10, 0), key=f"rt_{chosen}")
        if st.button("Update pickup"):
            ok, value, msg = validate_pickup_date(pickup_string(new_date, new_time))
            if ok:
                order.pickup_date = value
                save_orders()
                flash(f"Pickup for {chosen} changed to {value}.")
                st.rerun()
            else:
                st.error(msg)

    with st.expander("Delete this order"):
        sure = st.checkbox("Yes, permanently delete this order", key=f"del_ok_{chosen}")
        if st.button("Delete order", disabled=not sure):
            st.session_state.orders = [o for o in orders if o.order_id != chosen]
            save_orders()
            flash(f"Order {chosen} deleted.")
            st.rerun()


# ----------------------------------------------------------------------------
# 7. TAB: BULK IMPORT  (CSV with row-by-row error log)
# ----------------------------------------------------------------------------
def render_import() -> None:
    st.caption("Upload a CSV. Each row is validated; rejected rows are listed with the exact reason.")
    source = st.radio("CSV source", ["Upload my own file", "Use the sample flawed file (demo)"],
                      horizontal=True)

    csv_text = None
    if source.startswith("Upload"):
        uploaded = st.file_uploader("Choose a CSV file", type=["csv"])
        if uploaded is not None:
            csv_text = uploaded.getvalue().decode("utf-8-sig", errors="replace")
    elif os.path.exists(FLAWED_CSV):
        with open(FLAWED_CSV, "r", encoding="utf-8-sig") as f:
            csv_text = f.read()
        st.code(csv_text, language="text")

    if csv_text is not None and st.button("Validate CSV"):
        # Generate IDs for rows without one, continuing after any existing ORD-IMP-xxxx
        start = 2001
        for o in st.session_state.orders:
            if o.order_id.startswith("ORD-IMP-"):
                try:
                    start = max(start, int(o.order_id.split("-")[-1]) + 1)
                except ValueError:
                    pass
        st.session_state.import_result = BulkDatasetImporter.import_from_csv_string(csv_text, start)

    result = st.session_state.import_result
    if result is None:
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Rows processed", result.total_rows)
    c2.metric("Valid", result.success_count)
    c3.metric("Rejected", result.failure_count)

    if result.errors:
        st.subheader("Row-by-row error log")
        st.dataframe(pd.DataFrame(result.errors).rename(columns={
            "row": "Row", "column": "Column", "value": "Rejected value", "message": "Reason"}),
            hide_index=True)

    if result.valid_orders:
        st.subheader("Valid rows ready to import")
        st.dataframe(orders_to_dataframe(result.valid_orders), hide_index=True)
        if st.button("➕ Append valid orders to register", type="primary"):
            existing = {o.order_id for o in st.session_state.orders}
            fresh = [o for o in result.valid_orders if o.order_id not in existing]
            skipped = len(result.valid_orders) - len(fresh)
            st.session_state.orders.extend(fresh)
            save_orders()
            st.session_state.import_result = None
            flash(f"Imported {len(fresh)} order(s)." + (f" Skipped {skipped} duplicate ID(s)." if skipped else ""))
            st.rerun()


# ----------------------------------------------------------------------------
# 8. TAB: EXPORT REPORTS
# ----------------------------------------------------------------------------
def render_export() -> None:
    st.caption("Creates a Markdown executive report, a plain-text audit ledger and a CSV, "
               "saved in the reports/ folder.")
    if st.button("Generate reports", type="primary"):
        st.session_state.last_export = ReportExporter().export_all(st.session_state.orders)

    paths = st.session_state.last_export
    if not paths:
        return
    st.success("Reports generated.")
    for key, label, mime in [("markdown", "Markdown report", "text/markdown"),
                             ("audit_text", "Plain-text audit ledger", "text/plain"),
                             ("csv", "CSV export", "text/csv")]:
        with open(paths[key], "rb") as f:
            st.download_button(f"⬇ Download {label}", f.read(),
                               file_name=os.path.basename(paths[key]), mime=mime)
    with open(paths["markdown"], "r", encoding="utf-8") as f:
        with st.expander("Preview Markdown report"):
            st.markdown(f.read())


# ----------------------------------------------------------------------------
# 9. PAGE LAYOUT  (this is what runs on every re-run)
# ----------------------------------------------------------------------------
def main() -> None:
    init_state()

    # Compact brand header; all UI remains native Streamlit components.
    brand, meta = st.columns([3, 1])
    with brand:
        st.title("🍰 Artisan Crust & Crumb")
        st.caption("BAKERY ORDER REGISTER  ·  PROJECT #87")
    with meta:
        st.metric("Orders in register", len(st.session_state.orders))

    if st.session_state.flash:
        st.success(st.session_state.flash)
        st.session_state.flash = None

    pages = {
        "📊  Dashboard": "dashboard",
        "📋  Orders": "orders",
        "➕  New order": "new",
        "✏️  Update order": "update",
        "📥  Bulk import": "import",
        "📤  Export reports": "export",
    }
    with st.sidebar:
        st.markdown("# 🍞 Artisan Crust")
        st.caption("BAKERY MANAGEMENT STUDIO")
        st.divider()
        st.markdown("**WORKSPACE**")
        selected = st.radio("Navigation", list(pages), label_visibility="collapsed", key="main_navigation")
        st.divider()
        st.markdown("**REGISTER STATUS**")
        st.metric("Saved orders", len(st.session_state.orders))
        st.caption("Changes are saved to the local JSON and CSV files.")
        with st.expander("Demo data tools"):
            st.warning("Reloading sample data replaces the current register.")
            confirm = st.checkbox("I understand — replace current data")
            if st.button("↻ Reload 42 sample orders", disabled=not confirm, use_container_width=True):
                from scripts.seed_sample_data import generate_samples
                generate_samples()
                st.session_state.orders = st.session_state.storage.load_orders()
                flash("Sample data reloaded (42 orders).")
                st.rerun()
        st.divider()
        st.caption("Project #87 · Python + Streamlit")

    page = pages[selected]
    if page == "dashboard":
        render_dashboard()
    elif page == "orders":
        st.subheader("Order register")
        st.caption("Search, filter and inspect every customer order.")
        render_orders()
    elif page == "new":
        st.subheader("Create a bakery order")
        st.caption("Enter customer, product, pricing and pickup details. Fields are validated before saving.")
        render_new_order()
    elif page == "update":
        st.subheader("Manage an existing order")
        st.caption("Record payments, update preparation status or reschedule collection.")
        render_update()
    elif page == "import":
        st.subheader("Bulk import")
        st.caption("Validate a CSV file and review rejected rows before importing accepted orders.")
        render_import()
    elif page == "export":
        st.subheader("Reports & exports")
        st.caption("Generate downloadable business summaries and audit records.")
        render_export()


main()
