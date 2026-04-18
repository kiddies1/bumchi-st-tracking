import os
import sys
from google import genai
from google.genai import types

# Setup the client with the stable V1 configuration
client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"],
    http_options={'api_version': 'v1'}
)

def process_label(image_path):
    # Only process image files
    ext = image_path.lower().split('.')[-1]
    if ext not in ['png', 'jpg', 'jpeg']:
        return None

    # Determine the correct mime type
    mime_type = "image/jpeg" if ext in ['jpg', 'jpeg'] else "image/png"

    print(f"Processing: {image_path}")
    
    with open(image_path, "rb") as f:
        image_bytes = f.read()
        
    try:
        # Use types.Part.from_bytes to tell the SDK exactly what we're sending
        response = client.models.generate_content(
            model="gemini-3.0-flash",
            contents=[
                "Extract only the Order ID from this label. Return just the digits.",
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            ]
        )
        
        order_id = response.text.strip()
        print(f"Detected Order ID: {order_id}")
        
        # NOTE: Once this works, you can insert your Shopify & WhatsApp logic here
        
        return order_id
        
    except Exception as e:
        print(f"Error communicating with Gemini API: {e}")
        return None

if __name__ == "__main__":
    target_dir = "labels/pending"
    processed_dir = "labels/processed"
    
    # Ensure our processed directory exists
    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir)

    # Grab all files in the pending folder, ignoring hidden ones like .gitkeep
    if os.path.exists(target_dir):
        files = [f for f in os.listdir(target_dir) if not f.startswith('.')]
    else:
        files = []
    
    if not files:
        print("No new labels found in labels/pending/")
        sys.exit(0)

    for filename in files:
        full_path = os.path.join(target_dir, filename)
        
        # Run the extraction
        process_label(full_path)
        
        # Move to processed folder so it isn't scanned again on the next run
        new_path = os.path.join(processed_dir, filename)
        os.rename(full_path, new_path)
        print(f"Moved to: {new_path}")
