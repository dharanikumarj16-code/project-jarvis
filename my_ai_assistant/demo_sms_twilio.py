import os
import sys
try:
    from twilio.rest import Client
except ImportError:
    print("❌ Twilio library not found.")
    print("   Please install it by running: pip install twilio")
    sys.exit(1)

def send_demo_sms():
    print("🤖 Twilio SMS Demo Sender")
    print("-------------------------")

    # --- CONFIGURATION (Replace these with your Twilio details) ---
    account_sid = "your_account_sid"   # Found on Twilio Dashboard
    auth_token = "your_auth_token"     # Found on Twilio Dashboard
    twilio_number = "+1234567890"      # Your Trial/Purchased Twilio Number
    target_number = "+917695992514"    # Your Verified Phone Number
    # --------------------------------------------------------------

    if account_sid == "your_account_sid":
        print("⚠️  Please open this script and update 'account_sid' and 'auth_token' with your Twilio credentials.")
        return

    try:
        client = Client(account_sid, auth_token)

        # Professional Bank Alert Message (Shortened for SMS)
        message_body = "Canada Bank ALERT: CAD 1,500.00 debited from A/c XXXX2457 on 23-Jan-2026. Avl Bal: CAD 567.90"

        print(f"📤 Sending message to {target_number}...")
        
        message = client.messages.create(
            body=message_body,
            from_=twilio_number,
            to=target_number
        )

        print(f"✅ Message sent successfully!")
        print(f"   SID: {message.sid}")
        
    except Exception as e:
        print(f"❌ Error sending SMS: {e}")
        print("   Tip: Check if your Account SID, Token, and Phone Numbers are correct.")

if __name__ == "__main__":
    send_demo_sms()
