"""Local file-based wallet implementation"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BaseWallet


class LocalFileWallet(BaseWallet):
    """
    Store tokens in local JSON files.

    Directory structure:
    ~/.syft/
    └── [email]/
        └── tokens/
            └── [service].json
    """

    name = "Local File Storage"

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize local file wallet.

        Config options:
            base_dir: Base directory for token storage (default: ~/.syft)
        """
        super().__init__(config)
        self.base_dir = Path(config.get("base_dir", Path.home() / ".syft"))

    def _get_token_dir(self, account: str) -> Path:
        """Get token directory for an account"""
        # Sanitize account for filesystem
        safe_account = account.replace("@", "_at_").replace(".", "_")
        return self.base_dir / safe_account / "tokens"

    def _get_token_path(self, service: str, account: str) -> Path:
        """Get path to token file"""
        return self._get_token_dir(account) / f"{service}.json"

    def store_token(self, service: str, account: str, token_data: Dict) -> bool:
        """Store a token in a JSON file"""
        try:
            # Create directory if it doesn't exist
            token_dir = self._get_token_dir(account)
            token_dir.mkdir(parents=True, exist_ok=True)

            # Add metadata
            token_with_metadata = {
                "service": service,
                "account": account,
                "token_data": token_data,
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "wallet_type": "local_file",
                },
            }

            # Write token file
            token_path = self._get_token_path(service, account)
            with open(token_path, "w") as f:
                json.dump(token_with_metadata, f, indent=2)

            # Set secure permissions (owner read/write only)
            token_path.chmod(0o600)

            return True

        except Exception as e:
            print(f"Failed to store token: {e}")
            return False

    def retrieve_token(self, service: str, account: str) -> Optional[Dict]:
        """Retrieve a token from a JSON file"""
        try:
            token_path = self._get_token_path(service, account)

            if not token_path.exists():
                return None

            with open(token_path, "r") as f:
                data = json.load(f)

            # Update last accessed time
            if "metadata" in data:
                data["metadata"]["last_accessed"] = datetime.now().isoformat()

                # Save updated metadata
                with open(token_path, "w") as f:
                    json.dump(data, f, indent=2)

            # Return just the token data
            return data.get("token_data")

        except Exception as e:
            print(f"Failed to retrieve token: {e}")
            return None

    def get_token_metadata(self, service: str, account: str) -> Optional[Dict]:
        """Retrieve token metadata without loading the token itself"""
        try:
            token_path = self._get_token_path(service, account)

            if not token_path.exists():
                return None

            with open(token_path, "r") as f:
                data = json.load(f)

            return data.get("metadata", {})

        except Exception as e:
            print(f"Failed to retrieve token metadata: {e}")
            return None

    def update_token_metadata(
        self, service: str, account: str, metadata_updates: Dict
    ) -> bool:
        """Update token metadata without modifying the token itself"""
        try:
            token_path = self._get_token_path(service, account)

            if not token_path.exists():
                return False

            # Read current data
            with open(token_path, "r") as f:
                data = json.load(f)

            # Update metadata
            if "metadata" not in data:
                data["metadata"] = {}

            data["metadata"].update(metadata_updates)
            data["metadata"]["last_updated"] = datetime.now().isoformat()

            # Write back
            with open(token_path, "w") as f:
                json.dump(data, f, indent=2)

            return True

        except Exception as e:
            print(f"Failed to update token metadata: {e}")
            return False

    def delete_token(self, service: str, account: str) -> bool:
        """Delete a token file"""
        try:
            token_path = self._get_token_path(service, account)

            if token_path.exists():
                token_path.unlink()

                # Clean up empty directories
                token_dir = self._get_token_dir(account)
                if token_dir.exists() and not any(token_dir.iterdir()):
                    token_dir.rmdir()

                account_dir = token_dir.parent
                if account_dir.exists() and not any(account_dir.iterdir()):
                    account_dir.rmdir()

            return True

        except Exception as e:
            print(f"Failed to delete token: {e}")
            return False

    def list_tokens(self, service: Optional[str] = None) -> List[str]:
        """List all stored tokens"""
        tokens = []

        try:
            if not self.base_dir.exists():
                return tokens

            # Iterate through all account directories
            for account_dir in self.base_dir.iterdir():
                if not account_dir.is_dir():
                    continue

                token_dir = account_dir / "tokens"
                if not token_dir.exists():
                    continue

                # Restore account from directory name
                account = account_dir.name.replace("_at_", "@").replace("_", ".")

                # List token files
                for token_file in token_dir.glob("*.json"):
                    token_service = token_file.stem

                    # Apply service filter if provided
                    if service and token_service != service:
                        continue

                    tokens.append(f"{token_service}:{account}")

            return sorted(tokens)

        except Exception as e:
            print(f"Failed to list tokens: {e}")
            return []

    def test_connection(self) -> bool:
        """Test if we can write to the base directory"""
        try:
            # Try to create base directory
            self.base_dir.mkdir(parents=True, exist_ok=True)

            # Try to write a test file
            test_file = self.base_dir / ".wallet_test"
            test_file.write_text("test")
            test_file.unlink()

            return True

        except Exception:
            return False

    def cleanup_old_tokens(
        self, service: str, account: str, keep_count: int = 5
    ) -> None:
        """
        Clean up old token backups (if implementing versioning).

        This is a utility method for future use if we want to keep
        multiple versions of tokens.
        """
        # For now, we only keep one token per service/account
        # This method is here for future expansion
        pass
