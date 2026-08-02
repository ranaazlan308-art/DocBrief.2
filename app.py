import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import time

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & STYLING
# ---------------------------------------------------------
st.set_page_config(
    page_title="A Pharma - Multi-Counter POS",
    page_icon="💊",
    layout="wide"
)

# Thermal Receipt Styling
RECEIPT_CSS = """
<style>
    .receipt-box {
        width: 300px;
        font-family: 'Courier New', Courier, monospace;
        font-size: 12px;
        padding: 10px;
        border: 1px solid #ccc;
        background-color: #fff;
        color: #000;
        margin: 0 auto;
    }
    .receipt-header {
        text-align: center;
        margin-bottom: 8px;
    }
    .receipt-header h2 {
        margin: 0;
        font-size: 18px;
        font-weight: bold;
    }
    .receipt-line {
        border-bottom: 1px dashed #000;
        margin: 5px 0;
    }
    .receipt-table {
        width: 100%;
        border-collapse: collapse;
    }
    .receipt-table th, .receipt-table td {
        text-align: left;
        padding: 2px 0;
    }
    .receipt-table .num {
        text-align: right;
    }
    .text-center { text-align: center; }
    .text-right { text-align: right; }
</style>
"""
st.markdown(RECEIPT_CSS, unsafe_allow_html=True)

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
                    discount_pct REAL DEFAULT 10.0,
                    tax_pct REAL DEFAULT 3.0,
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
# 3. AUTHENTICATION & SESSION STATE
# ---------------------------------------------------------
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.role = ""
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'last_receipt' not in st.session_state:
    st.session_state.last_receipt = None

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

# ---------------------------------------------------------
# 4. LOGIN INTERFACE
# ---------------------------------------------------------
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
# 5. HEADER & SIDEBAR MENU
# ---------------------------------------------------------
st.sidebar.markdown("## 💊 **A Pharma**")
st.sidebar.markdown(f"**User:** `{st.session_state.username}` | **Role:** `{st.session_state.role.upper()}`")

if st.sidebar.button("🔄 Sync & Refresh Data", use_container_width=True):
    st.rerun()

if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.cart = []
    st.session_state.last_receipt = None
    st.rerun()

# ---------------------------------------------------------
# 6. DASHBOARDS ACCORDING TO ROLE
# ---------------------------------------------------------

