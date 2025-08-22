# Testing Guide for Syft-Client

This document provides comprehensive instructions for running tests and setting up CI/CD for the syft-client library.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Test Types](#test-types)
- [Setting Up Tests](#setting-up-tests)
- [Running Tests](#running-tests)
- [CI/CD Setup](#cicd-setup)
- [Troubleshooting](#troubleshooting)

## Overview

The syft-client testing framework includes:
- **Unit tests** with mocked Google Drive API (fast, no credentials needed)
- **Integration tests** with real Google Drive API (slower, requires credentials)
- **Two-user workflow tests** to validate the complete communication setup
- **GitHub Actions CI/CD** for automated testing

## Quick Start

### Install Test Dependencies

```bash
# Install syft-client with test dependencies
pip install -e ".[test]"

# Or install just test dependencies
pip install pytest pytest-mock pytest-cov black flake8 mypy

# If you encounter dependency conflicts, install minimal testing setup
pip install pytest pytest-mock
```

### Run Unit Tests (No Credentials Needed)

```bash
# Run all unit tests
pytest tests/unit -v

# Run with coverage
pytest tests/unit --cov=syft_client --cov-report=html

# Alternative: Use the test runner script (works around dependency conflicts)
python run_tests.py

# Run specific tests
python run_tests.py tests/unit/test_import.py -v
```

### Run Integration Tests (Requires Setup)

```bash
# Set environment variables
export SYFT_TEST_MODE=integration
export TEST_USER1_EMAIL=your-test-user1@gmail.com
export TEST_USER2_EMAIL=your-test-user2@gmail.com

# Run integration tests
pytest tests/integration -v -m integration
```

## Test Types

### 1. Unit Tests (`tests/unit/`)

**Purpose:** Test individual components with mocked dependencies
**Speed:** Fast (< 30 seconds total)
**Requirements:** No Google credentials needed

```bash
# Run all unit tests
pytest tests/unit

# Run specific test files
pytest tests/unit/test_auth.py
pytest tests/unit/test_gdrive_client.py
pytest tests/unit/test_import.py

# Run with specific markers
pytest -m unit
```

### 2. Integration Tests (`tests/integration/`)

**Purpose:** Test with real Google Drive API
**Speed:** Slower (2-5 minutes)
**Requirements:** Google Drive credentials for two test accounts

```bash
# Set up environment
export SYFT_TEST_MODE=integration

# Run all integration tests
pytest tests/integration -m integration

# Run specific test categories
pytest tests/integration -m "integration and auth"
pytest tests/integration -m "integration and two_user"
pytest tests/integration -m "integration and syftbox"
```

### 3. Stress/Performance Tests

```bash
# Run slow/stress tests
pytest tests/integration -m "integration and slow"

# Skip slow tests (default in CI)
pytest tests/integration -m "integration and not slow"
```

## Setting Up Tests

### 1. For Unit Tests Only

No additional setup required - unit tests use mocked Google Drive API.

### 2. For Integration Tests

#### Step 1: Create Test Google Accounts

1. Create two Gmail accounts for testing:
   - `your-project-test-user1@gmail.com`
   - `your-project-test-user2@gmail.com`

#### Step 2: Set Up Google Drive API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google Drive API
4. Create credentials:
   - **For local testing:** OAuth 2.0 Client IDs (Desktop application)
   - **For CI/CD:** Service Account key

#### Step 3: Configure Credentials

**For Local Testing:**
```bash
# Create test credentials directory
mkdir -p ~/.syft/test

# Download credentials files
# user1-creds.json and user2-creds.json from Google Cloud Console

# Set environment variables
export TEST_USER1_EMAIL=your-test-user1@gmail.com
export TEST_USER2_EMAIL=your-test-user2@gmail.com
export SYFT_TEST_MODE=integration
```

**For CI/CD:**
```bash
# Service account for cleanup operations
export GOOGLE_APPLICATION_CREDENTIALS=~/.syft/test/service-account.json

# OAuth credentials for user accounts  
export TEST_USER1_CREDENTIALS="$(cat ~/.syft/test/user1-creds.json)"
export TEST_USER2_CREDENTIALS="$(cat ~/.syft/test/user2-creds.json)"
```

### 3. Authenticate Test Users

```bash
# Authenticate both test users locally
python -c "
import syft_client as sc
user1 = sc.login('$TEST_USER1_EMAIL', '~/.syft/test/user1-creds.json')
user2 = sc.login('$TEST_USER2_EMAIL', '~/.syft/test/user2-creds.json')
print('✅ Both test users authenticated')
"
```

## Running Tests

### Basic Test Commands

```bash
# Run all tests (unit only by default)
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_auth.py -v

# Run specific test function
pytest tests/unit/test_auth.py::TestLoginFunction::test_login_with_stored_credentials -v
```

### Test Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only two-user workflow tests
pytest -m two_user

# Run only authentication tests
pytest -m auth

# Combine markers
pytest -m "integration and not slow"
```

### Coverage Reports

```bash
# Generate HTML coverage report
pytest tests/unit --cov=syft_client --cov-report=html
open htmlcov/index.html

# Generate terminal coverage report
pytest tests/unit --cov=syft_client --cov-report=term-missing

# Generate XML coverage for CI
pytest tests/unit --cov=syft_client --cov-report=xml
```

### Performance Testing

```bash
# Run with timing information
pytest --durations=10

# Run with performance profiling
pytest --profile --profile-svg
```

## CI/CD Setup

### GitHub Actions Configuration

The repository includes three GitHub Actions workflows:

1. **`ci.yml`** - Main CI pipeline for all pushes/PRs
2. **`pr-check.yml`** - Quick validation for pull requests
3. **`integration.yml`** - Scheduled integration tests

### Required GitHub Secrets

Set these secrets in your GitHub repository settings:

```bash
# Service account for folder management and cleanup
GOOGLE_SERVICE_ACCOUNT_KEY='{...service account JSON...}'

# OAuth credentials for test users
TEST_USER1_CREDENTIALS='{...OAuth client JSON...}'
TEST_USER2_CREDENTIALS='{...OAuth client JSON...}'

# Test user email addresses
TEST_USER1_EMAIL=your-test-user1@gmail.com
TEST_USER2_EMAIL=your-test-user2@gmail.com
```

### Workflow Triggers

- **Push to main/develop:** Full CI with unit tests
- **Pull Request:** Quick validation (unit tests + linting)
- **Scheduled (nightly):** Full integration test suite
- **Manual:** Integration tests with configurable scope

### Local CI Simulation

```bash
# Install development dependencies
pip install -e ".[test,dev]"

# Run the same checks as CI
black --check syft_client tests
flake8 syft_client tests
mypy syft_client
pytest tests/unit --cov=syft_client

# Run integration tests (if credentials available)
export SYFT_TEST_MODE=integration
pytest tests/integration -m integration
```

## Test Configuration

### pytest.ini

The project includes comprehensive pytest configuration:

```ini
[tool:pytest]
# Test discovery
testpaths = tests
python_files = test_*.py

# Markers for different test types
markers =
    unit: Unit tests (fast, mocked dependencies)
    integration: Integration tests (slow, real Google Drive API)
    two_user: Tests requiring two user accounts
    slow: Tests that take more than 30 seconds

# Coverage and reporting
addopts = 
    --cov=syft_client
    --cov-report=term-missing
    --cov-fail-under=80
    --maxfail=10
```

### Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `SYFT_TEST_MODE` | Set to `integration` for integration tests | Integration tests |
| `TEST_USER1_EMAIL` | First test user email | Integration tests |
| `TEST_USER2_EMAIL` | Second test user email | Integration tests |
| `GOOGLE_APPLICATION_CREDENTIALS` | Service account key path | CI cleanup |
| `CI` | Indicates CI environment | Auto-detected |

## Troubleshooting

### Common Issues

#### 1. "No module named 'syft_client'"
```bash
# Install in development mode
pip install -e .
```

#### 2. "Authentication failed" in integration tests
```bash
# Check credentials are properly set
echo $TEST_USER1_EMAIL
ls ~/.syft/test/

# Re-authenticate manually
python -c "import syft_client; syft_client.login('$TEST_USER1_EMAIL', force_relogin=True)"
```

#### 3. "Rate limit exceeded" in integration tests
```bash
# Run with longer delays
pytest tests/integration -m integration --tb=short --maxfail=3

# Or run tests serially
pytest tests/integration -m integration -x
```

#### 4. Tests hanging or timing out
```bash
# Run with timeout
pytest tests/integration --timeout=300

# Check for authentication prompts
pytest tests/integration -s  # Don't capture output
```

#### 5. "Permission denied" errors
```bash
# Check Google Drive API permissions
# Ensure test users have proper folder access

# Clean up test data
python tests/utils/cleanup.py
```

### Debug Mode

```bash
# Run with debug logging
pytest tests/integration -v -s --log-cli-level=DEBUG

# Run single test with full output
pytest tests/integration/test_two_user_workflow.py::TestTwoUserWorkflow::test_bidirectional_friend_setup -v -s
```

### Test Data Cleanup

```bash
# Manual cleanup of test data
python -c "
from tests.utils.cleanup import cleanup_all_test_data
cleanup_all_test_data()
"

# Reset SyftBox for test users
python -c "
import syft_client as sc
import os
user1 = sc.login(os.environ['TEST_USER1_EMAIL'])
user2 = sc.login(os.environ['TEST_USER2_EMAIL'])
user1.reset_syftbox()
user2.reset_syftbox()
print('✅ SyftBoxes reset')
"
```

### Performance Analysis

```bash
# Generate performance report
pytest tests/integration --benchmark-json=benchmark.json

# Profile memory usage
pytest tests/integration --memray

# Analyze test durations
pytest tests/integration --durations=0 | sort -k2 -n
```

## Best Practices

### Writing Tests

1. **Use appropriate markers**:
   ```python
   @pytest.mark.unit
   def test_unit_function():
       pass

   @pytest.mark.integration
   @pytest.mark.two_user
   def test_integration_workflow():
       pass
   ```

2. **Clean up test data**:
   ```python
   def test_something(integration_test_clients):
       user1, user2 = integration_test_clients['user1'], integration_test_clients['user2']
       # Test automatically cleans up via fixture
   ```

3. **Handle API delays**:
   ```python
   import time
   user1.add_friend(user2.my_email)
   time.sleep(2)  # Allow Google Drive to propagate
   assert user2.my_email in user1.friends
   ```

4. **Use retry logic for flaky operations**:
   ```python
   from tests.utils.test_helpers import retry_on_failure

   @retry_on_failure(max_attempts=3)
   def test_flaky_operation():
       # Test that might fail due to API timing
   ```

### Running Tests Efficiently

1. **Run unit tests during development**:
   ```bash
   pytest tests/unit -x  # Stop on first failure
   ```

2. **Use integration tests for verification**:
   ```bash
   pytest tests/integration -m "integration and not slow"
   ```

3. **Run full test suite before releases**:
   ```bash
   pytest tests/ --cov=syft_client --cov-fail-under=90
   ```

## Contributing

When adding new tests:

1. Add unit tests for all new functions
2. Add integration tests for user-facing features
3. Update test documentation if needed
4. Ensure tests pass in CI before merging

For questions about testing, please open an issue on GitHub.