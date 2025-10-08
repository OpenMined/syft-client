"""Google Personal platform implementation (personal Gmail accounts)"""

# Use lazy imports to avoid triggering google.colab import in subprocesses
def __getattr__(name):
    """Lazy load classes to prevent google.colab import issues"""
    if name == 'GooglePersonalClient':
        from .client import GooglePersonalClient
        return GooglePersonalClient
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
    'GooglePersonalClient',
    'GmailTransport',
    'GDriveFilesTransport',
    'GSheetsTransport',
    'GFormsTransport'
]