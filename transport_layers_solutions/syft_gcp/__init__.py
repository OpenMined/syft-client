"""
Syft GCP Transport Layer

A simple Python SDK for accessing Google APIs (Gmail, Sheets, Drive, Forms)
with automated setup and secure authentication.

Usage:
    from transport_layers_solutions.syft_gcp import GCPTransport

    gcp = GCPTransport("my-project-id")
    gcp.connect()

    # Use services
    gcp.gmail.users().labels().list(userId='me').execute()
    gcp.sheets.spreadsheets().create(body={'properties': {'title': 'My Sheet'}}).execute()
"""

from .transport import GCPTransport

__version__ = "0.1.0"
__all__ = ["GCPTransport"]
