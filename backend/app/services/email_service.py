"""Email service — SMTP-based transactional emails."""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_smtp_config() -> dict | None:
    host = getattr(settings, "SMTP_HOST", "")
    port = getattr(settings, "SMTP_PORT", 587)
    user = getattr(settings, "SMTP_USER", "")
    password = getattr(settings, "SMTP_PASSWORD", "")
    sender = getattr(settings, "SMTP_FROM", user)
    if not (host and user and password):
        return None
    return {"host": host, "port": int(port), "user": user, "password": password, "sender": sender}


def send_email(to: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """Send a transactional email. Returns True on success, False if SMTP not configured."""
    cfg = _get_smtp_config()
    if not cfg:
        logger.warning("smtp_not_configured", to=to, subject=subject)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["sender"]
    msg["To"] = to

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["sender"], [to], msg.as_string())
        logger.info("email_sent", to=to, subject=subject)
        return True
    except Exception as exc:
        logger.error("email_failed", to=to, subject=subject, error=str(exc))
        return False


def _digest_html(
    user_email: str,
    top_skills: list[dict],
    top_companies: list[dict],
    profile_tips: list[str],
    role: str,
) -> str:
    skills_rows = "".join(
        f"<tr><td style='padding:6px 12px;border-bottom:1px solid #1e293b;'>{s['skill']}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #1e293b;color:#60a5fa;'>{s['frequency_pct']}%</td></tr>"
        for s in top_skills[:10]
    )
    companies_list = ", ".join(c["name"] for c in top_companies[:5])
    tips_html = "".join(f"<li style='margin-bottom:6px;'>{t}</li>" for t in profile_tips[:3])

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;margin:0;padding:24px;">
  <div style="max-width:560px;margin:0 auto;">
    <div style="background:#1e293b;border-radius:12px;padding:28px;margin-bottom:20px;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:20px;">
        <span style="background:#2563eb;border-radius:8px;padding:6px 10px;font-size:16px;">⚡</span>
        <span style="font-weight:700;font-size:18px;">LinkedIn<span style="color:#60a5fa;">Intelligence</span></span>
      </div>
      <h2 style="margin:0 0 4px;font-size:20px;">Resumen semanal de mercado</h2>
      <p style="margin:0;color:#64748b;font-size:13px;">Las 10 skills más demandadas para <strong style="color:#94a3b8;">{role}</strong> esta semana</p>
    </div>

    <div style="background:#1e293b;border-radius:12px;padding:24px;margin-bottom:16px;">
      <h3 style="margin:0 0 16px;font-size:15px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;">Top Skills en Demanda</h3>
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr>
            <th style="text-align:left;padding:6px 12px;border-bottom:1px solid #334155;color:#64748b;font-size:12px;">Skill</th>
            <th style="text-align:left;padding:6px 12px;border-bottom:1px solid #334155;color:#64748b;font-size:12px;">Frecuencia</th>
          </tr>
        </thead>
        <tbody>{skills_rows}</tbody>
      </table>
    </div>

    <div style="background:#1e293b;border-radius:12px;padding:24px;margin-bottom:16px;">
      <h3 style="margin:0 0 12px;font-size:15px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;">Empresas Contratando</h3>
      <p style="margin:0;color:#e2e8f0;font-size:14px;">{companies_list}</p>
    </div>

    {'<div style="background:#1e293b;border-radius:12px;padding:24px;margin-bottom:16px;"><h3 style="margin:0 0 12px;font-size:15px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;">Tips para tu perfil</h3><ul style="margin:0;padding-left:20px;font-size:14px;">' + tips_html + '</ul></div>' if profile_tips else ''}

    <p style="text-align:center;color:#334155;font-size:12px;margin-top:24px;">
      LinkedIn Intelligence · Para profesionales tech de Latam<br>
      <a href="#" style="color:#334155;">Cancelar suscripción</a>
    </p>
  </div>
</body>
</html>
"""
