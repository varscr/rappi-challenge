import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

def send_report_email(recipient_email: str, html_content: str, report_path: Path) -> bool:
    """Send the HTML report via SMTP. Supports real or simulated mode."""
    
    # 1. Get credentials from environment or st.secrets
    smtp_server = os.getenv("SMTP_SERVER") or st.secrets.get("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT") or st.secrets.get("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER") or st.secrets.get("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD") or st.secrets.get("SMTP_PASSWORD")

    # 2. Simulated mode if credentials are missing
    if not all([smtp_server, smtp_port, smtp_user, smtp_password]):
        print(f"SIMULATION: Email would be sent to {recipient_email} using {report_path.name}")
        return True

    # 3. Real SMTP logic
    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = recipient_email
        msg["Subject"] = f"Rappi Operations — Reporte Ejecutivo de Insights ({report_path.stem})"

        # Attach HTML body
        msg.attach(MIMEText(html_content, "html"))

        # Connect and send
        with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
