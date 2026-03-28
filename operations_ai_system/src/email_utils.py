import os
from pathlib import Path
import streamlit as st
import resend
from dotenv import load_dotenv

load_dotenv()

def send_report_email(recipient_email: str, html_content: str, report_path: Path) -> bool:
    """Send the HTML report via Resend API. Supports real or simulated mode."""
    
    # 1. Get API Key from environment or st.secrets
    resend_api_key = os.getenv("RESEND_API_KEY")
    
    # If running on Streamlit Cloud, st.secrets will be available
    try:
        if not resend_api_key and "RESEND_API_KEY" in st.secrets:
            resend_api_key = st.secrets["RESEND_API_KEY"]
    except Exception:
        pass

    # 2. Simulated mode if API Key is missing
    if not resend_api_key:
        print(f"SIMULATION: Email would be sent to {recipient_email} using Resend API.")
        return True

    # 3. Real Resend logic
    try:
        resend.api_key = resend_api_key
        
        # Resend Free Tier requires sending from a verified domain or 'onboarding@resend.dev'
        # if no domain is verified yet.
        params = {
            "from": "Rappi AI <onboarding@resend.dev>",
            "to": [recipient_email],
            "subject": f"Rappi Operations — Reporte Ejecutivo ({report_path.stem})",
            "html": html_content,
        }

        resend.Emails.send(params)
        return True
    except Exception as e:
        print(f"Error sending email via Resend: {e}")
        return False
