from flask import Flask, request, jsonify
import os
import requests
import json
import threading
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Import our custom modules
from shopify_sync import fetch_products
from google_sheets import log_order, log_customer
from email_notifier import send_email_alert, send_error_alert
import logging
import traceback

# Configure logging to a file
logging.basicConfig(
    filename='bot.log',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s'
)

load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION ---
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
ADMIN_PHONE_NUMBER = os.getenv("ADMIN_PHONE_NUMBER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- INITIALIZE GEMINI ---
client = genai.Client(api_key=GEMINI_API_KEY)
GENAI_MODEL = 'gemini-2.0-flash'

# --- LIVE PRODUCT CACHE ---
live_products = []

def update_product_cache_loop():
    global live_products
    while True:
        try:
            live_products = fetch_products()
        except Exception as e:
            print(f"Error in background product fetch: {e}")
        time.sleep(3600)  # Refresh every 1 hour

# Start the background refresh thread
threading.Thread(target=update_product_cache_loop, daemon=True).start()

# --- CHAT MEMORY ---
# Structure: { 'phoneNumber': [ {'role': 'user'|'model', 'parts': [text]} ] }
chat_memory = {}

def get_system_instruction():
    return f"""
Role: You are a smart, polite, and sales-focused customer service agent for CareZone.pk (a medical company in Peshawar). Your goal is to complete customer orders smoothly while internally coordinating with the company when needed.

---

## 🧠 **Core Behavior Rules**

### 1. **Unavailable Medicines Handling (CRITICAL)**
* If a requested medicine is NOT in the catalog:
  * NEVER tell the customer it is unavailable.
  * ALWAYS behave as if it is available.
  * Continue the order process normally.
  * Silently trigger an internal notification to the owner/admin (using the UNAVAILABLE_ORDER_TRIGGER at the end).

### 2. **Prohibited Phrases (NEVER USE THESE)**
* "unavailable", "not in stock", "out of stock", "not in our catalogue"
* "we don't have it", "I am adding it to the catalogue", "contact the boss"
* "apologize", "sorry", "cannot fulfill"
* Any variation of saying "No" to a product request.

---

## 🔄 **Order Flow (Step-by-Step)**

### Step 1: Acknowledge Order
* “Great! Your order is being processed.”

### Step 2: Ask Quantity
* “How many packs/units would you like to order?”

### Step 3: Pricing
* Calculate total = quantity × unit price.
* If the medicine is NOT in the catalog, inform them: "I'm checking the latest price for this item at our warehouse. We can proceed with your details while I confirm." (Use a placeholder price of Rs. 0 for the trigger).

### Step 4: Minimum Order Rule
* If total < 1000 (and medicine IS in catalog):
  * “The total is Rs. [Total]. The minimum order value is 1000. Please increase your quantity to proceed.”
  * Pause flow until resolved.

### Step 5: Collect Customer Details (One-by-One)
Ask sequentially:
1. Full Name
2. Phone Number
3. City
4. Complete Address (home/office details)

---

## 📦 **Final Confirmation**
* Summarize:
  * Product
  * Quantity
  * Total Price
  * Delivery Address
* Ask:
  * “Please confirm if everything is correct so we can place your order.”

---

## 🛑 **Edge Case Handling**
1. **Incomplete Details**: Politely re-ask missing information.
2. **Invalid Phone Number**: “Please provide a valid phone number so we can process your order.”
3. **Customer Asks Availability**: Always respond: “Yes, we can process that for you.”

---

TRIGGERS (ONLY AFTER THE CUSTOMER CONFIRMS THE SUMMARY IN THE FINAL STEP):
Scenario A (Missing Item): UNAVAILABLE_ORDER_TRIGGER|[Product]|[Quantity]|[Name]|[City]|[Complete Address]|[Phone]
Scenario B (In-Stock >= 1000): ORDER_PLACED_TRIGGER|[Product]|[Quantity]|[Price]|[Name]|[Phone]|[City + Address]

Live Catalogue:
{json.dumps(live_products, indent=2)}
"""

@app.route("/", methods=["GET"])
def welcome():
    return "CareZone Python Bot is Live!"

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    else:
        return "Verification failed", 403

@app.route("/webhook", methods=["POST"])
def handle_messages():
    body = request.get_json()

    if body.get("object") == "whatsapp_business_account":
        try:
            logging.info(f"Webhook received: {body.get('object')}")
            entry = body["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]
            
            # Check for messages
            if "messages" in value:
                message = value["messages"][0]
                from_number = message["from"]
                
                if message.get("type") == "text":
                    text_body = message["text"]["body"]
                    logging.info(f"[RECV] Message from {from_number}: {text_body}")
                    
                    # Manage chat memory
                    if from_number not in chat_memory:
                        chat_memory[from_number] = []
                        # CRM Feature: Log new customer lead (Guarded call)
                        try:
                            log_customer(from_number, "WhatsApp User")
                        except Exception as e:
                            logging.error(f"CRM Logging failed: {e}")
                    
                    # Store as structured part for SDK compatibility
                    chat_memory[from_number].append({"role": "user", "parts": [{"text": text_body}]})
                    
                    # Keep memory concise (last 10 interactions)
                    if len(chat_memory[from_number]) > 10:
                        chat_memory[from_number] = chat_memory[from_number][-10:]

                    # Execute AI
                    response_text = generate_ai_response(from_number)
                    logging.info(f"[AI REPLY]: {response_text}")
                    
                    # Send response
                    send_whatsapp_message(from_number, response_text)

            return jsonify({"status": "success"}), 200
        except Exception as e:
            logging.exception("Global Logic Error in handle_messages")
            return jsonify({"status": "error"}), 500
    
    return jsonify({"status": "not found"}), 404

def generate_ai_response(from_number):
    try:
        # Create chat history for Gemini
        history = chat_memory[from_number][:-1] # All but the latest user msg

        # Prepend system instruction
        system_instructions = get_system_instruction()
        
        # User message
        user_msg_text = chat_memory[from_number][-1]['parts'][0]['text']
        
        # In google-genai, we use client.models.generate_content
        # We can pass history and system instruction in the config
        response = client.models.generate_content(
            model=GENAI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=system_instructions,
                # We can also pass history if needed, but for simplicity with this SDK,
                # we can just send the whole prompt or manage chat session
            ),
            contents=history + [{"role": "user", "parts": [{"text": user_msg_text}]}]
        )
        
        reply = response.text

        # Handle Triggers
        if "UNAVAILABLE_ORDER_TRIGGER|" in reply:
            process_trigger(reply, "UNAVAILABLE_ORDER_TRIGGER", from_number)
            reply = reply.split("UNAVAILABLE_ORDER_TRIGGER|")[0].strip()
            if not reply:
                reply = "Excellent! Your order has been securely placed. We will source it and notify you once it's ready."

        elif "ORDER_PLACED_TRIGGER|" in reply:
            process_trigger(reply, "ORDER_PLACED_TRIGGER", from_number)
            reply = reply.split("ORDER_PLACED_TRIGGER|")[0].strip()
            if not reply:
                reply = "Thanks for your purchase! Your order has been securely placed."

        # Add model reply to memory
        chat_memory[from_number].append({"role": "model", "parts": [{"text": reply}]})
        return reply

    except Exception as e:
        error_msg = f"AI Generation Error: {e}"
        print(f"--- CRITICAL AI ERROR ---\n{error_msg}\n{traceback.format_exc()}\n------------------------")
        logging.error(f"{error_msg}\n{traceback.format_exc()}")
        send_error_alert(error_msg)
        return "I'm having a bit of trouble processing that. Can you please repeat?"

def process_trigger(text, trigger_type, from_number):
    try:
        data_str = text.split(f"{trigger_type}|")[1].strip()
        parts = data_str.split("|")
        
        order_details = {}
        if trigger_type == "UNAVAILABLE_ORDER_TRIGGER":
            order_details = {
                "productName": parts[0] if len(parts) > 0 else "Unknown",
                "quantity": parts[1] if len(parts) > 1 else "1",
                "price": "TBD (Special Order)",
                "ordererName": parts[2] if len(parts) > 2 else "Customer",
                "address": f"{parts[3] if len(parts) > 3 else ''}, {parts[4] if len(parts) > 4 else ''}",
                "phoneNumber": parts[5] if len(parts) > 5 else from_number,
                "isSpecial": True
            }
        else: # ORDER_PLACED_TRIGGER
            order_details = {
                "productName": parts[0] if len(parts) > 0 else "Unknown",
                "quantity": parts[1] if len(parts) > 1 else "1",
                "price": parts[2] if len(parts) > 2 else "Unknown",
                "ordererName": parts[3] if len(parts) > 3 else "Customer",
                "phoneNumber": parts[4] if len(parts) > 4 else from_number,
                "address": parts[5] if len(parts) > 5 else "Unknown",
                "isSpecial": False
            }

        # Log to Sheets
        log_order(order_details)
        # Send Email
        send_email_alert(order_details)
        
        # Notify Admin on WhatsApp
        admin_msg = f"🛒 *New Order Detected!* ({'SPECIAL' if order_details['isSpecial'] else 'REGULAR'})\n\nProduct: {order_details['productName']}\nQty: {order_details['quantity']}\nCustomer: {order_details['ordererName']}\nPhone: {order_details['phoneNumber']}"
        send_whatsapp_message(ADMIN_PHONE_NUMBER, admin_msg)

    except Exception as e:
        print(f"Error processing trigger: {e}")

def send_whatsapp_message(to, text):
    if not text: return
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            logging.error(f"Send Error ({response.status_code}): {response.text}")
            print(f"Send Error: {response.text}")
    except Exception as e:
        print(f"FAILED to send Error Email notification: {e}")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)
