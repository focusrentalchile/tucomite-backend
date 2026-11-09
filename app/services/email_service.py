"""SMTP helpers for branded transactional email."""

import html
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.core.config import settings


class EmailNotConfigured(Exception):
    """Raised when SMTP settings are missing."""


class EmailSendError(Exception):
    """Raised when SMTP delivery fails."""


@dataclass(frozen=True)
class SmtpDeliveryConfig:
    """Resolved SMTP connection values for one send."""

    host: str
    port: int
    user: str
    password: str
    from_address: str
    use_tls: bool


def smtp_config_from_env() -> SmtpDeliveryConfig:
    """Build SMTP config from process environment defaults."""
    return SmtpDeliveryConfig(
        host=settings.smtp_host,
        port=settings.smtp_port,
        user=settings.smtp_user,
        password=settings.smtp_password,
        from_address=settings.smtp_from,
        use_tls=settings.smtp_use_tls,
    )


def smtp_configured(config: SmtpDeliveryConfig | None = None) -> bool:
    """True when host and from address are present."""
    cfg = config or smtp_config_from_env()
    return bool(cfg.host.strip() and cfg.from_address.strip())


def build_support_reply_html(*, visitor_name: str, reply_body: str, site_url: str) -> str:
    """Branded HTML body for a public contact reply."""
    safe_name = html.escape(visitor_name.strip() or "hola")
    safe_body = html.escape(reply_body).replace("\n", "<br />")
    safe_url = html.escape(site_url.strip() or "https://tucomite.cl")
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Respuesta de Tu Comité</title>
</head>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;color:#001545;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f6fb;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border:1px solid #d9e0ef;border-radius:16px;overflow:hidden;">
          <tr>
            <td style="padding:28px 28px 12px;background:#001545;color:#ffffff;">
              <div style="font-size:22px;font-weight:700;letter-spacing:0.02em;">Tu Comité</div>
              <div style="margin-top:6px;font-size:14px;opacity:0.85;">Tu comunidad, mejor conectada</div>
            </td>
          </tr>
          <tr>
            <td style="padding:28px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:1.5;">Hola {safe_name},</p>
              <p style="margin:0 0 12px;font-size:16px;line-height:1.5;">Respondimos tu mensaje:</p>
              <div style="margin:0 0 24px;padding:16px 18px;border-left:4px solid #1554d1;background:#f0f4fc;border-radius:8px;font-size:15px;line-height:1.55;">
                {safe_body}
              </div>
              <table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 auto 8px;">
                <tr>
                  <td align="center" bgcolor="#1554d1" style="border-radius:10px;">
                    <a href="{safe_url}" style="display:inline-block;padding:12px 22px;color:#ffffff;text-decoration:none;font-size:15px;font-weight:700;">
                      Ir a Tu Comité
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin:20px 0 0;font-size:13px;line-height:1.45;color:#5a6a8a;">
                Si no enviaste este mensaje, puedes ignorar este correo.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_html_email(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    smtp: SmtpDeliveryConfig | None = None,
) -> None:
    """Send one HTML email through configured SMTP."""
    cfg = smtp or smtp_config_from_env()
    if not smtp_configured(cfg):
        raise EmailNotConfigured("SMTP is not configured.")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = cfg.from_address
    message["To"] = to_email
    message.set_content("Abrí este correo en un cliente que soporte HTML para ver la respuesta.")
    message.add_alternative(html_body, subtype="html")
    try:
        if cfg.use_tls:
            with smtplib.SMTP(cfg.host, cfg.port, timeout=30) as server:
                server.starttls()
                if cfg.user:
                    server.login(cfg.user, cfg.password)
                server.send_message(message)
        else:
            with smtplib.SMTP(cfg.host, cfg.port, timeout=30) as server:
                if cfg.user:
                    server.login(cfg.user, cfg.password)
                server.send_message(message)
    except Exception as error:  # noqa: BLE001 — surface SMTP failures as domain error
        raise EmailSendError(str(error)) from error
