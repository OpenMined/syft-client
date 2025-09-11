"""
Helper functions for integration tests
"""

import syft_client as sc
from .gdrive_adapter import GDriveAdapter


def login_with_adapter(email: str, verbose: bool = False, **kwargs) -> GDriveAdapter:
    """
    Helper function to login and wrap the result in a GDriveAdapter.
    
    Args:
        email: Email address to login with
        verbose: Whether to print verbose output
        **kwargs: Additional arguments to pass to sc.login()
        
    Returns:
        GDriveAdapter: Wrapped client for backward compatibility
    """
    # Determine provider based on email domain
    provider = kwargs.pop('provider', None)
    if not provider:
        if '@gmail.com' in email or '@googlemail.com' in email:
            provider = 'google_personal'
        else:
            # Assume organization account for other domains
            provider = 'google_org'
    
    # Login with syft_client
    syft_client = sc.login(email, provider=provider, verbose=verbose, **kwargs)
    
    # Wrap in adapter for backward compatibility
    return GDriveAdapter(syft_client)