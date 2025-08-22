#!/usr/bin/env python3
"""
Simple test runner for syft-client that works around dependency conflicts
"""
import os
import sys
import subprocess
from pathlib import Path

def main():
    """Run tests with proper configuration"""
    
    # Add current directory to Python path
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    
    # Set environment variables
    os.environ['PYTHONPATH'] = str(current_dir)
    
    # Check if pytest is available
    try:
        import pytest
        print("✅ pytest is available")
    except ImportError:
        print("❌ pytest not found. Install with: pip install pytest")
        return 1
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        test_args = sys.argv[1:]
    else:
        # Default: run unit tests only
        test_args = ["tests/unit", "-v", "-m", "unit"]
    
    # Add some basic options
    base_args = [
        "--tb=short",  # Short traceback format
        "--disable-warnings",  # Disable warnings for cleaner output
        "-x",  # Stop on first failure
    ]
    
    final_args = base_args + test_args
    
    print(f"🧪 Running: pytest {' '.join(final_args)}")
    
    # Run pytest directly
    try:
        exit_code = pytest.main(final_args)
        return exit_code
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)