#!/usr/bin/env python3
"""
Debug 1Password CLI commands directly
"""

import subprocess
import json

def run_op_command(cmd_list, description):
    """Run a 1Password CLI command and show results"""
    print(f"\n{'='*60}")
    print(f"TEST: {description}")
    print(f"Command: {' '.join(cmd_list)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True
        )
        
        print(f"Return code: {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        
        return result.returncode == 0
    except Exception as e:
        print(f"Exception: {type(e).__name__}: {e}")
        return False

def test_op_cli():
    """Test various 1Password CLI commands to find what works"""
    
    # First check if op is available
    print("Checking 1Password CLI availability...")
    result = subprocess.run(["op", "--version"], capture_output=True, text=True)
    print(f"1Password CLI version: {result.stdout.strip()}")
    
    # Test 1: Basic item creation with simple values
    cmd1 = [
        "op", "item", "create",
        "--category", "login",
        "--title", "test_simple",
        "username=testuser",
        "password=testpass123"
    ]
    run_op_command(cmd1, "Simple login item (no special chars)")
    
    # Test 2: With email username
    cmd2 = [
        "op", "item", "create",
        "--category", "login",
        "--title", "test_email",
        "username=test@example.com",
        "password=testpass123"
    ]
    run_op_command(cmd2, "Login item with email username")
    
    # Test 3: With tags
    cmd3 = [
        "op", "item", "create",
        "--category", "login",
        "--title", "test_tags",
        "username=testuser",
        "password=testpass123",
        "--tags", "email,google,syftclient"
    ]
    run_op_command(cmd3, "Login item with tags")
    
    # Test 4: With description
    cmd4 = [
        "op", "item", "create",
        "--category", "login",
        "--title", "test_description",
        "username=testuser",
        "password=testpass123",
        "notesPlain=Test description"
    ]
    run_op_command(cmd4, "Login item with description")
    
    # Test 5: Full syft-wallet style command
    cmd5 = [
        "op", "item", "create",
        "--category", "login",
        "--title", "google_personal-test_at_gmail_com",
        "username=test@gmail.com",
        "password=abcdefghijklmnop",
        "--tags", "email,google_personal,syftclient",
        "notesPlain=google_personal email account"
    ]
    run_op_command(cmd5, "Full syft-wallet style command")
    
    # Test 6: Check if it's a field format issue
    cmd6 = [
        "op", "item", "create",
        "--category", "login",
        "--title", "test_json_format",
        "--template", json.dumps({
            "fields": [
                {"id": "username", "type": "STRING", "value": "test@gmail.com"},
                {"id": "password", "type": "CONCEALED", "value": "testpass123"}
            ]
        })
    ]
    run_op_command(cmd6, "Using JSON template format")

def test_field_formats():
    """Test different field format approaches"""
    
    print("\n\n" + "="*60)
    print("TESTING FIELD FORMATS")
    print("="*60)
    
    # Test different ways to pass fields
    base_cmd = ["op", "item", "create", "--category", "login", "--title", "field_test"]
    
    # Format 1: field=value
    cmd1 = base_cmd + ["username=user@test.com", "password=pass123"]
    run_op_command(cmd1, "Format: field=value")
    
    # Format 2: Separate field type and value
    cmd2 = base_cmd + ["username[text]=user@test.com", "password[password]=pass123"]
    run_op_command(cmd2, "Format: field[type]=value")
    
    # Format 3: Using --field flag (if supported)
    cmd3 = base_cmd + ["--field", "username=user@test.com", "--field", "password=pass123"]
    run_op_command(cmd3, "Format: --field field=value")

def check_existing_items():
    """Check if we can see existing items"""
    print("\n\n" + "="*60)
    print("CHECKING EXISTING ITEMS")
    print("="*60)
    
    # List items to see format
    result = subprocess.run(
        ["op", "item", "list", "--categories", "Login", "--format", "json"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        try:
            items = json.loads(result.stdout)
            print(f"Found {len(items)} login items")
            
            # Look for our test items
            for item in items:
                if "google_personal" in item.get("title", "").lower() or "test" in item.get("title", "").lower():
                    print(f"\nItem: {item.get('title')}")
                    print(f"  ID: {item.get('id')}")
                    print(f"  Tags: {item.get('tags', [])}")
                    
                    # Get full item details
                    detail_result = subprocess.run(
                        ["op", "item", "get", item['id'], "--format", "json"],
                        capture_output=True,
                        text=True
                    )
                    if detail_result.returncode == 0:
                        details = json.loads(detail_result.stdout)
                        print(f"  Fields: {len(details.get('fields', []))}")
                        for field in details.get('fields', [])[:5]:  # First 5 fields
                            print(f"    - {field.get('id')}: {field.get('label', 'N/A')}")
        except json.JSONDecodeError:
            print("Could not parse JSON output")
    else:
        print(f"Failed to list items: {result.stderr}")

if __name__ == "__main__":
    print("=== 1Password CLI Direct Debug ===\n")
    
    # Run tests
    test_op_cli()
    test_field_formats()
    check_existing_items()
    
    print("\n=== Debug Complete ===")
    
    # Clean up test items
    print("\nTo clean up test items, run:")
    print("op item list --categories Login | grep test_ | awk '{print $1}' | xargs -I {} op item delete {}")