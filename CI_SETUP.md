# CI/CD Setup Guide for Syft-Client

This guide explains how to set up the GitHub Actions CI/CD pipeline for syft-client, including the real Google Drive API integration testing.

## Overview

The CI/CD pipeline includes:
- **Unit Tests**: Fast tests with mocked dependencies
- **Integration Tests**: Real Google Drive API tests with two-user workflow
- **Code Quality**: Linting, formatting, type checking
- **Security Scanning**: Automated security vulnerability detection
- **Automated Cleanup**: Test data cleanup to prevent pollution

## Prerequisites

Before setting up CI/CD, you need:

1. **Two Google accounts for testing** (e.g., test-user1@gmail.com, test-user2@gmail.com)
2. **Google Cloud Project** with Drive API enabled
3. **Service Account** for automated operations
4. **OAuth Credentials** for user authentication
5. **GitHub repository** with appropriate permissions

## Step-by-Step Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project: `syft-client-testing`
3. Enable the Google Drive API:
   ```bash
   gcloud services enable drive.googleapis.com --project=syft-client-testing
   ```

### 2. Create Service Account

The service account is used for cleanup operations and folder management in CI.

1. Go to **IAM & Admin** → **Service Accounts**
2. Click **Create Service Account**
3. Name: `syft-ci-service-account`
4. Grant roles:
   - **Service Account User** (for impersonation if needed)
   - No additional project roles needed
5. Create and download the JSON key file

### 3. Create OAuth Credentials for Test Users

Create OAuth credentials that will be used to authenticate as the test users.

1. Go to **APIs & Credentials** → **Credentials**
2. Click **Create Credentials** → **OAuth 2.0 Client IDs**
3. Application type: **Desktop application**
4. Name: `Syft Test User Credentials`
5. Download the JSON file

**Note**: You'll use the same OAuth credentials for both test users, but authenticate as different accounts.

### 4. Set Up Test Users

#### Create Test Accounts
1. Create two Gmail accounts:
   - `your-project-test-user1@gmail.com`
   - `your-project-test-user2@gmail.com`

#### Authenticate Test Users Locally
Before setting up CI, authenticate both users locally to generate tokens:

```bash
# Set up local environment
mkdir -p ~/.syft/test
cp ~/Downloads/client_credentials.json ~/.syft/test/oauth-credentials.json

# Authenticate User 1
export TEST_USER1_EMAIL=your-project-test-user1@gmail.com
python -c "
import syft_client as sc
client = sc.login('$TEST_USER1_EMAIL', '~/.syft/test/oauth-credentials.json', verbose=True)
print('✅ User 1 authenticated')
"

# Authenticate User 2  
export TEST_USER2_EMAIL=your-project-test-user2@gmail.com
python -c "
import syft_client as sc
client = sc.login('$TEST_USER2_EMAIL', '~/.syft/test/oauth-credentials.json', verbose=True)
print('✅ User 2 authenticated')
"
```

This creates tokens in `~/.syft/gdrive/` that you'll need for CI.

### 5. Configure GitHub Secrets

Add the following secrets to your GitHub repository (**Settings** → **Secrets and Variables** → **Actions**):

#### Required Secrets

```bash
# Service account key (entire JSON content)
GOOGLE_SERVICE_ACCOUNT_KEY='{"type": "service_account", "project_id": "syft-client-testing", ...}'

# OAuth credentials (same file for both users)
TEST_USER1_CREDENTIALS='{"installed": {"client_id": "...", "client_secret": "...", ...}}'
TEST_USER2_CREDENTIALS='{"installed": {"client_id": "...", "client_secret": "...", ...}}'

# Test user email addresses
TEST_USER1_EMAIL=your-project-test-user1@gmail.com
TEST_USER2_EMAIL=your-project-test-user2@gmail.com
```

#### How to Get Secret Values

**For GOOGLE_SERVICE_ACCOUNT_KEY:**
```bash
cat ~/Downloads/syft-ci-service-account-key.json
# Copy the entire JSON content
```

**For TEST_USER1_CREDENTIALS and TEST_USER2_CREDENTIALS:**
```bash
cat ~/.syft/test/oauth-credentials.json
# Copy the entire JSON content for both secrets (same content)
```

#### Optional Secrets (for enhanced features)

```bash
# Slack webhook for notifications (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Codecov token for coverage reporting (optional)  
CODECOV_TOKEN=your-codecov-token
```

### 6. Test the Setup Locally

Before pushing to GitHub, test the setup locally:

```bash
# Install dependencies
pip install -e ".[test]"

# Test unit tests (should work without credentials)
pytest tests/unit -v

# Test integration tests (requires credentials)
export SYFT_TEST_MODE=integration
export TEST_USER1_EMAIL=your-project-test-user1@gmail.com
export TEST_USER2_EMAIL=your-project-test-user2@gmail.com

pytest tests/integration/test_auth.py -v

# Test two-user workflow
pytest tests/integration/test_two_user_workflow.py::TestTwoUserWorkflow::test_bidirectional_friend_setup -v
```

### 7. Verify CI/CD Pipeline

#### Push Changes and Check CI

1. Commit and push your changes:
   ```bash
   git add .
   git commit -m "Add CI/CD setup with real Google Drive integration"
   git push
   ```

2. Check the GitHub Actions tab for:
   - ✅ **Code Quality** job (linting, formatting)
   - ✅ **Unit Tests** job (multiple Python versions)
   - ✅ **Build Package** job

#### Test Integration Tests

Integration tests only run on the main branch or when manually triggered:

1. **Merge to main branch** to trigger full integration tests
2. **Manual trigger**: Go to Actions → Integration Tests → Run workflow

#### Monitor Test Results

