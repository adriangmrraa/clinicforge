import hmac
import hashlib
import time
import requests
import json
import uuid

# Configuration
WHATSAPP_SERVICE_URL = "http://localhost:8002"
YCLOUD_WEBHOOK_SECRET = os.getenv("YCLOUD_WEBHOOK_SECRET", "test_secret")
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "test_token")

def generate_signature(body, secret):
    t = str(int(time.time()))
    payload = f"{t}.{body}"
    s = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"t={t},s={s}"

def test_invalid_signature():
    print("\n--- Testing Invalid Signature ---")
    url = f"{WHATSAPP_SERVICE_URL}/webhook/ycloud"
    payload = json.dumps({"test": "data"})
    headers = {"ycloud-signature": "t=1234567890,s=invalid_signature"}
    try:
        response = requests.post(url, data=payload, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        if response.status_code == 401:
            print("PASS: Invalid signature rejected")
        else:
            print("FAIL: Invalid signature accepted")
    except Exception as e:
        print(f"Error: {e}")

def test_valid_signature_and_flow():
    print("\n--- Testing Valid Signature & Flow ---")
    url = f"{WHATSAPP_SERVICE_URL}/webhook/ycloud"
    
    # Payload matching n8n structure
    wamid = f"wamid.{uuid.uuid4()}"
    payload_data = [
        {
            "id": "evt_123",
            "type": "whatsapp.inbound_message.received",
            "apiVersion": "v2",
            "createTime": "2023-10-27T10:00:00Z",
            "whatsappInboundMessage": {
                "id": wamid,
                "wamid": wamid,
                "from": "123456789",
                "to": "987654321",
                "type": "text",
                "text": {"body": "Hola, prueba agente"},
                "customerProfile": {"name": "Test User"},
                "sendTime": "2023-10-27T10:00:00Z"
            }
        }
    ]
    payload = json.dumps(payload_data)
    signature = generate_signature(payload, YCLOUD_WEBHOOK_SECRET)
    headers = {
        "ycloud-signature": signature,
        "Content-Type": "application/json"
    }
    
    # First Request
    print(f"Sending First Request (WAMID: {wamid})...")
    try:
        response = requests.post(url, data=payload, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        if response.status_code == 200:
             print("PASS: Valid request accepted")
        else:
             print(f"FAIL: Request failed with {response.status_code}")
    except Exception as e:
         print(f"Error: {e}")

    # Duplicate Request
    print(f"\nSending Duplicate Request (WAMID: {wamid})...")
    try:
        response = requests.post(url, data=payload, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        # We expect a 200 OK from whatsapp_service regardless, but the content might show it was duplicate handled by orchestrator
        # OR if orchestrator returns a 'send=False' with status='duplicate', whatsapp_service just returns that json.
        response_json = response.json()
        if response_json.get("status") == "duplicate":
            print("PASS: Duplicate request correctly identified")
        else:
            print(f"FAIL: Duplicate not identified or unexpected response {response_json}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_invalid_signature()
    test_valid_signature_and_flow()
