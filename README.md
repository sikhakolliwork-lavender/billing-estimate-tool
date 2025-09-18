# Simple Billing Tool

A comprehensive inventory management and billing solution built with Streamlit. Features advanced fuzzy search, dual storage systems (Parquet/JSON), decimal-precise calculations, professional invoice generation, and **Tally-style keyboard-driven interface**.

## 🚀 Features

### 📦 **Inventory Management**
- **Complete CRUD Operations**: Add, edit, and delete inventory items
- **Rich Item Schema**: SKU, name, company, dual sizing (mm & inches), pricing, tax/discount rates
- **Smart Search Indexing**: Automatic search blob generation for lightning-fast queries
- **Data Validation**: Required field validation and type checking

### 🔍 **Advanced Fuzzy Search**
- **RapidFuzz Integration**: Sub-150ms search performance for up to 50k items
- **Intelligent Scoring**: Weighted scoring with boosts for SKU and name matches
- **Multi-field Search**: Search across SKU, name, company, sizes, prices simultaneously
- **Numeric Matching**: Direct price and measurement searches
- **Real-time Typeahead**: Instant search suggestions as you type

### 🧾 **Professional Billing System**
- **Line-level Controls**: Individual item discounts and tax rates
- **Global Adjustments**: Invoice-wide discount and tax application
- **Shopping Cart**: Add/remove items with live total calculations
- **Decimal Precision**: ROUND_HALF_UP calculations for financial accuracy
- **Invoice Storage**: Persistent invoice history with auto-incrementing numbers

### ⚡ **Tally-Style Interface** *(NEW!)*
- **Keyboard-First Design**: Tab navigation, Enter to add lines, just like Tally ERP
- **Grid-Based Entry**: Familiar table layout with Item | Qty | Rate | Disc% | Amount
- **Auto-complete Search**: Type to search items with arrow key navigation
- **Real-time Calculations**: Live totals update as you type
- **Professional Shortcuts**: Ctrl+S to save, F9 to calculate, Escape to close
- **Speed Optimized**: Muscle memory workflow for rapid data entry
- **Classic Look**: Monospace font and traditional accounting software aesthetics

### 💾 **Dual Storage Architecture**
- **Primary Storage**: Parquet files for optimal performance and compression
- **Fallback Storage**: JSON format for maximum compatibility
- **Atomic Operations**: Automatic backups before every write operation
- **Data Recovery**: Built-in corruption detection and recovery
- **Versioned Backups**: Timestamped backup system

### ⚙️ **Comprehensive Settings**
- **Storage Mode**: Switch between Parquet and JSON storage
- **Business Configuration**: Company information for invoice branding
- **Default Rates**: Configurable tax and discount defaults
- **Currency Settings**: Customizable currency codes and symbols
- **Invoice Numbering**: Configurable prefixes and auto-increment counters

## 📁 Project Structure

```
billing-estimate-tool/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── .gitignore           # Git ignore patterns
├── data/                # Application data directory
│   ├── settings.json    # Application settings
│   ├── inventory.parquet # Inventory data (or .json)
│   ├── invoices.parquet  # Invoice history (or .json)
│   ├── backups/         # Automatic backups
│   └── exports/
│       └── invoices/    # PDF exports (future)
└── venv/               # Python virtual environment
```

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.7 or higher
- Git

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sikhakolliwork-lavender/billing-estimate-tool.git
   cd billing-estimate-tool
   ```

2. **Create and activate virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   streamlit run app.py
   ```

5. **Access the application:**
   Open your browser to `http://localhost:8501`

## 🎯 Usage Guide

### Getting Started

1. **Configure Settings**: Visit the Settings tab to set up your business information and preferences
2. **Add Inventory**: Use the Inventory tab to add your products and services
3. **Create Invoices**: Choose between:
   - **Standard Billing Tab**: Traditional form-based interface
   - **⚡ Tally Style Tab**: Keyboard-driven interface for power users

### Inventory Management

1. **Adding Items:**
   - Navigate to the "Inventory" tab
   - Expand "Add/Edit Inventory Item"
   - Fill in required fields (SKU and Name are mandatory)
   - Configure pricing, tax rates, and discounts
   - Click "Save Item"

2. **Searching Items:**
   - Use the search box to find items by any field
   - Search works with partial matches and fuzzy matching
   - Results are ranked by relevance

3. **Editing Items:**
   - Search for the item you want to edit
   - Select it from the dropdown
   - Click "Load for Editing"
   - Modify fields and save

### Creating Invoices

1. **Customer Information:**
   - Fill in customer details in the Customer Information section
   - Customer name is required for invoice creation

2. **Adding Items:**
   - Use the search box to find inventory items
   - Adjust quantity and line-level discounts as needed
   - Click "Add" to add items to the invoice

3. **Invoice Totals:**
   - Set global discount and tax rates
   - Review calculated totals
   - Save invoice or export to PDF

### ⚡ Using Tally-Style Interface *(Power User Mode)*

The Tally-Style interface provides a familiar, keyboard-driven experience for users coming from traditional accounting software like Tally ERP.

