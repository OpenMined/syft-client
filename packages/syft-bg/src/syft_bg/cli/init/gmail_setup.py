"""Gmail OAuth setup for notification service."""

from pathlib import Path

import click


def setup_gmail(
    credentials_path: Path,
    token_path: Path,
    skip: bool = False,
    quiet: bool = False,
) -> bool:
    """Set up Gmail authentication.

    Args:
        credentials_path: Path to OAuth credentials.json
        token_path: Path to save gmail_token.json
        skip: If True, skip OAuth setup (token must already exist)
        quiet: If True, suppress output messages

    Returns:
        True if setup successful, False otherwise
    """
    if token_path.exists():
        if not quiet:
            click.echo(f"Gmail token exists: {token_path}")
        return True

    # If skip requested but token doesn't exist, fail
    if skip:
        click.echo("Error: Cannot skip Gmail OAuth - token not found")
        click.echo(f"  Expected: {token_path}")
        click.echo()
        click.echo("Either:")
        click.echo("  - Run without --skip-oauth to complete Gmail authentication")
        click.echo("  - Provide existing token with --gmail-token /path/to/token.json")
        return False

    if not quiet:
        click.echo("Gmail is required for email notifications.")
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
        click.echo("Setting up Gmail authentication...")
    try:
        from syft_bg.notify.gmail import GmailAuth

        auth = GmailAuth()
        credentials = auth.setup_auth(credentials_path)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json())
        if not quiet:
            click.echo(f"Gmail token saved: {token_path}")
        return True
    except ImportError:
        click.echo("Gmail auth module not available, skipping setup", err=True)
        return False
    except Exception as e:
        click.echo(f"Gmail setup failed: {e}", err=True)
        return False
