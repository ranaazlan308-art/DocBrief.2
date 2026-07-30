import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & CUSTOM STYLING
# ---------------------------------------------------------
st.set_page_config(
    page_title="A Pharma - Smart POS & Management",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for UI Enhancements
st.markdown("""
    <style>
        .main-header { font-size: 26px; font-weight: bold; color: #1E88E5; margin-bottom: 10px; }
        .card { background-color: #f8f9fa; border-radius: 10px; padding: 15px; border-left: 5px solid #1E88E5; margin-bottom: 10px; }
        .badge-danger { background-color: #ff4d4d; color: white; padding: 3px 8px; border-radius: 5px; font-weight: bold; font-size: 11px; }
        .badge-warning { background-color: #ffa500; color: white; padding: 3px 8px; border-radius: 5px; font-weight: bold; font-size: 11px; }
        .badge-success { background-color: #28a745; color: white; padding: 3px 8px; border-radius: 5px; font-weight: bold; font-size: 11px; }
        .stButton>button { border-radius: 6px; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. DATABASE MANAGEMENT & SAFE AUTO MIGRATION
# ---------------------------------------------------------
def get_connection():
    return sqlite3.connect("pharmacy_multi.db", timeout=20, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT,
                    role TEXT)''')
    
    # Inventory Table
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    category TEXT,
                    price REAL,
                    stock INTEGER,
                    batch_no TEXT DEFAULT 'B-001',
                    expiry_date DATE DEFAULT '2026-12-31')''')
    
    # Sales Table
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
    
    # Safely Add Missing Columns to Inventory Table
    c.execute("PRAGMA table_info(inventory)")
    inv_cols = [col[1] for col in c.fetchall()]
    
    if 'batch_no' not in inv_cols:
        try:
            c.execute("ALTER TABLE inventory ADD COLUMN batch_no TEXT DEFAULT 'B-001'")
        except sqlite3.OperationalError:
            pass
            
    if 'expiry_date' not in inv_cols:
        try:
            c.execute("ALTER TABLE inventory ADD COLUMN expiry_date DATE DEFAULT '2026-12-31'")
        except sqlite3.OperationalError:
            pass

    # Safely Add Missing Columns to Sales Table
    c.execute("PRAGMA table_info(sales)")
    sales_cols = [col[1] for col in c.fetchall()]
    
    if 'payment_method' not in sales_cols:
        try:
            c.execute("ALTER TABLE sales ADD COLUMN payment_method TEXT DEFAULT 'Cash'")
        except sqlite3.OperationalError:
            pass

    # Default Accounts
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin')")
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('staff1', 'staff123', 'staff')")
    
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# 3. RECEIPT HTML GENERATOR (THERMAL PRINT ENGINE)
# ---------------------------------------------------------
def generate_receipt_html(bill_id, print_auto=False):
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

    auto_print_script = "<script>window.onload = function() { window.print(); }</script>" if print_auto else ""

    html_code = f"""
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
        <button class="btn-print no-print" onclick="window.print()">🖨️ Print Thermal Receipt</button>
        
        <div class="text-center">
            <h2 style="margin:0; font-size:18px;">A PHARMA</h2>
            <p style="margin:2px 0;">Smart POS Pharmacy System<br>Helpline: +92-300-0000000</p>
        </div>
        
        <div class="line"></div>
        <div>
            <b>Bill ID:</b> {bill_id}<br>
            <b>Date:</b> {date_str}<br>
            <b>Customer:</b> {cust_name}<br>
            <b>Pay Mode:</b> {pay_mode}<br>
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
            <tbody>
                {items_rows}
            </tbody>
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
        
        {auto_print_script}
    </body>
    </html>
    """
    return html_code

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
        st.error("❌ Invalid Username or Password")

if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center;'>🔐 A Pharma Smart POS Login</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.info("💡 **Login Credentials:**\n- Admin: `admin` / `admin123`\n- Staff: `staff1` / `staff123`")
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("🚀 Login to Terminal", use_container_width=True, type="primary"):
            login(u, p)
    st.stop()

# ---------------------------------------------------------
# 5. SIDEBAR NAVIGATION
# ---------------------------------------------------------
st.sidebar.markdown("## 💊 **A PHARMA**")
st.sidebar.markdown(f"👤 **User:** `{st.session_state.username}`\n🔰 **Role:** `{st.session_state.role.upper()}`")
st.sidebar.markdown("---")

if st.sidebar.button("🔄 Sync System Data", use_container_width=True):
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
    st.markdown("<div class='main-header'>🛒 Staff Billing & Sales Terminal</div>", unsafe_allow_html=True)
    
    staff_tabs = st.tabs(["💳 New Counter Sale", "⚠️ Stock & Expiry Alerts", "📜 Re-Print Receipt"])

    # TAB 1: NEW BILL COUNTER
    with staff_tabs[0]:
        conn = get_connection()
        inventory_df = pd.read_sql("SELECT id, name, price, stock, batch_no, expiry_date FROM inventory WHERE stock > 0", conn)
        conn.close()

        col1, col2 = st.columns([1.3, 1])

        with col1:
            st.subheader("📋 Item Selection")
            cust_name = st.text_input("Customer Name", value="Walk-in Customer")
            
            if not inventory_df.empty:
                selected_med = st.selectbox("Search & Select Medicine", inventory_df['name'].tolist())
                med_info = inventory_df[inventory_df['name'] == selected_med].iloc[0]
                
                in_cart_qty = sum(item['qty'] for item in st.session_state.cart if item['name'] == selected_med)
                available_stock = int(med_info['stock']) - in_cart_qty

                # Display Info Badge
                st.markdown(f"""
                <div class='card'>
                    <b>Price:</b> Rs. {med_info['price']} | <b>Available Stock:</b> {available_stock}<br>
                    <b>Batch:</b> {med_info['batch_no']} | <b>Expiry:</b> {med_info['expiry_date']}
                </div>
                """, unsafe_allow_html=True)
                
                if available_stock > 0:
                    qty = st.number_input("Quantity", min_value=1, max_value=available_stock, value=1)

                    if st.button("➕ Add to Cart", use_container_width=True, type="primary"):
                        st.session_state.cart.append({
                            "name": selected_med,
                            "unit_price": float(med_info['price']),
                            "qty": int(qty),
                            "subtotal": float(med_info['price']) * int(qty)
                        })
                        st.toast(f"Added {selected_med} to cart!")
                        st.rerun()
                else:
                    st.error("⚠️ Stock is fully allocated or out of stock!")
            else:
                st.warning("⚠️ No available inventory found in database.")

        with col2:
            st.subheader("🛒 Current Cart Summary")
            if st.session_state.cart:
                cart_df = pd.DataFrame(st.session_state.cart)
                st.dataframe(cart_df[['name', 'qty', 'unit_price', 'subtotal']], use_container_width=True)
                
                subtotal = float(cart_df['subtotal'].sum())
                
                c_pay, c_disc, c_tax = st.columns(3)
                with c_pay:
                    pay_method = st.selectbox("Payment", ["Cash", "Card", "Online Wallet"])
                with c_disc:
                    discount_pct = st.number_input("Disc (%)", min_value=0.0, max_value=100.0, value=0.0)
                with c_tax:
                    tax_pct = st.number_input("Tax (%)", min_value=0.0, max_value=50.0, value=0.0)
                
                disc_val = subtotal * (discount_pct / 100.0)
                taxable_amt = subtotal - disc_val
                tax_val = taxable_amt * (tax_pct / 100.0)
                grand_total = taxable_amt + tax_val

                st.markdown(f"**Subtotal:** Rs. {subtotal:,.2f}")
                if discount_pct > 0:
                    st.markdown(f"**Discount:** -Rs. {disc_val:,.2f}")
                if tax_pct > 0:
                    st.markdown(f"**Tax:** +Rs. {tax_val:,.2f}")
                    
                st.markdown(f"### Grand Total: <span style='color:#1E88E5;'>Rs. {grand_total:,.2f}</span>", unsafe_allow_html=True)

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("Clear Cart ❌", use_container_width=True):
                        st.session_state.cart = []
                        st.rerun()

                with col_btn2:
                    if st.button("Complete & Print Bill 🚀", type="primary", use_container_width=True):
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
                            st.success(f"Sale Completed! Bill ID: {bill_id}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error saving sale: {e}")
                        finally:
                            conn.close()
            else:
                st.info("Cart is empty. Add medicines to proceed.")

        # DISPLAY PRINTABLE RECEIPT
        if st.session_state.last_printed_bill:
            st.markdown("---")
            st.subheader(f"🖨️ Printable Receipt: `{st.session_state.last_printed_bill}`")
            rc_html = generate_receipt_html(st.session_state.last_printed_bill, print_auto=False)
            st.components.v1.html(rc_html, height=450, scrolling=True)

    # TAB 2: ALERTS & NOTIFICATIONS
    with staff_tabs[1]:
        st.subheader("🔔 Low Stock & Expiry Warnings")
        conn = get_connection()
        alerts_df = pd.read_sql("SELECT name, category, price, stock, expiry_date FROM inventory", conn)
        conn.close()

        if not alerts_df.empty:
            low_stock = alerts_df[alerts_df['stock'] <= 10]
            st.markdown("#### 🚨 Low Stock Items (Less than 10 units)")
            if not low_stock.empty:
                st.dataframe(low_stock, use_container_width=True)
            else:
                st.success("All medicines have adequate stock levels.")
        else:
            st.info("No items in inventory.")

    # TAB 3: RE-PRINT HISTORY
    with staff_tabs[2]:
        st.subheader("📜 Search & Re-Print Historical Receipts")
        conn = get_connection()
        bills_df = pd.read_sql("SELECT bill_id, customer_name, grand_total, payment_method, sold_by, timestamp FROM sales GROUP BY bill_id ORDER BY MAX(id) DESC LIMIT 50", conn)
        conn.close()

        if not bills_df.empty:
            selected_bill = st.selectbox("Select Recent Bill ID", bills_df['bill_id'].tolist())
            if selected_bill:
                rc_html_history = generate_receipt_html(selected_bill, print_auto=False)
                st.components.v1.html(rc_html_history, height=450, scrolling=True)
        else:
            st.info("No historical sales found.")

# ==================== ADMIN DASHBOARD ====================
elif st.session_state.role == "admin":
    st.markdown("<div class='main-header'>⚙️ Admin Central Control & Analytics Dashboard</div>", unsafe_allow_html=True)
    
    tabs = st.tabs(["📊 Analytics & Sales", "📦 Inventory & Expiry", "👥 Staff Management"])

    # TAB 1: Live Analytics & Sales
    with tabs[0]:
        conn = get_connection()
        sales_df = pd.read_sql("SELECT * FROM sales ORDER BY id DESC", conn)
        conn.close()

        if not sales_df.empty:
            unique_bills = sales_df.drop_duplicates(subset=['bill_id'])
            total_rev = unique_bills['grand_total'].sum()
            total_items = sales_df['qty'].sum()
            total_tx = len(unique_bills)

            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Total Net Revenue", f"Rs. {total_rev:,.2f}")
            col_m2.metric("Total Items Sold", f"{int(total_items):,}")
            col_m3.metric("Total Transactions", f"{total_tx:,}")

            st.markdown("---")
            st.subheader("📈 Top Selling Medicines Chart")
            top_meds = sales_df.groupby('medicine_name')['qty'].sum().reset_index().sort_values(by='qty', ascending=False).head(7)
            st.bar_chart(data=top_meds, x='medicine_name', y='qty', use_container_width=True)

            st.markdown("---")
            st.subheader("📑 Sales Log & Export")
            
            # Export CSV
            csv_data = sales_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Complete Sales Report (CSV)",
                data=csv_data,
                file_name=f"Sales_Report_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv'
            )
            
            st.dataframe(sales_df, use_container_width=True)
        else:
            st.info("No sales transactions available to calculate analytics.")

    # TAB 2: Inventory & Expiry Management
    with tabs[1]:
        st.subheader("📦 Inventory Management & Expiry Tracking")
        col_a, col_b = st.columns([1, 1.5])
        
        with col_a:
            st.markdown("#### Add / Update Medicine Stock")
            med_name = st.text_input("Medicine Name")
            med_cat = st.selectbox("Category", ["Tablet", "Syrup", "Injection", "Capsule", "Ointment", "Other"])
            med_price = st.number_input("Unit Price (Rs.)", min_value=0.0, format="%.2f")
            med_stock = st.number_input("Stock Quantity", min_value=0, step=1)
            med_batch = st.text_input("Batch No.", value="B-101")
            med_expiry = st.date_input("Expiry Date", datetime.now() + timedelta(days=365))

            if st.button("Save Item to Inventory", use_container_width=True, type="primary"):
                if med_name:
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO inventory (name, category, price, stock, batch_no, expiry_date) VALUES (?, ?, ?, ?, ?, ?)",
                                  (med_name, med_cat, med_price, med_stock, med_batch, str(med_expiry)))
                        conn.commit()
                        st.success(f"Added {med_name} to Inventory!")
                    except sqlite3.IntegrityError:
                        c.execute("UPDATE inventory SET category=?, price=?, stock=stock+?, batch_no=?, expiry_date=? WHERE name=?",
                                  (med_cat, med_price, med_stock, med_batch, str(med_expiry), med_name))
                        conn.commit()
                        st.success(f"Updated Stock & Info for {med_name}!")
                    finally:
                        conn.close()
                        st.rerun()

        with col_b:
            st.markdown("#### Live Stock & Expiry Records")
            conn = get_connection()
            inv_df = pd.read_sql("SELECT id AS 'ID', name AS 'Name', category AS 'Category', price AS 'Price', stock AS 'Stock', batch_no AS 'Batch', expiry_date AS 'Expiry' FROM inventory", conn)
            conn.close()
            st.dataframe(inv_df, use_container_width=True)

    # TAB 3: User Accounts
    with tabs[2]:
        st.subheader("👥 Manage Staff Terminal Accounts")
        col_u1, col_u2 = st.columns([1, 1.5])
        
        with col_u1:
            new_user = st.text_input("New Staff Username")
            new_pass = st.text_input("New Staff Password", type="password")
            if st.button("Create Staff Account", use_container_width=True):
                if new_user and new_pass:
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'staff')", (new_user, new_pass))
                        conn.commit()
                        st.success(f"Staff Account '{new_user}' Created Successfully!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("⚠️ User already exists!")
                    finally:
                        conn.close()

        with col_u2:
            conn = get_connection()
            users_df = pd.read_sql("SELECT id, username, role FROM users", conn)
            conn.close()
            st.dataframe(users_df, use_container_width=True)
