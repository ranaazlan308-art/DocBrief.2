import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import time
import os
import platform
import threading
import hashlib
import hmac

# Windows direct printing support
if platform.system() == "Windows":
    try:
        import win32print
        import win32api
    except ImportError:
        win32print = None
else:
    win32print = None


# ---------------------------------------------------------
# 0. SECURITY & PASSWORD HASHING FUNCTIONS
# ---------------------------------------------------------
def hash_password(password: str) -> str:
    salt = b"A_PHARMA_SECURE_SALT"
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return hashed.hex()

def verify_password(stored_hash: str, input_password: str) -> bool:
    return hmac.compare_digest(stored_hash, hash_password(input_password))


# ---------------------------------------------------------
# 1. DIRECT THERMAL PRINTING FUNCTION (Threaded)
# ---------------------------------------------------------
def print_receipt_in_background(receipt_data):
    def _print_job():
        try:
            WIDTH = 32
            LINE = "=" * WIDTH
            DASH = "-" * WIDTH

            subtotal_str = f"Rs. {receipt_data['subtotal']:.2f}".rjust(18)
            discount_str = f"-Rs. {receipt_data['discount']:.2f}".rjust(18)
            tax_str = f"+Rs. {receipt_data['tax']:.2f}".rjust(18)
            grand_total_str = f"Rs. {receipt_data['grand_total']:.2f}".rjust(15)

            text_receipt = f"{LINE}\n"
            text_receipt += f"          A PHARMA          \n"
            text_receipt += f"  Multi-Counter POS System  \n"
            text_receipt += f"{LINE}\n"
            text_receipt += f"Bill #: {receipt_data['bill_id']}\n"
            text_receipt += f"Date  : {receipt_data['date']}\n"
            text_receipt += f"Cust  : {receipt_data['customer'][:16]}\n"
            text_receipt += f"Cashier: {receipt_data['sold_by'][:15]}\n"
            text_receipt += f"{DASH}\n"
            text_receipt += f"ITEM             QTY   AMOUNT\n"
            text_receipt += f"{DASH}\n"

            for item in receipt_data['items']:
                name = item['name'][:15].ljust(15)
                qty = f"x{item['qty']}".rjust(5)
                total = f"{item['total']:.2f}".rjust(10)
                text_receipt += f"{name} {qty} {total}\n"

            text_receipt += f"{DASH}\n"
            text_receipt += f"Subtotal: {subtotal_str}\n"
            text_receipt += f"Discount: {discount_str}\n"
            text_receipt += f"Tax     : {tax_str}\n"
            text_receipt += f"{DASH}\n"
            text_receipt += f"GRAND TOTAL: {grand_total_str}\n"
            text_receipt += f"{LINE}\n"
            text_receipt += f"   Thank You! Get Well Soon!   \n"
            text_receipt += f"{LINE}\n\n\n\n\n"

            filename = f"temp_receipt_{receipt_data['bill_id']}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(text_receipt)

            sys_name = platform.system()
            if sys_name == "Windows" and win32print is not None:
                try:
                    printer_name = win32print.GetDefaultPrinter()
                    hPrinter = win32print.OpenPrinter(printer_name)
                    try:
                        hJob = win32print.StartDocPrinter(hPrinter, 1, ("Receipt", None, "RAW"))
                        win32print.StartPagePrinter(hPrinter)
                        win32print.WritePrinter(hPrinter, text_receipt.encode('utf-8'))
                        win32print.EndPagePrinter(hPrinter)
                        win32print.EndDocPrinter(hPrinter)
                    finally:
                        win32print.ClosePrinter(hPrinter)
                except Exception:
                    os.system(f'print /d:PRN "{filename}" 2>NUL || notepad /p "{filename}"')
            elif sys_name in ["Linux", "Darwin"]:
                os.system(f'lp -o raw "{filename}"')
            else:
                os.system(f'notepad /p "{filename}"')

            time.sleep(2)
            if os.path.exists(filename):
                os.remove(filename)

        except Exception as e:
            print(f"Printing Error: {e}")

    thread = threading.Thread(target=_print_job)
    thread.daemon = True
    thread.start()


# ---------------------------------------------------------
# 2. PAGE CONFIGURATION & DATABASE MANAGEMENT
# ---------------------------------------------------------
st.set_page_config(
    page_title="A Pharma - Thermal POS",
    page_icon="💊",
    layout="wide"
)

