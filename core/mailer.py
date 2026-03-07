import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .config import settings
from .logging import logger

def send_email(subject: str, body: str):
    """
    Sends an email notification to the administrator.
    """
    if not all([settings.SMTP_EMAIL, settings.SMTP_PASSWORD, settings.ADMIN_EMAIL]):
        logger.warning("SMTP settings are not fully configured. Email not sent.")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = settings.SMTP_EMAIL
        msg['To'] = settings.ADMIN_EMAIL
        msg['Subject'] = f"[{settings.PROJECT_NAME}] {subject}"

        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_EMAIL, settings.SMTP_PASSWORD)
            server.send_message(msg)
            
        logger.info(f"Email sent successfully: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

def notify_server_wake():
    send_email(
        "Server Wake Alert",
        "The backend server has just started/woken up from a cold start."
    )

def notify_error(error_msg: str):
    send_email(
        "Critical Error Alert",
        f"An error occurred in the backend: {error_msg}"
    )

def notify_downtime():
    send_email(
        "Downtime Detected",
        "The server failed to respond to a keep-alive ping."
    )
