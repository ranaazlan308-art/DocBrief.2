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
    """Password ko SHA256 ke zariye secure hash me badalta hai."""
    salt = b"A_PHARMA_SECURE_SALT"  # System Salt
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return hashed.hex()

def verify_password(stored_hash: str, input_password: str) -> bool:
    """Input password aur saved hash ko compare karta hai."""
    return hmac.compare_digest(stored_hash, hash_password(input_password))


# ---------------------------------------------------------
# 1. DIRECT THERMAL PRINTING FUNCTION (Threaded)
# ---------------------------------------------------------
def print_receipt_in_background(receipt_data):
    """
    Direct Windows Thermal Printing / Raw Spooling.
    """
    def _print_job():
        try:
            WIDTH = 32
            LINE = "=" * WIDTH
            DASH = "-" * WIDTH

            # Pre-formatting string variables to avoid nesting quotes inside f-strings
            subtotal_str = f"Rs. {receipt_data['subtotal']:.2f}".rjust(18)
            discount_str = f"-Rs. {receipt_data['discount']:.2f}".rjust(18)
            tax_str = f"+Rs. {receipt_data['tax']:.2f}".rjust(18)
            grand_total_str = f"Rs. {receipt_data['grand_total']:.2f}".rjust(15)

            # Clean Monospace Receipt Formatting
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
                    # Windows Direct Raw Printing to Default Thermal Printer
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
                    # Fallback method if raw printer fails
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
    
    # Hashed Passwords for Default Users
    admin_hash = hash_password("admin123")
    staff_hash = hash_password("staff123")
    
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', ?, 'admin')", (admin_hash,))
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('staff1', ?, 'staff')", (staff_hash,))
    
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
    c.execute("SELECT username, password, role FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    
    # Verify Hash Password
    if user and verify_password(user[1], password):
        st.session_state.authenticated = True
        st.session_state.username = user[0]
        st.session_state.role = user[2]
        st.rerun()
    else:
        st.error("Invalid Username or Password")

# ---------------------------------------------------------
# 4. LOGIN INTERFACE
# ---------------------------------------------------------
if not st.session_state.authenticated:
    st.title("🔒 A Pharma POS Login")
    st.info("Default Login -> **Admin:** `admin` / `admin123` | **Staff:** `staff1` / `staff123`")
