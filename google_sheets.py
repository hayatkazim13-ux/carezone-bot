import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from datetime import datetime
import pytz
from dotenv import load_dotenv

load_dotenv()

def get_sheets_client():
    """
    Authenticates with Google Sheets using service account credentials.
    Supports either a JSON file or an environment variable.
    """
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # 1. Try environment variable (for Cloud deployment like Render/Railway)
    env_creds = os.getenv("GOOGLE_CREDENTIALS")
    if env_creds:
        try:
            # Handle potential base64 or escaped newlines
            creds_dict = json.loads(env_creds.replace('\\n', '\n'))
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        except Exception as e:
            print(f"Error parsing GOOGLE_CREDENTIALS env var: {e}")

    # 2. Fallback to local credentials.json file
    try:
        with open('credentials.json', 'r') as f:
            creds_data = json.load(f)
        
        # Scrub private key (Fix for common formatting/newline issues)
        if 'private_key' in creds_data:
            creds_data['private_key'] = creds_data['private_key'].replace('\\n', '\n').strip()
            
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_data, scope)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"Failed to authenticate with Google Sheets: {e}")
        return None

def log_customer(phone_number, name):
    """
    Logs a new customer lead to the 'Customers' tab.
    """
    try:
        spreadsheet_id = os.getenv("SPREADSHEET_ID")
        if not spreadsheet_id:
            return

        client = get_sheets_client()
        if not client:
            return

        sheet = client.open_by_key(spreadsheet_id).worksheet("Customers")
        
        # Get current time in Pakistan
        tz = pytz.timezone('Asia/Karachi')
        date_str = datetime.now(tz).strftime('%m/%d/%Y, %I:%M:%S %p')
        
        row = [date_str, phone_number, name]
        sheet.append_row(row)
        print(f"Customer {name} ({phone_number}) logged to Google Sheets.")
    except Exception as e:
        print(f"Failed to log customer to Google Sheets: {e}")

def log_order(order_details):
    """
    Logs a new order to the main sheet.
    Expected order_details keys: productName, price, ordererName, address, quantity, phoneNumber
    """
    try:
        spreadsheet_id = os.getenv("SPREADSHEET_ID")
        if not spreadsheet_id:
            print("No SPREADSHEET_ID found in .env. Skipping Google Sheets logging.")
            return

        client = get_sheets_client()
        if not client:
            return

        # Open the first sheet (default)
        sheet = client.open_by_key(spreadsheet_id).get_worksheet(0)
        
        row = [
            order_details.get('productName', 'Unknown'),
            order_details.get('price', 'Unknown'),      # B: Total Price
            order_details.get('ordererName', 'Customer'),
            order_details.get('address', 'Unknown'),    # D: City + Delivery Place
            "New Order",                                # E: Status
            "No",                                       # F: Paid
            order_details.get('quantity', 'Unknown'),   # G: Quantity
            order_details.get('phoneNumber', 'Unknown') # H: Phone Number
        ]
        
        sheet.append_row(row)
        print("Order logged to Google Sheets.")
    except Exception as e:
        print(f"Failed to log order to Google Sheets: {e}")

if __name__ == "__main__":
    # Test logging
    test_order = {
        "productName": "TEST PRODUCT (PYTHON)",
        "price": "0",
        "ordererName": "Developer Test",
        "address": "Peshawar, Test Street",
        "quantity": "1",
        "phoneNumber": "+920000000000"
    }
    log_order(test_order)
