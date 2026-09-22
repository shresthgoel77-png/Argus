import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from .provider_base import BaseEmailProvider, EmailSendResult


class SMTPEmailProvider(BaseEmailProvider):
    key = "smtp"
    
    def send(self, to: str, subject: str, html_body: str, text_body: str) -> EmailSendResult:
        # Check if SMTP is configured. If not, exit gracefully with not_configured indicator.
        if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
            return EmailSendResult(success=False, error_message="not_configured")
            
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            # Use configured from_address if set, else fallback to the username
            msg['From'] = settings.smtp_from_address if settings.smtp_from_address else settings.smtp_username
            msg['To'] = to
            
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            
            msg.attach(part1)
            msg.attach(part2)
            
            port = settings.smtp_port if settings.smtp_port else (587 if settings.smtp_use_tls else 25)
            server = smtplib.SMTP(settings.smtp_host, port)
            
            if settings.smtp_use_tls:
                server.starttls()
                
            server.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            server.send_message(msg)
            server.quit()
            
            return EmailSendResult(success=True)
            
        except smtplib.SMTPAuthenticationError:
            return EmailSendResult(success=False, error_message="SMTP Authentication Error")
        except smtplib.SMTPConnectError:
            return EmailSendResult(success=False, error_message="SMTP Connection Error")
        except smtplib.SMTPException:
            return EmailSendResult(success=False, error_message="SMTP Send Error")
        except Exception:
            return EmailSendResult(success=False, error_message="SMTP Send Error")
