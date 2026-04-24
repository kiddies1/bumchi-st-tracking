import os
import csv
import requests
from datetime import datetime
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Optional

class ShippingDetails(BaseModel):
    order_id: Optional[str]
    name: Optional[str]
    phone: Optional[str]
    tracking_id: Optional[str]

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# --- WhatsApp API Configuration ---
WA_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WA_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_ID") 
WA_TEMPLATE_NAME = "YOUR_APPROVED_TEMPLATE_NAME" # Update this to your exact template name

def send_whatsapp_message(details: ShippingDetails):
    # Hardcoded for testing. Later replace with: to_number = details.phone
    to_number = "919994555088" 
    
    url = f"https://graph.facebook.com/v19.0/{WA_PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Variables must be in the exact order they appear in the template {{1}}, {{2}}, etc.
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": WA_TEMPLATE_NAME,
            "language": {
                "code": "en" # Adjust if your template is en_US, en_GB, etc.
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": details.name or "Customer"},               # {{1}} name
                        {"type": "text", "text": details.order_id or "Unknown"},            # {{2}} order_id
                        {"type": "text", "text": "S T Couriers"},                           # {{3}} courier_name
                        {"type": "text", "text": details.tracking_id or "Pending"},         # {{4}} tracking_id
                        {"type": "text", "text": "https://stcourier.com/track/shipment"}    # {{5}} tracking_url
                    ]
                }
            ]
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"WhatsApp message successfully sent for order {details.order_id}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send WhatsApp message. Error: {e}")
        # Print the exact Meta API error if there is one (very helpful for debugging)
        if response is not None and response.text:
            print(f"Meta API Response: {response.text}")

def log_to_csv(details: ShippingDetails, filename: str):
    csv_file = "shipping_master_log.csv"
    file_exists = os.path.isfile(csv_file)
    
    with open(csv_file, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Source File", "Order ID", "Name", "Phone", "Tracking ID"])
        
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            filename,
            details.order_id, 
            details.name, 
            details.phone, 
            details.tracking_id
        ])

def process_label(image_path):
    filename = os.path.basename(image_path)
    ext = filename.lower().split('.')[-1]
    mime_type = "image/png" if ext == "png" else "image/jpeg"
    
    print(f"Starting OCR for: {filename}")
    
    with open(image_path, "rb") as f:
        image_bytes = f.read()
        
    try:
        # Kept the Flash model as requested
        response = client.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=[
                "Extract Order ID, Name, and Phone. Also find the ST Courier tracking number from the barcode label.",
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ShippingDetails,
                temperature=0.1,
            )
        )
        
        details: ShippingDetails = response.parsed
        
        # 1. Log the details
        log_to_csv(details, filename)
        
        # 2. Trigger the WhatsApp automation if we got a tracking ID
        if details.tracking_id:
            send_whatsapp_message(details)
        else:
            print(f"Skipped WhatsApp notification for {filename} (No tracking ID found)")
            
        return True
    except Exception as e:
        print(f"Error processing {filename}: {e}")
        return False

if __name__ == "__main__":
    target_dir = "labels/pending"
    
    if not os.path.exists(target_dir):
        print(f"Directory {target_dir} not found.")
        exit(0)

    files = [f for f in os.listdir(target_dir) if f.lower().endswith(('png', 'jpg', 'jpeg'))]
    
    if not files:
        print("No labels found in labels/pending/")
        exit(0)

    processed_count = 0
    for filename in files:
        full_path = os.path.join(target_dir, filename)
        if process_label(full_path):
            os.remove(full_path)
            print(f"Success: {filename} logged and deleted.")
            processed_count += 1
            
    print(f"Total labels processed: {processed_count}")
