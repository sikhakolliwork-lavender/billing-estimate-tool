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
import io

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
            "currency": "INR",
            "currency_symbol": "₹",
            "rounding_mode": "ROUND_HALF_UP",
            "business_info": {
                "name": "LOSRA ENTERPRISES",
                "address": "#74-2-20, Yanamalakuduru Lakula Rd, Vijayawada, Andhra Pradesh 520007",
                "phone": "8977127227, 9848417615",
                "email": "losraenterprises437@gmail.com"
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
                    'display_text', 'created_at', 'updated_at'
                ])

            # Ensure display_text column exists (for backward compatibility)
            if 'display_text' not in df.columns:
                df['display_text'] = df.apply(self._create_display_text, axis=1)

            return df
        except Exception as e:
            st.error(f"Failed to load inventory: {e}")
            return pd.DataFrame(columns=[
                'item_id', 'sku', 'name', 'company', 'size_mm', 'size_inch',
                'base_price', 'tax_rate', 'discount_rate', 'search_blob',
                'display_text', 'created_at', 'updated_at'
            ])

    def save_inventory(self, df):
        """Save inventory data"""
        file_path = self._get_file_path(str(self.inventory_file))
        self._backup_file(file_path)

        try:
            # Update search blob and display text for all items
            df['search_blob'] = df.apply(self._create_search_blob, axis=1)
            df['display_text'] = df.apply(self._create_display_text, axis=1)
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

    def _create_display_text(self, row):
        """Create formatted display text for dropdown suggestions"""
        parts = []

        # SKU and Name (primary info)
        if row.get('sku'):
            parts.append(f"{row['sku']}")
        if row.get('name'):
            parts.append(f"{row['name']}")

        # Company
        if row.get('company'):
            parts.append(f"{row['company']}")

        # Price with currency (remove .00 if whole number)
        if row.get('base_price') is not None:
            price = float(row['base_price'])
            if price == int(price):
                parts.append(f"₹{int(price)}")
            else:
                parts.append(f"₹{price:.2f}")

        # Sizes (remove .0 if whole number)
        size_parts = []
        if row.get('size_mm') is not None and row['size_mm'] != '':
            size_mm = float(row['size_mm'])
            if size_mm == int(size_mm):
                size_parts.append(f"{int(size_mm)}mm")
            else:
                size_parts.append(f"{size_mm}mm")
        if row.get('size_inch') is not None and row['size_inch'] != '':
            size_inch = float(row['size_inch'])
            if size_inch == int(size_inch):
                size_parts.append(f"{int(size_inch)}\"")
            else:
                size_parts.append(f"{size_inch}\"")
        if size_parts:
            parts.append(" / ".join(size_parts))

        # Tax and discount rates (remove .0 if whole number)
        rates = []
        if row.get('tax_rate') is not None and float(row['tax_rate']) > 0:
            tax_rate = float(row['tax_rate'])
            if tax_rate == int(tax_rate):
                rates.append(f"Tax: {int(tax_rate)}%")
            else:
                rates.append(f"Tax: {tax_rate:.1f}%")
        if row.get('discount_rate') is not None and float(row['discount_rate']) > 0:
            disc_rate = float(row['discount_rate'])
            if disc_rate == int(disc_rate):
                rates.append(f"Disc: {int(disc_rate)}%")
            else:
                rates.append(f"Disc: {disc_rate:.1f}%")
        if rates:
            parts.append(" | ".join(rates))

        return " | ".join(parts)

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

    def import_from_csv(self, csv_file, mode="replace"):
        """Import inventory from CSV file

        Args:
            csv_file: Uploaded file object or file path
            mode: 'replace' to replace all items, 'append' to add to existing

        Returns:
            dict: {'success': bool, 'message': str, 'imported_count': int, 'errors': list}
        """
        try:
            # Read CSV file
            if hasattr(csv_file, 'read'):
                # It's an uploaded file object
                csv_content = csv_file.read()
                if isinstance(csv_content, bytes):
                    csv_content = csv_content.decode('utf-8')
                csv_df = pd.read_csv(io.StringIO(csv_content))
            else:
                # It's a file path
                csv_df = pd.read_csv(csv_file)

            if csv_df.empty:
                return {'success': False, 'message': 'CSV file is empty', 'imported_count': 0, 'errors': []}

            # Required columns
            required_cols = ['sku', 'name']
            missing_cols = [col for col in required_cols if col not in csv_df.columns]
            if missing_cols:
                return {
                    'success': False,
                    'message': f'Missing required columns: {", ".join(missing_cols)}',
                    'imported_count': 0,
                    'errors': []
                }

            # Define column mapping and defaults
            column_mapping = {
                'sku': 'sku',
                'name': 'name',
                'company': 'company',
                'size_mm': 'size_mm',
                'size_inch': 'size_inch',
                'base_price': 'base_price',
                'tax_rate': 'tax_rate',
                'discount_rate': 'discount_rate'
            }

            # Load existing inventory
            existing_df = self.load_inventory() if mode == "append" else pd.DataFrame()

            # Process CSV data
            current_time = datetime.now().isoformat()
            new_items = []
            errors = []

            for idx, row in csv_df.iterrows():
                try:
                    # Validate required fields
                    if pd.isna(row.get('sku')) or pd.isna(row.get('name')):
                        errors.append(f"Row {idx + 2}: SKU and Name are required")
                        continue

                    # Create new item
                    new_item = {
                        'item_id': str(uuid.uuid4()),
                        'sku': str(row.get('sku', '')).strip(),
                        'name': str(row.get('name', '')).strip(),
                        'company': str(row.get('company', '')).strip() if not pd.isna(row.get('company')) else '',
                        'size_mm': float(row.get('size_mm', 0)) if not pd.isna(row.get('size_mm')) else 0.0,
                        'size_inch': float(row.get('size_inch', 0)) if not pd.isna(row.get('size_inch')) else 0.0,
                        'base_price': float(row.get('base_price', 0)) if not pd.isna(row.get('base_price')) else 0.0,
                        'tax_rate': float(row.get('tax_rate', self.settings["default_tax_rate"])) if not pd.isna(row.get('tax_rate')) else self.settings["default_tax_rate"],
                        'discount_rate': float(row.get('discount_rate', self.settings["default_discount_rate"])) if not pd.isna(row.get('discount_rate')) else self.settings["default_discount_rate"],
                        'search_blob': '',  # Will be updated in save
                        'display_text': '',  # Will be updated in save
                        'created_at': current_time,
                        'updated_at': current_time
                    }

                    new_items.append(new_item)

                except Exception as e:
                    errors.append(f"Row {idx + 2}: {str(e)}")

            if not new_items:
                return {
                    'success': False,
                    'message': 'No valid items found in CSV',
                    'imported_count': 0,
                    'errors': errors
                }

            # Create DataFrame and combine with existing
            new_df = pd.DataFrame(new_items)

            if mode == "append" and not existing_df.empty:
                # Check for duplicate SKUs
                duplicate_skus = set(new_df['sku']) & set(existing_df['sku'])
                if duplicate_skus:
                    errors.append(f"Duplicate SKUs found (will be skipped): {', '.join(duplicate_skus)}")
                    new_df = new_df[~new_df['sku'].isin(duplicate_skus)]

                final_df = pd.concat([existing_df, new_df], ignore_index=True)
            else:
                final_df = new_df

            # Save the inventory
            success = self.save_inventory(final_df)

            if success:
                return {
                    'success': True,
                    'message': f'Successfully imported {len(new_items)} items',
                    'imported_count': len(new_items),
                    'errors': errors
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to save imported data',
                    'imported_count': 0,
                    'errors': errors
                }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error processing CSV: {str(e)}',
                'imported_count': 0,
                'errors': [str(e)]
            }

