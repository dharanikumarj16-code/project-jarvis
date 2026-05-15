import smtplib
import os

FROM_EMAIL = "[EMAIL_ADDRESS]"
TO_EMAIL = "[EMAIL_ADDRESS]"
GMAIL_APP_PASSWORD = "[PASSWORD]"

def draft_email(subject, body):                 
    """Returns a drafted email ready to send"""
    return f"Subject: {subject}\n\n{body}"

def send_email(draft):
    """Sends the email using SMTP"""
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(FROM_EMAIL, GMAIL_APP_PASSWORD)
            smtp.sendmail(FROM_EMAIL, TO_EMAIL, draft)
        return "Email sent successfully!"
    except Exception as e:
        return f"Failed to send email: {e}"

def check_inbox():
    """Returns a sample of recent emails (simulated)"""
    # In a real implementation, this would connect to the inbox using IMAP
    sample_emails = [
        {"from": "[EMAIL_ADDRESS]", "subject": "Project Update", "body": "Here's the latest progress on the project..."},
        {"from": "[EMAIL_ADDRESS]", "subject": "Meeting Request", "body": "Could you please attend a meeting tomorrow?"}
    ]
    return f"Recent emails:\n{sample_emails}"