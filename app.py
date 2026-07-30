import streamlit as st
import sqlite3
import pandas as pd
import urllib.parse
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & ULTRA-HIGH CONTRAST DARK THEME
# ---------------------------------------------------------
st.set_page_config(
    page_title="A Pharma - Dark POS System",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# High-Contrast Modern Dark Theme CSS
st.markdown("""
    <style>
        /* Base Dark Background & Text Color */
        .stApp {
            background-color: #090d16 !important;
            color: #f8fafc !important;
        }

        /* Sidebar Dark Styling */
        [data-testid="stSidebar"] {
            background-color: #0f172a !important;
            border-right: 2px solid #1e293b;
        }

        /* Bold Clear Main Headers with Cyan Accent */
        .main-header {
            font-size: 32px;
            font-weight: 900;
            color: #00f2fe;
            padding: 10px 0px;
            border-bottom: 3px solid #00f2fe;
            margin-bottom: 20px;
            text-shadow: 0 0 10px rgba(0, 242, 254, 0.3);
        }

        /* High Contrast Dark Cards */
        .kpi-card {
            background: #111827;
            padding: 20px;
            border-radius: 14px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
            border: 2px solid #334155;
            border-left: 8px solid #00f2fe;
            margin-bottom: 15px;
        }
        .kpi-title { font-size: 14px; color: #94a3b8; text-transform: uppercase; font-weight: 800; letter-spacing: 0.5px; }
        .kpi-value { font-size: 28px; font-weight: 900; color: #00f2fe; margin-top: 5px; }

        /* Highly Visible Stock Badges on Dark BG */
        .badge-success { background-color: #059669; color: #ffffff; padding: 6px 14px; border-radius: 20px; font-weight: 800; font-size: 13px; display: inline-block; border: 1px solid #10b981; }
        .badge-warning { background-color: #d97706; color: #ffffff; padding: 6px 14px; border-radius: 20px; font-weight: 800; font-size: 13px; display: inline-block; border: 1px solid #f59e0b; }
        .badge-danger { background-color: #dc2626; color: #ffffff; padding: 6px 14px; border-radius: 20px; font-weight: 800; font-size: 13px; display: inline-block; border: 1px solid #ef4444; }

        /* Prominent Glowing JazzCash Payment Box */
        .jazzcash-card {
            background: #111827;
            border: 3px solid #ff0055;
            border-radius: 14px;
            padding: 15px;
            text-align: center;
            box-shadow: 0 0 20px rgba(255, 0, 85, 0.3);
            margin-top: 15px;
        }
        .jazzcash-header {
            background: linear-gradient(135deg, #ff8000 0%, #ff0055 100%);
            color: #ffffff;
            font-weight: 900;
            font-size: 16px;
            padding: 8px;
            border-radius: 8px;
            margin-bottom: 12px;
            letter-spacing: 1px;
        }

        /* Large Clear Dark Input Boxes & Selectboxes */
        .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input {
            background-color: #1e293b !important;
            border: 2px solid #475569 !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
            font-size: 15px !important;
            color: #ffffff !important;
        }
        
        /* High Contrast Buttons */
        .stButton>button {
            border-radius: 8px !important;
            font-weight: 800 !important;
            font-size: 15px !important;
            padding: 10px 20px !important;
            border: 1px solid #38bdf8 !important;
        }

        /* Tab Highlighting */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #1e293b;
            border-radius: 8px 8px 0 0;
            color: #94a3b8;
            font-weight: 800;
            padding: 10px 20px;
        }
        .stTabs [aria-selected="true"] {
            background-color: #00f2fe !important;
            color: #090d16 !important;
        }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. DATABASE MANAGEMENT
# ---------------------------------------------------------
def get_connection():
    return sqlite3.connect("pharmacy_multi.db", timeout=20, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT,
                    role TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    category TEXT,
                    price REAL,
                    stock INTEGER,
                    batch_no TEXT DEFAULT 'B-001',
                    expiry_date DATE DEFAULT '2026-12-31')''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_id TEXT,
                    customer_name TEXT,
                    medicine_name TEXT,
                    qty INTEGER,
                    unit_price REAL,
                    total_price REAL,
                    subtotal REAL DEFAULT 0.0,
                    discount_pct REAL DEFAULT 0.0,
                    tax_pct REAL DEFAULT 0.0,
                    grand_total REAL DEFAULT 0.0,
                    payment_method TEXT DEFAULT 'Cash',
                    sold_by TEXT,
                    timestamp DATETIME)''')
    
    # Migrations
    c.execute("PRAGMA table_info(inventory)")
    inv_cols = [col[1] for col in c.fetchall()]
    if 'batch_no' not in inv_cols:
        try: c.execute("ALTER TABLE inventory ADD COLUMN batch_no TEXT DEFAULT 'B-001'")
        except: pass
    if 'expiry_date' not in inv_cols:
        try: c.execute("ALTER TABLE inventory ADD COLUMN expiry_date DATE DEFAULT '2026-12-31'")
        except: pass

    c.execute("PRAGMA table_info(sales)")
    sales_cols = [col[1] for col in c.fetchall()]
    if 'payment_method' not in sales_cols:
        try: c.execute("ALTER TABLE sales ADD COLUMN payment_method TEXT DEFAULT 'Cash'")
        except: pass

    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin')")
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('staff1', 'staff123', 'staff')")
    
    conn.commit()
    conn.close()

init_db()

# Helper: Ultra-Clear High Resolution QR Code URL
def get_jazzcash_qr_url(amount, bill_id, till_id="00012345"):
    payload = f"JazzCash Merchant POS|TillID:{till_id}|Bill:{bill_id}|Amount:{amount:.2f}|Currency:PKR"
    encoded_payload = urllib.parse.quote(payload)
    return f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded_payload}&color=ff0055"

# ---------------------------------------------------------
# 3. THERMAL RECEIPT ENGINE (CLEAR WHITE RECEIPT FOR PRINT)
# ---------------------------------------------------------
def generate_receipt_html(bill_id):
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM sales WHERE bill_id=?", conn, params=(bill_id,))
    conn.close()
    
    if df.empty:
        return "<p style='color:#ff5252; font-size:16px; font-weight:bold;'>Bill Record Not Found!</p>"

    row0 = df.iloc[0]
    cust_name = row0['customer_name']
    biller = row0['sold_by']
    date_str = row0['timestamp']
    pay_mode = row0.get('payment_method', 'Cash')
    subtotal = float(row0.get('subtotal', 0.0))
    discount_pct = float(row0.get('discount_pct', 0.0))
    tax_pct = float(row0.get('tax_pct', 0.0))
    grand_total = float(row0.get('grand_total', 0.0))

    disc_val = subtotal * (discount_pct / 100.0)
    tax_val = (subtotal - disc_val) * (tax_pct / 100.0)

    items_rows = ""
    for _, item in df.iterrows():
        items_rows += f"""
        <tr>
            <td style="padding: 4px 0; font-weight: bold;">{str(item['medicine_name'])[:16]}</td>
            <td style="text-align: right; padding: 4px 0;">{item['qty']}</td>
            <td style="text-align: right; padding: 4px 0;">{item['unit_price']:.0f}</td>
            <td style="text-align: right; padding: 4px 0; font-weight: bold;">{item['total_price']:.0f}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @media print {{
                @page {{ margin: 0; size: 80mm auto; }}
                body {{ margin: 0; padding: 5px; }}
                .no-print {{ display: none !important; }}
            }}
            body {{
                font-family: 'Courier New', monospace;
                font-size: 13px;
                color: #000;
                width: 290px;
                margin: 0 auto;
                background-color: #fff;
                font-weight: 600;
                padding: 10px;
                border-radius: 8px;
            }}
            .text-center {{ text-align: center; }}
            .text-right {{ text-align: right; }}
            .line {{ border-bottom: 2px dashed #000; margin: 8px 0; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
            .btn-print {{
                background-color: #ff0055;
                color: #ffffff;
                padding: 10px 14px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                margin-bottom: 12px;
                width: 100%;
                font-weight: 900;
                text-transform: uppercase;
            }}
        </style>
    </head>
    <body>
        <button class="btn-print no-print" onclick="window.print()">🖨️ PRINT RECEIPT</button>
        <div class="text-center">
            <h2 style="margin:0; font-size:20px; font-weight:900;">A PHARMA</h2>
            <p style="margin:3px 0; font-size:12px;">ULTRA POS & PHARMACY<br>Helpline: +92-300-0000000</p>
        </div>
        <div class="line"></div>
        <div>
            <b>Bill ID:</b> {bill_id}<br>
            <b>Date:</b> {date_str}<br>
            <b>Customer:</b> {cust_name}<br>
            <b>Payment Method:</b> {pay_mode}<br>
            <b>Cashier:</b> {biller}
        </div>
        <div class="line"></div>
        <table>
            <thead>
                <tr style="border-bottom: 1px solid #000;">
                    <th style="text-align:left;">Item</th>
                    <th style="text-align:right;">Qty</th>
                    <th style="text-align:right;">Price</th>
                    <th style="text-align:right;">Total</th>
                </tr>
            </thead>
            <tbody>{items_rows}</tbody>
        </table>
        <div class="line"></div>
        <table>
            <tr><td>Subtotal:</td><td class="text-right">Rs. {subtotal:,.2f}</td></tr>
            {"<tr><td>Discount (" + str(discount_pct) + "%):</td><td class='text-right'>-Rs. " + f"{disc_val:,.2f}" + "</td></tr>" if discount_pct > 0 else ""}
            {"<tr><td>Tax (" + str(tax_pct) + "%):</td><td class='text-right'>+Rs. " + f"{tax_val:,.2f}" + "</td></tr>" if tax_pct > 0 else ""}
        </table>
        <div class="line"></div>
        <div style="font-size:16px; font-weight:900;">
            GRAND TOTAL: <span style="float:right;">Rs. {grand_total:,.2f}</span>
        </div>
        <div class="line"></div>
        <div class="text-center" style="margin-top:10px;">
            <p style="margin:0;">Thank You For Choosing Us!<br>*** Get Well Soon ***</p>
        </div>
    </body>
    </html>
    """

# ---------------------------------------------------------
# 4. AUTHENTICATION & LOGIN
# ---------------------------------------------------------
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.role = ""
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'last_printed_bill' not in st.session_state:
    st.session_state.last_printed_bill = None

def login(username, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT username, role FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()
    if user:
        st.session_state.authenticated = True
        st.session_state.username = user[0]
        st.session_state.role = user[1]
        st.rerun()
    else:
        st.error("❌ Invalid Username or Password!")

if not st.session_state.authenticated:
    st.markdown("<br><h1 style='text-align: center; color: #00f2fe; font-weight:900; text-shadow: 0 0 10px rgba(0,242,254,0.4);'>💊 A PHARMA LOGIN TERMINAL</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.info("🔑 **Default Access Logins:**\n- **Admin:** `admin` / `admin123`\n- **Staff:** `staff1` / `staff123`")
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("🚀 Access System", use_container_width=True, type="primary"):
            login(u, p)
    st.stop()

# ---------------------------------------------------------
# 5. SIDEBAR NAVIGATION
# ---------------------------------------------------------
st.sidebar.markdown("<h2 style='color:#00f2fe;'>💊 A PHARMA POS</h2>", unsafe_allow_html=True)
st.sidebar.markdown(f"👤 **User:** <span style='color:#00f2fe; font-weight:bold;'>{st.session_state.username.upper()}</span>", unsafe_allow_html=True)
st.sidebar.markdown(f"🔰 **Role:** <span style='color:#ff0055; font-weight:bold;'>{st.session_state.role.upper()}</span>", unsafe_allow_html=True)
st.sidebar.markdown("---")

if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.rerun()

if st.sidebar.button("🚪 Logout System", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.cart = []
    st.session_state.last_printed_bill = None
    st.rerun()

# ---------------------------------------------------------
# 6. DASHBOARDS
# ---------------------------------------------------------

# ==================== STAFF DASHBOARD ====================
if st.session_state.role == "staff":
    st.markdown("<div class='main-header'>⚡ CHECKOUT & BILLING COUNTER</div>", unsafe_allow_html=True)
    
    staff_tabs = st.tabs(["🛍️ NEW BILLING COUNTER", "🚨 STOCK ALERTS", "📜 INVOICE HISTORY"])

    # TAB 1: NEW BILLING COUNTER
    with staff_tabs[0]:
        conn = get_connection()
        inventory_df = pd.read_sql("SELECT id, name, price, stock, batch_no, expiry_date FROM inventory WHERE stock > 0", conn)
        conn.close()

        col_med, col_cart = st.columns([1.3, 1])

        with col_med:
            st.markdown("### 1️⃣ Select Items")
            cust_name = st.text_input("Customer Name", value="Walk-in Customer")
            
            if not inventory_df.empty:
                selected_med = st.selectbox("🔍 Search Medicine Name", inventory_df['name'].tolist())
                med_info = inventory_df[inventory_df['name'] == selected_med].iloc[0]
                
                in_cart_qty = sum(item['qty'] for item in st.session_state.cart if item['name'] == selected_med)
                available_stock = int(med_info['stock']) - in_cart_qty

                # Clear Visual Info Card
                badge_html = f"<span class='badge-success'>{available_stock} Units Available</span>" if available_stock > 10 else f"<span class='badge-warning'>Low Stock: {available_stock} Left</span>"
                st.markdown(f"""
                <div class='kpi-card' style='border-left-color: #00f2fe;'>
                    <div style='font-size:22px; font-weight:800; color:#00f2fe;'>Unit Price: Rs. {med_info['price']:,.2f}</div>
                    <div style='margin: 8px 0;'><b>Stock Status:</b> {badge_html}</div>
                    <div style='color:#94a3b8; font-size:13px;'><b>Batch No:</b> {med_info['batch_no']} | <b>Expiry:</b> {med_info['expiry_date']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                if available_stock > 0:
                    qty = st.number_input("Enter Quantity", min_value=1, max_value=available_stock, value=1)

                    if st.button("➕ Add Item to Cart", use_container_width=True, type="primary"):
                        st.session_state.cart.append({
                            "name": selected_med,
                            "unit_price": float(med_info['price']),
                            "qty": int(qty),
                            "subtotal": float(med_info['price']) * int(qty)
                        })
                        st.toast(f"✅ Added {selected_med} (Qty: {qty})")
                        st.rerun()
                else:
                    st.error("⚠️ Stock limit reached for this item!")
            else:
                st.warning("⚠️ No available stock found in database!")

        with col_cart:
            st.markdown("### 2️⃣ Order & Payment")
            if st.session_state.cart:
                cart_df = pd.DataFrame(st.session_state.cart)
                
                # Clear Table Display
                st.dataframe(cart_df[['name', 'qty', 'unit_price', 'subtotal']], use_container_width=True, height=180)
                
                subtotal = float(cart_df['subtotal'].sum())
                
                cp1, cp2, cp3 = st.columns(3)
                with cp1:
                    pay_method = st.selectbox("Payment Mode", ["Cash", "JazzCash", "Card", "EasyPaisa"])
                with cp2:
                    discount_pct = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, value=0.0)
                with cp3:
                    tax_pct = st.number_input("Tax (%)", min_value=0.0, max_value=50.0, value=0.0)
                
                disc_val = subtotal * (discount_pct / 100.0)
                tax_val = (subtotal - disc_val) * (tax_pct / 100.0)
                grand_total = (subtotal - disc_val) + tax_val

                st.markdown(f"<h2 style='color:#00e676; font-weight:900; text-shadow: 0 0 10px rgba(0,230,118,0.3);'>Grand Total: Rs. {grand_total:,.2f}</h2>", unsafe_allow_html=True)

                # HIGH VISIBILITY DARK JAZZCASH INTEGRATION
                if pay_method == "JazzCash":
                    temp_bill_id = f"AP-{datetime.now().strftime('%M%S')}"
                    qr_url = get_jazzcash_qr_url(grand_total, temp_bill_id)
                    
                    st.markdown(f"""
                    <div class='jazzcash-card'>
                        <div class='jazzcash-header'>🔴 JAZZCASH QR PAYMENT</div>
                        <div style='color:#f8fafc; font-weight:800; font-size:14px; margin-bottom:8px;'>Scan via JazzCash App to Pay</div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.image(qr_url, caption=f"Scan & Pay Exact Amount: Rs. {grand_total:,.2f}", width=220)

                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    if st.button("Empty Cart ❌", use_container_width=True):
                        st.session_state.cart = []
                        st.rerun()

                with b_col2:
                    if st.button("Checkout & Print Bill 🚀", type="primary", use_container_width=True):
                        bill_id = f"AP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        conn = get_connection()
                        c = conn.cursor()
                        try:
                            for item in st.session_state.cart:
                                c.execute('''INSERT INTO sales 
                                             (bill_id, customer_name, medicine_name, qty, unit_price, total_price, subtotal, discount_pct, tax_pct, grand_total, payment_method, sold_by, timestamp) 
                                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                          (bill_id, cust_name, item['name'], item['qty'], item['unit_price'], item['subtotal'], subtotal, discount_pct, tax_pct, grand_total, pay_method, st.session_state.username, now_str))
                                
                                c.execute("UPDATE inventory SET stock = stock - ? WHERE name = ?", (item['qty'], item['name']))
                            
                            conn.commit()
                            st.session_state.last_printed_bill = bill_id
                            st.session_state.cart = []
                            st.success(f"✅ Transaction Completed! Invoice ID: {bill_id}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error saving sale: {e}")
                        finally:
                            conn.close()
            else:
                st.info("🛒 Cart is empty. Select items to generate receipt.")

        # THERMAL RECEIPT DISPLAY
        if st.session_state.last_printed_bill:
            st.markdown("---")
            st.markdown(f"### 🖨️ Active Receipt Preview (`{st.session_state.last_printed_bill}`)")
            rc_html = generate_receipt_html(st.session_state.last_printed_bill)
            st.components.v1.html(rc_html, height=480, scrolling=True)

    # TAB 2: STOCK ALERTS
    with staff_tabs[1]:
        st.markdown("### 🚨 Low Stock & Expiry Tracking")
        conn = get_connection()
        alerts_df = pd.read_sql("SELECT name AS 'Medicine', category AS 'Category', price AS 'Price (Rs.)', stock AS 'Remaining Stock', expiry_date AS 'Expiry Date' FROM inventory", conn)
        conn.close()

        if not alerts_df.empty:
            low_stock = alerts_df[alerts_df['Remaining Stock'] <= 10]
            if not low_stock.empty:
                st.warning("⚠️ Critical Low Stock Items Found!")
                st.dataframe(low_stock, use_container_width=True)
            else:
                st.success("✅ All stock levels are sufficient.")
        else:
            st.info("No stock records available.")

    # TAB 3: RECEIPT HISTORY
    with staff_tabs[2]:
        st.markdown("### 📜 Invoice & Transaction History")
        conn = get_connection()
        bills_df = pd.read_sql("SELECT bill_id, customer_name, grand_total, payment_method, sold_by, timestamp FROM sales GROUP BY bill_id ORDER BY MAX(id) DESC LIMIT 30", conn)
        conn.close()

        if not bills_df.empty:
            sel_bill = st.selectbox("Select Invoice to Re-Print", bills_df['bill_id'].tolist())
            if sel_bill:
                rc_html_history = generate_receipt_html(sel_bill)
                st.components.v1.html(rc_html_history, height=480, scrolling=True)

# ==================== ADMIN DASHBOARD ====================
elif st.session_state.role == "admin":
    st.markdown("<div class='main-header'>⚙️ BUSINESS INTELLIGENCE & ADMIN CONTROL</div>", unsafe_allow_html=True)
    
    tabs = st.tabs(["📊 ANALYTICS & KPIS", "📦 INVENTORY CONTROL", "👥 STAFF MANAGEMENT"])

    # TAB 1: ANALYTICS
    with tabs[0]:
        conn = get_connection()
        sales_df = pd.read_sql("SELECT * FROM sales ORDER BY id DESC", conn)
        conn.close()

        if not sales_df.empty:
            unique_bills = sales_df.drop_duplicates(subset=['bill_id'])
            total_rev = unique_bills['grand_total'].sum()
            total_items = sales_df['qty'].sum()
            total_tx = len(unique_bills)

            m1, m2, m3 = st.columns(3)
            m1.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-title'>Total Net Sales Revenue</div>
                <div class='kpi-value'>Rs. {total_rev:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
            
            m2.markdown(f"""
            <div class='kpi-card' style='border-left-color: #00e676;'>
                <div class='kpi-title'>Total Quantity Sold</div>
                <div class='kpi-value' style='color:#00e676;'>{int(total_items):,} Units</div>
            </div>
            """, unsafe_allow_html=True)

            m3.markdown(f"""
            <div class='kpi-card' style='border-left-color: #ff0055;'>
                <div class='kpi-title'>Completed Transactions</div>
                <div class='kpi-value' style='color:#ff0055;'>{total_tx:,} Bills</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### 📈 Top Selling Medicines")
            top_meds = sales_df.groupby('medicine_name')['qty'].sum().reset_index().sort_values(by='qty', ascending=False).head(7)
            st.bar_chart(data=top_meds, x='medicine_name', y='qty', use_container_width=True)

            st.markdown("---")
            st.markdown("### 📄 Master Sales Audit Log")
            st.download_button(
                label="📥 Export Complete Sales Log (CSV)",
                data=sales_df.to_csv(index=False).encode('utf-8'),
                file_name=f"Sales_Report_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv'
            )
            st.dataframe(sales_df, use_container_width=True)
        else:
            st.info("No sales transactions recorded yet.")

    # TAB 2: INVENTORY CONTROL
    with tabs[1]:
        st.markdown("### 📦 Add or Restock Medicine")
        c1, c2 = st.columns([1, 1.5])
        
        with c1:
            m_name = st.text_input("Medicine Name")
            m_cat = st.selectbox("Category", ["Tablet", "Syrup", "Injection", "Capsule", "Ointment", "Other"])
            m_price = st.number_input("Unit Selling Price (Rs.)", min_value=0.0, format="%.2f")
            m_stock = st.number_input("Stock Quantity to Add", min_value=0, step=1)
            m_batch = st.text_input("Batch No.", value="B-101")
            m_expiry = st.date_input("Expiry Date", datetime.now() + timedelta(days=365))

            if st.button("Save Item to Inventory", use_container_width=True, type="primary"):
                if m_name:
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO inventory (name, category, price, stock, batch_no, expiry_date) VALUES (?, ?, ?, ?, ?, ?)",
                                  (m_name, m_cat, m_price, m_stock, m_batch, str(m_expiry)))
                        conn.commit()
                        st.success(f"✅ Added {m_name} to database!")
                    except sqlite3.IntegrityError:
                        c.execute("UPDATE inventory SET category=?, price=?, stock=stock+?, batch_no=?, expiry_date=? WHERE name=?",
                                  (m_cat, m_price, m_stock, m_batch, str(m_expiry), m_name))
                        conn.commit()
                        st.success(f"✅ Updated Stock for {m_name}!")
                    finally:
                        conn.close()
                        st.rerun()

        with c2:
            st.markdown("### 📋 Current Active Stock Table")
            conn = get_connection()
            inv_df = pd.read_sql("SELECT id AS 'ID', name AS 'Name', category AS 'Category', price AS 'Price (Rs.)', stock AS 'Stock', batch_no AS 'Batch', expiry_date AS 'Expiry' FROM inventory", conn)
            conn.close()
            st.dataframe(inv_df, use_container_width=True)

    # TAB 3: STAFF MANAGEMENT
    with tabs[2]:
        st.markdown("### 👥 Manage Staff Accounts")
        u1, u2 = st.columns([1, 1.5])
        
        with u1:
            n_user = st.text_input("New Staff Username")
            n_pass = st.text_input("New Staff Password", type="password")
            if st.button("Create Staff Account", use_container_width=True):
                if n_user and n_pass:
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'staff')", (n_user, n_pass))
                        conn.commit()
                        st.success(f"✅ Staff Account '{n_user}' created successfully!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("⚠️ Username already exists!")
                    finally:
                        conn.close()

        with u2:
            conn = get_connection()
            users_df = pd.read_sql("SELECT id AS 'User ID', username AS 'Username', role AS 'System Role' FROM users", conn)
            conn.close()
            st.dataframe(users_df, use_container_width=True)
