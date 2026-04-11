import requests
import json
import time

URL = "http://127.0.0.1:8080/webhook"

def simulate_message(from_number, text):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": from_number,
                        "type": "text",
                        "text": {"body": text}
                    }]
                }
            }]
        }]
    }
    print(f"\n[USER -> BOT]: {text}")
    try:
        response = requests.post(URL, json=payload, timeout=30)
        print(f"[BOT RESPONSE]: {response.status_code} - {response.text}")
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    test_user = "923991234567"
    
    # 1. New user greeting (should trigger customer log)
    simulate_message(test_user, "Hi, I want to buy something.")
    time.sleep(5) # Wait for AI processing
    
    # 2. Ask for something definitely NOT in catalog (testing 'Never Say No')
    simulate_message(test_user, "I need some 'Dragon-X Ultra Vitamin' which is very rare.")
    time.sleep(5)
    
    # 3. provide quantity
    simulate_message(test_user, "I want 5 packs.")
    time.sleep(5)
    
    # 4. provide details (Finalizing)
    simulate_message(test_user, "My name is Kazim, Peshawar, Street 5 House 1, phone 03470890549. Please confirm.")
    time.sleep(5)
    
    # 5. Confirm summary (Triggering Order log)
    simulate_message(test_user, "Yes, confirm it.")
