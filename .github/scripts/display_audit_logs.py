#!/usr/bin/env python3
"""
Display audit logs for CI test users.
Updated to work with new syft_client API.
"""
import syft_client as sc
import os
import sys

def main():
    user1_email = os.environ.get('TEST_USER1_EMAIL')
    user2_email = os.environ.get('TEST_USER2_EMAIL')
    
    print('🔍 Checking audit logs for both test users...')
    
    for email in [user1_email, user2_email]:
        try:
            # Determine provider based on email
            provider = 'google_personal' if '@gmail.com' in email else 'google_org'
            client = sc.login(email, provider=provider, verbose=False)
            print(f'\n📁 Audit logs for {email}:')
            
            # Get Google platform and service
            google_platform = client.platforms.get('google_personal') or client.platforms.get('google_org')
            if google_platform:
                # Try to get service from platform
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build
                import json
                
                # Get credentials from wallet location
                sanitized_email = email.replace('@', '_at_').replace('.', '_')
                token_path = os.path.expanduser(f'~/.syft/gdrive/{sanitized_email}/token.json')
                
                if os.path.exists(token_path):
                    with open(token_path, 'r') as f:
                        token_data = json.load(f)
                    creds = Credentials.from_authorized_user_info(token_data)
                    service = build('drive', 'v3', credentials=creds)
                    
                    # List files in CI_AUDIT_LOGS_DO_NOT_DELETE folder at root
                    results = service.files().list(
                        q="name='CI_AUDIT_LOGS_DO_NOT_DELETE' and 'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
                        fields="files(id)"
                    ).execute()
                    
                    if results.get('files'):
                        audit_folder_id = results['files'][0]['id']
                        
                        # List audit files
                        audit_files = service.files().list(
                            q=f"'{audit_folder_id}' in parents and trashed=false",
                            fields="files(id,name,createdTime)",
                            orderBy="createdTime desc"
                        ).execute()
                        
                        for file in audit_files.get('files', []):
                            print(f"   - {file['name']} (created: {file['createdTime']})")
                    else:
                        print('   No audit logs folder found')
                else:
                    print(f'   Token file not found for {email}')
            else:
                print(f'   Could not access Google platform for {email}')
        except Exception as e:
            print(f'   Error checking {email}: {e}')
    
    print('\n✅ Audit log listing complete')

if __name__ == "__main__":
    main()