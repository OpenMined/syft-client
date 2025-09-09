# Test Notebooks

This directory contains test notebooks for verifying syft_client functionality across different environments.

## Purpose

These notebooks should be run to test that the login flow and environment detection work correctly in each supported environment.

## Test Notebooks

1. **test_colab.ipynb** - Test notebook for Google Colab environment
   - Upload this to Google Colab and run all cells
   - Verifies Colab-specific features and authentication

2. **test_jupyter.ipynb** - Test notebook for local Jupyter environment
   - Run locally with `jupyter notebook test_jupyter.ipynb`
   - Tests standard Jupyter functionality

## Running Tests

### Google Colab
1. Open [Google Colab](https://colab.research.google.com/)
2. Upload `test_colab.ipynb` or open directly from GitHub
3. Run all cells to verify functionality

### Jupyter
1. Ensure Jupyter is installed: `pip install jupyter`
2. Navigate to this directory
3. Run: `jupyter notebook test_jupyter.ipynb`
4. Execute all cells

## Expected Results

Each notebook will:
- Detect the correct environment
- Show appropriate error messages when no email is provided
- Demonstrate the login flow for that environment