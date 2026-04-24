import os
import sys
import csv
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Optional

# 1. Added tracking_id to the schema
class ShippingDetails(BaseModel):
    order_id: Optional[str]
    name: Optional[str]
    phone: Optional[str]
    tracking_id: Optional[str] # New Field

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def save_to_csv(details: ShippingDetails):
    csv_file = "shipping_data.csv"
    file_exists = os.path.isfile(csv_file)
    
    with open(csv_file, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Write header only if the file is new
        if not file_exists:
            writer.writerow(["Order ID", "Name", "Phone", "Tracking ID"])
        
        writer.writerow([
            details.order_id, 
            details.name, 
            details.phone, 
            details.tracking_id
        ])

def process_label(image_path):
    ext = image_path.lower().split('.')[-1]
    if ext not in ['png', 'jpg', 'jpeg']:
        return None

    mime_type = "image/jpeg" if ext in ['jpg', 'jpeg'] else "image/png"
    print(f"Processing: {image_path}")
    
    with open(image_path, "rb") as f:
        image_bytes = f.read()
        
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                # Updated Prompt to specifically mention the ST Courier barcode
                "Extract the Order ID, Recipient Name, and Phone Number. "
                "Also, locate the ST Courier barcode and extract the tracking number associated with it.",
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ShippingDetails,
                temperature=0.1,
            )
        )
        
        details: ShippingDetails = response.parsed
        
        # Save the result to our CSV file
        save_to_csv(details)
        
        print(f"--- Extracted & Saved ---")
        print(f"Tracking ID: {details.tracking_id}")
        print(f"Name       : {details.name}")
        print(f"-------------------------")
        
        return details
        
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    target_dir = "labels/pending"
    processed_dir = "labels/processed"
    
    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir)

    files = [f for f in os.listdir(target_dir) if not f.startswith('.')] if os.path.exists(target_dir) else []
    
    if not files:
        print("No new labels found.")
        sys.exit(0)

    for filename in files:
        full_path = os.path.join(target_dir, filename)
        process_label(full_path)
        os.rename(full_path, os.path.join(processed_dir, filename))
