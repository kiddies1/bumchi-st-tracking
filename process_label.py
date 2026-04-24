import os
import csv
import json
import time
import requests
from datetime import datetime
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Optional

# 1. Schema Definition
class ShippingDetails(BaseModel):
    order_id: Optional[str]
    name: Optional[str]
    phone: Optional[str]
    tracking_id: Optional[str]

# Setup Gemini Client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# --- WhatsApp API Configuration ---
WA_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WA_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_ID") 
WA_TEMPLATE_NAME = "tracking_details" # Ensure this matches Meta exactly

def send_whatsapp_message(details: ShippingDetails):
    # Hardcoded for testing. Later replace with: to_number = details.phone
    to_number = "919994555088" 
    
    url = f"https://graph.facebook.com/v19.0/{WA_PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Updated payload: Now includes "parameter_name" to satisfy Meta's named variable requirements
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": WA_TEMPLATE_NAME,
            "language": {
                "code": "en" 
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "parameter_name": "name", "text": details.name or "Customer"},
                        {"type": "text", "parameter_name": "order_id", "text": details.order_id or "Unknown"},
                        {"type": "text", "parameter_name": "courier_name", "text": "S T Couriers"},
                        {"type": "text", "parameter_name": "tracking_id", "text": details.tracking_id or "Pending"},
                        {"type": "text", "parameter_name": "tracking_url", "text": "https://stcourier.com/track/shipment"}
                    ]
                }
            ]
        }
    }

    print("\nSending WhatsApp Message...")
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"✅ WhatsApp message successfully sent to {to_number} for order {details.order_id}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to send WhatsApp message. Error: {e}")
        if response is not None and response.text:
            print(f"Raw Meta API Response: {response.text}")
            
        # Optional: Print the payload on failure for easier debugging
        print("Payload sent:")
        print(json.dumps(payload, indent=2))

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
    
    print(f"\n--- Starting OCR for: {filename} ---")
    
    with open(image_path, "rb") as f:
        image_bytes = f.read()
        
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Using the stable 2.5-flash model
            response = client.models.generate_content(
                model="gemini-2.5-flash", 
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
            print(f"Extraction Successful: {details.name} | Order: {details.order_id} | Tracking: {details.tracking_id}")
            
            log_to_csv(details, filename)
            
            if details.tracking_id:
                send_whatsapp_message(details)
            else:
                print(f"⚠️ Skipped WhatsApp notification for {filename} (No tracking ID found)")
                
            return True

        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "503" in error_msg or "high demand" in error_msg or "quota" in error_msg:
                if attempt < max_retries - 1:
                    sleep_time = 2 ** (attempt + 1)
                    print(f"API bottleneck detected. Retrying in {sleep_time} seconds (Attempt {attempt + 1}/{max_retries})...")
                    time.sleep(sleep_time)
                    continue 
            
            print(f"❌ Error processing {filename}: {e}")
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
            print(f"🧹 {filename} logged and deleted from pending.")
            processed_count += 1
            
    print(f"\n✅ Total labels processed: {processed_count}")
    
