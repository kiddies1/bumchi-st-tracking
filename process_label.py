import os
import sys
from google import genai

# Setup the new client
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def process_label(image_path):
    # Skip non-image files like .gitkeep
    if not image_path.lower().endswith(('.png', '.jpg', '.jpeg')):
        return None

    print(f"Processing: {image_path}")
    
    # Use the new SDK methods
    with open(image_path, "rb") as f:
        image_bytes = f.read()
        
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=["Extract only the Order ID from this label. Return just the digits.", image_bytes]
    )
    
    order_id = response.text.strip()
    print(f"Detected Order ID: {order_id}")
    return order_id

if __name__ == "__main__":
    target_dir = "labels/pending"
    processed_dir = "labels/processed"
    
    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir)

    files = [f for f in os.listdir(target_dir) if not f.startswith('.')]
    
    if not files:
        print("No new labels found.")
        sys.exit(0)

    for filename in files:
        full_path = os.path.join(target_dir, filename)
        process_label(full_path)
        
        # Move to processed folder
        os.rename(full_path, os.path.join(processed_dir, filename))
