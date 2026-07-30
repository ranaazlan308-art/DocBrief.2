import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import time

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & STYLING
# ---------------------------------------------------------
st.set_page_config(
    page_title="Multi-Counter Pharmacy POS",
    page_icon="💊",
    layout="wide"
)

# ---------------------------------------------------------
# 2. DATABASE MANAGEMENT (With Timeout Guard)
# ---------------------------------------------------------
def get_connection():
    # timeout=20 dene se 5 PCs ek sath data write kar sakte hain file lock hue bagair
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
                    medicine_name TEXT,
                    qty INTEGER,
                    total_price REAL,
                    sold_by TEXT,
                    timestamp DATETIME)''')
    
    # Default Admin & Staff Accounts
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
    st.title("🔒 Pharmacy Network Login")
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
st.sidebar.markdown(f"### 👤 Active User: `{st.session_state.username}`")
st.sidebar.markdown(f"**Role:** `{st.session_state.role.upper()}`")

# Manual Sync Button for Admin & Staff
if st.sidebar.button("🔄 Sync & Refresh Data", use_container_width=True):
    st.rerun()

if st.sidebar.button(" Logout", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.cart = []
    st.rerun()

# ---------------------------------------------------------
# 6. DASHBOARDS ACCORDING TO ROLE
# ---------------------------------------------------------

# ==================== STAFF DASHBOARD ====================
if st.session_state.role == "staff":
    st.title("🛒 Staff Billing Counter")
    
    conn = get_connection()
    inventory_df = pd.read_sql("SELECT id, name, price, stock FROM inventory WHERE stock > 0", conn)
    conn.close()

    col1, col2 = st.columns([1.5, 1])

    with col1:
        st.subheader("Add Medicines to Bill")
        if not inventory_df.empty:
            selected_med = st.selectbox("Select Medicine", inventory_df['name'].tolist())
            med_info = inventory_df[inventory_df['name'] == selected_med].iloc[0]
            
            # Stock Validation Check
            in_cart_qty = sum(item['qty'] for item in st.session_state.cart if item['name'] == selected_med)
            available_stock = int(med_info['stock']) - in_cart_qty

            st.info(f"Available Stock: **{available_stock}** | Unit Price: **Rs. {med_info['price']}**")
            
            if available_stock > 0:
                qty = st.number_input("Quantity", min_value=1, max_value=available_stock, value=1)

                if st.button("➕ Add to Cart", use_container_width=True):
                    st.session_state.cart.append({
                        "name": selected_med,
                        "price": float(med_info['price']),
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
        st.subheader("Current Bill")
        if st.session_state.cart:
            cart_df = pd.DataFrame(st.session_state.cart)
            st.dataframe(cart_df[['name', 'qty', 'subtotal']], use_container_width=True)
            
            total_bill = cart_df['subtotal'].sum()
            st.markdown(f"### Total: **Rs. {total_bill:,.2f}**")

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("Clear Cart", use_container_width=True):
                    st.session_state.cart = []
                    st.rerun()

            with col_btn2:
                if st.button(" Complete Sale", type="primary", use_container_width=True):
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        for item in st.session_state.cart:
                            # Save Sale Record
                            c.execute("INSERT INTO sales (medicine_name, qty, total_price, sold_by, timestamp) VALUES (?, ?, ?, ?, ?)",
                                      (item['name'], item['qty'], item['subtotal'], st.session_state.username, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            # Update Stock
                            c.execute("UPDATE inventory SET stock = stock - ? WHERE name = ?", (item['qty'], item['name']))
                        
                        conn.commit()
                        st.session_state.cart = []
                        st.success("Sale Recorded & Stock Deducted!")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving sale: {e}")
                    finally:
                        conn.close()
        else:
            st.write("Cart is empty.")

# ==================== ADMIN DASHBOARD ====================
elif st.session_state.role == "admin":
    st.title("⚙️ Admin Central Control")
    
    tabs = st.tabs(["📊 Live Sales Analytics", "📦 Stock Management", "👥 Staff Accounts"])

    # TAB 1: Real-time Sales Monitor
    with tabs[0]:
        st.subheader("Multi-Counter Live Sales Stream")
        conn = get_connection()
        sales_df = pd.read_sql("SELECT * FROM sales ORDER BY id DESC", conn)
        conn.close()

        if not sales_df.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Revenue", f"Rs. {sales_df['total_price'].sum():,.2f}")
            m2.metric("Total Items Sold", int(sales_df['qty'].sum()))
            m3.metric("Total Transactions", len(sales_df))

            st.dataframe(sales_df, use_container_width=True)
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
