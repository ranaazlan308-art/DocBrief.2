import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import time

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="A Pharma - Multi-Counter POS",
    page_icon="💊",
    layout="wide"
)

# ---------------------------------------------------------
# 2. DATABASE MANAGEMENT
# ---------------------------------------------------------
def get_connection():
    conn = sqlite3.connect("pharmacy_multi.db", timeout=20, check_same_thread=False)
    return conn

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
                    stock INTEGER)''')
    
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
                    sold_by TEXT,
                    timestamp DATETIME)''')
    
    # Default Accounts
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin')")
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('staff1', 'staff123', 'staff')")
    
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# 3. RECEIPT HTML GENERATOR & PRINT ENGINE
# ---------------------------------------------------------
def generate_receipt_html(bill_id, print_auto=False):
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM sales WHERE bill_id=?", conn, params=(bill_id,))
    conn.close()
    
    if df.empty:
        return "<p>Bill not found!</p>"

    row0 = df.iloc[0]
    cust_name = row0['customer_name']
    biller = row0['sold_by']
    date_str = row0['timestamp']
    subtotal = row0['subtotal']
    discount_pct = row0['discount_pct']
    tax_pct = row0['tax_pct']
    grand_total = row0['grand_total']

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
                background-color: #008CBA;
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 13px;
                margin-bottom: 10px;
                width: 100%;
            }}
        </style>
    </head>
    <body>
        <button class="btn-print no-print" onclick="window.print()">🖨️ Click Here to Print Receipt</button>
        
        <div class="text-center">
            <h2 style="margin:0; font-size:18px;">A PHARMA</h2>
            <p style="margin:2px 0;">Retail & Wholesale Pharmacy<br>Tel: +92-300-0000000</p>
        </div>
        
        <div class="line"></div>
        <div>
            <b>Bill #:</b> {bill_id}<br>
            <b>Date:</b> {date_str}<br>
            <b>Customer:</b> {cust_name}<br>
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
            <p style="margin:0;">Thank You For Shopping!<br>*** Get Well Soon ***</p>
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
        st.error("Invalid Username or Password")

if not st.session_state.authenticated:
    st.title("🔒 A Pharma POS Login")
    st.info("Default Login -> **Admin:** `admin` / `admin123` | **Staff:** `staff1` / `staff123`")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login to Terminal", use_container_width=True):
            login(u, p)
    st.stop()

# ---------------------------------------------------------
# 5. SIDEBAR MENU
# ---------------------------------------------------------
st.sidebar.markdown("## 💊 **A PHARMA**")
st.sidebar.markdown(f"**User:** `{st.session_state.username}` | **Role:** `{st.session_state.role.upper()}`")

