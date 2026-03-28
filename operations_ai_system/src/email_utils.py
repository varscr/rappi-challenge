import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

def send_report_email(recipient_email: str, html_content: str, report_path: Path) -> tuple[bool, str]:
    """Send the HTML report via Resend API. Supports real or simulated mode.
    
    Returns:
        (success_bool, status_message)
    """
    
    # 1. Try to import resend, handle gracefully if missing
    try:
        import resend
    except ImportError:
        st.info("ℹ️ Modo Simulación: Librería 'resend' no instalada.")
        return True, "Simulación: Librería faltante"

    # 2. Get API Key from environment or st.secrets
    resend_api_key = os.getenv("RESEND_API_KEY")
    
    # If running on Streamlit Cloud, st.secrets will be available
    try:
        if not resend_api_key and "RESEND_API_KEY" in st.secrets:
            resend_api_key = st.secrets["RESEND_API_KEY"]
    except Exception:
        pass

    # 3. Simulated mode if API Key is missing
    if not resend_api_key:
        st.info("ℹ️ Modo Simulación: No se encontró RESEND_API_KEY.")
        return True, "Simulación: Sin API Key"

    # 4. Real Resend logic
    try:
        resend.api_key = resend_api_key
        
        params = {
            "from": "Rappi AI <onboarding@resend.dev>",
            "to": [recipient_email],
            "subject": f"Rappi Operations — Reporte Ejecutivo ({report_path.stem})",
            "html": html_content,
        }

        r = resend.Emails.send(params)
        # Resend returns an ID if successful
        if hasattr(r, "id") or (isinstance(r, dict) and "id" in r):
            return True, f"✅ Email real enviado a {recipient_email}"
        return True, "Email procesado (verificar dashboard de Resend)"
        
    except Exception as e:
        error_msg = str(e)
        # Check for Sandbox restriction
        if "send testing emails to your own email address" in error_msg:
            return False, "⚠️ Sandbox: Solo puedes enviar emails a TU PROPIA dirección de registro en Resend."
        return False, f"❌ Error API: {error_msg}"
