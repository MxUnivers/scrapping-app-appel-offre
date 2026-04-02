# test_smtp.py
import smtplib
from email.mime.text import MIMEText
from config import Config

def test_smtp_connection():
    try:
        server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT)
        server.starttls()
        server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        
        msg = MIMEText("✅ Connexion SMTP réussie!")
        msg['Subject'] = "Test SMTP"
        msg['From'] = Config.MAIL_USERNAME
        msg['To'] = Config.MAIL_USERNAME
        # msg['To'] = Config.MAIL_USERNAME
        
        server.send_message(msg)
        server.quit()
        
        print("✅ SMTP OK - Email envoyé!")
        return True
    except Exception as e:
        print(f"❌ SMTP Error: {e}")
        return False

if __name__ == "__main__":
    test_smtp_connection()