if st.sidebar.button("🔄 Sync & Refresh Data", use_container_width=True):
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
    st.title("🛒 Staff Billing Counter - A Pharma")
    
    staff_tabs = st.tabs(["💳 New Bill Counter", "📜 Sales History & Re-Print"])

    # TAB 1: NEW BILL
    with staff_tabs[0]:
        conn = get_connection()
        inventory_df = pd.read_sql("SELECT id, name, price, stock FROM inventory WHERE stock > 0", conn)
        conn.close()

        col1, col2 = st.columns([1.3, 1])

        with col1:
            st.subheader("Add Medicines to Bill")
            cust_name = st.text_input("Customer Name", value="Walk-in Customer")
            
            if not inventory_df.empty:
                selected_med = st.selectbox("Select Medicine", inventory_df['name'].tolist())
                med_info = inventory_df[inventory_df['name'] == selected_med].iloc[0]
                
                in_cart_qty = sum(item['qty'] for item in st.session_state.cart if item['name'] == selected_med)
                available_stock = int(med_info['stock']) - in_cart_qty

                st.info(f"Available Stock: **{available_stock}** | Unit Price: **Rs. {med_info['price']}**")
                
                if available_stock > 0:
                    qty = st.number_input("Quantity", min_value=1, max_value=available_stock, value=1)

                    if st.button("➕ Add to Cart", use_container_width=True):
                        st.session_state.cart.append({
                            "name": selected_med,
                            "unit_price": float(med_info['price']),
                            "qty": int(qty),
                            "subtotal": float(med_info['price']) * int(qty)
                        })
                        st.success(f"{selected_med} added to cart.")
                        st.rerun()
                else:
                    st.error("Selected medicine ka stock khatam ho chuka hai!")
            else:
                st.warning("⚠️ No medicines currently available in stock.")

        with col2:
            st.subheader("Current Bill Summary")
            if st.session_state.cart:
                cart_df = pd.DataFrame(st.session_state.cart)
                st.dataframe(cart_df[['name', 'qty', 'unit_price', 'subtotal']], use_container_width=True)
                
                subtotal = float(cart_df['subtotal'].sum())
                
                disc_col, tax_col = st.columns(2)
                with disc_col:
                    discount_pct = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
                with tax_col:
                    tax_pct = st.number_input("Tax / GST (%)", min_value=0.0, max_value=50.0, value=0.0, step=1.0)
                
                disc_val = subtotal * (discount_pct / 100.0)
                taxable_amt = subtotal - disc_val
                tax_val = taxable_amt * (tax_pct / 100.0)
                grand_total = taxable_amt + tax_val

                st.markdown(f"**Subtotal:** Rs. {subtotal:,.2f}")
                if discount_pct > 0:
                    st.markdown(f"**Discount ({discount_pct}%):** -Rs. {disc_val:,.2f}")
                if tax_pct > 0:
                    st.markdown(f"**Tax ({tax_pct}%):** +Rs. {tax_val:,.2f}")
                    
                st.markdown(f"### Grand Total: **Rs. {grand_total:,.2f}**")

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("Clear Cart ❌", use_container_width=True):
                        st.session_state.cart = []
                        st.rerun()

                with col_btn2:
                    if st.button("Complete & Save Bill 🚀", type="primary", use_container_width=True):
                        bill_id = f"AP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        conn = get_connection()
                        c = conn.cursor()
                        try:
                            for item in st.session_state.cart:
                                c.execute('''INSERT INTO sales 
                                             (bill_id, customer_name, medicine_name, qty, unit_price, total_price, subtotal, discount_pct, tax_pct, grand_total, sold_by, timestamp) 
                                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                          (bill_id, cust_name, item['name'], item['qty'], item['unit_price'], item['subtotal'], subtotal, discount_pct, tax_pct, grand_total, st.session_state.username, now_str))
                                
                                c.execute("UPDATE inventory SET stock = stock - ? WHERE name = ?", (item['qty'], item['name']))
                            
                            conn.commit()
                            st.session_state.last_printed_bill = bill_id
                            st.session_state.cart = []
                            st.success(f"Sale Recorded Successfully! Bill ID: {bill_id}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error saving sale: {e}")
                        finally:
                            conn.close()
            else:
                st.write("Cart is empty.")

        # DISPLAY PRINTABLE RECEIPT
        if st.session_state.last_printed_bill:
            st.markdown("---")
            st.subheader(f"🖨️ Receipt for Bill: `{st.session_state.last_printed_bill}`")
            rc_html = generate_receipt_html(st.session_state.last_printed_bill, print_auto=False)
            st.components.v1.html(rc_html, height=450, scrolling=True)

    # TAB 2: RE-PRINT HISTORY
    with staff_tabs[1]:
        st.subheader("Previous Bills & Thermal Re-Printing")
        conn = get_connection()
        bills_df = pd.read_sql("SELECT DISTINCT bill_id, customer_name, grand_total, sold_by, timestamp FROM sales ORDER BY id DESC LIMIT 50", conn)
        conn.close()

        if not bills_df.empty:
            selected_bill = st.selectbox("Select Bill to Print / View", bills_df['bill_id'].tolist())
            if selected_bill:
                rc_html_history = generate_receipt_html(selected_bill, print_auto=False)
                st.components.v1.html(rc_html_history, height=450, scrolling=True)
        else:
            st.info("No bills generated yet.")

# ==================== ADMIN DASHBOARD ====================
elif st.session_state.role == "admin":
    st.title("⚙️ Admin Central Control - A Pharma")
    
    tabs = st.tabs(["📊 Live Sales & Printing", "📦 Stock Management", "👥 Staff Accounts"])

    # TAB 1: Live Sales Monitor
    with tabs[0]:
        st.subheader("Multi-Counter Live Sales Stream")
        conn = get_connection()
        sales_df = pd.read_sql("SELECT * FROM sales ORDER BY id DESC", conn)
        conn.close()

        if not sales_df.empty:
            m1, m2, m3 = st.columns(3)
            unique_bills = sales_df.drop_duplicates(subset=['bill_id'])
            total_rev = unique_bills['grand_total'].sum()
                
            m1.metric("Total Net Revenue", f"Rs. {total_rev:,.2f}")
            m2.metric("Total Items Sold", int(sales_df['qty'].sum()))
            m3.metric("Total Transactions", len(unique_bills))

            st.dataframe(sales_df, use_container_width=True)

            st.markdown("---")
            st.subheader("🔍 Print Any Historical Receipt")
            search_bill = st.selectbox("Select Bill ID", unique_bills['bill_id'].tolist())
            if search_bill:
                admin_rc_html = generate_receipt_html(search_bill, print_auto=False)
                st.components.v1.html(admin_rc_html, height=450, scrolling=True)
        else:
            st.info("No sales transactions recorded yet.")

    # TAB 2: Stock Management
    with tabs[1]:
        st.subheader("Inventory Control")
        col_a, col_b = st.columns([1, 1.5])
        
        with col_a:
            st.markdown("#### Add / Update Medicine")
            med_name = st.text_input("Medicine Name")
            med_cat = st.selectbox("Category", ["Tablet", "Syrup", "Injection", "Capsule", "Ointment", "Other"])
            med_price = st.number_input("Unit Price (Rs.)", min_value=0.0, format="%.2f")
            med_stock = st.number_input("Stock Quantity", min_value=0, step=1)

            if st.button("Save Item to Inventory", use_container_width=True):
                if med_name:
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO inventory (name, category, price, stock) VALUES (?, ?, ?, ?)",
                                  (med_name, med_cat, med_price, med_stock))
                        conn.commit()
                        st.success(f"Added {med_name} to Inventory!")
                    except sqlite3.IntegrityError:
                        c.execute("UPDATE inventory SET category=?, price=?, stock=stock+? WHERE name=?",
                                  (med_cat, med_price, med_stock, med_name))
                        conn.commit()
                        st.success(f"Updated Stock & Price for {med_name}!")
                    finally:
                        conn.close()
                        st.rerun()

        with col_b:
            st.markdown("#### Live Inventory Status")
            conn = get_connection()
            inv_df = pd.read_sql("SELECT id AS 'ID', name AS 'Name', category AS 'Category', price AS 'Price', stock AS 'Stock' FROM inventory", conn)
            conn.close()
            st.dataframe(inv_df, use_container_width=True)

    # TAB 3: User Accounts
    with tabs[2]:
        st.subheader("Manage Staff Accounts")
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
                        st.success(f"Staff Account '{new_user}' Created!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Is username se account pehle se majood hai!")
                    finally:
                        conn.close()

        with col_u2:
            conn = get_connection()
            users_df = pd.read_sql("SELECT id, username, role FROM users", conn)
            conn.close()
            st.dataframe(users_df, use_container_width=True)
