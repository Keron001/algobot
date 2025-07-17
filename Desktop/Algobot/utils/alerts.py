import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional
import requests

def send_email_alert(subject: str, message: str, to_email: Optional[str] = None) -> bool:
    """
    Send an email alert using SMTP.
    Args:
        subject (str): Email subject.
        message (str): Email body.
        to_email (Optional[str]): Recipient email. If None, uses ALERT_EMAIL_TO from env.
    Returns:
        bool: True if sent successfully, False otherwise.
    """
    smtp_server = os.environ.get('ALERT_EMAIL_SMTP', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('ALERT_EMAIL_PORT', 587))
    smtp_user = os.environ.get('ALERT_EMAIL_USER')
    smtp_pass = os.environ.get('ALERT_EMAIL_PASS')
    from_email = smtp_user
    to_email = to_email or os.environ.get('ALERT_EMAIL_TO')
    if not (smtp_user and smtp_pass and to_email):
        return False
    try:
        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, [to_email], msg.as_string())
        return True
    except Exception:
        return False

def send_telegram_alert(message: str, chat_id: Optional[str] = None) -> bool:
    """
    Send a Telegram alert using a bot token and chat ID.
    Args:
        message (str): Message to send.
        chat_id (Optional[str]): Telegram chat ID. If None, uses TELEGRAM_CHAT_ID from env.
    Returns:
        bool: True if sent successfully, False otherwise.
    """
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = chat_id or os.environ.get('TELEGRAM_CHAT_ID')
    if not (bot_token and chat_id):
        return False
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    payload = {'chat_id': chat_id, 'text': message}
    try:
        resp = requests.post(url, data=payload, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False 