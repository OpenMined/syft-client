# PyPI Publishing Setup

This document explains how to set up PyPI publishing for the syft-client package.

## Prerequisites

1. PyPI account at https://pypi.org
2. Test PyPI account at https://test.pypi.org (optional, for testing)
3. Repository admin access to configure GitHub secrets

## Step 1: Create PyPI API Tokens

### For PyPI (Production)
1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Set token name: `syft-client-github-actions`
4. Set scope: `Entire account` (or specific to syft-client project if it exists)
5. Copy the token (starts with `pypi-`)

### For Test PyPI (Testing)
1. Go to https://test.pypi.org/manage/account/token/
2. Click "Add API token" 
3. Set token name: `syft-client-github-actions-test`
4. Set scope: `Entire account`
5. Copy the token (starts with `pypi-`)

## Step 2: Add GitHub Secrets

In your GitHub repository:

1. Go to Settings → Secrets and variables → Actions
2. Add the following repository secrets:
   - `PYPI_API_TOKEN`: Your PyPI production token
   - `TEST_PYPI_API_TOKEN`: Your Test PyPI token (optional)

## Step 3: Publishing Options

### Option 1: Publish to Test PyPI (Manual Testing)

1. Go to Actions tab in GitHub
2. Select "Publish to PyPI" workflow
3. Click "Run workflow"
4. Check "Publish to Test PyPI instead of PyPI"
5. Click "Run workflow"

This will publish to https://test.pypi.org/project/syft-client/

### Option 2: Publish to PyPI (Production Release)

1. Create a new release on GitHub:
   - Go to Releases → Create a new release
   - Create a new tag (e.g., `v0.1.0`)
   - Set release title and description
   - Click "Publish release"

2. The workflow will automatically:
   - Build the package
   - Run tests across multiple Python versions and OSes  
   - Publish to PyPI if tests pass

## Package Installation

After publishing, users can install with:

```bash
# From PyPI (production)
pip install syft-client

# From Test PyPI (testing)
pip install --index-url https://test.pypi.org/simple/ syft-client
```

## Version Management

Update the version in `pyproject.toml` before creating a release:

```toml
[project]
version = "0.1.1"  # Increment as needed
```

## Troubleshooting

- **"Token is invalid"**: Regenerate the API token and update GitHub secrets
- **"Package already exists"**: Version already published, increment version number
- **"Authentication failed"**: Check that secrets are properly set in GitHub repository settings

## Workflow Details

The publishing workflow (`.github/workflows/publish.yml`) includes:

- **Build**: Creates wheel and source distributions
- **Test Install**: Verifies package installs correctly across platforms
- **Publish Test**: Publishes to Test PyPI (manual trigger only)
- **Publish Production**: Publishes to PyPI (release trigger only)
- **Post-Publish**: Creates deployment notifications