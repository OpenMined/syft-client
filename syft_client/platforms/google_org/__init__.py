"""Google Organizational platform implementation (Google Workspace)"""

# Use lazy imports to avoid triggering google.colab import in subprocesses
def __getattr__(name):
    """Lazy load classes to prevent google.colab import issues"""
    if name == 'GoogleOrgClient':
        from .client import GoogleOrgClient
        return GoogleOrgClient
    elif name == 'GmailTransport':
        from .gmail import GmailTransport
        return GmailTransport
    elif name == 'GDriveFilesTransport':
        from .gdrive_files import GDriveFilesTransport
        return GDriveFilesTransport
    elif name == 'GSheetsTransport':
        from .gsheets import GSheetsTransport
        return GSheetsTransport
    elif name == 'GFormsTransport':
        from .gforms import GFormsTransport
        return GFormsTransport
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'GoogleOrgClient',
    'GmailTransport',
    'GDriveFilesTransport',
    'GSheetsTransport',
    'GFormsTransport'
]