# Initialize data manager
if 'data_manager' not in st.session_state:
    st.session_state.data_manager = DataManager()

data_manager = st.session_state.data_manager

# Removed complex workflow functions - using simple single-form approach instead

def main():
    st.set_page_config(
        page_title="Simple Billing Tool",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("📊 Simple Billing Tool")
    st.markdown("Complete inventory management and billing solution")

    # Create tabs
    tab1, tab2, tab2_tally, tab3 = st.tabs(["📦 Inventory", "🧾 Billing", "⚡ Tally Style", "⚙️ Settings"])

    with tab1:
        inventory_tab()

    with tab2:
        billing_tab()

    with tab2_tally:
        tally_billing_tab()

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

    # CSV Import section
    with st.expander("📁 Import from CSV", expanded=False):
        st.markdown("### CSV Import")
        st.markdown("Upload a CSV file to bulk import inventory items. The CSV should have the following format:")

        # Show sample CSV format
        sample_data = {
            'sku': ['ITEM001', 'ITEM002', 'ITEM003'],
            'name': ['Sample Item 1', 'Sample Item 2', 'Sample Item 3'],
            'company': ['Company A', 'Company B', 'Company C'],
            'size_mm': [25.4, 50.8, 76.2],
            'size_inch': [1.0, 2.0, 3.0],
            'base_price': [100.50, 200.00, 300.75],
            'tax_rate': [18.0, 18.0, 5.0],
            'discount_rate': [5.0, 10.0, 0.0]
        }
        sample_df = pd.DataFrame(sample_data)

        st.markdown("**Sample CSV Format:**")
        st.dataframe(sample_df, use_container_width=True)

        st.markdown("""
        **Column Descriptions:**
        - `sku` *(required)*: Stock Keeping Unit - unique identifier
        - `name` *(required)*: Item name
        - `company` *(optional)*: Company or brand name
        - `size_mm` *(optional)*: Size in millimeters
        - `size_inch` *(optional)*: Size in inches
        - `base_price` *(optional)*: Base price (default: 0)
        - `tax_rate` *(optional)*: Tax rate percentage (default: from settings)
        - `discount_rate` *(optional)*: Discount rate percentage (default: from settings)

        **Notes:**
        - Only SKU and Name are required columns
        - Empty cells will use default values
        - Duplicate SKUs will be skipped in append mode
        """)

        # File upload and import options
        col1, col2 = st.columns([2, 1])

        with col1:
            uploaded_file = st.file_uploader(
                "Choose CSV file",
                type=['csv'],
                help="Upload a CSV file with inventory data"
            )

        with col2:
            import_mode = st.radio(
                "Import Mode:",
                ["append", "replace"],
                help="Append: Add to existing inventory\nReplace: Replace all existing items"
            )

        if uploaded_file is not None:
            if st.button("🚀 Import CSV", type="primary"):
                with st.spinner("Importing items..."):
                    result = data_manager.import_from_csv(uploaded_file, mode=import_mode)

                if result['success']:
                    st.success(f"✅ {result['message']}")
                    if result['imported_count'] > 0:
                        st.balloons()
                        # Refresh the page to show new items
                        st.rerun()
                else:
                    st.error(f"❌ {result['message']}")

                # Show any errors or warnings
                if result['errors']:
                    with st.expander("⚠️ Import Warnings/Errors", expanded=True):
                        for error in result['errors']:
                            st.warning(error)

        # Download sample CSV
        st.markdown("---")
        st.markdown("**Download Sample CSV Template:**")
        csv_content = sample_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Sample CSV",
            data=csv_content,
            file_name="inventory_template.csv",
            mime="text/csv",
            help="Download a template CSV file with sample data"
        )

    # Search and display inventory
    st.subheader("Inventory Items")

    # Add search/filter options
    col1, col2 = st.columns([3, 1])

    with col1:
        search_query = st.text_input("🔍 Search inventory (SKU, name, company, size, price...)",
                                    placeholder="Type to search...")

    with col2:
        show_all = st.checkbox("Show All", value=True, help="Uncheck to filter by search")

    if search_query and not show_all:
        filtered_df = data_manager.search_inventory(search_query, limit=50)
    else:
        filtered_df = df

    if not filtered_df.empty:
        # Display inventory table with enhanced columns
        if 'display_text' in filtered_df.columns:
            display_cols = ['sku', 'name', 'company', 'size_mm', 'size_inch', 'base_price', 'tax_rate', 'discount_rate', 'display_text']
        else:
            display_cols = ['sku', 'name', 'company', 'size_mm', 'size_inch', 'base_price', 'tax_rate', 'discount_rate']

        st.dataframe(filtered_df[display_cols], use_container_width=True)

        # Item actions
        if not filtered_df.empty:
            col1, col2 = st.columns(2)

            with col1:
                if 'display_text' in filtered_df.columns:
                    # Use display_text for better item selection
                    item_options = filtered_df[['item_id', 'display_text']].set_index('item_id')['display_text'].to_dict()
                    selected_item = st.selectbox("Select item to edit:",
                                               options=list(item_options.keys()),
                                               format_func=lambda x: item_options[x])
                else:
                    # Fallback to old format
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
        'display_text': '',  # Will be updated in save_inventory
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

