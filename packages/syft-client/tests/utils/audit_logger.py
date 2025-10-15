"""
CI Audit Trail Logger for Integration Tests
Provides proof of test execution in Google Drive
"""
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


class CIAuditLogger:
    """Creates verifiable audit trail of CI test execution in Google Drive"""
    
    def __init__(self, client, test_name: str = "integration_test"):
        """
        Initialize the audit logger
        
        Args:
            client: GDriveUnifiedClient instance
            test_name: Name of the test being run
        """
        self.client = client
        self.test_name = test_name
        self.ci_run_id = os.environ.get('GITHUB_RUN_ID', 'local_test')
        self.ci_run_number = os.environ.get('GITHUB_RUN_NUMBER', '0')
        self.commit_sha = os.environ.get('GITHUB_SHA', 'local')
        self.actor = os.environ.get('GITHUB_ACTOR', 'local_user')
        self.timestamp = datetime.utcnow().isoformat() + 'Z'
        self.audit_folder_id = None
        
    def setup_audit_folder(self) -> bool:
        """Create audit folder structure in Google Drive"""
        try:
            # Create ci_audit_logs folder at root level (outside SyftBox)
            # This ensures audit logs survive test cleanup
            audit_folder_name = "CI_AUDIT_LOGS_DO_NOT_DELETE"
            
            # Check if folder exists at root level
            results = self.client.service.files().list(
                q=f"name='{audit_folder_name}' and 'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id)"
            ).execute()
            
            if results.get('files'):
                self.audit_folder_id = results['files'][0]['id']
            else:
                # Create audit folder at root level
                folder_metadata = {
                    'name': audit_folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': ['root']
                }
                folder = self.client.service.files().create(
                    body=folder_metadata,
                    fields='id'
                ).execute()
                self.audit_folder_id = folder.get('id')
            
            print(f"✅ Audit folder ready: {audit_folder_name}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup audit folder: {e}")
            return False
    
    def log_test_start(self, test_details: Dict[str, Any]) -> Optional[str]:
        """Log the start of a test with details"""
        if not self.audit_folder_id and not self.setup_audit_folder():
            return None
            
        try:
            log_entry = {
                "event": "test_start",
                "test_name": self.test_name,
                "timestamp": self.timestamp,
                "ci_run_id": self.ci_run_id,
                "ci_run_number": self.ci_run_number,
                "commit_sha": self.commit_sha,
                "actor": self.actor,
                "user_email": self.client.my_email,
                "test_details": test_details
            }
            
            filename = f"test_start_{self.test_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            
            # Create file in Google Drive
            file_metadata = {
                'name': filename,
                'mimeType': 'application/json',
                'parents': [self.audit_folder_id]
            }
            
            from googleapiclient.http import MediaInMemoryUpload
            media = MediaInMemoryUpload(
                json.dumps(log_entry, indent=2).encode('utf-8'),
                mimetype='application/json'
            )
            
            file = self.client.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name'
            ).execute()
            
            print(f"📝 Logged test start: {filename}")
            return file.get('id')
            
        except Exception as e:
            print(f"⚠️ Failed to log test start: {e}")
            return None
    
    def log_communication(self, from_user: str, to_user: str, message: str = None) -> Optional[str]:
        """Log proof of communication between users"""
        if not self.audit_folder_id and not self.setup_audit_folder():
            return None
            
        try:
            log_entry = {
                "event": "user_communication",
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "ci_run_id": self.ci_run_id,
                "from_user": from_user,
                "to_user": to_user,
                "message": message or f"Test communication from {from_user} to {to_user}",
                "proof": f"CI Run #{self.ci_run_number} - Commit: {self.commit_sha[:7]}"
            }
            
            filename = f"comm_{from_user.split('@')[0]}_to_{to_user.split('@')[0]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            
            # Create file in Google Drive
            file_metadata = {
                'name': filename,
                'mimeType': 'application/json',
                'parents': [self.audit_folder_id]
            }
            
            from googleapiclient.http import MediaInMemoryUpload
            media = MediaInMemoryUpload(
                json.dumps(log_entry, indent=2).encode('utf-8'),
                mimetype='application/json'
            )
            
            file = self.client.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name'
            ).execute()
            
            print(f"💬 Logged communication: {from_user} → {to_user}")
            return file.get('id')
            
        except Exception as e:
            print(f"⚠️ Failed to log communication: {e}")
            return None
    
    def log_test_result(self, test_name: str, result: str, details: Dict[str, Any] = None) -> Optional[str]:
        """Log test result with pass/fail status"""
        if not self.audit_folder_id and not self.setup_audit_folder():
            return None
            
        try:
            log_entry = {
                "event": "test_result",
                "test_name": test_name,
                "result": result,  # "PASSED" or "FAILED"
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "ci_run_id": self.ci_run_id,
                "ci_run_number": self.ci_run_number,
                "user_email": self.client.my_email,
                "details": details or {}
            }
            
            filename = f"result_{test_name}_{result}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            
            # Create file in Google Drive
            file_metadata = {
                'name': filename,
                'mimeType': 'application/json',
                'parents': [self.audit_folder_id]
            }
            
            from googleapiclient.http import MediaInMemoryUpload
            media = MediaInMemoryUpload(
                json.dumps(log_entry, indent=2).encode('utf-8'),
                mimetype='application/json'
            )
            
            file = self.client.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name'
            ).execute()
            
            emoji = "✅" if result == "PASSED" else "❌"
            print(f"{emoji} Logged test result: {test_name} - {result}")
            return file.get('id')
            
        except Exception as e:
            print(f"⚠️ Failed to log test result: {e}")
            return None
    
    def write_audit_ledger(self, summary: Dict[str, Any]) -> Optional[str]:
        """Write or append to the main audit ledger file"""
        if not self.audit_folder_id and not self.setup_audit_folder():
            return None
            
        try:
            ledger_name = "AUDIT_LEDGER.txt"
            
            # Check if ledger exists
            results = self.client.service.files().list(
                q=f"name='{ledger_name}' and '{self.audit_folder_id}' in parents and trashed=false",
                fields="files(id)"
            ).execute()
            
            # Create ledger entry
            ledger_entry = f"""
================================================================================
CI RUN: {self.ci_run_id} (#{self.ci_run_number})
DATE: {self.timestamp}
COMMIT: {self.commit_sha}
ACTOR: {self.actor}
USER: {self.client.my_email}

TEST RESULTS:
{json.dumps(summary, indent=2)}

STATUS: {"✅ ALL TESTS PASSED" if summary.get('all_passed', False) else "❌ SOME TESTS FAILED"}
================================================================================
"""
            
            if results.get('files'):
                # Append to existing ledger
                file_id = results['files'][0]['id']
                
                # Get current content
                current = self.client.service.files().get_media(fileId=file_id).execute()
                updated_content = current.decode('utf-8') + '\n' + ledger_entry
                
                from googleapiclient.http import MediaInMemoryUpload
                media = MediaInMemoryUpload(
                    updated_content.encode('utf-8'),
                    mimetype='text/plain'
                )
                
                self.client.service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute()
                
                print(f"📚 Updated audit ledger: {ledger_name}")
                
            else:
                # Create new ledger
                file_metadata = {
                    'name': ledger_name,
                    'mimeType': 'text/plain',
                    'parents': [self.audit_folder_id]
                }
                
                from googleapiclient.http import MediaInMemoryUpload
                media = MediaInMemoryUpload(
                    ledger_entry.encode('utf-8'),
                    mimetype='text/plain'
                )
                
                file = self.client.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                
                print(f"📚 Created audit ledger: {ledger_name}")
                return file.get('id')
                
        except Exception as e:
            print(f"⚠️ Failed to write audit ledger: {e}")
            return None
    
    def create_proof_message(self, target_folder_id: str, message_type: str = "test") -> Optional[str]:
        """Create a proof message in a specific folder"""
        try:
            proof_content = f"""
CI TEST MESSAGE
===============
Type: {message_type}
CI Run ID: {self.ci_run_id} (#{self.ci_run_number})
Timestamp: {datetime.utcnow().isoformat()}Z
Commit: {self.commit_sha[:7]}
Actor: {self.actor}
From: {self.client.my_email}

This message is proof that CI integration tests successfully executed
and users were able to communicate through the SyftBox folders.
"""
            
            filename = f"CI_PROOF_{self.ci_run_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
            
            file_metadata = {
                'name': filename,
                'mimeType': 'text/plain',
                'parents': [target_folder_id]
            }
            
            from googleapiclient.http import MediaInMemoryUpload
            media = MediaInMemoryUpload(
                proof_content.encode('utf-8'),
                mimetype='text/plain'
            )
            
            file = self.client.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name'
            ).execute()
            
            print(f"✉️ Created proof message: {filename}")
            return file.get('id')
            
        except Exception as e:
            print(f"⚠️ Failed to create proof message: {e}")
            return None