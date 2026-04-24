import os
import csv
import json
import time
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Optional

# --- Configuration & Secrets ---
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

WA_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WA_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_ID") 
WA_TEMPLATE_NAME = "YOUR_APPROVED_TEMPLATE_NAME"

EMAIL_SENDER = os.environ.get("GMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
EMAIL_RECIPIENT = "bumchi321@gmail.com"

# --- Schema Definition ---
class ShippingDetails(BaseModel):
    order_id: Optional[str]
    name: Optional[str]
    phone: Optional[str]
    tracking_id: Optional[str]

def send_whatsapp_message(details: ShippingDetails):
    """Sends the WA message and returns a tuple: (Success_Boolean, Error_Message)"""
    to_number = "919994555088" # Hardcoded for testing
    url = f"https://graph.facebook.com/v19.0/{WA_PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": WA_TEMPLATE_NAME,
            "language": {"code": "en"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": details.name or "Customer"},
                        {"type": "text", "text": details.order_id or "Unknown"},
                        {"type": "text", "text": "S T Couriers"},
                        {"type": "text", "text": details.tracking_id or "Pending"},
                        {"type": "text", "text": "https://stcourier.com/track/shipment"}
                    ]
                }
            ]
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return True, "Sent Successfully", payload
    except requests.exceptions.RequestException as e:
        error_msg = response.text if response is not None and response.text else str(e)
        return False, f"API Error: {error_msg}", payload

def log_to_csv(result: dict):
    """Writes every attempt to the CSV, regardless of success."""
    csv_file = "shipping_master_log.csv"
    file_exists = os.path.isfile(csv_file)
    
    with open(csv_file, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Source File", "Order ID", "Name", "Extracted Phone", "Tracking ID", "Gemini Status", "WhatsApp Status", "Notes"])
        
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            result['filename'],
            result.get('order_id', ''),
            result.get('name', ''),
            result.get('phone', ''),
            result.get('tracking_id', ''),
            result['gemini_status'],
            result['wa_status'],
            result['notes']
        ])

def send_summary_email(run_results: list):
    """Formats the run results into an HTML table and sends an email."""
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("Skipping email summary: GMAIL_SENDER or GMAIL_APP_PASSWORD not configured.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Bumchi Label Processing Summary - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT

    success_count = sum(1 for r in run_results if r['gemini_status'] == 'Success' and r['wa_status'] == 'Success')
    total = len(run_results)

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Bumchi Label OCR Run Summary</h2>
        <p><strong>Total Processed:</strong> {total}<br>
        <strong>Fully Successful:</strong> {success_count}<br>
        <strong>Failures/Partial:</strong> {total - success_count}</p>
        
        <table border="1" cellpadding="8" cellspacing="0" style="width: 100%; border-collapse: collapse;">
          <tr style="background-color: #f2f2f2; text-align: left;">
            <th>Filename</th>
            <th>Order Details</th>
            <th>Extracted Phone</th>
            <th>Gemini Status</th>
            <th>WA Status</th>
            <th>Notes / Template Message</th>
          </tr>
    """

    for r in run_results:
        wa_color = "green" if r['wa_status'] == "Success" else "red"
        gemini_color = "green" if r['gemini_status'] == "Success" else "red"
        
        # Format the payload to show what was sent
        payload_str = f"<br><br><small><b>Message Payload:</b><br>{json.dumps(r.get('wa_payload', {}), indent=2)}</small>" if r.get('wa_payload') else ""
        
        html_content += f"""
          <tr>
            <td>{r['filename']}</td>
            <td><b>ID:</b> {r.get('order_id', 'N/A')}<br><b>Name:</b> {r.get('name', 'N/A')}<br><b>Track:</b> {r.get('tracking_id', 'N/A')}</td>
            <td>{r.get('phone', 'N/A')}</td>
            <td style="color: {gemini_color};"><b>{r['gemini_status']}</b></td>
            <td style="color: {wa_color};"><b>{r['wa_status']}</b></td>
            <td>{r['notes']} {payload_str}</td>
          </tr>
        """
    
    html_content += """
        </table>
      </body>
    </html>
    """

    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
        print(f"Summary email successfully sent to {EMAIL_RECIPIENT}")
    except Exception as e:
        print(f"Failed to send email summary: {e}")

def process_label(image_path):
    filename = os.path.basename(image_path)
    ext = filename.lower().split('.')[-1]
    mime_type = "image/png" if ext == "png" else "image/jpeg"
    
    # Base dictionary to hold this image's results
    result = {
        "filename": filename, "order_id": "", "name": "", "phone": "", 
        "tracking_id": "", "gemini_status": "Pending", "wa_status": "Pending", 
        "notes": "", "wa_payload": {}
    }
    
    with open(image_path, "rb") as f:
        image_bytes = f.read()
        
    max_retries = 3
    for attempt in range(max_retries):
        try:
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
            result['gemini_status'] = "Success"
            result['order_id'] = details.order_id
            result['name'] = details.name
            result['phone'] = details.phone
            result['tracking_id'] = details.tracking_id
            
            if details.tracking_id:
                wa_success, wa_msg, payload = send_whatsapp_message(details)
                result['wa_status'] = "Success" if wa_success else "Failed"
                result['notes'] = wa_msg
                result['wa_payload'] = payload
            else:
                result['wa_status'] = "Skipped"
                result['notes'] = "No Tracking ID extracted"
                
            return True, result # Move to next file

        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "503" in error_msg or "quota" in error_msg:
                if attempt < max_retries - 1:
                    time.sleep(2 ** (attempt + 1))
                    continue
            
            # Gemini completely failed
            result['gemini_status'] = "Failed"
            result['wa_status'] = "Skipped"
            result['notes'] = f"Gemini Error: {e}"
            return False, result

if __name__ == "__main__":
    target_dir = "labels/pending"
    
    if not os.path.exists(target_dir):
        print(f"Directory {target_dir} not found.")
        exit(0)

    files = [f for f in os.listdir(target_dir) if f.lower().endswith(('png', 'jpg', 'jpeg'))]
    
    if not files:
        print("No labels found in labels/pending/")
        exit(0)

    run_results = []
    
    for filename in files:
        full_path = os.path.join(target_dir, filename)
        print(f"Processing: {filename}")
        
        success, record = process_label(full_path)
        run_results.append(record)
        log_to_csv(record)
        
        if success:
            os.remove(full_path)
            
    # Send the final summary email after the loop finishes
    send_summary_email(run_results)