# Custom CSS for Input Field Visibility Fix
st.markdown("""
<style>
    /* Input Boxes ko visible karne ki CSS */
    div[data-baseweb="input"] {
        border: 2px solid #2e6fdb !important;
        border-radius: 8px !important;
    }
    input {
        color: #000000 !important;
    }
</style>
""", unsafe_allow_html=True)

def get_connection():
    conn = sqlite3.connect("pharmacy_multi.db", timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

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
                    stock INTEGER)''')
    
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
    
    admin_hash = hash_password("admin123")
    staff_hash = hash_password("staff123")
    
    c.execute("""INSERT INTO users (username, password, role) VALUES ('admin', ?, 'admin') 
                 ON CONFLICT(username) DO UPDATE SET password=excluded.password, role='admin'""", (admin_hash,))
    c.execute("""INSERT INTO users (username, password, role) VALUES ('staff1', ?, 'staff') 
                 ON CONFLICT(username) DO UPDATE SET password=excluded.password, role='staff'""", (staff_hash,))
    
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# 3. AUTHENTICATION & SESSION STATE
# ---------------------------------------------------------
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'role' not in st.session_state:
    st.session_state.role = ""
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'last_receipt' not in st.session_state:
    st.session_state.last_receipt = None

def login(username_input, password_input):
    if not username_input or not password_input:
        st.error("⚠️ Username aur Password dono likhna zaroori hai!")
        return

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT username, password, role FROM users WHERE username=?", (username_input.strip(),))
    user = c.fetchone()
    conn.close()
    
    if user and verify_password(user[1], password_input):
        st.session_state.authenticated = True
        st.session_state.username = user[0]
        st.session_state.role = user[2]
        st.success("Login Successful!")
        st.rerun()
    else:
        st.error("❌ Galat Username ya Password!")

# ---------------------------------------------------------
# 4. LOGIN INTERFACE
# ---------------------------------------------------------
if not st.session_state.authenticated:
    st.title("🔒 A Pharma POS Login")
    st.markdown("---")
    
    # Simple Container for maximum visibility
    with st.container():
        st.subheader("🔑 Sign In To Proceed")
        
        u_input = st.text_input("👤 Username", placeholder="e.g. admin", key="login_user")
        p_input = st.text_input("🔑 Password", type="password", placeholder="e.g. admin123", key="login_pass")
        
        st.write("") # Spacing
        if st.button("🔓 Login to Terminal", use_container_width=True, type="primary"):
            login(u_input, p_input)

    st.markdown("---")
    st.info("""
    **Default Login Details:**
    * **Admin Account:** Username: `admin` | Password: `admin123`
    * **Staff Account:** Username: `staff1` | Password: `staff123`
    """)

# ---------------------------------------------------------
# 5. MAIN APP (AFTER LOGIN)
# ---------------------------------------------------------
else:
    st.sidebar.markdown("## 💊 **A Pharma**")
    st.sidebar.markdown(f"**User:** `{st.session_state.username}` | **Role:** `{st.session_state.role.upper()}`")

    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.session_state.role = ""
        st.session_state.cart = []
        st.session_state.last_receipt = None
        st.rerun()

    # ==================== STAFF DASHBOARD ====================
    if st.session_state.role == "staff":
        st.title("🛒 Billing Counter")
        
        conn = get_connection()
        inventory_df = pd.read_sql("SELECT id, name, category, price, stock FROM inventory WHERE stock > 0", conn)
        conn.close()

        col1, col2 = st.columns([1.3, 1])

        with col1:
            st.subheader("Select Items")
            cust_name = st.text_input("Customer Name", value="Walk-in Customer")
            
            if not inventory_df.empty:
                filter_col1, filter_col2 = st.columns(2)
                categories = ["All"] + list(inventory_df['category'].dropna().unique())
                
                with filter_col1:
                    selected_cat = st.selectbox("Category", categories)
                with filter_col2:
                    search_query = st.text_input("🔎 Search Medicine", "")

                filtered_df = inventory_df.copy()
                if selected_cat != "All":
                    filtered_df = filtered_df[filtered_df['category'] == selected_cat]
                if search_query:
                    filtered_df = filtered_df[filtered_df['name'].str.contains(search_query, case=False, na=False)]

                if not filtered_df.empty:
                    selected_med = st.selectbox("Medicine", filtered_df['name'].tolist())
                    med_info = filtered_df[filtered_df['name'] == selected_med].iloc[0]
                    
                    in_cart_qty = sum(item['qty'] for item in st.session_state.cart if item['name'] == selected_med)
                    available_stock = int(med_info['stock']) - in_cart_qty

                    st.info(f"Available Stock: **{available_stock}** | Price: **Rs. {med_info['price']:.2f}**")
                    
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
                            st.success(f"Added {qty} x {selected_med}")
                            st.rerun()
                    else:
                        st.warning("Out of stock!")
                else:
                    st.warning("No medicine found.")
            else:
                st.warning("No items in inventory.")

            st.subheader("Cart")
            if st.session_state.cart:
                cart_df = pd.DataFrame(st.session_state.cart)
                st.dataframe(cart_df[['name', 'price', 'qty', 'total']], use_container_width=True)
                
                if st.button("🗑️ Clear Cart"):
                    st.session_state.cart = []
                    st.rerun()
            else:
                st.caption("Cart is empty.")

        with col2:
            st.subheader("Checkout")
            if st.session_state.cart:
                subtotal = sum(item['total'] for item in st.session_state.cart)
                
                discount = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, value=10.0)
                tax = st.number_input("Tax (%)", min_value=0.0, max_value=100.0, value=3.0)

                discount_amount = subtotal * (discount / 100)
                tax_amount = (subtotal - discount_amount) * (tax / 100)
                grand_total = subtotal - discount_amount + tax_amount

                st.markdown(f"**Subtotal:** Rs. {subtotal:.2f}")
                st.markdown(f"**Discount ({discount:.1f}%):** -Rs. {discount_amount:.2f}")
                st.markdown(f"**Tax ({tax:.1f}%):** +Rs. {tax_amount:.2f}")
                st.markdown(f"### **Grand Total:** Rs. {grand_total:.2f}")

                if st.button("✅ Complete Sale & Thermal Print", use_container_width=True):
                    bill_id = f"BILL-{int(time.time())}"
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    conn = get_connection()
                    c = conn.cursor()

                    try:
                        for item in st.session_state.cart:
                            c.execute("""INSERT INTO sales 
                                        (bill_id, customer_name, medicine_name, qty, unit_price, total_price, subtotal, discount_pct, tax_pct, grand_total, sold_by, timestamp)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                      (bill_id, cust_name, item['name'], item['qty'], item['price'], item['total'],
                                       subtotal, discount, tax, grand_total, st.session_state.username, now))

                            c.execute("UPDATE inventory SET stock = stock - ? WHERE id = ?", (item['qty'], item['id']))

                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Transaction Error: {e}")
                    finally:
                        conn.close()

                    receipt_obj = {
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

                    st.session_state.last_receipt = receipt_obj
                    print_receipt_in_background(receipt_obj)

                    st.session_state.cart = []
                    st.success("Sale Complete! Sent to printer.")
                    st.rerun()

            if st.session_state.last_receipt:
                r = st.session_state.last_receipt
                st.markdown("---")
                st.subheader("🧾 Thermal Receipt Preview")

                receipt_container = st.container(border=True)
                with receipt_container:
                    st.markdown("<h3 style='text-align: center; margin:0;'>A PHARMA</h3>", unsafe_allow_html=True)
                    st.markdown("<p style='text-align: center; font-size:12px; margin:0;'>Multi-Counter POS System</p>", unsafe_allow_html=True)
                    st.caption(f"**Bill #:** {r['bill_id']} | **Date:** {r['date']}")
                    st.write(f"**Customer:** {r['customer']} | **Cashier:** {r['sold_by']}")
                    st.markdown("---")

                    item_rows = [{"Item": f"{item['name']} (x{item['qty']})", "Amount": f"Rs. {item['total']:.2f}"} for item in r['items']]
                    st.table(pd.DataFrame(item_rows))

                    st.markdown("---")
                    col_r1, col_r2 = st.columns(2)
                    with col_r1:
                        st.write("Subtotal:")
                        st.write("Discount:")
                        st.write("Tax:")
                        st.markdown("**Grand Total:**")
                    with col_r2:
                        st.write(f"Rs. {r['subtotal']:.2f}")
                        st.write(f"-Rs. {r['discount']:.2f}")
                        st.write(f"+Rs. {r['tax']:.2f}")
                        st.markdown(f"**Rs. {r['grand_total']:.2f}**")
                    
                    st.markdown("<p style='text-align: center; margin-top:15px; font-size:12px;'><i>Thank you! Get Well Soon!</i></p>", unsafe_allow_html=True)

                if st.button("🖨️ Reprint to Thermal Printer", use_container_width=True):
                    print_receipt_in_background(r)
                    st.success("Receipt sent to thermal printer!")

    # ==================== ADMIN DASHBOARD ====================
    elif st.session_state.role == "admin":
        st.title("⚙️ Admin Dashboard")

        conn = get_connection()
        low_stock_df = pd.read_sql("SELECT name, stock FROM inventory WHERE stock <= 5", conn)
        conn.close()

        if not low_stock_df.empty:
            st.error(f"⚠️ **Low Stock Alert ({len(low_stock_df)} items <= 5):** " + 
                     ", ".join([f"{row['name']} ({row['stock']})" for _, row in low_stock_df.iterrows()]))

        tab1, tab2, tab3, tab4 = st.tabs(["📦 Inventory Management", "📊 Sales Analytics", "👤 User Management", "💾 System Backup"])

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

            if st.button("💾 Save Item"):
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
                    st.success(f"'{med_name}' updated successfully.")
                    st.rerun()
                else:
                    st.error("Please enter a medicine name.")

            st.subheader("Current Stock")
            conn = get_connection()
            inv_df = pd.read_sql("SELECT * FROM inventory", conn)
            conn.close()

            if not inv_df.empty:
                st.dataframe(inv_df, use_container_width=True)
                st.markdown("---")
                q_col1, q_col2, q_col3 = st.columns([2, 1, 1])
                with q_col1:
                    selected_stock_med = st.selectbox("Select Medicine to Modify Stock", inv_df['name'].tolist())
                with q_col2:
                    new_stock_val = st.number_input("New Stock Value", min_value=0, step=1)
                with q_col3:
                    st.write("")
                    st.write("")
                    if st.button("Update Stock"):
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("UPDATE inventory SET stock = ? WHERE name = ?", (new_stock_val, selected_stock_med))
                        conn.commit()
                        conn.close()
                        st.success(f"Stock updated to {new_stock_val}")
                        st.rerun()
            else:
                st.info("Inventory is empty.")

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
                col_m2.metric("Total Bills", total_bills)
                col_m3.metric("Items Sold", items_sold)

                csv_data = sales_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Sales Data CSV",
                    data=csv_data,
                    file_name=f"sales_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

                st.dataframe(sales_df, use_container_width=True)
            else:
                st.info("No sales data recorded yet.")

        with tab3:
            st.subheader("Add New User")
            u_col1, u_col2, u_col3 = st.columns(3)
            with u_col1:
                new_u = st.text_input("Username")
            with u_col2:
                new_p = st.text_input("Password", type="password")
            with u_col3:
                new_r = st.selectbox("Role", ["staff", "admin"])

            if st.button("➕ Create Account"):
                if new_u and new_p:
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        hashed_p = hash_password(new_p)
                        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (new_u, hashed_p, new_r))
                        conn.commit()
                        st.success(f"User '{new_u}' added!")
                    except sqlite3.IntegrityError:
                        st.error("Username already exists!")
                    finally:
                        conn.close()
                else:
                    st.error("Username and Password are required.")

            st.subheader("Users")
            conn = get_connection()
            users_df = pd.read_sql("SELECT id, username, role FROM users", conn)
            conn.close()
            st.dataframe(users_df, use_container_width=True)

            if len(users_df) > 1:
                st.markdown("---")
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

        with tab4:
            st.subheader("💾 Database Backup & Security")
            st.write("Aap yahan se poora database file download kar sakte hain taake data secure rahe.")
            
            if os.path.exists("pharmacy_multi.db"):
                with open("pharmacy_multi.db", "rb") as db_file:
                    st.download_button(
                        label="📥 Download Full Database Backup (.db)",
                        data=db_file,
                        file_name=f"pharmacy_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                        mime="application/x-sqlite3",
                        use_container_width=True
                    )
