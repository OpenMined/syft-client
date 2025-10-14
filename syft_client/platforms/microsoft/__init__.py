"""Microsoft platform implementation (Outlook, Office 365)"""

from .client import MicrosoftClient
from .ms_forms import MSFormsTransport
from .onedrive_files import OneDriveFilesTransport
from .outlook import OutlookTransport

__all__ = [
    "MicrosoftClient",
    "OutlookTransport",
    "OneDriveFilesTransport",
    "MSFormsTransport",
]
