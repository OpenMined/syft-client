"""Google Drive OAuth setup for monitoring services."""

from pathlib import Path

import click

from syft_bg.common.drive import DRIVE_SCOPES


def setup_drive(credentials_path: Path, token_path: Path) -> bool:
    """Set up Google Drive authentication.

    Args:
        credentials_path: Path to OAuth credentials.json
        token_path: Path to save drive token

    Returns:
        True if setup successful, False otherwise
    """
    if token_path.exists():
        click.echo(f"Drive token exists: {token_path}")
        return True

    click.echo("Google Drive access is required for monitoring jobs and peers.")
    click.echo()

    # Check for credentials file
    if not credentials_path.exists():
        click.echo(f"credentials.json not found at {credentials_path}")
        click.echo()
        click.echo("To get credentials.json:")
        click.echo("  1. Go to Google Cloud Console -> APIs & Services -> Credentials")
        click.echo("  2. Create OAuth 2.0 Client ID (Desktop app)")
        click.echo("  3. Download as credentials.json")
        click.echo(f"  4. Place it at: {credentials_path}")
        click.echo()

        creds_input = click.prompt(
            "Or enter path to credentials.json", type=click.Path(exists=True)
        )
        credentials_path = Path(creds_input).expanduser()

    click.echo("Setting up Google Drive authentication...")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_path), DRIVE_SCOPES
        )
        creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
        click.echo(f"Drive token saved: {token_path}")
        return True
    except ImportError:
        click.echo("google-auth-oauthlib not installed, skipping Drive setup", err=True)
        return False
    except Exception as e:
        click.echo(f"Drive setup failed: {e}", err=True)
        return False
