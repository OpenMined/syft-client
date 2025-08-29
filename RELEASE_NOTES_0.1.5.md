# Release Notes - syft-client v0.1.5

## What's New in v0.1.5

### 🐛 Bug Fixes
- **Fixed duplicate token fields** - Removed duplicate `client_id` and `client_secret` fields in token saving (gdrive_unified.py)
- **Fixed CI workflow** - Corrected undefined variable references in GitHub Actions integration tests

### 📚 Documentation
- **NEW: Getting Started Guide** - Comprehensive beginner-friendly guide (GETTING_STARTED.md)
- **NEW: API Reference** - Complete API documentation with examples (API_REFERENCE.md)
- **NEW: Interactive Tutorial** - Jupyter notebook with hands-on examples (syft_client_tutorial.ipynb)
- **NEW: TODO Roadmap** - Future improvements and feature requests (TODO.md)

### 🧹 Cleanup
- Removed unnecessary empty `__init__.py` files from test directories

## Installation

```bash
pip install syft-client==0.1.5
```

## Upgrading from 0.1.4

```bash
pip install --upgrade syft-client
```

## What's Fixed

1. **Token Storage Bug**: Previously, when saving authentication tokens, `client_id` and `client_secret` were being saved twice in the token dictionary. This has been fixed.

2. **CI/CD Pipeline**: The GitHub Actions workflow now properly defines sanitized email variables before using them, preventing undefined variable errors during testing.

## What's Improved

- Much better documentation for new users
- Interactive tutorial notebook ready for Google Colab
- Clear API reference with examples
- Roadmap for future development

## Breaking Changes

None. This release is fully backward compatible with v0.1.4.

## Contributors

Thank you to everyone who contributed to this release!

## Next Steps

Check out the [TODO.md](TODO.md) file for planned improvements in future releases.

---

For questions or issues, please visit: https://github.com/OpenMined/syft-client/issues