# ==================== STAFF DASHBOARD ====================
if st.session_state.role == "staff":
    st.title("🛒 Staff Billing Counter - A Pharma")
    
    conn = get_connection()
    inventory_df = pd.read_sql("SELECT id, name, category, price, stock FROM inventory WHERE stock > 0", conn)
    conn.close()

    col1, col2 = st.columns([1.3, 1])

    with col1:
        st.subheader("Add Medicines to Bill")
        cust_name = st.text_input("Customer Name", value="Walk-in Customer")
        
        if not inventory_df.empty:
            # Category Filter & Search
            filter_col1, filter_col2 = st.columns(2)
            categories = ["All"] + list(inventory_df['category'].dropna().unique())
            
            with filter_col1:
                selected_cat = st.selectbox("Filter Category", categories)
            with filter_col2:
                search_query = st.text_input("🔎 Search Medicine", "")

            filtered_df = inventory_df.copy()
            if selected_cat != "All":
                filtered_df = filtered_df[filtered_df['category'] == selected_cat]
            if search_query:
                filtered_df = filtered_df[filtered_df['name'].str.contains(search_query, case=False, na=False)]

            if not filtered_df.empty:
                selected_med = st.selectbox("Select Medicine", filtered_df['name'].tolist())
                med_info = filtered_df[filtered_df['name'] == selected_med].iloc[0]
                
                in_cart_qty = sum(item['qty'] for item in st.session_state.cart if item['name'] == selected_med)
                available_stock = int(med_info['stock']) - in_cart_qty

                st.info(f"Available Stock: **{available_stock}** | Unit Price: **Rs. {med_info['price']:.2f}**")
                
                if available_stock > 0:
                    qty = st.number_input("Quantity", min_value=1, max_value=available_stock, value=1)
                    if st.button("➕ Add to Cart", use_container_width=True):
                        found = False
                        for item in st.session_state.cart:
                            if item['name'] == selected_med:
                                item['qty'] += qty
                                item['total'] = item['qty'] * item['price']
                                found = True
                                break
                        if not found:
                            st.session_state.cart.append({
                                'id': med_info['id'],
                                'name': selected_med,
                                'price': med_info['price'],
                                'qty': qty,
                                'total': qty * med_info['price']
                            })
                        st.success(f"Added {qty} x {selected_med} to cart.")
                        st.rerun()
                else:
                    st.warning("Selected medicine is out of stock!")
            else:
                st.warning("No medicines match your search criteria.")
        else:
            st.warning("No available inventory found. Please contact Administrator.")

        # Display Current Cart
        st.subheader("Cart Items")
        if st.session_state.cart:
            cart_df = pd.DataFrame(st.session_state.cart)
            st.dataframe(cart_df[['name', 'price', 'qty', 'total']], use_container_width=True)
            
            if st.button("🗑️ Clear Cart"):
                st.session_state.cart = []
                st.rerun()
        else:
            st.caption("Cart is currently empty.")

    with col2:
        st.subheader("Checkout & Receipt")
        if st.session_state.cart:
            subtotal = sum(item['total'] for item in st.session_state.cart)
            
            # ✨ Auto 10% Discount and Auto 3% Tax Added (Default Values)
            discount = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, value=10.0)
            tax = st.number_input("Tax (%)", min_value=0.0, max_value=100.0, value=3.0)

            discount_amount = subtotal * (discount / 100)
            tax_amount = (subtotal - discount_amount) * (tax / 100)
            grand_total = subtotal - discount_amount + tax_amount

            st.markdown(f"**Subtotal:** Rs. {subtotal:.2f}")
            st.markdown(f"**Discount ({discount:.1f}%):** -Rs. {discount_amount:.2f}")
            st.markdown(f"**Tax ({tax:.1f}%):** +Rs. {tax_amount:.2f}")
            st.markdown(f"### **Grand Total:** Rs. {grand_total:.2f}")

            if st.button("✅ Complete Sale & Print Receipt", use_container_width=True):
                bill_id = f"BILL-{int(time.time())}"
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                conn = get_connection()
                c = conn.cursor()

                for item in st.session_state.cart:
                    c.execute("""INSERT INTO sales 
                                (bill_id, customer_name, medicine_name, qty, unit_price, total_price, subtotal, discount_pct, tax_pct, grand_total, sold_by, timestamp)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                              (bill_id, cust_name, item['name'], item['qty'], item['price'], item['total'],
                               subtotal, discount, tax, grand_total, st.session_state.username, now))

                    c.execute("UPDATE inventory SET stock = stock - ? WHERE id = ?", (item['qty'], item['id']))

                conn.commit()
                conn.close()

                st.session_state.last_receipt = {
                    'bill_id': bill_id,
                    'customer': cust_name,
                    'items': st.session_state.cart.copy(),
                    'subtotal': subtotal,
                    'discount': discount_amount,
                    'tax': tax_amount,
                    'grand_total': grand_total,
                    'date': now,
                    'sold_by': st.session_state.username
                }

                st.session_state.cart = []
                st.success("Sale processed successfully!")
                st.rerun()

        # Thermal receipt layout
        if st.session_state.last_receipt:
            r = st.session_state.last_receipt
            items_html = ""
            for item in r['items']:
                items_html += f"""
                <tr>
                    <td>{item['name']} x{item['qty']}</td>
                    <td class="num">{item['total']:.2f}</td>
                </tr>
                """

            receipt_html = f"""
            <div class="receipt-box">
                <div class="receipt-header">
                    <h2>A PHARMA</h2>
                    <p>Multi-Counter POS System</p>
                    <p>Bill #: {r['bill_id']}<br>Date: {r['date']}</p>
                </div>
                <div class="receipt-line"></div>
                <p><strong>Customer:</strong> {r['customer']}<br><strong>Cashier:</strong> {r['sold_by']}</p>
                <div class="receipt-line"></div>
                <table class="receipt-table">
                    <thead>
                        <tr><th>Item</th><th class="num">Amount</th></tr>
                    </thead>
                    <tbody>
                        {items_html}
                    </tbody>
                </table>
                <div class="receipt-line"></div>
                <table class="receipt-table">
                    <tr><td>Subtotal</td><td class="num">{r['subtotal']:.2f}</td></tr>
                    <tr><td>Discount</td><td class="num">-{r['discount']:.2f}</td></tr>
                    <tr><td>Tax</td><td class="num">+{r['tax']:.2f}</td></tr>
                    <tr><td><strong>Grand Total</strong></td><td class="num"><strong>Rs. {r['grand_total']:.2f}</strong></td></tr>
                </table>
                <div class="receipt-line"></div>
                <p class="text-center">Thank you! Get Well Soon!</p>
            </div>
            """
            st.markdown(receipt_html, unsafe_allow_html=True)

# ==================== ADMIN DASHBOARD ====================
elif st.session_state.role == "admin":
    st.title("⚙️ Admin Dashboard - A Pharma")

    # Low Stock Warning Alert
    conn = get_connection()
    low_stock_df = pd.read_sql("SELECT name, stock FROM inventory WHERE stock <= 5", conn)
    conn.close()

    if not low_stock_df.empty:
        st.error(f"⚠️ **Low Stock Alert ({len(low_stock_df)} items remaining <= 5):** " + 
                 ", ".join([f"{row['name']} ({row['stock']} left)" for _, row in low_stock_df.iterrows()]))

    tab1, tab2, tab3 = st.tabs(["📦 Inventory Management", "📊 Sales Analytics", "👤 User Management"])

    # TAB 1: INVENTORY MANAGEMENT
    with tab1:
        st.subheader("Add / Update Medicine")
        col_a, col_b, col_c, col_d = st.columns(4)
        
        with col_a:
            med_name = st.text_input("Medicine Name")
        with col_b:
            category = st.text_input("Category", value="General")
        with col_c:
            price = st.number_input("Price (Rs.)", min_value=0.0, step=0.5)
        with col_d:
            stock = st.number_input("Stock Qty", min_value=0, step=1)

        if st.button("💾 Save Medicine"):
            if med_name:
                conn = get_connection()
                c = conn.cursor()
                c.execute("""INSERT INTO inventory (name, category, price, stock) 
                             VALUES (?, ?, ?, ?)
                             ON CONFLICT(name) DO UPDATE SET 
                             category=excluded.category, 
                             price=excluded.price, 
                             stock=stock + excluded.stock""", (med_name, category, price, stock))
                conn.commit()
                conn.close()
                st.success(f"Inventory item '{med_name}' updated successfully.")
                st.rerun()
            else:
                st.error("Please enter a valid medicine name.")

        st.subheader("Current Stock Inventory")
        conn = get_connection()
        inv_df = pd.read_sql("SELECT * FROM inventory", conn)
        conn.close()

        if not inv_df.empty:
            st.dataframe(inv_df, use_container_width=True)
            
            st.markdown("---")
            st.caption("⚡ Quick Stock Adjuster")
            q_col1, q_col2, q_col3 = st.columns([2, 1, 1])
            with q_col1:
                selected_stock_med = st.selectbox("Select Medicine to Modify Stock", inv_df['name'].tolist())
            with q_col2:
                new_stock_val = st.number_input("New Total Stock", min_value=0, step=1)
            with q_col3:
                st.write("")
                st.write("")
                if st.button("Update Stock"):
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("UPDATE inventory SET stock = ? WHERE name = ?", (new_stock_val, selected_stock_med))
                    conn.commit()
                    conn.close()
                    st.success(f"Updated {selected_stock_med} stock to {new_stock_val}")
                    st.rerun()
        else:
            st.info("No items currently in inventory.")

    # TAB 2: SALES ANALYTICS
    with tab2:
        st.subheader("Sales Reports")
        conn = get_connection()
        sales_df = pd.read_sql("SELECT * FROM sales ORDER BY timestamp DESC", conn)
        conn.close()

        if not sales_df.empty:
            col_m1, col_m2, col_m3 = st.columns(3)
            total_rev = sales_df.drop_duplicates(subset=['bill_id'])['grand_total'].sum()
            total_bills = sales_df['bill_id'].nunique()
            items_sold = sales_df['qty'].sum()

            col_m1.metric("Total Revenue", f"Rs. {total_rev:,.2f}")
            col_m2.metric("Total Transactions", total_bills)
            col_m3.metric("Total Items Sold", items_sold)

            # CSV Download Option
            csv_data = sales_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Sales Data as CSV",
                data=csv_data,
                file_name=f"sales_report_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

            st.subheader("Recent Transactions")
            st.dataframe(sales_df, use_container_width=True)
        else:
            st.info("No sales data recorded yet.")

    # TAB 3: USER MANAGEMENT
    with tab3:
        st.subheader("Create New User")
        u_col1, u_col2, u_col3 = st.columns(3)
        with u_col1:
            new_u = st.text_input("New Username")
        with u_col2:
            new_p = st.text_input("New Password", type="password")
        with u_col3:
            new_r = st.selectbox("Role", ["staff", "admin"])

        if st.button("➕ Create Account"):
            if new_u and new_p:
                conn = get_connection()
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (new_u, new_p, new_r))
                    conn.commit()
                    st.success(f"User '{new_u}' added successfully!")
                except sqlite3.IntegrityError:
                    st.error("Username already exists!")
                finally:
                    conn.close()
            else:
                st.error("Username and Password are required.")

        st.subheader("System Users")
        conn = get_connection()
        users_df = pd.read_sql("SELECT id, username, role FROM users", conn)
        conn.close()
        st.dataframe(users_df, use_container_width=True)

        # Remove Users Section
        if len(users_df) > 1:
            st.markdown("---")
            st.caption("🗑️ Delete User Account")
            d_col1, d_col2 = st.columns([2, 1])
            with d_col1:
                other_users = users_df[users_df['username'] != st.session_state.username]['username'].tolist()
                user_to_delete = st.selectbox("Select User to Remove", other_users)
            with d_col2:
                st.write("")
                st.write("")
                if st.button("❌ Delete User"):
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("DELETE FROM users WHERE username = ?", (user_to_delete,))
                    conn.commit()
                    conn.close()
                    st.success(f"User '{user_to_delete}' removed.")
                    st.rerun()
