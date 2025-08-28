"""
Test helper utilities for syft-client tests
"""
import os
import time
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import Mock, MagicMock
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestEnvironment:
    """Helper class to manage test environment"""
    
    @staticmethod
    def is_integration_test() -> bool:
        """Check if we're running integration tests"""
        return os.environ.get('SYFT_TEST_MODE') == 'integration'
    
    @staticmethod
    def is_ci() -> bool:
        """Check if we're running in CI"""
        return os.environ.get('CI') == 'true' or os.environ.get('GITHUB_ACTIONS') == 'true'
    
    @staticmethod
    def get_test_users() -> Dict[str, str]:
        """Get test user emails from environment"""
        return {
            'user1': os.environ.get('TEST_USER1_EMAIL', 'test-user1@example.com'),
            'user2': os.environ.get('TEST_USER2_EMAIL', 'test-user2@example.com')
        }
    
    @staticmethod
    def has_google_credentials() -> bool:
        """Check if Google credentials are available"""
        return bool(
            os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') or
            os.environ.get('TEST_USER1_CREDENTIALS') or
            os.environ.get('TEST_USER2_CREDENTIALS')
        )


class MockGoogleDriveBuilder:
    """Builder class for creating mock Google Drive services"""
    
    def __init__(self):
        self.mock_service = Mock()
        self.folders = {}  # folder_id -> folder_data
        self.permissions = {}  # folder_id -> [permissions]
        self.next_id = 2000
        
    def with_folders(self, folder_names: List[str]) -> 'MockGoogleDriveBuilder':
        """Add mock folders to the service"""
        for name in folder_names:
            folder_id = str(self.next_id)
            self.next_id += 1
            self.folders[folder_id] = {
                'id': folder_id,
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
        return self
    
    def with_user_email(self, email: str) -> 'MockGoogleDriveBuilder':
        """Set the user email for about() calls"""
        mock_about = Mock()
        mock_about.get().execute.return_value = {'user': {'emailAddress': email}}
        self.mock_service.about.return_value = mock_about
        return self
    
    def with_create_folder_response(self, folder_id: str = None) -> 'MockGoogleDriveBuilder':
        """Mock folder creation responses"""
        if folder_id is None:
            folder_id = str(self.next_id)
            self.next_id += 1
        
        mock_files = Mock()
        mock_files.create().execute.return_value = {'id': folder_id}
        mock_files.list().execute.return_value = {'files': list(self.folders.values())}
        mock_files.permissions().create().execute.return_value = {'id': f'perm_{folder_id}'}
        
        self.mock_service.files.return_value = mock_files
        return self
    
    def build(self) -> Mock:
        """Build the mock service"""
        return self.mock_service


def create_temp_credentials_file(credentials_data: Dict[str, Any] = None) -> str:
    """
    Create a temporary credentials file for testing
    
    Args:
        credentials_data: Custom credentials data, or None for default
        
    Returns:
        Path to the temporary credentials file
    """
    if credentials_data is None:
        credentials_data = {
            "type": "service_account",
            "project_id": "test-project-123",
            "private_key_id": "test-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\ntest-private-key\n-----END PRIVATE KEY-----\n",
            "client_email": "test@test-project-123.iam.gserviceaccount.com",
            "client_id": "123456789",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
        }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(credentials_data, f, indent=2)
        return f.name


def create_temp_token_file(token_data: Dict[str, Any] = None) -> str:
    """
    Create a temporary token file for testing
    
    Args:
        token_data: Custom token data, or None for default
        
    Returns:
        Path to the temporary token file
    """
    if token_data is None:
        token_data = {
            "type": "authorized_user",
            "client_id": "test-client-id.apps.googleusercontent.com",
            "client_secret": "test-client-secret",
            "refresh_token": "test-refresh-token",
            "token": "test-access-token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "scopes": ["https://www.googleapis.com/auth/drive"]
        }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(token_data, f, indent=2)
        return f.name


def wait_for_drive_propagation(seconds: int = 2, message: str = None):
    """
    Wait for Google Drive API changes to propagate
    
    Args:
        seconds: Number of seconds to wait
        message: Optional message to display
    """
    if message:
        print(f"   ⏳ {message}")
    time.sleep(seconds)


def assert_folder_structure_exists(client, expected_folders: List[str], timeout: int = 10):
    """
    Assert that expected folder structure exists, with retry logic
    
    Args:
        client: GDriveUnifiedClient instance
        expected_folders: List of folder names that should exist
        timeout: Maximum seconds to wait for folders to appear
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        missing_folders = []
        
        for folder_name in expected_folders:
            if not client._folder_exists(folder_name):
                missing_folders.append(folder_name)
        
        if not missing_folders:
            return  # All folders found
        
        time.sleep(1)  # Wait before retry
    
    # If we get here, some folders are still missing
    missing_folders = [f for f in expected_folders if not client._folder_exists(f)]
    if missing_folders:
        raise AssertionError(f"Missing folders after {timeout}s: {missing_folders}")


def extract_email_from_folder_name(folder_name: str) -> Optional[str]:
    """
    Extract email from syft folder names
    
    Args:
        folder_name: Folder name like "syft_user1_to_user2_pending"
        
    Returns:
        Extracted email or None if not a syft folder
    """
    if not folder_name.startswith('syft_'):
        return None
    
    parts = folder_name.split('_')
    if len(parts) < 4:
        return None
    
    # Extract target user part (between 'to' and suffix)
    try:
        to_index = parts.index('to')
        if to_index + 1 < len(parts):
            user_part = parts[to_index + 1]
            # This is a simplified extraction - real implementation may vary
            return f"{user_part}@gmail.com"
    except ValueError:
        pass
    
    return None


def generate_test_folder_names(user1_email: str, user2_email: str) -> Dict[str, List[str]]:
    """
    Generate expected folder names for two users
    
    Args:
        user1_email: First user's email
        user2_email: Second user's email
        
    Returns:
        Dictionary with folder names for each user
    """
    def clean_email_for_folder(email: str) -> str:
        return email.split('@')[0].replace('.', '_').replace('+', '_')
    
    user1_clean = clean_email_for_folder(user1_email)
    user2_clean = clean_email_for_folder(user2_email)
    
    return {
        'user1_folders': [
            f"syft_{user1_clean}_to_{user2_clean}_pending",
            f"syft_{user1_clean}_to_{user2_clean}_outbox_inbox",
            f"syft_{user1_clean}_archive_{user2_clean}"
        ],
        'user2_folders': [
            f"syft_{user2_clean}_to_{user1_clean}_pending",
            f"syft_{user2_clean}_to_{user1_clean}_outbox_inbox", 
            f"syft_{user2_clean}_archive_{user1_clean}"
        ]
    }


class TestTimer:
    """Helper class for timing test operations"""
    
    def __init__(self, name: str = "Operation"):
        self.name = name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        print(f"⏱️  Starting {self.name}...")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        
        if exc_type:
            print(f"❌ {self.name} failed after {duration:.2f}s")
        else:
            print(f"✅ {self.name} completed in {duration:.2f}s")
    
    @property
    def duration(self) -> float:
        """Get the duration of the timed operation"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0


def retry_on_failure(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator to retry operations that might fail due to API rate limits or temporary issues
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts
        backoff: Multiplier for delay on each retry
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed: {e}")
                    
                    if attempt < max_attempts - 1:
                        time.sleep(current_delay)
                        current_delay *= backoff
            
            # All attempts failed
            raise last_exception
        
        return wrapper
    return decorator


class TestDataCollector:
    """Collect test data for analysis and debugging"""
    
    def __init__(self):
        self.data = {
            'test_runs': [],
            'performance_metrics': {},
            'errors': [],
            'folder_operations': []
        }
    
    def record_test_run(self, test_name: str, duration: float, success: bool, details: Dict[str, Any] = None):
        """Record a test run"""
        self.data['test_runs'].append({
            'name': test_name,
            'duration': duration,
            'success': success,
            'timestamp': time.time(),
            'details': details or {}
        })
    
    def record_performance_metric(self, operation: str, duration: float, metadata: Dict[str, Any] = None):
        """Record a performance metric"""
        if operation not in self.data['performance_metrics']:
            self.data['performance_metrics'][operation] = []
        
        self.data['performance_metrics'][operation].append({
            'duration': duration,
            'timestamp': time.time(),
            'metadata': metadata or {}
        })
    
    def record_error(self, error_type: str, message: str, context: Dict[str, Any] = None):
        """Record an error"""
        self.data['errors'].append({
            'type': error_type,
            'message': message,
            'timestamp': time.time(),
            'context': context or {}
        })
    
    def record_folder_operation(self, operation: str, folder_name: str, success: bool, duration: float = None):
        """Record a folder operation"""
        self.data['folder_operations'].append({
            'operation': operation,
            'folder_name': folder_name,
            'success': success,
            'duration': duration,
            'timestamp': time.time()
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of collected data"""
        total_tests = len(self.data['test_runs'])
        successful_tests = sum(1 for run in self.data['test_runs'] if run['success'])
        
        return {
            'total_tests': total_tests,
            'successful_tests': successful_tests,
            'failed_tests': total_tests - successful_tests,
            'success_rate': successful_tests / total_tests if total_tests > 0 else 0,
            'total_errors': len(self.data['errors']),
            'average_test_duration': sum(run['duration'] for run in self.data['test_runs']) / total_tests if total_tests > 0 else 0,
            'performance_operations': list(self.data['performance_metrics'].keys()),
            'folder_operations': len(self.data['folder_operations'])
        }
    
    def export_data(self, filepath: str):
        """Export collected data to a JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.data, f, indent=2, default=str)


# Global test data collector instance
test_data_collector = TestDataCollector()


def validate_syftbox_structure(client) -> Tuple[bool, List[str]]:
    """
    Validate that SyftBox has the correct structure
    
    Args:
        client: GDriveUnifiedClient instance
        
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    
    try:
        # Check if SyftBoxTransportService exists
        if not client._folder_exists("SyftBoxTransportService"):
            issues.append("SyftBoxTransportService folder is missing")
        
        # Check for any orphaned syft_ folders
        results = client.service.files().list(
            q="name contains 'syft_' and trashed=false",
            fields="files(name,parents)"
        ).execute()
        
        syft_folders = results.get('files', [])
        
        # Validate folder naming patterns
        for folder in syft_folders:
            name = folder['name']
            if not (name.endswith('_pending') or name.endswith('_outbox_inbox') or 'archive' in name):
                issues.append(f"Invalid syft folder name pattern: {name}")
        
        return len(issues) == 0, issues
        
    except Exception as e:
        issues.append(f"Error validating SyftBox structure: {e}")
        return False, issues


def create_test_report(test_results: Dict[str, Any], output_file: str = None) -> str:
    """
    Create a formatted test report
    
    Args:
        test_results: Dictionary of test results
        output_file: Optional file to write report to
        
    Returns:
        Formatted report string
    """
    report_lines = [
        "# Syft-Client Test Report",
        "",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        "",
        "## Summary",
        ""
    ]
    
    if 'summary' in test_results:
        summary = test_results['summary']
        report_lines.extend([
            f"- **Total Tests:** {summary.get('total_tests', 0)}",
            f"- **Successful:** {summary.get('successful_tests', 0)} ✅",
            f"- **Failed:** {summary.get('failed_tests', 0)} ❌",
            f"- **Success Rate:** {summary.get('success_rate', 0)*100:.1f}%",
            f"- **Average Duration:** {summary.get('average_test_duration', 0):.2f}s",
            ""
        ])
    
    if 'errors' in test_results and test_results['errors']:
        report_lines.extend([
            "## Errors",
            ""
        ])
        
        for i, error in enumerate(test_results['errors'][:10], 1):  # Limit to first 10 errors
            report_lines.append(f"{i}. **{error.get('type', 'Unknown')}:** {error.get('message', 'No message')}")
        
        if len(test_results['errors']) > 10:
            report_lines.append(f"... and {len(test_results['errors']) - 10} more errors")
        
        report_lines.append("")
    
    if 'performance_metrics' in test_results:
        report_lines.extend([
            "## Performance Metrics",
            ""
        ])
        
        for operation, metrics in test_results['performance_metrics'].items():
            if metrics:
                avg_duration = sum(m['duration'] for m in metrics) / len(metrics)
                report_lines.append(f"- **{operation}:** {avg_duration:.2f}s average ({len(metrics)} samples)")
        
        report_lines.append("")
    
    report_content = "\n".join(report_lines)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(report_content)
    
    return report_content