# Removed complex workflow state - using simple form-based approach instead

    # Customer information
    with st.expander("Customer Information", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            customer_name = st.text_input("Customer Name*")
            customer_email = st.text_input("Customer Email")
        with col2:
            customer_address = st.text_area("Customer Address")
            notes = st.text_area("Invoice Notes")

    # Simple Single-Line Item Entry
    st.subheader("🛒 Add Items to Invoice")

    # Load inventory for search
    inventory_df = data_manager.load_inventory()

    if not inventory_df.empty:
        # Create search options with display text
        search_options = ["Select an item..."] + inventory_df['display_text'].tolist()

        # Simple instruction
        st.markdown("**Select an item, enter quantity and discount, then press Add to Invoice**")

        # Item selection outside form for better interactivity
        selected_display_text = st.selectbox(
            "🔍 Select Item",
            options=search_options,
            help="Type to search through all inventory items"
        )

        # Show form only if item is selected
        if selected_display_text != "Select an item...":
            selected_item = inventory_df[inventory_df['display_text'] == selected_display_text].iloc[0]

            # Show item details
            if selected_item.get('company'):
                st.info(f"**{selected_item['name']}** ({selected_item['sku']}) - {selected_item['company']} - ₹{selected_item['base_price']}")
            else:
                st.info(f"**{selected_item['name']}** ({selected_item['sku']}) - ₹{selected_item['base_price']}")

            # Form for quantity, discount and add button
            with st.form("add_item_form", clear_on_submit=True):
                col1, col2, col3 = st.columns([1, 1, 1])

                with col1:
                    quantity = st.number_input(
                        "Quantity",
                        min_value=1,
                        value=1,
                        help="Enter quantity"
                    )

                with col2:
                    default_discount = float(selected_item.get('discount_rate', 0))
                    discount = st.number_input(
                        "Discount %",
                        min_value=0.0,
                        max_value=100.0,
                        value=default_discount,
                        help="Enter discount percentage"
                    )

                with col3:
                    submitted = st.form_submit_button("✅ Add to Invoice", use_container_width=True, type="primary")

                # Calculate and show subtotal below the form
                subtotal = float(selected_item['base_price']) * quantity
                if discount > 0:
                    discount_amount = subtotal * (discount / 100)
                    final_amount = subtotal - discount_amount
                    st.caption(f"Subtotal: ₹{subtotal:.2f} - Discount: ₹{discount_amount:.2f} = **₹{final_amount:.2f}**")
                else:
                    st.caption(f"Total: **₹{subtotal:.2f}**")

                # Add to cart if submitted
                if submitted:
                    add_to_cart(selected_item, quantity, discount)
                    st.success(f"✅ Added {quantity}x {selected_item['name']} to invoice!")
                    st.rerun()

        else:
            st.info("👆 Please select an item first to enter quantity and discount.")

        # Quick action buttons for common scenarios
        if selected_display_text != "Select an item...":
            st.markdown("**Quick Add:**")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                if st.button("Add 1 (No Discount)", use_container_width=True):
                    add_to_cart(selected_item, 1, 0)
                    st.success(f"✅ Added 1x {selected_item['name']} to invoice!")
                    st.rerun()

            with col2:
                if st.button("Add 2 (No Discount)", use_container_width=True):
                    add_to_cart(selected_item, 2, 0)
                    st.success(f"✅ Added 2x {selected_item['name']} to invoice!")
                    st.rerun()

            with col3:
                if st.button("Add 5 (No Discount)", use_container_width=True):
                    add_to_cart(selected_item, 5, 0)
                    st.success(f"✅ Added 5x {selected_item['name']} to invoice!")
                    st.rerun()

            with col4:
                if st.button("Add 10 (No Discount)", use_container_width=True):
                    add_to_cart(selected_item, 10, 0)
                    st.success(f"✅ Added 10x {selected_item['name']} to invoice!")
                    st.rerun()

    else:
        st.info("No inventory items found. Please add items in the Inventory tab first.")

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

def tally_billing_tab():
    """Tally-style billing interface with keyboard navigation"""
    st.header("⚡ Tally-Style Billing")
    st.markdown("**Keyboard-driven invoice creation like Tally - Tab to navigate, Enter to add items**")

    # Initialize session state for tally interface
    if 'tally_invoice_lines' not in st.session_state:
        st.session_state.tally_invoice_lines = []
    if 'tally_customer_info' not in st.session_state:
        st.session_state.tally_customer_info = {
            'name': '', 'address': '', 'email': '', 'notes': ''
        }

    # Load inventory for autocomplete
    inventory_df = data_manager.load_inventory()
    inventory_items = []
    if not inventory_df.empty:
        for _, row in inventory_df.iterrows():
            inventory_items.append({
                'id': row['item_id'],
                'sku': row['sku'],
                'name': row['name'],
                'company': row.get('company', ''),
                'price': float(row['base_price']),
                'tax_rate': float(row['tax_rate']),
                'discount_rate': float(row['discount_rate']),
                'display': row['display_text'] if 'display_text' in row else f"{row['sku']} - {row['name']}"
            })

    # Customer info (compact)
    with st.expander("Customer Information", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            customer_name = st.text_input("Customer Name", value=st.session_state.tally_customer_info['name'])
            customer_email = st.text_input("Email", value=st.session_state.tally_customer_info['email'])
        with col2:
            customer_address = st.text_area("Address", value=st.session_state.tally_customer_info['address'])
            notes = st.text_area("Notes", value=st.session_state.tally_customer_info['notes'])

        # Update session state
        st.session_state.tally_customer_info = {
            'name': customer_name, 'address': customer_address,
            'email': customer_email, 'notes': notes
        }

    # Main billing interface with JavaScript
    tally_interface_html = f"""
    <style>
        .tally-container {{
            font-family: 'Courier New', monospace;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 10px 0;
        }}

        .tally-header {{
            background: #2c3e50;
            color: white;
            padding: 10px;
            margin-bottom: 10px;
            text-align: center;
            border-radius: 4px;
            font-weight: bold;
        }}

        .tally-grid {{
            display: grid;
            grid-template-columns: 2fr 80px 100px 80px 120px 60px;
            gap: 8px;
            align-items: center;
            background: white;
            padding: 8px;
            border-radius: 4px;
            margin-bottom: 5px;
            border: 1px solid #ddd;
        }}

        .tally-grid.header {{
            background: #34495e;
            color: white;
            font-weight: bold;
            border: none;
        }}

        .tally-input {{
            padding: 6px;
            border: 1px solid #bdc3c7;
            border-radius: 3px;
            font-family: inherit;
            font-size: 14px;
        }}

        .tally-input:focus {{
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 5px rgba(52, 152, 219, 0.3);
        }}

        .tally-amount {{
            text-align: right;
            font-weight: bold;
            color: #27ae60;
        }}

        .tally-total {{
            background: #ecf0f1;
            padding: 10px;
            border-radius: 4px;
            margin-top: 10px;
        }}

        .autocomplete-dropdown {{
            position: absolute;
            background: white;
            border: 1px solid #bdc3c7;
            border-top: none;
            border-radius: 0 0 4px 4px;
            max-height: 200px;
            overflow-y: auto;
            z-index: 1000;
            width: 100%;
        }}

        .autocomplete-item {{
            padding: 8px;
            cursor: pointer;
            border-bottom: 1px solid #ecf0f1;
        }}

        .autocomplete-item:hover, .autocomplete-item.selected {{
            background: #3498db;
            color: white;
        }}

        .shortcut-help {{
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            padding: 8px;
            border-radius: 4px;
            margin-bottom: 10px;
            font-size: 12px;
        }}
    </style>

    <div class="tally-container">
        <div class="tally-header">
            INVOICE ENTRY - Tab to navigate • Enter to add line • F1 for help
        </div>

        <div class="shortcut-help">
            <strong>Keyboard Shortcuts:</strong> Tab=Next Field | Shift+Tab=Previous | Enter=Add Line | Ctrl+S=Save | F9=Calculate
        </div>

        <!-- Header Row -->
        <div class="tally-grid header">
            <div>Item Description</div>
            <div>Qty</div>
            <div>Rate</div>
            <div>Disc%</div>
            <div>Amount</div>
            <div>Action</div>
        </div>

        <!-- Current Input Row -->
        <div class="tally-grid" id="input-row">
            <div style="position: relative;">
                <input type="text" id="item-search" class="tally-input"
                       placeholder="Type item name or SKU..."
                       autocomplete="off" />
                <div id="autocomplete-dropdown" class="autocomplete-dropdown" style="display: none;"></div>
            </div>
            <input type="number" id="quantity" class="tally-input" value="1" min="1" />
            <input type="number" id="rate" class="tally-input" step="0.01" readonly />
            <input type="number" id="discount" class="tally-input" value="0" min="0" max="100" step="0.1" />
            <div id="line-amount" class="tally-amount">₹0.00</div>
            <button id="add-line" style="padding: 6px; background: #27ae60; color: white; border: none; border-radius: 3px;">Add</button>
        </div>

        <!-- Invoice Lines Display -->
        <div id="invoice-lines"></div>

        <!-- Totals Section -->
        <div class="tally-total">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <div>
                    <label>Global Discount %:</label>
                    <input type="number" id="global-discount" value="0" min="0" max="100" step="0.1"
                           style="margin-left: 10px; padding: 4px; width: 80px;" />
                    <br><br>
                    <label>Global Tax %:</label>
                    <input type="number" id="global-tax" value="0" min="0" max="100" step="0.1"
                           style="margin-left: 10px; padding: 4px; width: 80px;" />
                </div>
                <div style="text-align: right;">
                    <div><strong>Subtotal: <span id="subtotal">₹0.00</span></strong></div>
                    <div>Discount: <span id="total-discount">₹0.00</span></div>
                    <div>Tax: <span id="total-tax">₹0.00</span></div>
                    <div style="font-size: 18px; margin-top: 10px;"><strong>TOTAL: <span id="grand-total">₹0.00</span></strong></div>
                </div>
            </div>
        </div>

        <div style="margin-top: 15px; text-align: center;">
            <button id="save-invoice" style="padding: 10px 20px; background: #2980b9; color: white; border: none; border-radius: 4px; margin-right: 10px;">Save Invoice</button>
            <button id="clear-all" style="padding: 10px 20px; background: #e74c3c; color: white; border: none; border-radius: 4px;">Clear All</button>
        </div>
    </div>

    <script>
        // Inventory data for autocomplete
        const inventoryItems = {json.dumps(inventory_items)};
        let currentLines = [];
        let selectedItemIndex = -1;
        let autocompleteItems = [];

        // DOM elements
        const itemSearch = document.getElementById('item-search');
        const quantity = document.getElementById('quantity');
        const rate = document.getElementById('rate');
        const discount = document.getElementById('discount');
        const lineAmount = document.getElementById('line-amount');
        const addLineBtn = document.getElementById('add-line');
        const autocompleteDropdown = document.getElementById('autocomplete-dropdown');
        const invoiceLines = document.getElementById('invoice-lines');
        const globalDiscount = document.getElementById('global-discount');
        const globalTax = document.getElementById('global-tax');

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {{
            itemSearch.focus();
            setupEventListeners();
            calculateLineAmount();
        }});

        function setupEventListeners() {{
            // Item search autocomplete
            itemSearch.addEventListener('input', handleItemSearch);
            itemSearch.addEventListener('keydown', handleItemKeyDown);

            // Quantity, rate, discount change
            quantity.addEventListener('input', calculateLineAmount);
            rate.addEventListener('input', calculateLineAmount);
            discount.addEventListener('input', calculateLineAmount);

            // Global values change
            globalDiscount.addEventListener('input', calculateTotals);
            globalTax.addEventListener('input', calculateTotals);

            // Add line
            addLineBtn.addEventListener('click', addLine);

            // Keyboard shortcuts
            document.addEventListener('keydown', handleGlobalKeyDown);

            // Tab navigation
            setupTabNavigation();
        }}

        function handleItemSearch() {{
            const query = itemSearch.value.toLowerCase();
            if (query.length < 1) {{
                hideAutocomplete();
                clearItemData();
                return;
            }}

            // Filter items
            autocompleteItems = inventoryItems.filter(item =>
                item.name.toLowerCase().includes(query) ||
                item.sku.toLowerCase().includes(query) ||
                item.company.toLowerCase().includes(query)
            );

            showAutocomplete();
        }}

        function showAutocomplete() {{
            if (autocompleteItems.length === 0) {{
                hideAutocomplete();
                return;
            }}

            let html = '';
            autocompleteItems.forEach((item, index) => {{
                const isSelected = index === selectedItemIndex;
                html += `<div class="autocomplete-item ${{isSelected ? 'selected' : ''}}"
                              onclick="selectItem(${{index}})"
                              data-index="${{index}}">
                           ${{item.display}}
                         </div>`;
            }});

            autocompleteDropdown.innerHTML = html;
            autocompleteDropdown.style.display = 'block';
        }}

        function hideAutocomplete() {{
            autocompleteDropdown.style.display = 'none';
            selectedItemIndex = -1;
        }}

        function selectItem(index) {{
            if (index >= 0 && index < autocompleteItems.length) {{
                const item = autocompleteItems[index];
                itemSearch.value = item.display;
                rate.value = item.price.toFixed(2);
                discount.value = item.discount_rate;
                hideAutocomplete();
                calculateLineAmount();
                quantity.focus();
            }}
        }}

        function handleItemKeyDown(e) {{
            if (autocompleteDropdown.style.display === 'none') return;

            switch(e.key) {{
                case 'ArrowDown':
                    e.preventDefault();
                    selectedItemIndex = Math.min(selectedItemIndex + 1, autocompleteItems.length - 1);
                    showAutocomplete();
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    selectedItemIndex = Math.max(selectedItemIndex - 1, 0);
                    showAutocomplete();
                    break;
                case 'Enter':
                    e.preventDefault();
                    if (selectedItemIndex >= 0) {{
                        selectItem(selectedItemIndex);
                    }}
                    break;
                case 'Escape':
                    hideAutocomplete();
                    break;
            }}
        }}

        function clearItemData() {{
            rate.value = '';
            discount.value = '0';
            calculateLineAmount();
        }}

        function calculateLineAmount() {{
            const qty = parseFloat(quantity.value) || 0;
            const rateVal = parseFloat(rate.value) || 0;
            const discVal = parseFloat(discount.value) || 0;

            const subtotal = qty * rateVal;
            const discAmount = subtotal * (discVal / 100);
            const amount = subtotal - discAmount;

            lineAmount.textContent = `₹${{amount.toFixed(2)}}`;
        }}

        function addLine() {{
            const qty = parseFloat(quantity.value) || 0;
            const rateVal = parseFloat(rate.value) || 0;
            const discVal = parseFloat(discount.value) || 0;

            if (!itemSearch.value.trim() || qty <= 0 || rateVal <= 0) {{
                alert('Please fill all required fields');
                return;
            }}

            const subtotal = qty * rateVal;
            const discAmount = subtotal * (discVal / 100);
            const amount = subtotal - discAmount;

            const line = {{
                item: itemSearch.value,
                quantity: qty,
                rate: rateVal,
                discount: discVal,
                amount: amount
            }};

            currentLines.push(line);
            updateInvoiceLines();
            clearInputs();
            calculateTotals();
            itemSearch.focus();
        }}

        function updateInvoiceLines() {{
            let html = '';
            currentLines.forEach((line, index) => {{
                html += `<div class="tally-grid">
                           <div>${{line.item}}</div>
                           <div>${{line.quantity}}</div>
                           <div>₹${{line.rate.toFixed(2)}}</div>
                           <div>${{line.discount.toFixed(1)}}%</div>
                           <div class="tally-amount">₹${{line.amount.toFixed(2)}}</div>
                           <button onclick="removeLine(${{index}})"
                                   style="padding: 4px; background: #e74c3c; color: white; border: none; border-radius: 2px;">×</button>
                         </div>`;
            }});
            invoiceLines.innerHTML = html;
        }}

        function removeLine(index) {{
            currentLines.splice(index, 1);
            updateInvoiceLines();
            calculateTotals();
        }}

        function clearInputs() {{
            itemSearch.value = '';
            quantity.value = '1';
            rate.value = '';
            discount.value = '0';
            lineAmount.textContent = '₹0.00';
            hideAutocomplete();
        }}

        function calculateTotals() {{
            const subtotal = currentLines.reduce((sum, line) => sum + line.amount, 0);
            const globalDiscVal = parseFloat(globalDiscount.value) || 0;
            const globalTaxVal = parseFloat(globalTax.value) || 0;

            const discountAmount = subtotal * (globalDiscVal / 100);
            const afterDiscount = subtotal - discountAmount;
            const taxAmount = afterDiscount * (globalTaxVal / 100);
            const total = afterDiscount + taxAmount;

            document.getElementById('subtotal').textContent = `₹${{subtotal.toFixed(2)}}`;
            document.getElementById('total-discount').textContent = `₹${{discountAmount.toFixed(2)}}`;
            document.getElementById('total-tax').textContent = `₹${{taxAmount.toFixed(2)}}`;
            document.getElementById('grand-total').textContent = `₹${{total.toFixed(2)}}`;
        }}

        function setupTabNavigation() {{
            const inputs = [itemSearch, quantity, rate, discount];

            inputs.forEach((input, index) => {{
                input.addEventListener('keydown', (e) => {{
                    if (e.key === 'Tab') {{
                        // Let default tab behavior work
                    }} else if (e.key === 'Enter') {{
                        e.preventDefault();
                        if (input === itemSearch && autocompleteDropdown.style.display !== 'none') {{
                            if (selectedItemIndex >= 0) {{
                                selectItem(selectedItemIndex);
                            }}
                        }} else if (input === discount) {{
                            addLine();
                        }} else {{
                            const nextIndex = (index + 1) % inputs.length;
                            inputs[nextIndex].focus();
                        }}
                    }}
                }});
            }});
        }}

        function handleGlobalKeyDown(e) {{
            if (e.ctrlKey && e.key === 's') {{
                e.preventDefault();
                saveInvoice();
            }} else if (e.key === 'F9') {{
                e.preventDefault();
                calculateTotals();
            }}
        }}

        function saveInvoice() {{
            if (currentLines.length === 0) {{
                alert('Add some items before saving');
                return;
            }}

            // Create a button to trigger Streamlit rerun with data
            const saveData = {{
                lines: currentLines,
                globalDiscount: parseFloat(globalDiscount.value) || 0,
                globalTax: parseFloat(globalTax.value) || 0
            }};

            // Store in localStorage temporarily
            localStorage.setItem('tally_invoice_data', JSON.stringify(saveData));

            // Trigger save via hidden button click
            const event = new CustomEvent('streamlit:saveTallyInvoice', {{ detail: saveData }});
            window.dispatchEvent(event);

            alert('Invoice data prepared. Click Save in Streamlit interface.');
        }}

        document.getElementById('save-invoice').addEventListener('click', saveInvoice);
        document.getElementById('clear-all').addEventListener('click', () => {{
            currentLines = [];
            updateInvoiceLines();
            clearInputs();
            calculateTotals();
        }});

        // Click outside to hide autocomplete
        document.addEventListener('click', (e) => {{
            if (!itemSearch.contains(e.target) && !autocompleteDropdown.contains(e.target)) {{
                hideAutocomplete();
            }}
        }});
    </script>
    """

    # Display the interface
    st.components.v1.html(tally_interface_html, height=600, scrolling=True)

    # Add save functionality below the interface
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("💾 Save Invoice", type="primary", use_container_width=True):
            customer_info = st.session_state.tally_customer_info
            if customer_info['name'].strip():
                st.success("🎯 Use Ctrl+S in the interface above or click 'Save Invoice' button in the interface to save")
            else:
                st.error("Please enter customer name in Customer Information section")

    with col2:
        if st.button("📊 Show Invoice Data", use_container_width=True):
            if 'tally_invoice_lines' in st.session_state and st.session_state.tally_invoice_lines:
                st.json(st.session_state.tally_invoice_lines)
            else:
                st.info("No invoice data yet. Add some items in the interface above.")

    with col3:
        if st.button("🗑️ Clear All Data", use_container_width=True):
            st.session_state.tally_invoice_lines = []
            st.success("All data cleared!")
            st.rerun()

    # Instructions for users
    with st.expander("📝 How to Use Tally Interface", expanded=False):
        st.markdown("""
        ### Keyboard Navigation (Just like Tally!)

        **🔤 Item Entry:**
        1. Type item name or SKU in the first field
        2. Use ↑↓ arrow keys to navigate autocomplete suggestions
        3. Press Enter to select item

        **⌨️ Field Navigation:**
        - **Tab**: Move to next field (Item → Qty → Rate → Disc%)
        - **Shift+Tab**: Move to previous field
        - **Enter**: Add current line to invoice (when in Discount field)

        **🎯 Quick Actions:**
        - **Ctrl+S**: Save invoice
        - **F9**: Recalculate totals
        - **Escape**: Close autocomplete dropdown

        **💡 Pro Tips:**
        - Quantity defaults to 1 (just press Tab if correct)
        - Rate auto-fills from inventory (press Tab if correct)
        - Discount defaults to item's default rate
        - Focus automatically returns to Item field after adding a line

        **📋 Workflow:**
        1. Type item → Tab → Enter quantity → Tab → Tab → Enter discount → Enter
        2. Repeat for next item
        3. Set global discount/tax if needed
        4. Save invoice when done
        """)

    # Display current lines if any
    if hasattr(st.session_state, 'tally_invoice_lines') and st.session_state.tally_invoice_lines:
        st.subheader("Current Invoice Lines")
        df_lines = pd.DataFrame(st.session_state.tally_invoice_lines)
        st.dataframe(df_lines, use_container_width=True)

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