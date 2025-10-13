"""SMTP platform implementation"""

from .client import SMTPClient
from .email import SMTPEmailTransport

__all__ = ["SMTPClient", "SMTPEmailTransport"]
