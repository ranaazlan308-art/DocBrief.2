import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# Page Configuration
st.set_page_config(page_title="PharmaCare - Pharmacy Management System", page_icon="💊", layout="wide")

# --- DATABASE SETUP ---
conn = sqlite3.connect('pharmacy.db', check_same_thread=False)
c = conn.cursor()

# Tables Creation
c.execute('''
    CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        category TEXT,
        price REAL,
        stock INTEGER
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT,
        medicine_name TEXT,
        quantity INTEGER,
        total_price REAL,
        date TEXT
    )
''')
conn.commit()

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("💊 PharmaCare POS")
st.sidebar.caption("Pharmacy Stock & Billing System")
menu = st.sidebar.radio("Navigation", ["🧾 New Bill / Billing System", "📦 Medicine Inventory (Stock)", "📊 Sales History & Reports"])

st.sidebar.divider()
st.sidebar.info("💡 Data automatically local SQLite database me save hota rehta hai.")

# --- 1. BILLING SYSTEM PAGE ---
if menu == "🧾 New Bill / Billing System":
    st.title("🧾 New Bill / Billing Counter")
    
    # Get available medicines from DB
    med_df = pd.read_sql_query("SELECT * FROM medicines WHERE stock > 0", conn)
    
    if med_df.empty:
        st.warning("⚠️ Pehle 'Medicine Inventory' section me ja kar medicines add karein!")
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Customer & Order Details")
            customer_name = st.text_input("Customer Name", value="Walk-in Customer")
            
            selected_med = st.selectbox("Select Medicine", med_df['name'].tolist())
            
            # Fetch details of selected medicine
            med_info = med_df[med_df['name'] == selected_med].iloc[0]
            max_stock = int(med_info['stock'])
            unit_price = float(med_info['price'])
            
            st.info(f"💰 **Unit Price:** PKR {unit_price:.2f} | 📦 **Available Stock:** {max_stock}")
            
            qty = st.number_input("Quantity", min_value=1, max_value=max_stock, value=1, step=1)
            total_bill = qty * unit_price
            
        with col2:
            st.subheader("Bill Summary")
            st.metric("Total Amount", f"PKR {total_bill:.2f}")
            
            if st.button("Print & Save Bill 🚀", type="primary", use_container_width=True):
                # Update Stock
                new_stock = max_stock - qty
                c.execute("UPDATE medicines SET stock = ? WHERE name = ?", (new_stock, selected_med))
                
                # Insert Sale Record
                today_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute("INSERT INTO sales (customer_name, medicine_name, quantity, total_price, date) VALUES (?, ?, ?, ?, ?)",
                          (customer_name, selected_med, qty, total_bill, today_date))
                
                conn.commit()
                st.success(f"✅ Bill Generated Successfully for {customer_name}!")
                st.balloons()

# --- 2. MEDICINE INVENTORY PAGE ---
elif menu == "📦 Medicine Inventory (Stock)":
    st.title("📦 Medicine Inventory Management")
    
    tab1, tab2 = st.tabs(["📋 Current Stock", "➕ Add / Update Medicine"])
    
    with tab1:
        st.subheader("Current Stock Records")
        df_inventory = pd.read_sql_query("SELECT id AS 'ID', name AS 'Medicine Name', category AS 'Category', price AS 'Price (PKR)', stock AS 'Stock Qty' FROM medicines", conn)
        
        if df_inventory.empty:
            st.info("No medicines added yet.")
        else:
            st.dataframe(df_inventory, use_container_width=True)
            
            # Low Stock Alert
            low_stock = df_inventory[df_inventory['Stock Qty'] <= 10]
            if not low_stock.empty:
                st.error("⚠️ Low Stock Alert (10 se kam stock bacha hai):")
                st.dataframe(low_stock, use_container_width=True)
                
    with tab2:
        st.subheader("Add New Medicine or Increase Stock")
        with st.form("add_med_form"):
            med_name = st.text_input("Medicine Name (e.g., Panadol 500mg)").strip()
            med_cat = st.selectbox("Category", ["Tablet", "Syrup", "Injection", "Capsule", "Ointment", "Other"])
            med_price = st.number_input("Price per Unit (PKR)", min_value=0.0, format="%.2f")
            med_qty = st.number_input("Stock Quantity", min_value=1, step=1)
            
            submit = st.form_submit_button("Add Medicine to Inventory")
            
            if submit:
                if med_name:
                    try:
                        c.execute("INSERT INTO medicines (name, category, price, stock) VALUES (?, ?, ?, ?)",
                                  (med_name, med_cat, med_price, med_qty))
                        conn.commit()
                        st.success(f"✅ {med_name} successfully add ho gayi!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("⚠️ Yeh medicine pehle se database me hai! Isko update karne ke liye dusra method use karein.")
                else:
                    st.warning("Please medicine ka naam likhein.")

# --- 3. SALES HISTORY & REPORTS PAGE ---
elif menu == "📊 Sales History & Reports":
    st.title("📊 Sales History & Earning Reports")
    
    df_sales = pd.read_sql_query("SELECT id AS 'Sale ID', customer_name AS 'Customer', medicine_name AS 'Medicine', quantity AS 'Qty', total_price AS 'Total Price (PKR)', date AS 'Date & Time' FROM sales ORDER BY id DESC", conn)
    
    if df_sales.empty:
        st.info("Abhi tak koi sale record nahi hua hai.")
    else:
        total_revenue = df_sales['Total Price (PKR)'].sum()
        total_orders = len(df_sales)
        
        m1, m2 = st.columns(2)
        m1.metric("Total Revenue Generated", f"PKR {total_revenue:.2f}")
        m2.metric("Total Bills Issued", total_orders)
        
        st.divider()
        st.subheader("Detailed Sales Log")
        st.dataframe(df_sales, use_container_width=True)
        
        # Download Sales Data
        csv_data = df_sales.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Sales History (CSV File)",
            data=csv_data,
            file_name=f"sales_report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )