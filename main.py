"""
main.py
Bakery Order Register — Interactive Terminal Application.
Project #87: Everyday Innovators Hackathon.

Features:
- Menu-driven ANSI terminal interface with pagination and color-coded statuses
- Defensive input validation routines with real-time range and regex checks
- Local persistence in JSON and CSV with corruption recovery
- Powerful search, filtering, and order lifecycle management
- Executive summaries, threshold alerts (overdue/imminent deadlines)
- Multi-format exports (Markdown, CSV, TXT audit ledger)
- Bulk dataset CSV ingestion with row-by-row validation error logs
- Option to launch the Streamlit graphical interface (app.py)
"""

import os
import sys
import subprocess
from datetime import datetime
from typing import List, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.models import BakeryOrder, PaymentStatus, OrderStatus, BakeryCategory
from core.validator import (
    validate_customer_name,
    validate_customer_phone,
    validate_customer_email,
    validate_item_category,
    validate_item_name,
    validate_quantity,
    validate_unit_price,
    validate_discount_percent,
    validate_tax_percent,
    validate_advance_paid,
    validate_pickup_date,
    validate_order_status,
    prompt_validated_input
)
from core.persistence import StorageManager
from core.analytics import AnalyticsEngine
from core.exporter import ReportExporter
from core.importer import BulkDatasetImporter


# ANSI Color Codes for terminal visual hierarchy
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BG_DARK = "\033[40m"


