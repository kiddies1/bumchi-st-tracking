import os
import google.generativeai as genai
import sys

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

def process_label(image_path):
    # Process the image
    sample_file = genai.upload_file(path=image_path)
    prompt = "Extract only the Order ID from this label. Return just the digits."
    response = model.generate_content([prompt, sample_file])
    
    order_id = response.text.strip()
    
    # Logic to send tracking info (placeholder)
    print(f"ORDER_ID={order_id}") 
    return order_id

if __name__ == "__main__":
    target_dir = "labels/pending"
    files = [f for f in os.listdir(target_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
    
    if not files:
        print("No new labels found.")
        sys.exit(0)

    for filename in files:
        if filename == ".gitkeep":
            continue
        full_path = os.path.join(target_dir, filename)
        process_label(full_path)
        
        # Move to processed folder locally
        os.rename(full_path, os.path.join("labels/processed", filename))
