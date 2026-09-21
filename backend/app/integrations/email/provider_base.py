from abc import ABC, abstractmethod
from pydantic import BaseModel

class EmailSendResult(BaseModel):
    success: bool
    error_message: str | None = None

class BaseEmailProvider(ABC):
    key: str
    
    @abstractmethod
    def send(self, to: str, subject: str, html_body: str, text_body: str) -> EmailSendResult:
        """Send an email."""
        pass
