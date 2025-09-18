import streamlit as st
import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
import json
import uuid
from pathlib import Path
import shutil
from rapidfuzz import fuzz, process
import os

# Configuration
DATA_DIR = Path("data")
BACKUPS_DIR = DATA_DIR / "backups"
EXPORTS_DIR = DATA_DIR / "exports" / "invoices"

# Ensure directories exist
for dir_path in [DATA_DIR, BACKUPS_DIR, EXPORTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

class DataManager:
    def __init__(self):
        self.settings_file = DATA_DIR / "settings.json"
        self.inventory_file = DATA_DIR / "inventory"
        self.invoices_file = DATA_DIR / "invoices"
        self.load_settings()

    def load_settings(self):
        """Load application settings"""
        default_settings = {
            "storage_mode": "parquet",  # parquet or json
            "default_tax_rate": 0.0,
            "default_discount_rate": 0.0,
            "invoice_number_prefix": "INV",
            "invoice_counter": 1,
            "currency": "USD",
            "currency_symbol": "$",
            "rounding_mode": "ROUND_HALF_UP",
            "business_info": {
                "name": "Your Business Name",
                "address": "123 Business St\nCity, State 12345",
                "phone": "(555) 123-4567",
                "email": "contact@business.com"
            }
        }

        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    default_settings.update(loaded_settings)
            except:
                pass

        self.settings = default_settings
        self.save_settings()

    def save_settings(self):
        """Save application settings"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            st.error(f"Failed to save settings: {e}")

    def _get_file_path(self, base_name):
        """Get file path based on storage mode"""
        if self.settings["storage_mode"] == "parquet":
            return f"{base_name}.parquet"
        else:
            return f"{base_name}.json"

    def _backup_file(self, file_path):
        """Create backup of file"""
        if Path(file_path).exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BACKUPS_DIR / f"{Path(file_path).stem}_{timestamp}{Path(file_path).suffix}"
            shutil.copy2(file_path, backup_path)

    def load_inventory(self):
        """Load inventory data"""
        file_path = self._get_file_path(str(self.inventory_file))

        try:
            if self.settings["storage_mode"] == "parquet" and Path(file_path).exists():
                df = pd.read_parquet(file_path)
            elif Path(file_path).exists():
                df = pd.read_json(file_path, orient='records')
            else:
                # Create empty inventory with proper schema
                df = pd.DataFrame(columns=[
                    'item_id', 'sku', 'name', 'company', 'size_mm', 'size_inch',
                    'base_price', 'tax_rate', 'discount_rate', 'search_blob',
                    'created_at', 'updated_at'
                ])

            return df
        except Exception as e:
            st.error(f"Failed to load inventory: {e}")
            return pd.DataFrame(columns=[
                'item_id', 'sku', 'name', 'company', 'size_mm', 'size_inch',
                'base_price', 'tax_rate', 'discount_rate', 'search_blob',
                'created_at', 'updated_at'
            ])

    def save_inventory(self, df):
        """Save inventory data"""
        file_path = self._get_file_path(str(self.inventory_file))
        self._backup_file(file_path)

        try:
            # Update search blob for all items
            df['search_blob'] = df.apply(self._create_search_blob, axis=1)
            df['updated_at'] = datetime.now().isoformat()

            if self.settings["storage_mode"] == "parquet":
                df.to_parquet(file_path, index=False)
            else:
                df.to_json(file_path, orient='records', indent=2)

            return True
        except Exception as e:
            st.error(f"Failed to save inventory: {e}")
            return False

    def load_invoices(self):
        """Load invoices data"""
        file_path = self._get_file_path(str(self.invoices_file))

        try:
            if self.settings["storage_mode"] == "parquet" and Path(file_path).exists():
                df = pd.read_parquet(file_path)
            elif Path(file_path).exists():
                df = pd.read_json(file_path, orient='records')
            else:
                df = pd.DataFrame(columns=[
                    'invoice_id', 'invoice_number', 'date', 'customer_name',
                    'customer_address', 'customer_email', 'notes',
                    'global_discount_rate', 'global_tax_rate', 'line_items',
                    'subtotal', 'total_discount', 'total_tax', 'grand_total',
                    'created_at', 'updated_at'
                ])

            return df
        except Exception as e:
            st.error(f"Failed to load invoices: {e}")
            return pd.DataFrame()

    def save_invoices(self, df):
        """Save invoices data"""
        file_path = self._get_file_path(str(self.invoices_file))
        self._backup_file(file_path)

        try:
            if self.settings["storage_mode"] == "parquet":
                df.to_parquet(file_path, index=False)
            else:
                df.to_json(file_path, orient='records', indent=2)

            return True
        except Exception as e:
            st.error(f"Failed to save invoices: {e}")
            return False

    def _create_search_blob(self, row):
        """Create searchable text blob for inventory item"""
        fields = [
            str(row.get('sku', '')),
            str(row.get('name', '')),
            str(row.get('company', '')),
            str(row.get('size_mm', '')),
            str(row.get('size_inch', '')),
            str(row.get('base_price', '')),
            str(row.get('tax_rate', '')),
            str(row.get('discount_rate', ''))
        ]
        return ' '.join(fields).lower()

    def search_inventory(self, query, limit=10):
        """Fuzzy search inventory items"""
        df = self.load_inventory()
        if df.empty or not query.strip():
            return df.head(limit)

        query = query.lower().strip()

        # Score each item
        scores = []
        for idx, row in df.iterrows():
            # Primary scoring on search blob
            blob_score = fuzz.partial_ratio(query, row['search_blob'])

            # Boost for exact matches in key fields
            sku_boost = 20 if query in str(row['sku']).lower() else 0
            name_boost = 15 if query in str(row['name']).lower() else 0
            company_boost = 10 if query in str(row['company']).lower() else 0

            # Numeric matching
            numeric_boost = 0
            if query.replace('.', '').isdigit():
                price_match = 15 if query in str(row['base_price']) else 0
                size_match = 10 if query in str(row['size_mm']) or query in str(row['size_inch']) else 0
                numeric_boost = max(price_match, size_match)

            total_score = blob_score + sku_boost + name_boost + company_boost + numeric_boost
            scores.append((idx, total_score))

        # Sort by score and return top results
        scores.sort(key=lambda x: x[1], reverse=True)
        top_indices = [idx for idx, score in scores[:limit] if score > 30]

        return df.loc[top_indices] if top_indices else df.head(limit)

# Initialize data manager
if 'data_manager' not in st.session_state:
    st.session_state.data_manager = DataManager()

data_manager = st.session_state.data_manager

def main():
    st.set_page_config(
        page_title="Simple Billing Tool",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("📊 Simple Billing Tool")
    st.markdown("Complete inventory management and billing solution")

    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📦 Inventory", "🧾 Billing", "⚙️ Settings"])

    with tab1:
        inventory_tab()

    with tab2:
        billing_tab()

    with tab3:
        settings_tab()

def inventory_tab():
    """Inventory management tab"""
    st.header("Inventory Management")

    # Load inventory
    df = data_manager.load_inventory()

    # Add/Edit item form
    with st.expander("Add/Edit Inventory Item", expanded=False):
        with st.form("inventory_form"):
            col1, col2 = st.columns(2)

            with col1:
                item_id = st.text_input("Item ID (leave empty for new)", key="item_id")
                sku = st.text_input("SKU*", key="sku")
                name = st.text_input("Item Name*", key="name")
                company = st.text_input("Company/Brand", key="company")

            with col2:
                size_mm = st.number_input("Size (mm)", min_value=0.0, key="size_mm")
                size_inch = st.number_input("Size (inches)", min_value=0.0, key="size_inch")
                base_price = st.number_input("Base Price", min_value=0.0, step=0.01, key="base_price")
                col_tax, col_disc = st.columns(2)
                with col_tax:
                    tax_rate = st.number_input("Tax Rate (%)", min_value=0.0, max_value=100.0,
                                             value=data_manager.settings["default_tax_rate"], key="tax_rate")
                with col_disc:
                    discount_rate = st.number_input("Discount Rate (%)", min_value=0.0, max_value=100.0,
                                                  value=data_manager.settings["default_discount_rate"], key="discount_rate")

            submitted = st.form_submit_button("Save Item")

            if submitted:
                if not sku or not name:
                    st.error("SKU and Name are required fields")
                else:
                    save_inventory_item(df, item_id, sku, name, company, size_mm, size_inch,
                                      base_price, tax_rate, discount_rate)

    # Search and display inventory
    st.subheader("Inventory Items")

    search_query = st.text_input("🔍 Search inventory (SKU, name, company, size, price...)",
                                placeholder="Type to search...")

    if search_query:
        filtered_df = data_manager.search_inventory(search_query, limit=50)
    else:
        filtered_df = df

    if not filtered_df.empty:
        # Display inventory table
        display_cols = ['sku', 'name', 'company', 'size_mm', 'size_inch', 'base_price', 'tax_rate', 'discount_rate']
        st.dataframe(filtered_df[display_cols], use_container_width=True)

        # Item actions
        if not filtered_df.empty:
            col1, col2 = st.columns(2)

            with col1:
                selected_item = st.selectbox("Select item to edit:",
                                           options=filtered_df['item_id'].tolist(),
                                           format_func=lambda x: f"{filtered_df[filtered_df['item_id']==x]['sku'].iloc[0]} - {filtered_df[filtered_df['item_id']==x]['name'].iloc[0]}")

                if st.button("Load for Editing"):
                    load_item_for_editing(filtered_df, selected_item)

            with col2:
                if st.button("Delete Selected Item", type="secondary"):
                    delete_inventory_item(df, selected_item)
    else:
        st.info("No inventory items found. Add your first item above!")

def save_inventory_item(df, item_id, sku, name, company, size_mm, size_inch, base_price, tax_rate, discount_rate):
    """Save or update inventory item"""
    current_time = datetime.now().isoformat()

    new_item = {
        'item_id': item_id if item_id else str(uuid.uuid4()),
        'sku': sku,
        'name': name,
        'company': company,
        'size_mm': size_mm,
        'size_inch': size_inch,
        'base_price': base_price,
        'tax_rate': tax_rate,
        'discount_rate': discount_rate,
        'search_blob': '',  # Will be updated in save_inventory
        'updated_at': current_time
    }

    if item_id and item_id in df['item_id'].values:
        # Update existing item
        df.loc[df['item_id'] == item_id, list(new_item.keys())] = list(new_item.values())
        action = "updated"
    else:
        # Add new item
        new_item['created_at'] = current_time
        df = pd.concat([df, pd.DataFrame([new_item])], ignore_index=True)
        action = "added"

    if data_manager.save_inventory(df):
        st.success(f"Item {action} successfully!")
        st.rerun()
    else:
        st.error(f"Failed to {action} item")

def load_item_for_editing(df, item_id):
    """Load item data into form for editing"""
    item = df[df['item_id'] == item_id].iloc[0]

    # Update session state with item data
    st.session_state.item_id = item['item_id']
    st.session_state.sku = item['sku']
    st.session_state.name = item['name']
    st.session_state.company = item['company']
    st.session_state.size_mm = float(item['size_mm'])
    st.session_state.size_inch = float(item['size_inch'])
    st.session_state.base_price = float(item['base_price'])
    st.session_state.tax_rate = float(item['tax_rate'])
    st.session_state.discount_rate = float(item['discount_rate'])

    st.success("Item loaded for editing. Check the form above.")
    st.rerun()

def delete_inventory_item(df, item_id):
    """Delete inventory item"""
    if item_id in df['item_id'].values:
        df = df[df['item_id'] != item_id]
        if data_manager.save_inventory(df):
            st.success("Item deleted successfully!")
            st.rerun()
        else:
            st.error("Failed to delete item")

def billing_tab():
    """Billing and invoice creation tab"""
    st.header("Create Invoice")

    # Initialize invoice session state
    if 'invoice_cart' not in st.session_state:
        st.session_state.invoice_cart = []

    # Customer information
    with st.expander("Customer Information", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            customer_name = st.text_input("Customer Name*")
            customer_email = st.text_input("Customer Email")
        with col2:
            customer_address = st.text_area("Customer Address")
            notes = st.text_area("Invoice Notes")

    # Item search and add
    st.subheader("Add Items")

    search_query = st.text_input("🔍 Search and add items",
                                placeholder="Start typing to search inventory...")

    if search_query:
        results = data_manager.search_inventory(search_query, limit=10)

        if not results.empty:
            st.write("Search Results:")
            for idx, item in results.iterrows():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

                with col1:
                    st.write(f"**{item['name']}** ({item['sku']})")
                    st.caption(f"{item['company']} | {data_manager.settings['currency_symbol']}{item['base_price']:.2f}")

                with col2:
                    quantity = st.number_input(f"Qty", min_value=1, value=1, key=f"qty_{item['item_id']}")

                with col3:
                    line_discount = st.number_input(f"Disc %", min_value=0.0, max_value=100.0,
                                                  value=float(item['discount_rate']), key=f"disc_{item['item_id']}")

                with col4:
                    if st.button("Add", key=f"add_{item['item_id']}"):
                        add_to_cart(item, quantity, line_discount)

    # Display cart
    if st.session_state.invoice_cart:
        st.subheader("Invoice Items")

        cart_data = []
        for i, cart_item in enumerate(st.session_state.invoice_cart):
            cart_data.append({
                "Item": f"{cart_item['name']} ({cart_item['sku']})",
                "Qty": cart_item['quantity'],
                "Price": f"{data_manager.settings['currency_symbol']}{cart_item['unit_price']:.2f}",
                "Discount %": f"{cart_item['discount_rate']:.1f}%",
                "Line Total": f"{data_manager.settings['currency_symbol']}{cart_item['line_total']:.2f}"
            })

        st.dataframe(pd.DataFrame(cart_data), use_container_width=True)

        # Cart actions
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Clear Cart"):
                st.session_state.invoice_cart = []
                st.rerun()

        with col2:
            remove_idx = st.number_input("Remove item #", min_value=1, max_value=len(st.session_state.invoice_cart))
            if st.button("Remove Item"):
                st.session_state.invoice_cart.pop(remove_idx - 1)
                st.rerun()

        # Invoice totals and global adjustments
        st.subheader("Invoice Totals")

        col1, col2 = st.columns(2)

        with col1:
            global_discount = st.number_input("Global Discount (%)", min_value=0.0, max_value=100.0, value=0.0)
            global_tax = st.number_input("Global Tax (%)", min_value=0.0, max_value=100.0,
                                       value=data_manager.settings["default_tax_rate"])

        with col2:
            totals = calculate_invoice_totals(global_discount, global_tax)

            st.write(f"**Subtotal:** {data_manager.settings['currency_symbol']}{totals['subtotal']:.2f}")
            st.write(f"**Discount:** -{data_manager.settings['currency_symbol']}{totals['total_discount']:.2f}")
            st.write(f"**Tax:** +{data_manager.settings['currency_symbol']}{totals['total_tax']:.2f}")
            st.write(f"**Grand Total:** {data_manager.settings['currency_symbol']}{totals['grand_total']:.2f}")

        # Save and export
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Save Invoice", type="primary"):
                if customer_name:
                    save_invoice(customer_name, customer_address, customer_email, notes,
                               global_discount, global_tax, totals)
                else:
                    st.error("Customer name is required")

        with col2:
            if st.button("Export PDF"):
                if customer_name:
                    export_invoice_pdf(customer_name, customer_address, customer_email, notes,
                                     global_discount, global_tax, totals)
                else:
                    st.error("Customer name is required")

def add_to_cart(item, quantity, discount_rate):
    """Add item to invoice cart"""
    # Calculate line total
    unit_price = Decimal(str(item['base_price']))
    qty = Decimal(str(quantity))
    discount = Decimal(str(discount_rate)) / 100

    line_subtotal = unit_price * qty
    line_discount = line_subtotal * discount
    line_total = line_subtotal - line_discount

    cart_item = {
        'item_id': item['item_id'],
        'sku': item['sku'],
        'name': item['name'],
        'company': item['company'],
        'quantity': float(qty),
        'unit_price': float(unit_price),
        'discount_rate': float(discount_rate),
        'tax_rate': float(item['tax_rate']),
        'line_total': float(line_total)
    }

    st.session_state.invoice_cart.append(cart_item)
    st.success(f"Added {item['name']} to cart")
    st.rerun()

def calculate_invoice_totals(global_discount_rate, global_tax_rate):
    """Calculate invoice totals with proper decimal arithmetic"""
    subtotal = Decimal('0')

    for item in st.session_state.invoice_cart:
        subtotal += Decimal(str(item['line_total']))

    global_discount_amount = subtotal * (Decimal(str(global_discount_rate)) / 100)
    after_discount = subtotal - global_discount_amount

    global_tax_amount = after_discount * (Decimal(str(global_tax_rate)) / 100)
    grand_total = after_discount + global_tax_amount

    return {
        'subtotal': float(subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'total_discount': float(global_discount_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'total_tax': float(global_tax_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'grand_total': float(grand_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    }

def save_invoice(customer_name, customer_address, customer_email, notes,
                global_discount, global_tax, totals):
    """Save invoice to storage"""
    invoice_number = f"{data_manager.settings['invoice_number_prefix']}-{data_manager.settings['invoice_counter']:04d}"

    invoice_data = {
        'invoice_id': str(uuid.uuid4()),
        'invoice_number': invoice_number,
        'date': date.today().isoformat(),
        'customer_name': customer_name,
        'customer_address': customer_address,
        'customer_email': customer_email,
        'notes': notes,
        'global_discount_rate': global_discount,
        'global_tax_rate': global_tax,
        'line_items': json.dumps(st.session_state.invoice_cart),
        'subtotal': totals['subtotal'],
        'total_discount': totals['total_discount'],
        'total_tax': totals['total_tax'],
        'grand_total': totals['grand_total'],
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }

    # Load existing invoices and add new one
    df = data_manager.load_invoices()
    df = pd.concat([df, pd.DataFrame([invoice_data])], ignore_index=True)

    if data_manager.save_invoices(df):
        # Increment invoice counter
        data_manager.settings['invoice_counter'] += 1
        data_manager.save_settings()

        st.success(f"Invoice {invoice_number} saved successfully!")
        st.session_state.invoice_cart = []  # Clear cart
        st.rerun()
    else:
        st.error("Failed to save invoice")

def export_invoice_pdf(customer_name, customer_address, customer_email, notes,
                      global_discount, global_tax, totals):
    """Export invoice as PDF"""
    st.info("PDF export functionality will be implemented with weasyprint")
    # TODO: Implement PDF generation with weasyprint

def settings_tab():
    """Settings management tab"""
    st.header("Application Settings")

    # Storage settings
    with st.expander("Storage Settings", expanded=True):
        storage_mode = st.selectbox("Storage Mode",
                                   options=["parquet", "json"],
                                   index=0 if data_manager.settings["storage_mode"] == "parquet" else 1)

        if st.button("Update Storage Mode"):
            data_manager.settings["storage_mode"] = storage_mode
            data_manager.save_settings()
            st.success("Storage mode updated!")

    # Business information
    with st.expander("Business Information", expanded=True):
        business_name = st.text_input("Business Name", value=data_manager.settings["business_info"]["name"])
        business_address = st.text_area("Business Address", value=data_manager.settings["business_info"]["address"])
        business_phone = st.text_input("Phone", value=data_manager.settings["business_info"]["phone"])
        business_email = st.text_input("Email", value=data_manager.settings["business_info"]["email"])

        if st.button("Update Business Info"):
            data_manager.settings["business_info"] = {
                "name": business_name,
                "address": business_address,
                "phone": business_phone,
                "email": business_email
            }
            data_manager.save_settings()
            st.success("Business information updated!")

    # Default rates and currency
    with st.expander("Default Rates & Currency", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            default_tax = st.number_input("Default Tax Rate (%)", min_value=0.0, max_value=100.0,
                                        value=data_manager.settings["default_tax_rate"])
            default_discount = st.number_input("Default Discount Rate (%)", min_value=0.0, max_value=100.0,
                                             value=data_manager.settings["default_discount_rate"])

        with col2:
            currency = st.text_input("Currency Code", value=data_manager.settings["currency"])
            currency_symbol = st.text_input("Currency Symbol", value=data_manager.settings["currency_symbol"])

        if st.button("Update Defaults"):
            data_manager.settings.update({
                "default_tax_rate": default_tax,
                "default_discount_rate": default_discount,
                "currency": currency,
                "currency_symbol": currency_symbol
            })
            data_manager.save_settings()
            st.success("Default rates and currency updated!")

    # Invoice numbering
    with st.expander("Invoice Numbering", expanded=True):
        invoice_prefix = st.text_input("Invoice Number Prefix", value=data_manager.settings["invoice_number_prefix"])
        invoice_counter = st.number_input("Next Invoice Number", min_value=1,
                                        value=data_manager.settings["invoice_counter"])

        if st.button("Update Invoice Numbering"):
            data_manager.settings.update({
                "invoice_number_prefix": invoice_prefix,
                "invoice_counter": invoice_counter
            })
            data_manager.save_settings()
            st.success("Invoice numbering updated!")

if __name__ == "__main__":
    main()