class BakeryCLI:
    """Console controller for Bakery Order Register."""

    def __init__(self):
        self.storage = StorageManager()
        self.orders: List[BakeryOrder] = self.storage.load_orders()
        self.exporter = ReportExporter()

        # If data is completely empty, offer to auto-seed
        if not self.orders:
            sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sample_orders.json")
            if os.path.exists(sample_path):
                sample_mgr = StorageManager(json_path=sample_path)
                self.orders = sample_mgr.load_orders_json()
                self.storage.sync_all(self.orders)

    def run(self) -> None:
        """Main event loop."""
        while True:
            self.display_header()
            self.display_threshold_alerts()
            self.display_menu()

            choice = input(f"{BOLD}{CYAN}Select an option [0-9, W for Web]: {RESET}").strip().upper()
            print()

            if choice == "1":
                self.record_new_order()
            elif choice == "2":
                self.view_all_orders_paginated()
            elif choice == "3":
                self.search_and_filter_orders()
            elif choice == "4":
                self.update_order_workflow()
            elif choice == "5":
                self.view_executive_summary()
            elif choice == "6":
                self.view_threshold_warnings()
            elif choice == "7":
                self.export_reports_workflow()
            elif choice == "8":
                self.bulk_csv_import_workflow()
            elif choice == "9":
                self.reset_or_seed_sample_data()
            elif choice == "W":
                self.launch_web_dashboard()
            elif choice == "0":
                print(f"{GREEN}Exiting Bakery Order Register. All changes persisted safely. Goodbye!{RESET}\n")
                break
            else:
                print(f"{RED}[Invalid Choice] Please select an option between 0 and 9, or 'W'.{RESET}")
                input(f"{DIM}Press Enter to continue...{RESET}")

    def display_header(self) -> None:
        """Displays branded terminal banner."""
        summary = AnalyticsEngine.generate_summary(self.orders)
        print("\n" + "=" * 80)
        print(f"{BOLD}{MAGENTA}   🍰 ARTISAN CRUST & CRUMB — BAKERY ORDER REGISTER (Project #87){RESET}")
        print(f"{DIM}   Reliable Order Tracking | Defensive Validation | Local Persistence (CSV/JSON){RESET}")
        print("=" * 80)
        print(
            f" {BOLD}Total Records:{RESET} {summary['total_orders']:<4} | "
            f"{BOLD}Gross Revenue:{RESET} {GREEN}${summary['gross_revenue']:,.2f}{RESET} | "
            f"{BOLD}Collected:{RESET} {CYAN}${summary['cash_collected']:,.2f}{RESET} | "
            f"{BOLD}Pending:{RESET} {YELLOW}${summary['outstanding_balance']:,.2f}{RESET}"
        )
        print("-" * 80)

    def display_threshold_alerts(self) -> None:
        """Displays highlighted alerts for overdue pickups or high unpaid balances."""
        summary = AnalyticsEngine.generate_summary(self.orders)
        if summary["overdue_count"] > 0:
            print(f" {RED}{BOLD}🚨 THRESHOLD ALERT:{RESET} {RED}{summary['overdue_count']} order(s) are OVERDUE for pickup! (Check Option 6){RESET}")
        if summary["imminent_count"] > 0:
            print(f" {YELLOW}⏰ NOTICE:{RESET} {YELLOW}{summary['imminent_count']} order(s) scheduled for pickup within the next 24 hours.{RESET}")
        if summary["warnings"]:
            print("-" * 80)

    def display_menu(self) -> None:
        """Prints main menu actions."""
        print(f"{BOLD}Main Operational Workflow:{RESET}")
        print(f"  {CYAN}1.{RESET} Record New Bakery Order (Defensive input validation)")
        print(f"  {CYAN}2.{RESET} View All Orders (Paginated & formatted ledger)")
        print(f"  {CYAN}3.{RESET} Search & Filter Orders (Keyword, Category, Payment, Status, Date)")
        print(f"  {CYAN}4.{RESET} Update Order Status / Record Additional Payment")
        print(f"  {CYAN}5.{RESET} Executive Summary & Analytics (KPIs, top items, revenue share)")
        print(f"  {CYAN}6.{RESET} Threshold Warning Center (Overdue alerts & critical metrics)")
        print(f"  {CYAN}7.{RESET} Multi-Format Export (Markdown, Standard CSV, Plaintext Audit)")
        print(f"  {CYAN}8.{RESET} Bulk Dataset Import (CSV ingestion with row-by-row error logs)")
        print(f"  {CYAN}9.{RESET} Reset / Reload Default Sample Test Dataset (42 records)")
        print(f"  {MAGENTA}W.{RESET} Launch Graphical Interface (Streamlit, app.py)")
        print(f"  {RED}0.{RESET} Exit Application")
        print("-" * 80)

    def record_new_order(self) -> None:
        """Interactive guided workflow to record a new order with defensive validation."""
        print(f"\n{BOLD}{CYAN}=== Record New Bakery Order ==={RESET}")
        print(f"{DIM}Follow the step-by-step prompts. Input will be validated defensively in real-time.{RESET}\n")

        # Generate unique sequential Order ID
        existing_ids = [o.order_id for o in self.orders if o.order_id.startswith("ORD-")]
        max_num = 1000
        for oid in existing_ids:
            try:
                num = int(oid.split("-")[-1])
                if num > max_num:
                    max_num = num
            except Exception:
                pass
        next_order_id = f"ORD-2026-{max_num + 1}"
        print(f" Assigned Order ID: {BOLD}{WHITE}{next_order_id}{RESET}")

        # Customer Details
        cust_name = prompt_validated_input(" Customer Full Name", validate_customer_name)
        cust_phone = prompt_validated_input(" Customer Phone (e.g. +1-555-123-4567)", validate_customer_phone)
        cust_email = prompt_validated_input(" Customer Email (Optional, press Enter to skip)", lambda s: validate_customer_email(s, required=False), default="")

        # Bakery Item Details
        print(f"\n Available Categories: {', '.join([c.value for c in BakeryCategory])}")
        category = prompt_validated_input(" Item Category", validate_item_category, default="Cake")
        item_name = prompt_validated_input(" Item Name / Product Description", validate_item_name)
        flavor_notes = input(" Flavor / Dietary / Custom Inscription Notes: ").strip()

        # Pricing and Quantity
        quantity = prompt_validated_input(" Quantity (Units/Packs, 1-500)", validate_quantity, default="1")
        unit_price = prompt_validated_input(" Unit Price ($0.50 - $5000.00)", validate_unit_price)

        subtotal = round(quantity * unit_price, 2)
        print(f" -> Subtotal: ${subtotal:.2f}")

        discount_pct = prompt_validated_input(" Discount Percentage (0-75%)", validate_discount_percent, default="0.0")
        tax_pct = prompt_validated_input(" Tax Percentage (0-30%)", validate_tax_percent, default="5.0")

        # Compute estimated total
        discount_amt = subtotal * (discount_pct / 100.0)
        taxable = subtotal - discount_amt
        tax_amt = taxable * (tax_pct / 100.0)
        est_total = round(taxable + tax_amt, 2)
        print(f" -> Calculated Total: {BOLD}${est_total:.2f}{RESET}")

        advance = prompt_validated_input(
            f" Advance Paid / Deposit ($0.00 - ${est_total:.2f})",
            lambda s: validate_advance_paid(s, est_total),
            default="0.0"
        )

        # Logistics
        pickup_date = prompt_validated_input(
            " Pickup Date & Time (YYYY-MM-DD or YYYY-MM-DD HH:MM)",
            lambda s: validate_pickup_date(s, allow_past=False)
        )

        special_inst = input(" Special Storage / Packaging Instructions: ").strip()

        # Create Order Object
        new_order = BakeryOrder(
            order_id=next_order_id,
            customer_name=cust_name,
            customer_phone=cust_phone,
            customer_email=cust_email,
            item_category=category,
            item_name=item_name,
            quantity=quantity,
            unit_price=unit_price,
            discount_percent=discount_pct,
            tax_percent=tax_pct,
            advance_paid=advance,
            pickup_date=pickup_date,
            flavor_notes=flavor_notes,
            special_instructions=special_inst,
            order_status=OrderStatus.PENDING.value
        )

        # Confirm and persist
        print(f"\n{BOLD}Order Summary Preview:{RESET}")
        print(f"  ID: {new_order.order_id} | Total: ${new_order.total_price:.2f} | Paid: ${new_order.advance_paid:.2f} | Balance: ${new_order.balance_due:.2f}")
        print(f"  Payment Status: {new_order.payment_status} | Pickup: {new_order.pickup_date}")
        
        confirm = input(f"{BOLD}Save this order to persistence? (Y/n): {RESET}").strip().lower()
        if confirm in ["", "y", "yes"]:
            self.orders.append(new_order)
            self.storage.sync_all(self.orders)
            print(f"{GREEN}{BOLD}✔ Order {new_order.order_id} recorded and synced to JSON and CSV!{RESET}")
        else:
            print(f"{YELLOW}Order discarded. Not saved.{RESET}")

        input(f"\n{DIM}Press Enter to return to main menu...{RESET}")

    def view_all_orders_paginated(self, order_subset: Optional[List[BakeryOrder]] = None) -> None:
        """Displays orders in a clean, fixed-width paginated ANSI table."""
        dataset = order_subset if order_subset is not None else self.orders
        if not dataset:
            print(f"{YELLOW}No orders found.{RESET}")
            input(f"\n{DIM}Press Enter to return...{RESET}")
            return

        page_size = 10
        total_pages = (len(dataset) + page_size - 1) // page_size
        current_page = 1

        while True:
            start_idx = (current_page - 1) * page_size
            end_idx = min(start_idx + page_size, len(dataset))
            page_items = dataset[start_idx:end_idx]

            print("\n" + "=" * 115)
            print(f"{BOLD}BAKERY ORDER REGISTER — PAGE {current_page} OF {total_pages} (Total: {len(dataset)}){RESET}")
            print("=" * 115)
            print(
                f" {'ID':<15} {'CUSTOMER':<18} {'ITEM':<22} {'QTY':<4} "
                f"{'TOTAL':<8} {'BAL DUE':<8} {'PICKUP':<12} {'PAYMENT':<9} {'STATUS':<9}"
            )
            print("-" * 115)

            for o in page_items:
                c_name = (o.customer_name[:16] + "..") if len(o.customer_name) > 18 else o.customer_name
                i_name = (o.item_name[:20] + "..") if len(o.item_name) > 22 else o.item_name
                
                # Status color coding
                st_color = WHITE
                if o.order_status == OrderStatus.COMPLETED.value:
                    st_color = GREEN
                elif o.order_status == OrderStatus.BAKING.value:
                    st_color = CYAN
                elif o.order_status == OrderStatus.READY.value:
                    st_color = YELLOW
                elif o.order_status == OrderStatus.CANCELLED.value:
                    st_color = RED

                # Payment color
                pay_color = GREEN if o.payment_status == PaymentStatus.PAID.value else (YELLOW if o.payment_status == PaymentStatus.PARTIAL.value else RED)

                print(
                    f" {WHITE}{o.order_id:<15}{RESET} "
                    f"{c_name:<18} "
                    f"{i_name:<22} "
                    f"{o.quantity:<4} "
                    f"${o.total_price:<7.2f} "
                    f"${o.balance_due:<7.2f} "
                    f"{o.pickup_date[:10]:<12} "
                    f"{pay_color}{o.payment_status:<9}{RESET} "
                    f"{st_color}{o.order_status:<9}{RESET}"
                )

            print("-" * 115)
            nav = input(f"{BOLD}[N]ext Page | [P]rev Page | [V]iew Order Details | [Q]uit to Menu: {RESET}").strip().upper()

            if nav == "N":
                if current_page < total_pages:
                    current_page += 1
                else:
                    print(f"{YELLOW}Already on the last page.{RESET}")
            elif nav == "P":
                if current_page > 1:
                    current_page -= 1
                else:
                    print(f"{YELLOW}Already on the first page.{RESET}")
            elif nav == "V":
                self.inspect_single_order_prompt(dataset)
            elif nav in ["Q", ""]:
                break

    def inspect_single_order_prompt(self, dataset: List[BakeryOrder]) -> None:
        """Displays full inspection of a single order by ID."""
        target_id = input(f"{CYAN}Enter Order ID to inspect: {RESET}").strip()
        match = next((o for o in dataset if o.order_id.lower() == target_id.lower()), None)
        if not match:
            print(f"{RED}Order with ID '{target_id}' not found.{RESET}")
            input(f"{DIM}Press Enter to continue...{RESET}")
            return

        print("\n" + "=" * 60)
        print(f"{BOLD}{MAGENTA}ORDER DETAILS: {match.order_id}{RESET}")
        print("=" * 60)
        print(f" Customer Name   : {match.customer_name}")
        print(f" Contact Phone   : {match.customer_phone}")
        print(f" Contact Email   : {match.customer_email or 'N/A'}")
        print(f" Category        : {match.item_category}")
        print(f" Item Name       : {match.item_name}")
        print(f" Flavor Notes    : {match.flavor_notes or 'Standard'}")
        print(f" Quantity        : {match.quantity}")
        print(f" Unit Price      : ${match.unit_price:.2f}")
        print(f" Subtotal        : ${match.subtotal:.2f}")
        print(f" Discount / Tax  : {match.discount_percent}% off | {match.tax_percent}% tax")
        print(f" Total Price     : {BOLD}${match.total_price:.2f}{RESET}")
        print(f" Advance Paid    : ${match.advance_paid:.2f}")
        print(f" Balance Due     : {RED if match.balance_due > 0 else GREEN}${match.balance_due:.2f}{RESET}")
        print(f" Payment Status  : {match.payment_status}")
        print(f" Order Status    : {match.order_status}")
        print(f" Order Created   : {match.order_date}")
        print(f" Pickup Date     : {match.pickup_date} {'(OVERDUE!)' if match.is_overdue() else ''}")
        print(f" Special Notes   : {match.special_instructions or 'None'}")
        print("=" * 60)
        input(f"\n{DIM}Press Enter to continue...{RESET}")

    def search_and_filter_orders(self) -> None:
        """Search and filtering engine supporting keywords, categories, and payment/order statuses."""
        print(f"\n{BOLD}{CYAN}=== Record Query & Search Filter ==={RESET}")
        print(" 1. Keyword Search (Customer Name, Phone, Item Name, Flavor Notes)")
        print(" 2. Filter by Bakery Category")
        print(" 3. Filter by Payment Status (Paid, Partial, Unpaid)")
        print(" 4. Filter by Order Status (Pending, Baking, Ready, Completed, Cancelled)")
        print(" 5. Filter by Pickup Date Range")

        opt = input(f"{BOLD}Select filter method [1-5]: {RESET}").strip()
        filtered = self.orders

        if opt == "1":
            kw = input("Enter search keyword: ").strip().lower()
            if kw:
                filtered = [
                    o for o in self.orders
                    if kw in o.customer_name.lower()
                    or kw in o.order_id.lower()
                    or kw in o.item_name.lower()
                    or kw in o.customer_phone.lower()
                    or kw in o.flavor_notes.lower()
                ]
        elif opt == "2":
            print(f"Categories: {', '.join([c.value for c in BakeryCategory])}")
            cat = input("Enter category to filter: ").strip().lower()
            filtered = [o for o in self.orders if o.item_category.lower() == cat]
        elif opt == "3":
            print("Payment statuses: Paid, Partial, Unpaid")
            p_stat = input("Enter payment status: ").strip().capitalize()
            filtered = [o for o in self.orders if o.payment_status == p_stat]
        elif opt == "4":
            print("Order statuses: Pending, Baking, Ready, Completed, Cancelled")
            o_stat = input("Enter order status: ").strip().capitalize()
            filtered = [o for o in self.orders if o.order_status == o_stat]
        elif opt == "5":
            start_d = input("Start Date (YYYY-MM-DD): ").strip()
            end_d = input("End Date (YYYY-MM-DD): ").strip()
            try:
                s_dt = datetime.strptime(start_d, "%Y-%m-%d")
                e_dt = datetime.strptime(end_d, "%Y-%m-%d").replace(hour=23, minute=59)
                filtered = [
                    o for o in self.orders
                    if s_dt <= datetime.strptime(o.pickup_date[:10], "%Y-%m-%d") <= e_dt
                ]
            except Exception as e:
                print(f"{RED}Invalid date input: {e}{RESET}")
                input(f"{DIM}Press Enter...{RESET}")
                return

        print(f"\n{GREEN}Found {len(filtered)} matching records.{RESET}")
        self.view_all_orders_paginated(filtered)

    def update_order_workflow(self) -> None:
        """Update payment or order status for an existing order."""
        print(f"\n{BOLD}{CYAN}=== Update Order / Record Payment ==={RESET}")
        target_id = input("Enter Order ID to modify: ").strip()
        order = next((o for o in self.orders if o.order_id.lower() == target_id.lower()), None)
        if not order:
            print(f"{RED}Order '{target_id}' not found.{RESET}")
            input(f"{DIM}Press Enter...{RESET}")
            return

        print(f"\nEditing Order: {BOLD}{order.order_id}{RESET} ({order.customer_name} - {order.item_name})")
        print(f"Current Status: {BOLD}{order.order_status}{RESET} | Payment: {BOLD}{order.payment_status}{RESET} | Balance Due: ${order.balance_due:.2f}")
        print("\nWhat would you like to update?")
        print(" 1. Record Additional Payment")
        print(" 2. Update Order Fulfillment Status (Pending/Baking/Ready/Completed/Cancelled)")
        print(" 3. Update Scheduled Pickup Date")

        sub_opt = input(f"{BOLD}Select [1-3]: {RESET}").strip()

        if sub_opt == "1":
            if order.balance_due <= 0:
                print(f"{GREEN}This order is already FULLY PAID! ($0.00 balance due).{RESET}")
            else:
                amt = prompt_validated_input(
                    f"Enter payment amount ($0.01 - ${order.balance_due:.2f})",
                    lambda s: validate_advance_paid(s, order.balance_due)
                )
                actual_paid = order.record_additional_payment(amt)
                self.storage.sync_all(self.orders)
                print(f"{GREEN}✔ Recorded payment of ${actual_paid:.2f}. New Balance Due: ${order.balance_due:.2f} ({order.payment_status}){RESET}")

        elif sub_opt == "2":
            print(f"Valid statuses: {', '.join([s.value for s in OrderStatus])}")
            new_st = prompt_validated_input("Enter new order status", validate_order_status, default=order.order_status)
            order.order_status = new_st
            self.storage.sync_all(self.orders)
            print(f"{GREEN}✔ Order status updated to {new_st}.{RESET}")

        elif sub_opt == "3":
            new_date = prompt_validated_input("Enter new pickup date (YYYY-MM-DD or YYYY-MM-DD HH:MM)", validate_pickup_date)
            order.pickup_date = new_date
            self.storage.sync_all(self.orders)
            print(f"{GREEN}✔ Pickup date updated to {new_date}.{RESET}")

        input(f"\n{DIM}Press Enter to return to main menu...{RESET}")

    def view_executive_summary(self) -> None:
        """Displays executive summary table and key trends."""
        summary = AnalyticsEngine.generate_summary(self.orders)

        print("\n" + "=" * 80)
        print(f"{BOLD}{MAGENTA}   EXECUTIVE SUMMARY & BUSINESS INTELLIGENCE REPORT{RESET}")
        print("=" * 80)
        print(f" Report Generated        : {summary['generated_at']}")
        print(f" Total Registered Orders : {BOLD}{summary['total_orders']}{RESET}")
        print(f" Active Non-Cancelled    : {summary['active_orders']}")
        print(f" Gross Revenue           : {BOLD}{GREEN}${summary['gross_revenue']:,.2f}{RESET}")
        print(f" Cash Collected (Paid)   : {CYAN}${summary['cash_collected']:,.2f}{RESET}")
        print(f" Outstanding Receivables : {YELLOW}${summary['outstanding_balance']:,.2f}{RESET}")
        print(f" Average Order Value     : ${summary['average_order_value']:,.2f}")
        print(f" Order Fulfillment Rate  : {BOLD}{summary['fulfillment_rate']}%{RESET}")
        print("-" * 80)

        print(f"{BOLD}Order Status Breakdown:{RESET}")
        for st, count in summary["status_breakdown"].items():
            pct = (count / summary["total_orders"] * 100.0) if summary["total_orders"] else 0.0
            print(f"   • {st:<12}: {count:>3} ({pct:>5.1f}%)")

        print(f"\n{BOLD}Payment Status Breakdown:{RESET}")
        for pst, count in summary["payment_breakdown"].items():
            pct = (count / summary["total_orders"] * 100.0) if summary["total_orders"] else 0.0
            print(f"   • {pst:<12}: {count:>3} ({pct:>5.1f}%)")

        print(f"\n{BOLD}Category Share & Performance:{RESET}")
        print(f"   {'Category':<18} {'Orders':<8} {'Units':<8} {'Revenue ($)':<12}")
        for cat, data in summary["category_breakdown"].items():
            print(f"   {cat:<18} {data['count']:<8} {data['units']:<8} ${data['revenue']:>10.2f}")

        print(f"\n{BOLD}Top Selling Products:{RESET}")
        for idx, item in enumerate(summary["top_items"], start=1):
            print(f"   {idx}. {item['name']} ({item['units']} units sold)")

        print("=" * 80)
        input(f"\n{DIM}Press Enter to return to main menu...{RESET}")

    def view_threshold_warnings(self) -> None:
        """Displays threshold warning flags, overdue pickups, and imminent orders."""
        summary = AnalyticsEngine.generate_summary(self.orders)

        print("\n" + "=" * 80)
        print(f"{BOLD}{RED}   THRESHOLD WARNING & OPERATIONAL ALERT CENTER{RESET}")
        print("=" * 80)

        if summary["warnings"]:
            for w in summary["warnings"]:
                print(f" {RED}{BOLD}[!] {w}{RESET}")
        else:
            print(f" {GREEN}✔ All operational indicators are within safe thresholds.{RESET}")

        print("\n" + "-" * 80)
        print(f"{BOLD}OVERDUE ORDERS LIST ({summary['overdue_count']}):{RESET}")
        if summary["overdue_orders"]:
            for o in summary["overdue_orders"]:
                print(
                    f"   • ID: {RED}{o['order_id']}{RESET} | Customer: {o['customer_name']:<18} | "
                    f"Due: {o['pickup_date']} | Status: {o['status']} | Bal: ${o['balance_due']:.2f}"
                )
        else:
            print("   None. All overdue pickups resolved.")

        print("\n" + "-" * 80)
        print(f"{BOLD}IMMINENT PICKUPS DUE WITHIN NEXT 24 HOURS ({summary['imminent_count']}):{RESET}")
        if summary["imminent_orders"]:
            for o in summary["imminent_orders"]:
                print(
                    f"   • ID: {YELLOW}{o['order_id']}{RESET} | Customer: {o['customer_name']:<18} | "
                    f"Item: {o['item_name']:<20} | Due: {o['pickup_date']} | Status: {o['status']}"
                )
        else:
            print("   None scheduled for the next 24 hours.")

        print("=" * 80)
        input(f"\n{DIM}Press Enter to return to main menu...{RESET}")

    def export_reports_workflow(self) -> None:
        """Exports summaries to Markdown, CSV, and TXT audit ledger."""
        print(f"\n{BOLD}{CYAN}=== Multi-Format Summary Export ==={RESET}")
        print("Generating structured Markdown report, plain-text audit log, and standardized CSV...")

        result_paths = self.exporter.export_all(self.orders)
        print(f"\n{GREEN}{BOLD}✔ Reports successfully generated!{RESET}")
        print(f"   1. Markdown Report    : {WHITE}{result_paths['markdown']}{RESET}")
        print(f"   2. Plain-Text Ledger  : {WHITE}{result_paths['audit_text']}{RESET}")
        print(f"   3. Standardized CSV   : {WHITE}{result_paths['csv']}{RESET}")

        input(f"\n{DIM}Press Enter to return to main menu...{RESET}")

    def bulk_csv_import_workflow(self) -> None:
        """Ingests legacy external CSV with format validation and row-by-row error logs."""
        print(f"\n{BOLD}{CYAN}=== Bulk Dataset CSV Import ==={RESET}")
        print(f"{DIM}Ingest legacy CSV files with automatic format validation and detailed row-by-row error logs.{RESET}\n")

        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        default_test = os.path.join(data_dir, "test_invalid_import.csv")

        print(f"Sample test files available in {data_dir}:")
        print(f"  • Sample flawed dataset to test error logs: {default_test}")
        print(f"  • Sample valid dataset: {os.path.join(data_dir, 'sample_orders.csv')}\n")

        file_path = input(f"Enter CSV file path to import [{default_test}]: ").strip()
        if not file_path:
            file_path = default_test

        result = BulkDatasetImporter.import_from_csv_file(file_path)

        print("\n" + "=" * 80)
        print(f"{BOLD}BULK IMPORT AUDIT LOG SUMMARY:{RESET}")
        print(f" Total Rows Processed  : {result.total_rows}")
        print(f" Successfully Validated : {GREEN}{result.success_count}{RESET}")
        print(f" Rejected / Malformed   : {RED}{result.failure_count}{RESET}")
        print("=" * 80)

        if result.errors:
            print(f"\n{RED}{BOLD}Row-by-Row Ingestion Error Logs:{RESET}")
            for err in result.errors:
                print(f"   [Row {err['row']:>2}] Column: {err['column']:<16} | Value: '{err['value']}' | Issue: {err['message']}")
            print("-" * 80)

        if result.valid_orders:
            print(f"\n{GREEN}Found {len(result.valid_orders)} valid orders ready for ingestion.{RESET}")
            conf = input("Do you wish to append these valid orders to your live register? (y/N): ").strip().lower()
            if conf == "y":
                self.orders.extend(result.valid_orders)
                self.storage.sync_all(self.orders)
                print(f"{GREEN}{BOLD}✔ Appended {len(result.valid_orders)} records to persistent storage!{RESET}")
            else:
                print(f"{YELLOW}Import cancelled. No records appended.{RESET}")

        input(f"\n{DIM}Press Enter to return to main menu...{RESET}")

    def reset_or_seed_sample_data(self) -> None:
        """Reloads the 42 sample test cases."""
        confirm = input(f"{YELLOW}Reload 42 sample records into live register? (y/N): {RESET}").strip().lower()
        if confirm == "y":
            from scripts.seed_sample_data import generate_samples
            generate_samples()
            self.orders = self.storage.load_orders()
            print(f"{GREEN}✔ Successfully reloaded 42 realistic test cases.{RESET}")
        input(f"\n{DIM}Press Enter to return...{RESET}")

    def launch_web_dashboard(self) -> None:
        """Launches the Streamlit graphical interface (app.py) in the default browser."""
        app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
        print(f"{GREEN}Starting the Streamlit interface... (press Ctrl+C here to stop it){RESET}")
        try:
            subprocess.run([sys.executable, "-m", "streamlit", "run", app_path])
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"{RED}Could not start Streamlit: {e}{RESET}")
        print(f"{YELLOW}If it did not start, install it with:  pip install streamlit{RESET}")
        input(f"\n{DIM}Press Enter to continue...{RESET}")


if __name__ == "__main__":
    cli = BakeryCLI()
    cli.run()
