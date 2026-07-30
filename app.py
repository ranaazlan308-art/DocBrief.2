import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io

# ReportLab Imports for Professional PDF Invoices
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="PharmaCare POS & Inventory System", 
    page_icon="💊", 
    layout="wide"
)

# --- DATABASE CONFIGURATION & AUTO-MIGRATION ---
DB_NAME = "pharmacy.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Medicines Table Creation
    c.execute('''
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            category TEXT,
            price REAL,
            stock INTEGER
        )
    ''')

    # Sales Table Creation
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

    # Admin Credentials Table Creation
    c.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')

    # Safe Auto-Migration for Old DB Schemas
    existing_columns = [col[1] for col in c.execute("PRAGMA table_info(sales)").fetchall()]
    new_cols = ['bill_id', 'customer_name', 'subtotal', 'discount_pct', 'tax_pct', 'grand_total']
    
    for col_name in new_cols:
        if col_name not in existing_columns:
            if col_name in ['bill_id', 'customer_name']:
                c.execute(f"ALTER TABLE sales ADD COLUMN {col_name} TEXT DEFAULT 'N/A'")
            else:
                c.execute(f"ALTER TABLE sales ADD COLUMN {col_name} REAL DEFAULT 0.0")

    # Default Admin Credentials (Username: admin | Password: admin123)
    c.execute("SELECT * FROM admins WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO admins (username, password) VALUES (?, ?)", ('admin', 'admin123'))
    
    conn.commit()
    conn.close()

# Initialize Database Schema
init_db()

