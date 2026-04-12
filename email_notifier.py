import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

import threading

def send_email_alert(order_details):
    """
    Sends an email alert to the admin about a new order (Non-blocking).
    """
    threading.Thread(target=_send_email_async, args=(order_details,), daemon=True).start()

def _send_email_async(order_details):
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_EMAIL_PASSWORD") # Must be a Gmail App Password

    if not email or not password:
        return

    try:
        subject = '🚨 New Order Received from WhatsApp Chatbot'
        body = f"""
🚨 New Order Received from WhatsApp Chatbot 🚨

Customer Name: {order_details.get('ordererName')}
Address: {order_details.get('address')}
Product: {order_details.get('productName')}
Price: {order_details.get('price')}

A new row has also been securely logged to your Google Sheet!
"""
        msg = MIMEMultipart()
        msg['From'] = email
        msg['To'] = email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(email, password)
        server.send_message(msg)
        server.quit()
        print("✅ Email notification sent to Admin.")
    except Exception as e:
        print(f"FAILED to send Email notification: {e}")

def send_error_alert(error_message):
    """
    Sends an error alert to the admin (Non-blocking).
    """
    threading.Thread(target=_send_error_async, args=(error_message,), daemon=True).start()

def _send_error_async(error_message):
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_EMAIL_PASSWORD")

    if not email or not password:
        return

    try:
        subject = '🔴 ALERT: WhatsApp Bot Error / Offline'
        body = f"Carezone Bot Error Alert:\n\n{error_message}\n\nPlease check your server logs."

        msg = MIMEMultipart()
        msg['From'] = email
        msg['To'] = email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(email, password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"FAILED to send Error Email notification: {e}")

if __name__ == "__main__":
    # Test alert
    test_order = {"ordererName": "Test", "address": "Peshawar", "productName": "Test Item", "price": "100"}
    send_email_alert(test_order)
