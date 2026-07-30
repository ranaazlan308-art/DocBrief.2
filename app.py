import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io

# ReportLab Canvas Engine (Zero-Error PDF Builder)
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="A.M Pharma POS & Inventory System", 
    page_icon="💊", 
    layout="wide"
)

# --- DATABASE CONFIGURATION & HELPER ---
DB_NAME = "pharmacy.db"

def get_db_connection():
    """Thread-safe SQLite connection creator"""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize DB and guarantee table schema update"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Medicines Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            category TEXT,
            price REAL,
            stock INTEGER
        )
    ''')

    # 2. Sales Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id TEXT,
            customer_name TEXT,
            medicine_name TEXT,
            quantity INTEGER,
            unit_price REAL,
            total_price REAL,
            subtotal REAL DEFAULT 0.0,
            discount_pct REAL DEFAULT 0.0,
            tax_pct REAL DEFAULT 0.0,
            grand_total REAL DEFAULT 0.0,
            date TEXT
        )
    ''')

    # 3. Admins Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')

    # Safe Auto-Migration: Purani DB file me missing columns inject karna
    c.execute("PRAGMA table_info(sales)")
    existing_cols = [col[1] for col in c.fetchall()]
    
    cols_to_check = {
        'bill_id': "TEXT DEFAULT 'INV-001'",
        'customer_name': "TEXT DEFAULT 'Walk-in'",
        'subtotal': "REAL DEFAULT 0.0",
        'discount_pct': "REAL DEFAULT 0.0",
        'tax_pct': "REAL DEFAULT 0.0",
        'grand_total': "REAL DEFAULT 0.0"
    }

    for col_name, col_type in cols_to_check.items():
        if col_name not in existing_cols:
            try:
                c.execute(f"ALTER TABLE sales ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass

    # Default Admin Check (Username: admin | Password: admin123)
    c.execute("SELECT * FROM admins WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO admins (username, password) VALUES (?, ?)", ('admin', 'admin123'))
    
    conn.commit()
    conn.close()

# Run Database Setup
init_db()

# --- SESSION STATE INITIALIZATION ---
if 'cart' not in st.session_state:
    st.session_state['cart'] = []
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- ULTRA-ROBUST PDF INVOICE GENERATOR ---
def generate_multi_item_pdf(bill_id, customer_name, cart_items, subtotal, discount_pct, tax_pct, grand_total, bill_date):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Header Section
    p.setFillColor(colors.HexColor('#1E3A8A'))
    p.rect(0, height - 80, width, 80, fill=True, stroke=False)
    
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 20)
    p.drawCentredString(width / 2.0, height - 35, "PHARMACARE PHARMACY")
    p.setFont("Helvetica", 10)
    p.drawCentredString(width / 2.0, height - 55, "Official Sales Tax Invoice & Cash Receipt")

    # Meta Data Section
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 10)
    
    y = height - 110
    p.drawString(40, y, f"Customer Name: {str(customer_name)}")
    p.drawString(380, y, f"Invoice No: #{str(bill_id)}")
    
    y -= 18
    p.drawString(40, y, f"Date & Time: {str(bill_date)}")
    p.drawString(380, y, "Payment Mode: Counter Cash")

    p.setStrokeColor(colors.HexColor('#CBD5E1'))
    p.setLineWidth(1)
    p.line(40, y - 10, width - 40, y - 10)

    # Items Table Header
    y -= 35
    p.setFillColor(colors.HexColor('#1E3A8A'))
    p.rect(40, y - 5, width - 80, 20, fill=True, stroke=False)
    
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(50, y, "#")
    p.drawString(80, y, "Item Description")
    p.drawRightString(320, y, "Qty")
    p.drawRightString(420, y, "Price (PKR)")
    p.drawRightString(550, y, "Total (PKR)")

    # Table Items List
    p.setFillColor(colors.black)
    p.setFont("Helvetica", 9)
    y -= 20
    
    for idx, item in enumerate(cart_items, 1):
        if y < 120:
            p.showPage()
            y = height - 50

        p.drawString(50, y, str(idx))
        p.drawString(80, y, str(item['medicine'])[:35])
        p.drawRightString(320, y, str(item['qty']))
        p.drawRightString(420, y, f"{float(item['unit_price']):.2f}")
        p.drawRightString(550, y, f"{float(item['total']):.2f}")
        
        y -= 15
        p.setStrokeColor(colors.HexColor('#F1F5F9'))
        p.line(40, y + 10, width - 40, y + 10)

    # Calculations Summary Block
    y -= 15
    disc_val = subtotal * (discount_pct / 100)
    taxable_amt = subtotal - disc_val
    tax_val = taxable_amt * (tax_pct / 100)

    p.setFont("Helvetica", 9)
    p.drawRightString(420, y, "Subtotal:")
    p.drawRightString(550, y, f"PKR {subtotal:.2f}")

    y -= 15
    p.drawRightString(420, y, f"Discount ({discount_pct:.1f}%):")
    p.drawRightString(550, y, f"- PKR {disc_val:.2f}")

    y -= 15
    p.drawRightString(420, y, f"Sales Tax / GST ({tax_pct:.1f}%):")
    p.drawRightString(550, y, f"+ PKR {tax_val:.2f}")

    # Grand Total Box
    y -= 25
    p.setFillColor(colors.HexColor('#1E3A8A'))
    p.rect(340, y - 5, 230, 22, fill=True, stroke=False)
    
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 11)
    p.drawRightString(430, y, "Grand Total:")
    p.drawRightString(550, y, f"PKR {grand_total:.2f}")

    # Footer
    p.setFillColor(colors.HexColor('#64748B'))
    p.setFont("Helvetica-Oblique", 8)
    p.drawCentredString(width / 2.0, 30, "Thank you for shopping with PharmaCare! Wish you good health.")

    p.showPage()
    p.save()
    
    buffer.seek(0)
    return buffer

