import os
import sys
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Optional

# 1. Define the exact data structure we want back from Gemini
class ShippingDetails(BaseModel):
    order_id: Optional[str]
    name: Optional[str]
    phone: Optional[str]

# Setup the client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def process_label(image_path):
    # Only process image files
    ext = image_path.lower().split('.')[-1]
    if ext not in ['png', 'jpg', 'jpeg']:
        return None

    mime_type = "image/jpeg" if ext in ['jpg', 'jpeg'] else "image/png"
    print(f"Processing: {image_path}")
    
    with open(image_path, "rb") as f:
        image_bytes = f.read()
        
    try:
        # 2. Pass our schema into the GenerateContentConfig
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                "Extract the Order ID, Recipient Name, and Phone Number from this shipping label.",
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ShippingDetails,
                temperature=0.1, # Low temperature forces the model to stick strictly to the text it sees
            )
        )
        
        # 3. The SDK automatically parses the JSON into our Python object
        details: ShippingDetails = response.parsed
        
        print(f"--- Extracted Details ---")
        print(f"Order ID : {details.order_id}")
        print(f"Name     : {details.name}")
        print(f"Phone    : {details.phone}")
        print(f"-------------------------")
        
        return details
        
    except Exception as e:
        print(f"Error communicating with Gemini API: {e}")
        return None

if __name__ == "__main__":
    target_dir = "labels/pending"
    processed_dir = "labels/processed"
    
    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir)

    if os.path.exists(target_dir):
        files = [f for f in os.listdir(target_dir) if not f.startswith('.')]
    else:
        files = []
    
    if not files:
        print("No new labels found in labels/pending/")
        sys.exit(0)

    for filename in files:
        full_path = os.path.join(target_dir, filename)
        
        process_label(full_path)
        
        new_path = os.path.join(processed_dir, filename)
        os.rename(full_path, new_path)
        print(f"Moved to: {new_path}\n")