Check the GitHub Actions logs for:
```
🔐 Testing authentication for both users...
   ✅ User1 (your-project-test-user1@gmail.com) authenticated successfully
   ✅ User2 (your-project-test-user2@gmail.com) authenticated successfully

🤝 User1 adding User2 as friend...
✅ Added your-project-test-user2@gmail.com as a friend

🧹 Starting test data cleanup...
✅ Basic cleanup completed
```

## Workflow Details

### 1. Main CI Pipeline (`ci.yml`)

**Triggers**: Push to main/develop, Pull Requests
**Duration**: ~5-10 minutes

Jobs:
- **lint**: Code quality checks (Black, Flake8, MyPy)
- **unit-tests**: Unit tests on multiple OS/Python versions
- **integration-tests**: Integration tests (main branch only)
- **security-scan**: Bandit security scanning
- **build-package**: Package building and validation

### 2. PR Quick Check (`pr-check.yml`)

**Triggers**: Pull Request opened/updated
**Duration**: ~2-3 minutes

Features:
- Quick linting on changed files only
- Fast unit tests (no slow tests)
- Security quick scan
- Auto-labeling of PRs
- PR size warnings

### 3. Integration Tests (`integration.yml`)

**Triggers**: 
- Scheduled (nightly at 2 AM UTC)
- Manual workflow dispatch
- Main branch push (if secrets available)

**Duration**: ~15-20 minutes

Test Suites:
- Authentication tests
- SyftBox operations
- Two-user workflow (complete friend setup)
- Friend management edge cases
- Stress/performance tests
- Comprehensive cleanup

## Monitoring and Maintenance

### 1. Regular Monitoring

**Daily Checks:**
- Monitor nightly integration test results
- Check for authentication failures
- Verify cleanup is working properly

**Weekly Checks:**
- Review test performance metrics
- Check for Google API rate limit issues
- Update test credentials if needed

### 2. Credential Rotation

**Monthly Rotation** (recommended):

```bash
# 1. Generate new OAuth credentials in Google Cloud Console
# 2. Update GitHub secrets
# 3. Test locally before deploying
# 4. Monitor first CI run after update
```

### 3. Troubleshooting Common Issues

#### Authentication Failures

```yaml
# Check logs for:
❌ Authentication failed: Invalid credentials
❌ Could not authenticate users for cleanup

# Solutions:
# 1. Regenerate OAuth credentials
# 2. Re-authenticate test users locally  
# 3. Update GitHub secrets
```

#### Rate Limiting

```yaml
# Check logs for:
⚠️ Rate limit exceeded
⚠️ Could not delete folder: quotaExceeded

# Solutions:
# 1. Reduce test frequency
# 2. Add longer delays between operations
# 3. Use different test accounts
```

#### Test Data Pollution

```yaml
# Check logs for:
⚠️ Found 15 folders to cleanup
❌ SyftBox reset failed

# Solutions:
# 1. Run manual cleanup
# 2. Reset test accounts
# 3. Check service account permissions
```

### 4. Manual Cleanup

If CI cleanup fails, run manual cleanup:

```bash
# Set environment variables
export TEST_USER1_EMAIL=your-project-test-user1@gmail.com  
export TEST_USER2_EMAIL=your-project-test-user2@gmail.com
export GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Run cleanup script
python -c "
from tests.utils.cleanup import cleanup_all_test_data, deep_cleanup
cleanup_all_test_data()
deep_cleanup()
print('✅ Manual cleanup completed')
"
```

### 5. Performance Optimization

**For Faster CI:**
- Run integration tests only on main branch
- Use test parallelization where possible
- Cache dependencies
- Skip slow tests in PR validation

**For More Reliable Tests:**
- Add retry logic for flaky operations
- Increase timeouts for slow operations
- Better error handling and reporting

## Security Considerations

### 1. Credential Security

- **Never commit credentials** to the repository
- Use GitHub secrets for all sensitive data
- Rotate credentials regularly
- Monitor secret access logs

### 2. Test Account Security

- Use dedicated accounts only for testing
- Don't store personal data in test accounts
- Regularly audit folder contents
- Enable 2FA where possible

### 3. API Security

- Limit Google Drive API scopes to minimum required
- Monitor API usage and quotas
- Use service accounts for automated operations
- Implement proper error handling

## Advanced Features

### 1. Conditional Integration Tests

```yaml
# Only run integration tests if secrets are available
if: github.ref == 'refs/heads/main' && secrets.TEST_USER1_EMAIL != ''
```

### 2. Multi-Environment Testing

```yaml
strategy:
  matrix:
    test-env: [staging, production]
    include:
      - test-env: staging
        user1-email: staging-user1@gmail.com
      - test-env: production  
        user1-email: prod-user1@gmail.com
```

### 3. Performance Tracking

```yaml
- name: Performance Tracking
  run: |
    pytest tests/integration --benchmark-json=perf.json
    # Upload to performance tracking service
```

### 4. Slack Notifications

```yaml
- name: Notify on Failure
  if: failure()
  uses: 8398a7/action-slack@v3
  with:
    status: failure
    webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

## Conclusion

This CI/CD setup provides:

- ✅ **Comprehensive Testing** with real Google Drive API
- ✅ **Two-User Workflow Validation** ensuring the core functionality works
- ✅ **Automated Cleanup** preventing test data pollution
- ✅ **Security Scanning** and code quality checks
- ✅ **Performance Monitoring** and regression detection
- ✅ **Flexible Configuration** for different testing scenarios

The setup ensures that changes to syft-client are thoroughly tested in realistic conditions while maintaining fast feedback loops for developers.

For questions or issues with CI/CD setup, please:
1. Check the GitHub Actions logs for detailed error messages
2. Review this documentation for troubleshooting steps  
3. Open an issue with CI/CD logs and configuration details