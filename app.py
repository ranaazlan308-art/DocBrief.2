import streamlit as st
import sqlite3
import pandas as pd
import urllib.parse
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & ADVANCED MODERN STYLING
# ---------------------------------------------------------
st.set_page_config(
    page_title="A Pharma - Ultra POS System",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Advanced Modern CSS (Glassmorphism, Vibrant Badges & Clean Layouts)
st.markdown("""
    <style>
        /* Main Theme Overrides */
        .stApp {
            background-color: #f4f6f9;
        }
        
        /* Headers */
        .main-header {
            font-size: 28px;
            font-weight: 800;
            background: linear-gradient(135deg, #0D47A1 0%, #1E88E5 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 15px;
        }
        
        /* Metric KPI Cards */
        .kpi-card {
            background: #ffffff;
            padding: 18px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
            border-left: 6px solid #1E88E5;
            transition: transform 0.2s ease-in-out;
        }
        .kpi-card:hover {
            transform: translateY(-2px);
        }
        .kpi-title { font-size: 13px; color: #6c757d; text-transform: uppercase; font-weight: 600; }
        .kpi-value { font-size: 24px; font-weight: bold; color: #1e293b; margin-top: 5px; }

        /* Custom Badges */
        .badge {
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: bold;
            display: inline-block;
        }
        .badge-danger { background-color: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }
        .badge-warning { background-color: #fff8e1; color: #f57f17; border: 1px solid #ffe082; }
        .badge-success { background-color: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }

        /* Payment Method Box */
        .jazzcash-box {
            background: linear-gradient(135deg, #ff8000 0%, #e60000 100%);
            color: white;
            padding: 12px;
            border-radius: 10px;
            text-align: center;
            margin-top: 10px;
        }

        /* Buttons */
        .stButton>button {
            border-radius: 8px !important;
            font-weight: 600 !important;
        }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. DATABASE MANAGEMENT & SAFE MIGRATION
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
    
    # Safe Migrations
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

    # Default Credentials
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin')")
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('staff1', 'staff123', 'staff')")
    
    conn.commit()
    conn.close()

init_db()

# Helper: No-Dependency QR Code Generator URL
def get_jazzcash_qr_url(amount, bill_id, till_id="00012345"):
    payload = f"JazzCash Merchant POS|TillID:{till_id}|Bill:{bill_id}|Amount:{amount:.2f}|Currency:PKR"
    encoded_payload = urllib.parse.quote(payload)
    return f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={encoded_payload}&color=e60000"

# ---------------------------------------------------------
# 3. THERMAL RECEIPT HTML ENGINE
# ---------------------------------------------------------
def generate_receipt_html(bill_id):
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM sales WHERE bill_id=?", conn, params=(bill_id,))
    conn.close()
    
    if df.empty:
        return "<p style='color:red;'>Bill not found!</p>"

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
            <td style="padding: 2px 0;">{str(item['medicine_name'])[:15]}</td>
            <td style="text-align: right; padding: 2px 0;">{item['qty']}</td>
            <td style="text-align: right; padding: 2px 0;">{item['unit_price']:.0f}</td>
            <td style="text-align: right; padding: 2px 0;">{item['total_price']:.0f}</td>
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
                font-size: 12px;
                color: #000;
                width: 280px;
                margin: 0 auto;
                background-color: #fff;
            }}
            .text-center {{ text-align: center; }}
            .text-right {{ text-align: right; }}
            .line {{ border-bottom: 1px dashed #000; margin: 5px 0; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
            .btn-print {{
                background-color: #1E88E5;
                color: white;
                padding: 8px 12px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 13px;
                margin-bottom: 10px;
                width: 100%;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <button class="btn-print no-print" onclick="window.print()">🖨️ Print Receipt</button>
        <div class="text-center">
            <h2 style="margin:0; font-size:18px;">A PHARMA</h2>
            <p style="margin:2px 0;">Smart POS System<br>Helpline: +92-300-0000000</p>
        </div>
        <div class="line"></div>
        <div>
            <b>Bill ID:</b> {bill_id}<br>
            <b>Date:</b> {date_str}<br>
            <b>Customer:</b> {cust_name}<br>
            <b>Payment Mode:</b> {pay_mode}<br>
            <b>Cashier:</b> {biller}
        </div>
        <div class="line"></div>
        <table>
            <thead>
                <tr>
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
        <div style="font-size:14px;">
            <b>GRAND TOTAL: <span style="float:right;">Rs. {grand_total:,.2f}</span></b>
        </div>
        <div class="line"></div>
        <div class="text-center" style="margin-top:10px;">
            <p style="margin:0;">Thank You For Choosing Us!<br>*** Get Well Soon ***</p>
        </div>
    </body>
    </html>
    """

# ---------------------------------------------------------
# 4. AUTHENTICATION & SESSION STATE
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
        st.error("❌ Invalid Credentials")

if not st.session_state.authenticated:
    st.markdown("<br><h2 style='text-align: center; color: #1E88E5;'>💊 A Pharma Modern Terminal</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.container():
            st.info("🔑 **Default Logins:**\n- Admin: `admin` / `admin123`\n- Staff: `staff1` / `staff123`")
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("🚀 Access System", use_container_width=True, type="primary"):
                login(u, p)
    st.stop()

# ---------------------------------------------------------
# 5. NAVIGATION SIDEBAR
# ---------------------------------------------------------
st.sidebar.markdown("## 💊 **A PHARMA POS**")
st.sidebar.markdown(f"👤 **User:** `{st.session_state.username}`")
st.sidebar.markdown(f"🔰 **Role:** `{st.session_state.role.upper()}`")
st.sidebar.markdown("---")

if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.rerun()

if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.cart = []
    st.session_state.last_printed_bill = None
    st.rerun()

# ---------------------------------------------------------
# 6. DASHBOARDS
# ---------------------------------------------------------

# ==================== STAFF DASHBOARD ====================
if st.session_state.role == "staff":
    st.markdown("<div class='main-header'>⚡ Modern Checkout & Sales Terminal</div>", unsafe_allow_html=True)
    
    staff_tabs = st.tabs(["🛍️ New Billing Counter", "🚨 Live Stock Alerts", "📜 Receipt History"])

    # TAB 1: BILLING & JAZZCASH INTEGRATION
    with staff_tabs[0]:
        conn = get_connection()
        inventory_df = pd.read_sql("SELECT id, name, price, stock, batch_no, expiry_date FROM inventory WHERE stock > 0", conn)
        conn.close()

        c_item, c_cart = st.columns([1.2, 1])

        with c_item:
            st.subheader("📦 Add Items")
            cust_name = st.text_input("Customer Name", value="Walk-in Customer")
            
            if not inventory_df.empty:
                selected_med = st.selectbox("Search Medicine", inventory_df['name'].tolist())
                med_info = inventory_df[inventory_df['name'] == selected_med].iloc[0]
                
                in_cart_qty = sum(item['qty'] for item in st.session_state.cart if item['name'] == selected_med)
                available_stock = int(med_info['stock']) - in_cart_qty

                # Modern Card Display
                st.markdown(f"""
                <div class='kpi-card' style='border-left-color: #00c853;'>
                    <span class='kpi-title'>Unit Price: Rs. {med_info['price']}</span><br>
                    <b>Available Stock:</b> <span class='badge badge-success'>{available_stock} Units</span><br>
                    <small><b>Batch:</b> {med_info['batch_no']} | <b>Expiry:</b> {med_info['expiry_date']}</small>
                </div>
                """, unsafe_allow_html=True)
                
                if available_stock > 0:
                    qty = st.number_input("Select Quantity", min_value=1, max_value=available_stock, value=1)

                    if st.button("➕ Add to Cart", use_container_width=True, type="primary"):
                        st.session_state.cart.append({
                            "name": selected_med,
                            "unit_price": float(med_info['price']),
                            "qty": int(qty),
                            "subtotal": float(med_info['price']) * int(qty)
                        })
                        st.toast(f"Added {selected_med}!")
                        st.rerun()
                else:
                    st.error("⚠️ Stock unavailable!")
            else:
                st.warning("No stock available in system.")

        with c_cart:
            st.subheader("🛒 Invoice Summary")
            if st.session_state.cart:
                cart_df = pd.DataFrame(st.session_state.cart)
                st.dataframe(cart_df[['name', 'qty', 'unit_price', 'subtotal']], use_container_width=True)
                
                subtotal = float(cart_df['subtotal'].sum())
                
                cp1, cp2, cp3 = st.columns(3)
                with cp1:
                    pay_method = st.selectbox("Payment Method", ["Cash", "JazzCash", "Card", "EasyPaisa"])
                with cp2:
                    discount_pct = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, value=0.0)
                with cp3:
                    tax_pct = st.number_input("Tax (%)", min_value=0.0, max_value=50.0, value=0.0)
                
                disc_val = subtotal * (discount_pct / 100.0)
                tax_val = (subtotal - disc_val) * (tax_pct / 100.0)
                grand_total = (subtotal - disc_val) + tax_val

                st.markdown(f"### Grand Total: <span style='color:#1E88E5;'>Rs. {grand_total:,.2f}</span>", unsafe_allow_html=True)

                # JAZZCASH DYNAMIC QR DISPLAY (NO EXTERNAL LIBRARY NEEDED)
                if pay_method == "JazzCash":
                    temp_bill_id = f"AP-{datetime.now().strftime('%M%S')}"
                    qr_url = get_jazzcash_qr_url(grand_total, temp_bill_id)
                    
                    st.markdown("""
                    <div class='jazzcash-box'>
                        <b>🔴 JazzCash Merchant QR Code</b><br>
                        <small>Scan using JazzCash App to Pay</small>
                    </div>
                    """, unsafe_allow_html=True)
                    st.image(qr_url, caption=f"Scan & Pay Rs. {grand_total:,.2f}", width=180)

                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    if st.button("Empty Cart ❌", use_container_width=True):
                        st.session_state.cart = []
                        st.rerun()

                with b_col2:
                    if st.button("Checkout & Print 🚀", type="primary", use_container_width=True):
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
                            st.success(f"Transaction Completed! ID: {bill_id}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                        finally:
                            conn.close()
            else:
                st.info("Cart is currently empty.")

        # THERMAL RECEIPT DISPLAY
        if st.session_state.last_printed_bill:
            st.markdown("---")
            st.subheader(f"🖨️ Active Receipt Preview: `{st.session_state.last_printed_bill}`")
            rc_html = generate_receipt_html(st.session_state.last_printed_bill)
            st.components.v1.html(rc_html, height=450, scrolling=True)

    # TAB 2: STOCK ALERTS
    with staff_tabs[1]:
        st.subheader("🚨 Real-Time Inventory Alerts")
        conn = get_connection()
        alerts_df = pd.read_sql("SELECT name, category, price, stock, expiry_date FROM inventory", conn)
        conn.close()

        if not alerts_df.empty:
            low_stock = alerts_df[alerts_df['stock'] <= 10]
            if not low_stock.empty:
                st.warning("The following items require immediate restock:")
                st.dataframe(low_stock, use_container_width=True)
            else:
                st.success("All inventory stock levels are optimal.")
        else:
            st.info("Inventory is empty.")

    # TAB 3: RECEIPT HISTORY
    with staff_tabs[2]:
        st.subheader("📜 Recent Transactions")
        conn = get_connection()
        bills_df = pd.read_sql("SELECT bill_id, customer_name, grand_total, payment_method, sold_by, timestamp FROM sales GROUP BY bill_id ORDER BY MAX(id) DESC LIMIT 30", conn)
        conn.close()

        if not bills_df.empty:
            sel_bill = st.selectbox("Select Invoice to Re-Print", bills_df['bill_id'].tolist())
            if sel_bill:
                rc_html_history = generate_receipt_html(sel_bill)
                st.components.v1.html(rc_html_history, height=450, scrolling=True)

# ==================== ADMIN DASHBOARD ====================
elif st.session_state.role == "admin":
    st.markdown("<div class='main-header'>⚙️ Business Intelligence & Admin Dashboard</div>", unsafe_allow_html=True)
    
    tabs = st.tabs(["📊 Analytics & KPIs", "📦 Inventory Control", "👥 Staff Management"])

    # TAB 1: ANALYTICS & KPIS
    with tabs[0]:
        conn = get_connection()
        sales_df = pd.read_sql("SELECT * FROM sales ORDER BY id DESC", conn)
        conn.close()

        if not sales_df.empty:
            unique_bills = sales_df.drop_duplicates(subset=['bill_id'])
            total_rev = unique_bills['grand_total'].sum()
            total_items = sales_df['qty'].sum()
            total_tx = len(unique_bills)

            # Modern Metric Display Cards
            m1, m2, m3 = st.columns(3)
            m1.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-title'>Total Net Revenue</div>
                <div class='kpi-value'>Rs. {total_rev:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
            
            m2.markdown(f"""
            <div class='kpi-card' style='border-left-color: #28a745;'>
                <div class='kpi-title'>Items Sold</div>
                <div class='kpi-value'>{int(total_items):,} Units</div>
            </div>
            """, unsafe_allow_html=True)

            m3.markdown(f"""
            <div class='kpi-card' style='border-left-color: #ff9800;'>
                <div class='kpi-title'>Completed Sales</div>
                <div class='kpi-value'>{total_tx:,} Orders</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("📈 Top Performing Medicines")
            top_meds = sales_df.groupby('medicine_name')['qty'].sum().reset_index().sort_values(by='qty', ascending=False).head(7)
            st.bar_chart(data=top_meds, x='medicine_name', y='qty', use_container_width=True)

            st.markdown("---")
            st.subheader("📄 Sales Records Log")
            st.download_button(
                label="📥 Export Sales Report (CSV)",
                data=sales_df.to_csv(index=False).encode('utf-8'),
                file_name=f"Sales_Report_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv'
            )
            st.dataframe(sales_df, use_container_width=True)
        else:
            st.info("No sales recorded yet.")

    # TAB 2: INVENTORY MANAGEMENT
    with tabs[1]:
        st.subheader("📦 Inventory & Batch Management")
        c1, c2 = st.columns([1, 1.5])
        
        with c1:
            st.markdown("#### Add/Update Stock")
            m_name = st.text_input("Medicine Name")
            m_cat = st.selectbox("Category", ["Tablet", "Syrup", "Injection", "Capsule", "Ointment", "Other"])
            m_price = st.number_input("Unit Price (Rs.)", min_value=0.0, format="%.2f")
            m_stock = st.number_input("Stock Quantity", min_value=0, step=1)
            m_batch = st.text_input("Batch No.", value="B-101")
            m_expiry = st.date_input("Expiry Date", datetime.now() + timedelta(days=365))

            if st.button("Save Medicine Stock", use_container_width=True, type="primary"):
                if m_name:
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO inventory (name, category, price, stock, batch_no, expiry_date) VALUES (?, ?, ?, ?, ?, ?)",
                                  (m_name, m_cat, m_price, m_stock, m_batch, str(m_expiry)))
                        conn.commit()
                        st.success(f"Saved {m_name}!")
                    except sqlite3.IntegrityError:
                        c.execute("UPDATE inventory SET category=?, price=?, stock=stock+?, batch_no=?, expiry_date=? WHERE name=?",
                                  (m_cat, m_price, m_stock, m_batch, str(m_expiry), m_name))
                        conn.commit()
                        st.success(f"Updated Stock for {m_name}!")
                    finally:
                        conn.close()
                        st.rerun()

        with c2:
            st.markdown("#### Live Stock Table")
            conn = get_connection()
            inv_df = pd.read_sql("SELECT id AS 'ID', name AS 'Name', category AS 'Category', price AS 'Price', stock AS 'Stock', batch_no AS 'Batch', expiry_date AS 'Expiry' FROM inventory", conn)
            conn.close()
            st.dataframe(inv_df, use_container_width=True)

    # TAB 3: USER MANAGEMENT
    with tabs[2]:
        st.subheader("👥 System Accounts")
        u1, u2 = st.columns([1, 1.5])
        
        with u1:
            n_user = st.text_input("Username")
            n_pass = st.text_input("Password", type="password")
            if st.button("Create Account", use_container_width=True):
                if n_user and n_pass:
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'staff')", (n_user, n_pass))
                        conn.commit()
                        st.success(f"Staff User '{n_user}' created!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("User exists!")
                    finally:
                        conn.close()

        with u2:
            conn = get_connection()
            users_df = pd.read_sql("SELECT id, username, role FROM users", conn)
            conn.close()
            st.dataframe(users_df, use_container_width=True)