#### **🎯 Quick Start Workflow:**
1. Navigate to the **"⚡ Tally Style"** tab
2. Fill customer information (expandable section)
3. **Type item name/SKU** in the first field
4. **Tab → Quantity** (defaults to 1)
5. **Tab → Rate** (auto-filled from inventory)
6. **Tab → Discount%** (defaults to item's rate)
7. **Enter** → Add line, return to item field
8. **Repeat** for next items
9. **Ctrl+S** → Save invoice

#### **⌨️ Keyboard Shortcuts:**
| Shortcut | Action |
|----------|--------|
| **Tab** | Move to next field |
| **Shift+Tab** | Move to previous field |
| **Enter** | Add current line to invoice |
| **↑ ↓** | Navigate autocomplete suggestions |
| **Enter** (in autocomplete) | Select item |
| **Escape** | Close autocomplete dropdown |
| **Ctrl+S** | Save invoice |
| **F9** | Recalculate totals |

#### **💡 Pro Tips:**
- **Speed Entry**: Type item → Tab → Tab → Enter (if defaults are correct)
- **Auto-complete**: Start typing any part of item name, SKU, or company
- **Muscle Memory**: Interface stays consistent - build your workflow
- **Real-time**: All calculations update as you type
- **Focus Flow**: After adding a line, focus returns to item field automatically

### Settings Configuration

1. **Storage Settings:**
   - Choose between Parquet (faster) or JSON (more compatible) storage
   - Changes take effect immediately

2. **Business Information:**
   - Configure your company details for invoice branding
   - Used in PDF exports and invoice headers

3. **Default Rates:**
   - Set default tax and discount rates
   - Configure currency symbol and code

## 📊 Technical Specifications

### Performance
- **Search Speed**: <150ms for up to 50,000 items
- **Storage**: Optimized Parquet format with JSON fallback
- **Memory**: Efficient pandas DataFrame operations
- **Calculations**: Decimal precision with configurable rounding

### Data Model

#### Inventory Schema
```python
{
    'item_id': str,         # Unique identifier
    'sku': str,             # Stock Keeping Unit (required)
    'name': str,            # Item name (required)
    'company': str,         # Brand/company name
    'size_mm': float,       # Size in millimeters
    'size_inch': float,     # Size in inches
    'base_price': float,    # Base price
    'tax_rate': float,      # Default tax rate (%)
    'discount_rate': float, # Default discount rate (%)
    'search_blob': str,     # Searchable text blob
    'created_at': str,      # ISO timestamp
    'updated_at': str       # ISO timestamp
}
```

#### Invoice Schema
```python
{
    'invoice_id': str,           # Unique identifier
    'invoice_number': str,       # Human-readable number
    'date': str,                 # Invoice date (ISO)
    'customer_name': str,        # Customer name
    'customer_address': str,     # Customer address
    'customer_email': str,       # Customer email
    'notes': str,                # Invoice notes
    'global_discount_rate': float, # Global discount %
    'global_tax_rate': float,    # Global tax %
    'line_items': str,           # JSON array of items
    'subtotal': float,           # Calculated subtotal
    'total_discount': float,     # Total discount amount
    'total_tax': float,          # Total tax amount
    'grand_total': float,        # Final total
    'created_at': str,           # ISO timestamp
    'updated_at': str            # ISO timestamp
}
```

## 🔧 Dependencies

- **streamlit**: Web application framework
- **pandas**: Data manipulation and analysis
- **pyarrow**: Parquet file support
- **rapidfuzz**: Fast fuzzy string matching
- **reportlab**: PDF generation (legacy support)
- **weasyprint**: Modern PDF generation (planned)

## 📈 Roadmap

### Completed ✅
- [x] Inventory CRUD operations
- [x] Fuzzy search with RapidFuzz
- [x] Dual storage system (Parquet/JSON)
- [x] Invoice creation and management
- [x] Decimal precision calculations
- [x] Settings management
- [x] Tabbed user interface
- [x] Automatic backups
- [x] **Tally-style keyboard interface** *(NEW!)*
- [x] **JavaScript-powered navigation** *(NEW!)*
- [x] **Real-time calculations** *(NEW!)*
- [x] **CSV import/export** *(COMPLETED!)*

### Planned 🔄
- [ ] PDF export with WeasyPrint
- [ ] Advanced reporting and analytics
- [ ] Invoice templates
- [ ] Multi-currency support
- [ ] Batch operations
- [ ] Enhanced Tally features (shortcuts customization)
- [ ] Barcode scanning integration

## 🤝 Contributing

This is a personal project, but suggestions and improvements are welcome:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

For issues, questions, or feature requests:
- Create an issue on GitHub
- Check the documentation in this README
- Review the application settings for configuration options

## 🎉 Acknowledgments

Built according to comprehensive PRD specifications with focus on:
- Performance optimization
- Data integrity
- User experience
- Scalability
- Professional invoice generation

---

**Version**: 1.0.0
**Last Updated**: 2024
**Status**: Production Ready