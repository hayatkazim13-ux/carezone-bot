import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_send():
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    to_number = os.getenv("ADMIN_PHONE_NUMBER") # Your private number

    print(f"--- TESTING CONNECTION ---")
    print(f"Target Number: {to_number}")
    print(f"Phone ID: {phone_id}")
    
    url = f"https://graph.facebook.com/v17.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": "Hello from CareZone Python Bot! Your API connection is working perfectly."}
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")

    if response.status_code == 200:
        print("\nSUCCESS! Meta accepted the message. If you didn't receive it, check if your number is in the 'To' list in the Sandbox dashboard.")
    else:
        print(f"\nFAILED. Error: {response.text}")

if __name__ == "__main__":
    if "your_token" in os.getenv("WHATSAPP_ACCESS_TOKEN", ""):
        print("Error: You haven't replaced the tokens in your .env file yet!")
    else:
        test_send()
