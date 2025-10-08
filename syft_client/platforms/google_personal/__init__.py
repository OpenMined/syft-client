"""Google Personal platform implementation (personal Gmail accounts)"""

# Lazy loading to avoid google.colab import in subprocess contexts
# We need to define the names in the module namespace for 'from X import Y' to work
# but we delay the actual import until first access

import sys as _sys
from typing import TYPE_CHECKING as _TYPE_CHECKING

# Type hints for IDEs (no runtime import)
if _TYPE_CHECKING:
    from .client import GooglePersonalClient
    from .gmail import GmailTransport
    from .gdrive_files import GDriveFilesTransport
    from .gsheets import GSheetsTransport
    from .gforms import GFormsTransport

# Lazy loader cache
_lazy_imports = {}

def __getattr__(name: str):
    """Lazy load classes when accessed"""
    # Check cache first
    if name in _lazy_imports:
        return _lazy_imports[name]

    # Import on demand
    if name == 'GooglePersonalClient':
        from .client import GooglePersonalClient
        _lazy_imports[name] = GooglePersonalClient
        return GooglePersonalClient
    elif name == 'GmailTransport':
        from .gmail import GmailTransport
        _lazy_imports[name] = GmailTransport
        return GmailTransport
    elif name == 'GDriveFilesTransport':
        from .gdrive_files import GDriveFilesTransport
        _lazy_imports[name] = GDriveFilesTransport
        return GDriveFilesTransport
    elif name == 'GSheetsTransport':
        from .gsheets import GSheetsTransport
        _lazy_imports[name] = GSheetsTransport
        return GSheetsTransport
    elif name == 'GFormsTransport':
        from .gforms import GFormsTransport
        _lazy_imports[name] = GFormsTransport
        return GFormsTransport

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
    """List available exports"""
    return ['GooglePersonalClient', 'GmailTransport', 'GDriveFilesTransport', 'GSheetsTransport', 'GFormsTransport']

__all__ = [
    'GooglePersonalClient',
    'GmailTransport',
    'GDriveFilesTransport',
    'GSheetsTransport',
    'GFormsTransport'
]

# Pre-populate the module's __dict__ with lazy loading proxies for 'from X import Y' compatibility
# This is needed because __getattr__ is only called for attribute access, not import statements
_current_module = _sys.modules[__name__]

class _LazyLoader:
    """Descriptor that loads the actual class on first access"""
    def __init__(self, import_func, name):
        self.import_func = import_func
        self.name = name
        self._cached = None

    def __call__(self, *args, **kwargs):
        """Make the loader callable so it works like a class"""
        if self._cached is None:
            self._cached = self.import_func()
        return self._cached(*args, **kwargs)

    def __getattr__(self, name):
        """Proxy attribute access to the real class"""
        if self._cached is None:
            self._cached = self.import_func()
        return getattr(self._cached, name)

    def __repr__(self):
        if self._cached is None:
            return f"<LazyLoader for {self.name}>"
        return repr(self._cached)

# Define lazy loaders for each class
GooglePersonalClient = _LazyLoader(lambda: __getattr__('GooglePersonalClient'), 'GooglePersonalClient')
GmailTransport = _LazyLoader(lambda: __getattr__('GmailTransport'), 'GmailTransport')
GDriveFilesTransport = _LazyLoader(lambda: __getattr__('GDriveFilesTransport'), 'GDriveFilesTransport')
GSheetsTransport = _LazyLoader(lambda: __getattr__('GSheetsTransport'), 'GSheetsTransport')
GFormsTransport = _LazyLoader(lambda: __getattr__('GFormsTransport'), 'GFormsTransport')