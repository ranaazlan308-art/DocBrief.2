import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & STYLING
# ---------------------------------------------------------
st.set_page_config(
    page_title="Multi-Counter Pharmacy POS",
    page_icon="💊",
    layout="wide"
)

# Live Sync: Har 5 Seconds baad screen/data refresh hoga (Auto-Polling)
st_autorefresh(interval=5000, key="datarefresh")

# ---------------------------------------------------------
# 2. DATABASE MANAGEMENT
# ---------------------------------------------------------
def get_connection():
    # Production ke liye PostgreSQL link switch karein
    # Example: return psycopg2.connect("postgresql://user:pass@localhost:5432/pharmacy_db")
    conn = sqlite3.connect("pharmacy_multi.db", check_same_thread=False)
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
    
    # Default Admin & Staff create karein agar na hon
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
    col1, col2 = st.columns([1, 2])
    with col1:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login to Terminal", use_container_width=True):
            login(u, p)
    st.stop()

# ---------------------------------------------------------
# 5. HEADER & USER BAR
# ---------------------------------------------------------
st.sidebar.markdown(f"### 👤 Active User: `{st.session_state.username}`")
st.sidebar.markdown(f"**Role:** `{st.session_state.role.upper()}`")
if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.rerun()

# ---------------------------------------------------------
# 6. DASHBOARD ACCORDING TO ROLE
# ---------------------------------------------------------

# ==================== STAFF DASHBOARD ====================
if st.session_state.role == "staff":
    st.title("🛒 Staff Billing Counter")
    
    conn = get_connection()
    inventory_df = pd.read_sql("SELECT id, name, price, stock FROM inventory WHERE stock > 0", conn)
    conn.close()

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Add Medicines to Bill")
        if not inventory_df.empty:
            selected_med = st.selectbox("Select Medicine", inventory_df['name'].tolist())
            med_info = inventory_df[inventory_df['name'] == selected_med].iloc[0]
            
            st.info(f"Available Stock: **{med_info['stock']}** | Unit Price: **Rs. {med_info['price']}**")
            qty = st.number_input("Quantity", min_value=1, max_value=int(med_info['stock']), value=1)

            if st.button("➕ Add to Cart"):
                st.session_state.cart.append({
                    "name": selected_med,
                    "price": med_info['price'],
                    "qty": qty,
                    "subtotal": med_info['price'] * qty
                })
                st.success(f"{selected_med} added to cart.")
        else:
            st.warning("No medicines currently in stock.")

    with col2:
        st.subheader("Current Bill")
        if st.session_state.cart:
            cart_df = pd.DataFrame(st.session_state.cart)
            st.dataframe(cart_df[['name', 'qty', 'subtotal']], use_container_width=True)
            
            total_bill = cart_df['subtotal'].sum()
            st.markdown(f"### Total: **Rs. {total_bill:,.2f}**")

            if st.button("🖨️ Complete & Print Bill", type="primary", use_container_width=True):
                conn = get_connection()
                c = conn.cursor()
                for item in st.session_state.cart:
                    # Save Sale Record
                    c.execute("INSERT INTO sales (medicine_name, qty, total_price, sold_by, timestamp) VALUES (?, ?, ?, ?, ?)",
                              (item['name'], item['qty'], item['subtotal'], st.session_state.username, datetime.now()))
                    # Update Stock Immediately
                    c.execute("UPDATE inventory SET stock = stock - ? WHERE name = ?", (item['qty'], item['name']))
                
                conn.commit()
                conn.close()
                st.session_state.cart = []
                st.success("Sale Recorded & Stock Deducted!")
                st.rerun()
        else:
            st.write("Cart is empty.")

# ==================== ADMIN DASHBOARD ====================
elif st.session_state.role == "admin":
    st.title("⚙️ Admin Central Control & Live Monitoring")
    
    tabs = st.tabs(["📊 Live Sales & Analytics", "📦 Stock Management", "👥 User Accounts"])

    # TAB 1: Real-time Sales Monitor
    with tabs[0]:
        st.subheader("Real-Time Multi-Counter Sales Stream")
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
            st.info("No sales transactions recorded today.")

    # TAB 2: Stock Management
    with tabs[1]:
        st.subheader("Inventory Control")
        col_a, col_b = st.columns([1, 2])
        
        with col_a:
            st.markdown("#### Add / Update Stock")
            med_name = st.text_input("Medicine Name")
            med_cat = st.text_input("Category")
            med_price = st.number_input("Unit Price", min_value=0.0, format="%.2f")
            med_stock = st.number_input("Stock Quantity", min_value=0, step=1)

            if st.button("Save Item to Inventory"):
                if med_name:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("""INSERT INTO inventory (name, category, price, stock) 
                                 VALUES (?, ?, ?, ?)
                                 ON CONFLICT(name) DO UPDATE SET 
                                 category=excluded.category,
                                 price=excluded.price,
                                 stock=inventory.stock + excluded.stock""",
                              (med_name, med_cat, med_price, med_stock))
                    conn.commit()
                    conn.close()
                    st.success(f"{med_name} inventory updated successfully!")
                    st.rerun()

        with col_b:
            st.markdown("#### Live Inventory Status")
            conn = get_connection()
            inv_df = pd.read_sql("SELECT * FROM inventory", conn)
            conn.close()
            st.dataframe(inv_df, use_container_width=True)

    # TAB 3: User Accounts
    with tabs[2]:
        st.subheader("Add Counter Staff")
        new_user = st.text_input("Staff Username")
        new_pass = st.text_input("Staff Password", type="password")
        if st.button("Create Staff Account"):
            if new_user and new_pass:
                conn = get_connection()
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'staff')", (new_user, new_pass))
                    conn.commit()
                    st.success(f"Staff Account '{new_user}' created!")
                except Exception as e:
                    st.error(f"Error: {e}")
                finally:
                    conn.close()
