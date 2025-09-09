"""Microsoft platform implementation (Outlook, Office 365)"""

from .client import MicrosoftClient
from .outlook import OutlookTransport
from .onedrive_files import OneDriveFilesTransport
from .ms_forms import MSFormsTransport

__all__ = [
    'MicrosoftClient',
    'OutlookTransport',
    'OneDriveFilesTransport', 
    'MSFormsTransport'
]