"""Google Drive OAuth setup for monitoring services."""

from pathlib import Path

import click

from syft_bg.common.drive import DRIVE_SCOPES


def setup_drive(
    credentials_path: Path,
    token_path: Path,
    skip: bool = False,
    quiet: bool = False,
) -> bool:
    """Set up Google Drive authentication.

    Args:
        credentials_path: Path to OAuth credentials.json
        token_path: Path to save drive token
        skip: If True, skip OAuth setup (token must already exist)
        quiet: If True, suppress output messages

    Returns:
        True if setup successful, False otherwise
    """
    if token_path.exists():
        if not quiet:
            click.echo(f"Drive token exists: {token_path}")
        return True

    # If skip requested but token doesn't exist, fail
    if skip:
        click.echo("Error: Cannot skip Drive OAuth - token not found")
        click.echo(f"  Expected: {token_path}")
        click.echo()
        click.echo("Either:")
        click.echo("  - Run without --skip-oauth to complete Drive authentication")
        click.echo("  - Provide existing token with --drive-token /path/to/token.json")
        return False

    if not quiet:
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

        if quiet:
            return False

        creds_input = click.prompt(
            "Or enter path to credentials.json", type=click.Path(exists=True)
        )
        credentials_path = Path(creds_input).expanduser()

    if not quiet:
        click.echo("Setting up Google Drive authentication...")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_path), DRIVE_SCOPES
        )

        # Manual OAuth flow for headless environments (Colab, SSH, containers)
        # Set redirect URI for out-of-band (manual) flow
        flow.redirect_uri = "http://localhost:1"

        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

        click.echo()
        click.echo("Please visit this URL to authorize the application:")
        click.echo()
        click.echo(f"    {auth_url}")
        click.echo()
        click.echo("After authorizing, you'll be redirected to a page that won't load.")
        click.echo(
            "Copy the 'code' parameter from the URL in your browser's address bar."
        )
        click.echo("The URL will look like: http://localhost:1/?code=XXXXX&scope=...")
        click.echo()

        code = input("Enter the authorization code: ").strip()
        flow.fetch_token(code=code)
        creds = flow.credentials

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