# --- SIDEBAR MENU ---
st.sidebar.title("💊 PharmaCare POS")

if st.session_state['logged_in']:
    st.sidebar.success("🔒 Admin Logged In")
    if st.sidebar.button("Logout 🚪", use_container_width=True):
        st.session_state['logged_in'] = False
        st.rerun()
else:
    st.sidebar.info("👤 Staff Mode")

nav_options = ["🧾 Billing Counter"]
if st.session_state['logged_in']:
    nav_options.extend(["📦 Medicine Inventory", "📊 Sales Reports", "⚙️ Admin Settings"])
else:
    nav_options.append("🔑 Admin Login")

menu = st.sidebar.radio("Navigation", nav_options)

# =========================================================
# MODULE 1: BILLING COUNTER
# =========================================================
if menu == "🧾 Billing Counter":
    st.title("🧾 Billing Counter")
    
    conn = get_db_connection()
    try:
        med_df = pd.read_sql_query("SELECT * FROM medicines WHERE stock > 0", conn)
    except Exception:
        med_df = pd.DataFrame()
    conn.close()
    
    if med_df.empty:
        st.warning("⚠️ Inventory me medicines mojood nahi hain. Admin Login karke stock add karein.")
    else:
        col1, col2 = st.columns([1, 1.5])
        
        with col1:
            st.subheader("➕ Add Items")
            customer_name = st.text_input("Customer Name", value="Walk-in Customer")
            
            selected_med = st.selectbox("Medicine Select Karein", med_df['name'].tolist())
            med_info = med_df[med_df['name'] == selected_med].iloc[0]
            
            max_stock = int(med_info['stock'])
            unit_price = float(med_info['price'])
            
            in_cart_qty = sum(item['qty'] for item in st.session_state['cart'] if item['medicine'] == selected_med)
            avail_stock = max_stock - in_cart_qty
            
            st.info(f"Price: **PKR {unit_price:.2f}** | Stock: **{avail_stock}**")
            
            if avail_stock > 0:
                qty = st.number_input("Quantity", min_value=1, max_value=avail_stock, value=1, step=1)
                if st.button("Cart me Add Karein 🛒", use_container_width=True):
                    st.session_state['cart'].append({
                        'medicine': selected_med,
                        'qty': qty,
                        'unit_price': unit_price,
                        'total': qty * unit_price
                    })
                    st.success("Item Cart me add ho gaya!")
                    st.rerun()
            else:
                st.error("Is item ka saara stock cart me add ho chuka hai!")

        with col2:
            st.subheader("🛒 Current Cart")
            if not st.session_state['cart']:
                st.info("Cart khali hai.")
            else:
                cart_df = pd.DataFrame(st.session_state['cart'])
                st.dataframe(cart_df[['medicine', 'qty', 'unit_price', 'total']], use_container_width=True)
                
                subtotal = float(cart_df['total'].sum())
                
                dc1, dc2 = st.columns(2)
                with dc1:
                    discount_pct = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, value=0.0)
                with dc2:
                    tax_pct = st.number_input("Tax / GST (%)", min_value=0.0, max_value=50.0, value=0.0)
                
                disc_val = subtotal * (discount_pct / 100)
                tax_val = (subtotal - disc_val) * (tax_pct / 100)
                grand_total = (subtotal - disc_val) + tax_val
                
                st.markdown(f"### Grand Total: **PKR {grand_total:.2f}**")
                
                c_btn1, c_btn2 = st.columns(2)
                with c_btn1:
                    if st.button("Cart Khali Karein ❌", use_container_width=True):
                        st.session_state['cart'] = []
                        st.rerun()
                with c_btn2:
                    if st.button("Checkout & Bill Banayein 🚀", type="primary", use_container_width=True):
                        bill_id = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        today_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        conn = get_db_connection()
                        c = conn.cursor()
                        
                        # Double Guard against Column mismatch errors
                        for item in st.session_state['cart']:
                            c.execute("UPDATE medicines SET stock = stock - ? WHERE name = ?", (item['qty'], item['medicine']))
                            
                            try:
                                c.execute('''
                                    INSERT INTO sales (bill_id, customer_name, medicine_name, quantity, unit_price, total_price, subtotal, discount_pct, tax_pct, grand_total, date)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (bill_id, customer_name, item['medicine'], item['qty'], item['unit_price'], item['total'], subtotal, discount_pct, tax_pct, grand_total, today_date))
                            except sqlite3.OperationalError:
                                # Safe Fallback for older database tables
                                c.execute('''
                                    INSERT INTO sales (medicine_name, quantity, total_price, date)
                                    VALUES (?, ?, ?, ?)
                                ''', (item['medicine'], item['qty'], item['total'], today_date))
                                
                        conn.commit()
                        conn.close()
                        
                        st.session_state['last_bill'] = {
                            'bill_id': bill_id, 'customer': customer_name,
                            'cart': list(st.session_state['cart']), 'subtotal': subtotal,
                            'discount_pct': discount_pct, 'tax_pct': tax_pct,
                            'grand_total': grand_total, 'date': today_date
                        }
                        st.session_state['cart'] = []
                        st.success(f"Bill Generated! Invoice ID: #{bill_id}")
                        st.rerun()

            if 'last_bill' in st.session_state:
                st.divider()
                lb = st.session_state['last_bill']
                
                pdf_bytes = generate_multi_item_pdf(
                    lb['bill_id'], lb['customer'], lb['cart'], 
                    lb['subtotal'], lb['discount_pct'], lb['tax_pct'], 
                    lb['grand_total'], lb['date']
                )
                
                st.subheader("📄 Printed Bill PDF")
                st.download_button(
                    label=f"📥 Download Printable Invoice PDF (#{lb['bill_id']})",
                    data=pdf_bytes,
                    file_name=f"Invoice_{lb['bill_id']}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

# =========================================================
# MODULE 2: ADMIN LOGIN
# =========================================================
elif menu == "🔑 Admin Login":
    st.title("🔑 Admin Login")
    st.info("Default Login -> Username: `admin` | Password: `admin123`")
    
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login", use_container_width=True):
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM admins WHERE username = ? AND password = ?", (u, p))
            row = c.fetchone()
            conn.close()
            
            if row:
                st.session_state['logged_in'] = True
                st.success("Login Successful!")
                st.rerun()
            else:
                st.error("Ghalat Username ya Password!")

# =========================================================
# MODULE 3: MEDICINE INVENTORY
# =========================================================
elif menu == "📦 Medicine Inventory":
    st.title("📦 Medicine Inventory")
    t1, t2, t3 = st.tabs(["📋 View Stock", "✏️ Update Stock", "➕ Add New Medicine"])
    
    with t1:
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT id AS 'ID', name AS 'Name', category AS 'Category', price AS 'Price', stock AS 'Stock' FROM medicines", conn)
        conn.close()
        st.dataframe(df, use_container_width=True)
        
    with t2:
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT * FROM medicines", conn)
        conn.close()
        
        if not df.empty:
            med_sel = st.selectbox("Medicine Select Karein", df['name'].tolist())
            row = df[df['name'] == med_sel].iloc[0]
            
            with st.form("edit_form"):
                new_price = st.number_input("Price (PKR)", value=float(row['price']))
                new_stock = st.number_input("Stock", value=int(row['stock']))
                
                if st.form_submit_button("Update Karein", use_container_width=True):
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("UPDATE medicines SET price = ?, stock = ? WHERE id = ?", (new_price, new_stock, int(row['id'])))
                    conn.commit()
                    conn.close()
                    st.success("Stock Updated!")
                    st.rerun()
                    
            if st.button(f"Delete {med_sel} 🗑️", use_container_width=True):
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("DELETE FROM medicines WHERE id = ?", (int(row['id']),))
                conn.commit()
                conn.close()
                st.success("Medicine Deleted!")
                st.rerun()

    with t3:
        with st.form("add_form"):
            name = st.text_input("Medicine Name")
            cat = st.selectbox("Category", ["Tablet", "Syrup", "Injection", "Capsule", "Ointment", "Other"])
            price = st.number_input("Price", min_value=0.0)
            stock = st.number_input("Stock Quantity", min_value=1, step=1)
            
            if st.form_submit_button("Add Medicine ➕", use_container_width=True):
                if name:
                    try:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("INSERT INTO medicines (name, category, price, stock) VALUES (?, ?, ?, ?)", (name, cat, price, stock))
                        conn.commit()
                        conn.close()
                        st.success("Medicine Added!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Yeh Medicine pehle se majood hai!")

# =========================================================
# MODULE 4: SALES REPORTS
# =========================================================
elif menu == "📊 Sales Reports":
    st.title("📊 Sales Reports")
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM sales ORDER BY id DESC", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Koi Sales Record nahi mila.")

# =========================================================
# MODULE 5: ADMIN SETTINGS
# =========================================================
elif menu == "⚙️ Admin Settings":
    st.title("⚙️ Admin Settings")
    with st.form("pass_form"):
        old_p = st.text_input("Purana Password", type="password")
        new_p = st.text_input("Naya Password", type="password")
        if st.form_submit_button("Password Change Karein"):
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM admins WHERE username = 'admin' AND password = ?", (old_p,))
            if c.fetchone():
                c.execute("UPDATE admins SET password = ? WHERE username = 'admin'", (new_p,))
                conn.commit()
                st.success("Password Updated!")
            else:
                st.error("Purana Password ghalat hai!")
            conn.close()