# --- SESSION STATE MANAGEMENT ---
if 'cart' not in st.session_state:
    st.session_state['cart'] = []
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- MULTI-ITEM PDF INVOICE GENERATOR ---
def generate_multi_item_pdf(bill_id, customer_name, cart_items, subtotal, discount_pct, tax_pct, grand_total, bill_date):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    # Document Header Title
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, alignment=1, textColor=colors.HexColor('#1E3A8A'))
    story.append(Paragraph("<b>PHARMACARE PHARMACY</b>", title_style))
    story.append(Paragraph("Official Tax Invoice & Sales Receipt", ParagraphStyle('Sub', parent=styles['Normal'], alignment=1, textColor=colors.gray)))
    story.append(Spacer(1, 15))

    # Metadata Section
    meta_data = [
        [f"Customer Name: {customer_name}", f"Date & Time: {bill_date}"],
        [f"Invoice No: #{bill_id}", "Payment Method: Cash / Counter"]
    ]
    t_meta = Table(meta_data, colWidths=[250, 250])
    t_meta.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#334155')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 15))

    # Purchased Items Table Layout
    table_data = [["#", "Item Description", "Qty", "Unit Price (PKR)", "Total (PKR)"]]
    for idx, item in enumerate(cart_items, 1):
        table_data.append([
            str(idx),
            item['medicine'],
            str(item['qty']),
            f"{item['unit_price']:.2f}",
            f"{item['total']:.2f}"
        ])

    disc_val = subtotal * (discount_pct / 100)
    taxable_amt = subtotal - disc_val
    tax_val = taxable_amt * (tax_pct / 100)

    # Financial Break-up Section
    table_data.append(["", "", "", "Subtotal:", f"PKR {subtotal:.2f}"])
    table_data.append(["", "", "", f"Discount ({discount_pct:.1f}%):", f"- PKR {disc_val:.2f}"])
    table_data.append(["", "", "", f"GST / Sales Tax ({tax_pct:.1f}%):", f"+ PKR {tax_val:.2f}"])
    table_data.append(["", "", "", "Grand Total:", f"PKR {grand_total:.2f}"])

    t_items = Table(table_data, colWidths=[30, 200, 50, 110, 110])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-5), 0.5, colors.HexColor('#CBD5E1')),
        ('FONTNAME', (3,-4), (4,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (3,-1), (4,-1), colors.HexColor('#E2E8F0')),
    ]))
    story.append(t_items)
    story.append(Spacer(1, 25))

    # Invoice Footer
    footer_style = ParagraphStyle('FooterStyle', parent=styles['Normal'], fontSize=9, alignment=1, textColor=colors.gray)
    story.append(Paragraph("Thank you for your business! Wish you good health.", footer_style))
    story.append(Paragraph("This is an auto-generated official digital tax receipt.", footer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

# --- SIDEBAR NAVIGATION CONTROL ---
st.sidebar.title("💊 PharmaCare POS")

# Role status UI
if st.session_state['logged_in']:
    st.sidebar.success("🔒 Admin Logged In")
    if st.sidebar.button("Logout 🚪", use_container_width=True):
        st.session_state['logged_in'] = False
        st.rerun()
else:
    st.sidebar.info("👤 Staff Mode (Limited Access)")

# Accessible Modules mapping
nav_options = ["🧾 Multi-Item Billing Counter"]
if st.session_state['logged_in']:
    nav_options.extend(["📦 Medicine Inventory", "📊 Sales Reports", "⚙️ Admin Settings"])
else:
    nav_options.append("🔑 Admin Login")

menu = st.sidebar.radio("Navigation Menu", nav_options)

# =========================================================
# MODULE 1: MULTI-ITEM BILLING & TAX/DISCOUNT COUNTER
# =========================================================
if menu == "🧾 Multi-Item Billing Counter":
    st.title("🧾 Billing Counter & Auto Tax/Discount Calculator")
    
    conn = get_db_connection()
    med_df = pd.read_sql_query("SELECT * FROM medicines WHERE stock > 0", conn)
    conn.close()
    
    if med_df.empty:
        st.warning("⚠️ Inventory khali hai ya koi item in-stock nahi hai. Admin panel se medicine add karein!")
    else:
        col_left, col_right = st.columns([1.2, 1.8])
        
        # Left Panel: Medicine & Cart Addition Controls
        with col_left:
            st.subheader("➕ Add Items to Cart")
            customer_name = st.text_input("Customer Name", value="Walk-in Customer")
            
            selected_med = st.selectbox("Select Medicine", med_df['name'].tolist())
            med_info = med_df[med_df['name'] == selected_med].iloc[0]
            
            max_stock = int(med_info['stock'])
            unit_price = float(med_info['price'])
            
            # Stock reserved in active session cart
            in_cart_qty = sum(item['qty'] for item in st.session_state['cart'] if item['medicine'] == selected_med)
            available_stock = max_stock - in_cart_qty
            
            st.info(f"💰 Unit Price: **PKR {unit_price:.2f}** | 📦 Stock Left: **{available_stock}**")
            
            if available_stock > 0:
                qty = st.number_input("Select Quantity", min_value=1, max_value=available_stock, value=1, step=1)
                
                if st.button("Add to Cart 🛒", type="secondary", use_container_width=True):
                    st.session_state['cart'].append({
                        'medicine': selected_med,
                        'qty': qty,
                        'unit_price': unit_price,
                        'total': qty * unit_price
                    })
                    st.success(f"Added {qty}x {selected_med} to cart!")
                    st.rerun()
            else:
                st.error("⚠️ Is item ka tamam stock aapke cart me add ho chuka hai!")

        # Right Panel: Cart Details & Financial Calculation
        with col_right:
            st.subheader("🛒 Current Cart Breakdown")
            
            if not st.session_state['cart']:
                st.info("Cart khali hai. Select karke item add karein.")
            else:
                cart_df = pd.DataFrame(st.session_state['cart'])
                st.dataframe(
                    cart_df[['medicine', 'qty', 'unit_price', 'total']].rename(columns={
                        'medicine': 'Medicine', 'qty': 'Qty', 'unit_price': 'Price (PKR)', 'total': 'Total (PKR)'
                    }),
                    use_container_width=True
                )
                
                # Auto Calculator Section
                st.markdown("### 🧮 Auto Calculator (Tax & Discount)")
                subtotal = float(cart_df['total'].sum())
                
                d_col, t_col = st.columns(2)
                with d_col:
                    discount_pct = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
                with t_col:
                    tax_pct = st.number_input("GST / Sales Tax (%)", min_value=0.0, max_value=50.0, value=17.0, step=0.5)
                
                # Financial Calculations
                discount_val = subtotal * (discount_pct / 100)
                taxable_amount = subtotal - discount_val
                tax_val = taxable_amount * (tax_pct / 100)
                grand_total = taxable_amount + tax_val
                
                # Real-Time UI Metrics Display
                st.divider()
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Subtotal", f"PKR {subtotal:.2f}")
                m2.metric(f"Discount ({discount_pct}%)", f"- PKR {discount_val:.2f}")
                m3.metric(f"GST ({tax_pct}%)", f"+ PKR {tax_val:.2f}")
                m4.metric("Grand Total", f"PKR {grand_total:.2f}")
                st.divider()
                
                btn_col1, btn_col2 = st.columns(2)
                
                with btn_col1:
                    if st.button("Clear Cart ❌", use_container_width=True):
                        st.session_state['cart'] = []
                        st.rerun()
                        
                with btn_col2:
                    if st.button("Checkout & Process Bill 🚀", type="primary", use_container_width=True):
                        bill_id = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        today_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        conn = get_db_connection()
                        c = conn.cursor()
                        
                        for item in st.session_state['cart']:
                            # Update DB Stock
                            c.execute("UPDATE medicines SET stock = stock - ? WHERE name = ?", (item['qty'], item['medicine']))
                            # Insert Sales Ledger
                            c.execute('''
                                INSERT INTO sales (bill_id, customer_name, medicine_name, quantity, unit_price, total_price, subtotal, discount_pct, tax_pct, grand_total, date) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (bill_id, customer_name, item['medicine'], item['qty'], item['unit_price'], item['total'], subtotal, discount_pct, tax_pct, grand_total, today_date))
                        
                        conn.commit()
                        conn.close()
                        
                        # Store in state for PDF generator
                        st.session_state['last_checkout'] = {
                            'bill_id': bill_id,
                            'customer': customer_name,
                            'cart': list(st.session_state['cart']),
                            'subtotal': subtotal,
                            'discount_pct': discount_pct,
                            'tax_pct': tax_pct,
                            'grand_total': grand_total,
                            'date': today_date
                        }
                        
                        st.session_state['cart'] = []
                        st.success(f"✅ Invoice #{bill_id} generated & saved successfully!")
                        st.rerun()

            # Printable PDF Generation Card
            if 'last_checkout' in st.session_state:
                st.divider()
                lc = st.session_state['last_checkout']
                st.subheader(f"📄 Download Receipt (Bill ID: #{lc['bill_id']})")
                
                pdf_bytes = generate_multi_item_pdf(
                    lc['bill_id'], lc['customer'], lc['cart'], 
                    lc['subtotal'], lc['discount_pct'], lc['tax_pct'], lc['grand_total'], 
                    lc['date']
                )
                
                st.download_button(
                    label=f"📥 Download Printable PDF Invoice (#{lc['bill_id']})",
                    data=pdf_bytes,
                    file_name=f"Invoice_{lc['bill_id']}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

# =========================================================
# MODULE 2: ADMIN AUTHENTICATION
# =========================================================
elif menu == "🔑 Admin Login":
    st.title("🔑 Admin / Owner Login Panel")
    st.caption("Default Admin Login Details: Username = `admin` | Password = `admin123`")
    
    with st.form("login_form"):
        u_name = st.text_input("Username").strip()
        u_pass = st.text_input("Password", type="password").strip()
        
        if st.form_submit_button("Login 🚀", use_container_width=True):
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM admins WHERE username = ? AND password = ?", (u_name, u_pass))
            row = c.fetchone()
            conn.close()
            
            if row:
                st.session_state['logged_in'] = True
                st.success("✅ Logged in successfully! Admin permissions granted.")
                st.rerun()
            else:
                st.error("❌ Invalid Username or Password!")

# =========================================================
# MODULE 3: MEDICINE INVENTORY MANAGEMENT
# =========================================================
elif menu == "📦 Medicine Inventory":
    st.title("📦 Medicine Inventory Management")
    tab1, tab2, tab3 = st.tabs(["📋 Current Stock List", "✏️ Edit / Update Stock", "➕ Add New Medicine"])
    
    # Stock Listing View
    with tab1:
        conn = get_db_connection()
        df_inv = pd.read_sql_query("SELECT id AS 'ID', name AS 'Medicine', category AS 'Category', price AS 'Price (PKR)', stock AS 'Stock Qty' FROM medicines", conn)
        conn.close()
        
        if not df_inv.empty:
            st.dataframe(df_inv, use_container_width=True)
            low_stock = df_inv[df_inv['Stock Qty'] <= 10]
            if not low_stock.empty:
                st.error("⚠️ Low Stock Alert (Less than 10 units left):")
                st.dataframe(low_stock, use_container_width=True)
        else:
            st.info("Inventory currently khali hai. Medicine add karein.")

    # Edit and Delete Controls
    with tab2:
        st.subheader("✏️ Edit Stock Details")
        
        conn = get_db_connection()
        med_list_df = pd.read_sql_query("SELECT * FROM medicines", conn)
        conn.close()
        
        if med_list_df.empty:
            st.info("No medicines available to edit.")
        else:
            med_to_edit = st.selectbox("Select Medicine to Modify", med_list_df['name'].tolist())
            curr_med = med_list_df[med_list_df['name'] == med_to_edit].iloc[0]
            
            col_u1, col_u2 = st.columns(2)
            
            with col_u1:
                with st.form("update_med_form"):
                    st.write(f"Editing: **{curr_med['name']}**")
                    categories = ["Tablet", "Syrup", "Injection", "Capsule", "Ointment", "Other"]
                    cat_index = categories.index(curr_med['category']) if curr_med['category'] in categories else 0
                    
                    new_category = st.selectbox("Category", categories, index=cat_index)
                    new_price = st.number_input("Unit Price (PKR)", min_value=0.0, value=float(curr_med['price']), format="%.2f")
                    new_stock = st.number_input("Stock Quantity", min_value=0, value=int(curr_med['stock']), step=1)
                    
                    if st.form_submit_button("Save / Update Stock 💾", type="primary", use_container_width=True):
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute('''
                            UPDATE medicines 
                            SET category = ?, price = ?, stock = ? 
                            WHERE id = ?
                        ''', (new_category, new_price, new_stock, int(curr_med['id'])))
                        conn.commit()
                        conn.close()
                        
                        st.success(f"✅ {curr_med['name']} updated successfully!")
                        st.rerun()

            with col_u2:
                st.write("---")
                st.warning("⚠️ **Delete Medicine**")
                st.write(f"Kya aap **{curr_med['name']}** ko inventory se permanently delete karna chahte hain?")
                if st.button(f"Delete {curr_med['name']} 🗑️", use_container_width=True):
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("DELETE FROM medicines WHERE id = ?", (int(curr_med['id']),))
                    conn.commit()
                    conn.close()
                    
                    st.success(f"❌ {curr_med['name']} deleted from database!")
                    st.rerun()

    # Add Medicine Controls
    with tab3:
        with st.form("add_med"):
            m_name = st.text_input("Medicine Name").strip()
            m_cat = st.selectbox("Category", ["Tablet", "Syrup", "Injection", "Capsule", "Ointment", "Other"])
            m_price = st.number_input("Unit Price (PKR)", min_value=0.0, format="%.2f")
            m_qty = st.number_input("Initial Stock Quantity", min_value=1, step=1)
            
            if st.form_submit_button("Add to Stock ➕", use_container_width=True):
                if m_name:
                    try:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("INSERT INTO medicines (name, category, price, stock) VALUES (?, ?, ?, ?)", (m_name, m_cat, m_price, m_qty))
                        conn.commit()
                        conn.close()
                        
                        st.success(f"Added {m_name} to stock!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("⚠️ Yeh medicine name pehle se stock me majood hai!")
                else:
                    st.warning("Medicine ka naam likhein.")

# =========================================================
# MODULE 4: SALES REPORTS & REVENUE LEDGER
# =========================================================
elif menu == "📊 Sales Reports":
    st.title("📊 Sales Reports & Revenue Analytics")
    
    conn = get_db_connection()
    try:
        df_sales = pd.read_sql_query("SELECT * FROM sales ORDER BY id DESC", conn)
    except Exception:
        df_sales = pd.DataFrame()
    conn.close()
    
    if not df_sales.empty:
        # Schema Column Guard Check
        for col in ['bill_id', 'customer_name', 'subtotal', 'discount_pct', 'tax_pct', 'grand_total']:
            if col not in df_sales.columns:
                df_sales[col] = 0.0 if 'pct' in col or 'total' in col or 'sub' in col else "N/A"
        
        # Fill NA defaults for Legacy Records
        df_sales['bill_id'] = df_sales['bill_id'].fillna("LEGACY-BILL")
        df_sales['grand_total'] = df_sales['grand_total'].fillna(df_sales['total_price'])

        distinct_bills = df_sales['bill_id'].nunique()
        total_revenue = df_sales.groupby('bill_id')['grand_total'].first().sum()
        
        c1, c2 = st.columns(2)
        c1.metric("Total Bills Generated", distinct_bills)
        c2.metric("Total Revenue Generated", f"PKR {total_revenue:.2f}")
        
        st.divider()
        st.subheader("Detailed Sales Ledger Table")
        
        display_df = df_sales[[
            'bill_id', 'customer_name', 'medicine_name', 'quantity', 
            'unit_price', 'total_price', 'subtotal', 'discount_pct', 
            'tax_pct', 'grand_total', 'date'
        ]].rename(columns={
            'bill_id': 'Bill ID',
            'customer_name': 'Customer',
            'medicine_name': 'Medicine',
            'quantity': 'Qty',
            'unit_price': 'Unit Price',
            'total_price': 'Item Total',
            'subtotal': 'Subtotal',
            'discount_pct': 'Disc %',
            'tax_pct': 'Tax %',
            'grand_total': 'Net Total (PKR)',
            'date': 'Date & Time'
        })
        
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("Abhi tak koi sales record register nahi huwe hain.")

# =========================================================
# MODULE 5: ADMIN SETTINGS
# =========================================================
elif menu == "⚙️ Admin Settings":
    st.title("⚙️ Admin Settings & Security")
    st.subheader("🔑 Change Admin Password")
    
    with st.form("change_pass_form"):
        old_pass = st.text_input("Current Password", type="password").strip()
        new_pass = st.text_input("New Password", type="password").strip()
        confirm_pass = st.text_input("Confirm New Password", type="password").strip()
        
        if st.form_submit_button("Update Password 💾", use_container_width=True):
            if new_pass != confirm_pass:
                st.error("❌ New passwords match nahi kar rahe!")
            elif len(new_pass) < 4:
                st.warning("⚠️ Naya password kam se kam 4 characters ka hona chahiye.")
            else:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT * FROM admins WHERE username = 'admin' AND password = ?", (old_pass,))
                row = c.fetchone()
                
                if row:
                    c.execute("UPDATE admins SET password = ? WHERE username = 'admin'", (new_pass,))
                    conn.commit()
                    conn.close()
                    st.success("✅ Admin password updated successfully!")
                else:
                    conn.close()
                    st.error("❌ Purana password galat hai!")
