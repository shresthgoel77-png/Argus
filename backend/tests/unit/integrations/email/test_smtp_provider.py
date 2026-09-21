import pytest
import smtplib
from unittest.mock import patch, MagicMock

from app.integrations.email.smtp_provider import SMTPEmailProvider


@pytest.fixture
def smtp_provider():
    return SMTPEmailProvider()

def test_smtp_not_configured(smtp_provider):
    with patch("app.integrations.email.smtp_provider.settings") as mock_settings:
        # Simulate missing host
        mock_settings.smtp_host = None
        mock_settings.smtp_username = "testuser"
        
        mock_password = MagicMock()
        mock_password.get_secret_value.return_value = "pass"
        mock_settings.smtp_password = mock_password
        
        result = smtp_provider.send("test@example.com", "Test Subject", "<p>HTML</p>", "Text")
        
        assert not result.success
        assert result.error_message == "not_configured"

@patch("app.integrations.email.smtp_provider.smtplib.SMTP")
def test_smtp_successful_send_with_tls(mock_smtp_class, smtp_provider):
    with patch("app.integrations.email.smtp_provider.settings") as mock_settings:
        mock_settings.smtp_host = "smtp.example.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_username = "user@example.com"
        
        mock_password = MagicMock()
        mock_password.get_secret_value.return_value = "password123"
        mock_settings.smtp_password = mock_password
        
        mock_settings.smtp_use_tls = True
        mock_settings.smtp_from_address = "noreply@example.com"
        
        # Setup mock instance
        mock_smtp_instance = MagicMock()
        mock_smtp_class.return_value = mock_smtp_instance
        
        result = smtp_provider.send("user2@example.com", "Hello", "<p>World</p>", "World")
        
        # Verify success
        assert result.success is True
        assert result.error_message is None
        
        # Verify interactions
        mock_smtp_class.assert_called_once_with("smtp.example.com", 587)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("user@example.com", "password123")
        mock_smtp_instance.send_message.assert_called_once()
        mock_smtp_instance.quit.assert_called_once()

@patch("app.integrations.email.smtp_provider.smtplib.SMTP")
def test_smtp_auth_failure(mock_smtp_class, smtp_provider):
    with patch("app.integrations.email.smtp_provider.settings") as mock_settings:
        mock_settings.smtp_host = "smtp.example.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_username = "wrong"
        
        mock_password = MagicMock()
        mock_password.get_secret_value.return_value = "pass"
        mock_settings.smtp_password = mock_password
        
        mock_settings.smtp_use_tls = True
        mock_settings.smtp_from_address = "from@example.com"
        
        mock_smtp_instance = MagicMock()
        mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
        mock_smtp_class.return_value = mock_smtp_instance
        
        result = smtp_provider.send("dst@example.com", "Subj", "<p>H</p>", "T")
        
        assert not result.success
        assert result.error_message == "SMTP Authentication Error"

@patch("app.integrations.email.smtp_provider.smtplib.SMTP")
def test_smtp_connection_failure(mock_smtp_class, smtp_provider):
    with patch("app.integrations.email.smtp_provider.settings") as mock_settings:
        mock_settings.smtp_host = "smtp.bad.com"
        mock_settings.smtp_port = 25
        mock_settings.smtp_username = "user"
        
        mock_password = MagicMock()
        mock_password.get_secret_value.return_value = "pass"
        mock_settings.smtp_password = mock_password
        
        mock_settings.smtp_use_tls = False
        mock_settings.smtp_from_address = "from@example.com"
        
        # Exception thrown upon SMTP construction (or connect)
        mock_smtp_class.side_effect = smtplib.SMTPConnectError(111, b"Connection refused")
        
        result = smtp_provider.send("dst@example.com", "Subj", "<p>H</p>", "T")
        
        assert not result.success
        assert result.error_message == "SMTP Connection Error"
