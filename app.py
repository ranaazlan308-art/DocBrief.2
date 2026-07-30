import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io

# ReportLab imports for PDF generation
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

# --- DATABASE SETUP & MIGRATIONS ---
conn = sqlite3.connect('pharmacy.db', check_same_thread=False)
c = conn.cursor()

# Medicines Table
c.execute('''
    CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        category TEXT,
        price REAL,
        stock INTEGER
    )
''')

# Sales Table
c.execute('''
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bill_id TEXT,
        customer_name TEXT,
        medicine_name TEXT,
        quantity INTEGER,
        unit_price REAL,
        total_price REAL,
        subtotal REAL,
        discount_pct REAL,
        tax_pct REAL,
        grand_total REAL,
        date TEXT
    )
''')

# Admin Credentials Table
c.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
''')

# Default Admin Setup (admin / admin123)
c.execute("SELECT * FROM admins WHERE username = 'admin'")
if not c.fetchone():
    c.execute("INSERT INTO admins (username, password) VALUES (?, ?)", ('admin', 'admin123'))
    conn.commit()

# Ensure all sales columns exist for backward compatibility
try:
    c.execute("ALTER TABLE sales ADD COLUMN subtotal REAL")
    c.execute("ALTER TABLE sales ADD COLUMN discount_pct REAL")
    c.execute("ALTER TABLE sales ADD COLUMN tax_pct REAL")
    c.execute("ALTER TABLE sales ADD COLUMN grand_total REAL")
    conn.commit()
except sqlite3.OperationalError:
    pass

# --- SESSION STATE INITIALIZATION ---
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

    # Header
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, alignment=1, textColor=colors.HexColor('#1E3A8A'))
    story.append(Paragraph("<b>PHARMACARE PHARMACY</b>", title_style))
    story.append(Paragraph("Official Tax Invoice & Receipt", ParagraphStyle('Sub', parent=styles['Normal'], alignment=1, textColor=colors.gray)))
    story.append(Spacer(1, 15))

    # Bill Metadata
    meta_data = [
        [f"Customer: {customer_name}", f"Date: {bill_date}"],
        [f"Bill ID: #{bill_id}", "Payment Mode: Cash"]
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

    # Items Table Header
    table_data = [["#", "Item / Medicine", "Qty", "Unit Price (PKR)", "Total (PKR)"]]
    for idx, item in enumerate(cart_items, 1):
        table_data.append([
            str(idx),
            item['medicine'],
            str(item['qty']),
            f"{item['unit_price']:.2f}",
            f"{item['total']:.2f}"
        ])

    disc_val = subtotal * (discount_pct / 100)
    tax_val = (subtotal - disc_val) * (tax_pct / 100)

    # Billing Financials Summary
    table_data.append(["", "", "", "Subtotal:", f"PKR {subtotal:.2f}"])
    table_data.append(["", "", "", f"Discount ({discount_pct:.1f}%):", f"- PKR {disc_val:.2f}"])
    table_data.append(["", "", "", f"GST / Tax ({tax_pct:.1f}%):", f"+ PKR {tax_val:.2f}"])
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

    # Footer Notes
    footer_style = ParagraphStyle('FooterStyle', parent=styles['Normal'], fontSize=9, alignment=1, textColor=colors.gray)
    story.append(Paragraph("Thank you for choosing PharmaCare! Get well soon.", footer_style))
    story.append(Paragraph("This is a computer-generated tax invoice.", footer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

# --- SIDEBAR & AUTH NAVIGATION ---
st.sidebar.title("💊 PharmaCare POS")

# Auth Status Widget
if st.session_state['logged_in']:
    st.sidebar.success("🔒 Admin Logged In")
    if st.sidebar.button("Logout 🚪", use_container_width=True):
        st.session_state['logged_in'] = False
        st.rerun()
else:
    st.sidebar.info("👤 Staff Mode (Limited Access)")

# Role-Based Dynamic Navigation
nav_options = ["🧾 Multi-Item Billing Counter"]
if st.session_state['logged_in']:
    nav_options.extend(["📦 Medicine Inventory", "📊 Sales Reports", "⚙️ Admin Settings"])
else:
    nav_options.append("🔑 Admin Login")

menu = st.sidebar.radio("Navigation Menu", nav_options)

# ==========================================
# 1. MULTI-ITEM BILLING COUNTER (ALL STAFF)
# ==========================================
if menu == "🧾 Multi-Item Billing Counter":
    st.title("🧾 Multi-Item Billing Counter")
    
    med_df = pd.read_sql_query("SELECT * FROM medicines WHERE stock > 0", conn)
    
    if med_df.empty:
        st.warning("⚠️ Pehle 'Medicine Inventory' section me (Admin login ke zariye) medicines add karein!")
    else:
        col_left, col_right = st.columns([1.2, 1.8])
        
        # Left Side: Cart Items Selection
        with col_left:
            st.subheader("➕ Add Items to Cart")
            customer_name = st.text_input("Customer Name", value="Walk-in Customer")
            
            selected_med = st.selectbox("Select Medicine", med_df['name'].tolist())
            med_info = med_df[med_df['name'] == selected_med].iloc[0]
            
            max_stock = int(med_info['stock'])
            unit_price = float(med_info['price'])
            
            in_cart_qty = sum(item['qty'] for item in st.session_state['cart'] if item['medicine'] == selected_med)
            available_stock = max_stock - in_cart_qty
            
            st.info(f"💰 Price: **PKR {unit_price:.2f}** | 📦 Available Stock: **{available_stock}**")
            
            if available_stock > 0:
                qty = st.number_input("Quantity", min_value=1, max_value=available_stock, value=1, step=1)
                
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
                st.error("⚠️ Stock limit reached for this item in cart!")

        # Right Side: Invoice Summary & Calculations
        with col_right:
            st.subheader("🛒 Current Cart / Invoice Breakdown")
            
            if not st.session_state['cart']:
                st.info("Cart abhi khali hai. Left side se items select karke add karein.")
            else:
                cart_df = pd.DataFrame(st.session_state['cart'])
                st.dataframe(
                    cart_df[['medicine', 'qty', 'unit_price', 'total']].rename(columns={
                        'medicine': 'Medicine', 'qty': 'Qty', 'unit_price': 'Price (PKR)', 'total': 'Total (PKR)'
                    }),
                    use_container_width=True
                )
                
                subtotal = cart_df['total'].sum()
                
                # Discount & Tax Inputs
                d_col, t_col = st.columns(2)
                with d_col:
                    discount_pct = st.number_input("Overall Discount (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
                with t_col:
                    tax_pct = st.number_input("GST / Sales Tax (%)", min_value=0.0, max_value=50.0, value=17.0, step=0.5)
                
                # Calculations
                discount_val = subtotal * (discount_pct / 100)
                taxable_subtotal = subtotal - discount_val
                tax_val = taxable_subtotal * (tax_pct / 100)
                grand_total = taxable_subtotal + tax_val
                
                # Live Metrics Display
                st.divider()
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Subtotal", f"PKR {subtotal:.2f}")
                m2.metric("Discount", f"- PKR {discount_val:.2f}")
                m3.metric("Tax", f"+ PKR {tax_val:.2f}")
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
                        
                        # Process Sales & Inventory Update
                        for item in st.session_state['cart']:
                            c.execute("UPDATE medicines SET stock = stock - ? WHERE name = ?", (item['qty'], item['medicine']))
                            c.execute('''
                                INSERT INTO sales (bill_id, customer_name, medicine_name, quantity, unit_price, total_price, subtotal, discount_pct, tax_pct, grand_total, date) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (bill_id, customer_name, item['medicine'], item['qty'], item['unit_price'], item['total'], subtotal, discount_pct, tax_pct, grand_total, today_date))
                        
                        conn.commit()
                        
                        # Save Last Checkout Payload for PDF Generation
                        st.session_state['last_checkout'] = {
                            'bill_id': bill_id,
                            'customer': customer_name,
                            'cart': st.session_state['cart'],
                            'subtotal': subtotal,
                            'discount_pct': discount_pct,
                            'tax_pct': tax_pct,
                            'grand_total': grand_total,
                            'date': today_date
                        }
                        
                        st.session_state['cart'] = []
                        st.success(f"✅ Invoice #{bill_id} generated & saved successfully!")
                        st.rerun()

            # PDF Receipt Ready Section
            if 'last_checkout' in st.session_state:
                st.divider()
                lc = st.session_state['last_checkout']
                st.subheader(f"📄 Download PDF Receipt (Bill #{lc['bill_id']})")
                
                pdf_bytes = generate_multi_item_pdf(
                    lc['bill_id'], lc['customer'], lc['cart'], 
                    lc['subtotal'], lc['discount_pct'], lc['tax_pct'], lc['grand_total'], 
                    lc['date']
                )
                
                st.download_button(
                    label="📥 Download Printable PDF Tax Invoice",
                    data=pdf_bytes,
                    file_name=f"Tax_Invoice_{lc['bill_id']}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

# ==========================================
# 2. ADMIN LOGIN PAGE
# ==========================================
elif menu == "🔑 Admin Login":
    st.title("🔑 Admin / Owner Login")
    st.caption("Default Login Details: Username = `admin` | Password = `admin123`")
    
    with st.form("login_form"):
        u_name = st.text_input("Username").strip()
        u_pass = st.text_input("Password", type="password").strip()
        
        if st.form_submit_button("Login 🚀", use_container_width=True):
            c.execute("SELECT * FROM admins WHERE username = ? AND password = ?", (u_name, u_pass))
            if c.fetchone():
                st.session_state['logged_in'] = True
                st.success("✅ Welcome Admin! You now have full access.")
                st.rerun()
            else:
                st.error("❌ Invalid Username or Password!")

# ==========================================
# 3. MEDICINE INVENTORY (ADMIN RESTRICTED)
# ==========================================
elif menu == "📦 Medicine Inventory":
    st.title("📦 Medicine Inventory Management")
    tab1, tab2 = st.tabs(["📋 Current Stock List", "➕ Add New Medicine"])
    
    with tab1:
        df_inv = pd.read_sql_query("SELECT id AS 'ID', name AS 'Medicine', category AS 'Category', price AS 'Price (PKR)', stock AS 'Stock Qty' FROM medicines", conn)
        if not df_inv.empty:
            st.dataframe(df_inv, use_container_width=True)
            low_stock = df_inv[df_inv['Stock Qty'] <= 10]
            if not low_stock.empty:
                st.error("⚠️ Low Stock Alert (10 se kam items bacche hain):")
                st.dataframe(low_stock, use_container_width=True)
        else:
            st.info("Inventory khali hai. Nayi medicine add karein.")
            
    with tab2:
        with st.form("add_med"):
            m_name = st.text_input("Medicine Name").strip()
            m_cat = st.selectbox("Category", ["Tablet", "Syrup", "Injection", "Capsule", "Ointment", "Other"])
            m_price = st.number_input("Unit Price (PKR)", min_value=0.0, format="%.2f")
            m_qty = st.number_input("Initial Stock Quantity", min_value=1, step=1)
            
            if st.form_submit_button("Add to Stock"):
                if m_name:
                    try:
                        c.execute("INSERT INTO medicines (name, category, price, stock) VALUES (?, ?, ?, ?)", (m_name, m_cat, m_price, m_qty))
                        conn.commit()
                        st.success(f"Added {m_name} to stock!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("⚠️ Yeh medicine pehle se stock me majood hai!")
                else:
                    st.warning("Please medicine ka naam daalein.")

# ==========================================
# 4. SALES REPORTS (ADMIN RESTRICTED)
# ==========================================
elif menu == "📊 Sales Reports":
    st.title("📊 Sales History & Revenue Reports")
    
    df_sales = pd.read_sql_query("""
        SELECT bill_id AS 'Bill ID', customer_name AS 'Customer', medicine_name AS 'Medicine', 
               quantity AS 'Qty', unit_price AS 'Unit Price', total_price AS 'Item Total',
               subtotal AS 'Bill Subtotal', discount_pct AS 'Disc %', tax_pct AS 'Tax %', 
               grand_total AS 'Bill Net Total (PKR)', date AS 'Date & Time' 
        FROM sales ORDER BY id DESC
    """, conn)
    
    if not df_sales.empty:
        # High level Summary Metrics
        distinct_bills = df_sales['Bill ID'].nunique()
        total_revenue = df_sales.groupby('Bill ID')['Bill Net Total (PKR)'].first().sum()
        
        c1, c2 = st.columns(2)
        c1.metric("Total Bills Processed", distinct_bills)
        c2.metric("Total Overall Revenue Generated", f"PKR {total_revenue:.2f}")
        
        st.divider()
        st.subheader("Detailed Sales Ledger")
        st.dataframe(df_sales, use_container_width=True)
    else:
        st.info("Abhi tak koi sales records register nahi hue hain.")

# ==========================================
# 5. ADMIN SETTINGS (ADMIN RESTRICTED)
# ==========================================
elif menu == "⚙️ Admin Settings":
    st.title("⚙️ Admin Settings")
    st.subheader("🔑 Change Admin Password")
    
    with st.form("change_pass_form"):
        old_pass = st.text_input("Current Password", type="password").strip()
        new_pass = st.text_input("New Password", type="password").strip()
        confirm_pass = st.text_input("Confirm New Password", type="password").strip()
        
        if st.form_submit_button("Update Password"):
            if new_pass != confirm_pass:
                st.error("❌ Naya password aur confirm password match nahi ho rahe!")
            elif len(new_pass) < 4:
                st.warning("⚠️ New password kam se kam 4 characters ka hona chahiye.")
            else:
                c.execute("SELECT * FROM admins WHERE username = 'admin' AND password = ?", (old_pass,))
                if c.fetchone():
                    c.execute("UPDATE admins SET password = ? WHERE username = 'admin'", (new_pass,))
                    conn.commit()
                    st.success("✅ Admin password successfully updated!")
                else:
                    st.error("❌ Purana password galat hai!")
