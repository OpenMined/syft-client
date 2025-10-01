# File Deletion Operations in syft-client

Generated on: Tue 30 Sep 2025 14:43:01 EDT

## unlink() calls

### syft_client//platforms/transport_base.py:455
```python
   450	                            extracted_items = [m.name for m in members]
   451	                    except tarfile.ReadError as e:
   452	                        if verbose:
   453	                            print(f"   ❌ Failed to extract archive: {e}")
   454	                        # Skip this message
   455	                        temp_file.unlink()
   456	                        continue
   457	                        
   458	                    if verbose:
   459	                        # List what was actually extracted
   460	                        print(f"   📂 Extracted to {download_path}:")
```

### syft_client//platforms/transport_base.py:562
```python
   557	                                if path_to_delete.is_dir():
   558	                                    shutil.rmtree(path_to_delete)
   559	                                    if verbose:
   560	                                        print(f"   🗑️  Deleted directory: {path_to_delete.name}")
   561	                                else:
   562	                                    path_to_delete.unlink()
   563	                                    if verbose:
   564	                                        print(f"   🗑️  Deleted file: {path_to_delete.name}")
   565	                            else:
   566	                                if verbose:
   567	                                    print(f"   ℹ️  Already deleted: {path_to_delete.name}")
```

### syft_client//platforms/transport_base.py:684
```python
   679	                        
   680	                        # Mark for archiving
   681	                        messages_to_archive.append(message_info)
   682	                    
   683	                    # Clean up temporary files
   684	                    temp_file.unlink()
   685	                    if extracted_dir.exists():
   686	                        import shutil
   687	                        shutil.rmtree(extracted_dir)
   688	                    
   689	                except Exception as e:
```

### syft_client//auth/wallets/local_file.py:156
```python
   151	        """Delete a token file"""
   152	        try:
   153	            token_path = self._get_token_path(service, account)
   154	            
   155	            if token_path.exists():
   156	                token_path.unlink()
   157	                
   158	                # Clean up empty directories
   159	                token_dir = self._get_token_dir(account)
   160	                if token_dir.exists() and not any(token_dir.iterdir()):
   161	                    token_dir.rmdir()
```

### syft_client//auth/wallets/local_file.py:218
```python
   213	            self.base_dir.mkdir(parents=True, exist_ok=True)
   214	            
   215	            # Try to write a test file
   216	            test_file = self.base_dir / '.wallet_test'
   217	            test_file.write_text('test')
   218	            test_file.unlink()
   219	            
   220	            return True
   221	            
   222	        except Exception:
   223	            return False
```

### syft_client//sync/peers.py:338
```python
   333	            try:
   334	                peers_dir = self._get_peers_directory()
   335	                file_name = f"{email.replace('@', '_at_').replace('.', '_')}.json"
   336	                file_path = peers_dir / file_name
   337	                if file_path.exists():
   338	                    file_path.unlink()
   339	            except:
   340	                pass
   341	            
   342	            # Invalidate cache
   343	            self._invalidate_peers_cache()
```

### syft_client//sync/peers.py:381
```python
   376	        try:
   377	            peers_dir = self._get_peers_directory()
   378	            if peers_dir.exists():
   379	                for file_path in peers_dir.glob("*.json"):
   380	                    try:
   381	                        file_path.unlink()
   382	                        files_cleared += 1
   383	                        if verbose:
   384	                            print(f"   ✓ Deleted peer file: {file_path.name}")
   385	                    except Exception as e:
   386	                        if verbose:
```

### syft_client//sync/peers.py:398
```python
   393	        try:
   394	            discovery_cache_dir = self._discovery._get_discovery_cache_dir()
   395	            if discovery_cache_dir.exists():
   396	                for file_path in discovery_cache_dir.glob("*_discovery.json"):
   397	                    try:
   398	                        file_path.unlink()
   399	                        files_cleared += 1
   400	                        if verbose:
   401	                            print(f"   ✓ Deleted discovery cache: {file_path.name}")
   402	                    except Exception as e:
   403	                        if verbose:
```

### syft_client//sync/message.py:197
```python
   192	                shutil.rmtree(self.message_dir)
   193	            
   194	            # Remove archive
   195	            archive_path = self.message_root / f"{self.message_id}.tar.gz"
   196	            if archive_path.exists():
   197	                archive_path.unlink()
   198	                
   199	        except Exception as e:
   200	            print(f"⚠️  Error cleaning up message: {e}")
      	
      	
```

### syft_client//sync/receiver/message_processor.py:123
```python
   118	                            import shutil
   119	                            shutil.rmtree(dest)
   120	                        item.rename(dest)
   121	                    else:
   122	                        if dest.exists():
   123	                            dest.unlink()
   124	                        item.rename(dest)
   125	                    
   126	                    stats["approved"] += 1
   127	                    
   128	                    if self.verbose:
```

## remove() calls

## os.remove() calls

## shutil.rmtree() calls

### syft_client//platforms/transport_base.py:558
```python
   553	                                        print(f"   ℹ️  Could not record deletion (file may already be gone): {e}")
   554	                            
   555	                            # THEN: Delete the file/directory
   556	                            if path_to_delete.exists():
   557	                                if path_to_delete.is_dir():
   558	                                    shutil.rmtree(path_to_delete)
   559	                                    if verbose:
   560	                                        print(f"   🗑️  Deleted directory: {path_to_delete.name}")
   561	                                else:
   562	                                    path_to_delete.unlink()
   563	                                    if verbose:
```

### syft_client//platforms/transport_base.py:687
```python
   682	                    
   683	                    # Clean up temporary files
   684	                    temp_file.unlink()
   685	                    if extracted_dir.exists():
   686	                        import shutil
   687	                        shutil.rmtree(extracted_dir)
   688	                    
   689	                except Exception as e:
   690	                    if verbose:
   691	                        print(f"   ❌ Error processing message {message_info.get('message_id', 'unknown')}: {e}")
   692	                        import traceback
```

### syft_client//syft_client.py:1129
```python
  1124	                print("Wallet reset cancelled.")
  1125	                return False
  1126	        
  1127	        try:
  1128	            # Delete the entire wallet directory
  1129	            shutil.rmtree(wallet_dir)
  1130	            print(f"\n✓ Wallet directory deleted: {wallet_dir}")
  1131	            print("All stored credentials have been removed.")
  1132	            print("\nYou will need to authenticate again on your next login.")
  1133	            return True
  1134	        except Exception as e:
```

### syft_client//sync/sender.py:161
```python
   156	                return self._send_prepared_archive(archive_path, recipient, archive_size, message_id)
   157	        finally:
   158	            # Clean up temp directory
   159	            import shutil
   160	            if os.path.exists(temp_dir):
   161	                shutil.rmtree(temp_dir)
   162	    
   163	    def prepare_message(self, path: str, recipient: str, temp_dir: str, sync_from_anywhere: bool = False) -> Optional[Tuple[str, str, int]]:
   164	        """
   165	        Prepare a SyftMessage archive for sending
   166	        
```

### syft_client//sync/sender.py:328
```python
   323	            
   324	        finally:
   325	            # Clean up temp directory
   326	            import shutil
   327	            if os.path.exists(temp_dir):
   328	                shutil.rmtree(temp_dir)
   329	    
   330	    def send_deletion_to_peers(self, path: str) -> Dict[str, bool]:
   331	        """
   332	        Send deletion message to all peers
   333	        
```

### syft_client//sync/message.py:102
```python
    97	            if source.is_file():
    98	                shutil.copy2(source, dest)
    99	            else:
   100	                # Copy directory
   101	                if dest.exists():
   102	                    shutil.rmtree(dest)
   103	                shutil.copytree(source, dest)
   104	            return True
   105	        except Exception as e:
   106	            print(f"❌ Error adding file: {e}")
   107	            return False
```

### syft_client//sync/message.py:192
```python
   187	    def cleanup(self):
   188	        """Clean up temporary message files"""
   189	        try:
   190	            # Remove message directory
   191	            if self.message_dir.exists():
   192	                shutil.rmtree(self.message_dir)
   193	            
   194	            # Remove archive
   195	            archive_path = self.message_root / f"{self.message_id}.tar.gz"
   196	            if archive_path.exists():
   197	                archive_path.unlink()
```

### syft_client//sync/receiver/message_processor.py:119
```python
   114	                    
   115	                    # Move the file/directory
   116	                    if item.is_dir():
   117	                        if dest.exists():
   118	                            import shutil
   119	                            shutil.rmtree(dest)
   120	                        item.rename(dest)
   121	                    else:
   122	                        if dest.exists():
   123	                            dest.unlink()
   124	                        item.rename(dest)
```

## Path.replace() calls (atomic moves)

### syft_client//platforms/google_org/wizard.py:35
```python
    30	def find_credentials(email: Optional[str] = None) -> Optional[Path]:
    31	    """Search for existing credentials.json in all possible locations"""
    32	    possible_paths = []
    33	    
    34	    if email:
    35	        safe_email = email.replace('@', '_at_').replace('.', '_')
    36	        possible_paths.append(Path.home() / ".syft" / safe_email / "credentials.json")
    37	    
    38	    possible_paths.extend([
    39	        Path.home() / ".syft" / "credentials.json",
    40	        Path.home() / ".syft" / "google_oauth" / "credentials.json",
```

### syft_client//platforms/google_org/wizard.py:624
```python
   619	        break
   620	    
   621	    # Copy to correct location
   622	    target_dir = Path.home() / ".syft"
   623	    if state.email:
   624	        safe_email = state.email.replace('@', '_at_').replace('.', '_')
   625	        target_dir = target_dir / safe_email
   626	    
   627	    target_dir.mkdir(parents=True, exist_ok=True)
   628	    target_path = target_dir / "credentials.json"
   629	    
```

### syft_client//platforms/google_org/wizard.py:944
```python
   939	        file_path, project_id = found_creds
   940	        
   941	        # Copy to the correct location
   942	        target_dir = Path.home() / ".syft"
   943	        if email:
   944	            safe_email = email.replace('@', '_at_').replace('.', '_')
   945	            target_dir = target_dir / safe_email
   946	        
   947	        target_dir.mkdir(parents=True, exist_ok=True)
   948	        target_path = target_dir / "credentials.json"
   949	        
```

### syft_client//platforms/google_org/gforms.py:201
```python
   196	            return False
   197	            
   198	        try:
   199	            # Create form
   200	            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
   201	            form_title = f"SyftClient_{subject.replace(' ', '_')}_{timestamp}"
   202	            
   203	            form = {
   204	                "info": {
   205	                    "title": form_title,
   206	                    "document_title": form_title
```

### syft_client//platforms/google_org/gdrive_files.py:247
```python
   242	                mime_type = 'application/octet-stream'
   243	                extension = '.pkl'
   244	            
   245	            # Create filename
   246	            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
   247	            filename = f"syft_{subject.replace(' ', '_')}_{timestamp}{extension}"
   248	            
   249	            # Upload file
   250	            file_metadata = {
   251	                'name': filename,
   252	                'parents': [self._folder_id] if self._folder_id else []
```

### syft_client//platforms/google_org/gdrive_files.py:1181
```python
  1176	                
  1177	                # Check if it follows syft folder pattern
  1178	                if '_to_' in name and name.startswith('syft_'):
  1179	                    parts = name.split('_to_')
  1180	                    if len(parts) == 2:
  1181	                        sender = parts[0].replace('syft_', '')
  1182	                        recipient_with_suffix = parts[1]
  1183	                        
  1184	                        # Remove suffixes to get clean email
  1185	                        recipient = recipient_with_suffix
  1186	                        for suffix in ['_outbox_inbox', '_outbox', '_pending', '_archive']:
```

### syft_client//platforms/google_org/gdrive_files.py:1187
```python
  1182	                        recipient_with_suffix = parts[1]
  1183	                        
  1184	                        # Remove suffixes to get clean email
  1185	                        recipient = recipient_with_suffix
  1186	                        for suffix in ['_outbox_inbox', '_outbox', '_pending', '_archive']:
  1187	                            recipient = recipient.replace(suffix, '')
  1188	                        
  1189	                        # If they're sharing with us and not already a contact
  1190	                        if recipient == my_email and sender not in existing_contacts:
  1191	                            # Verify it's from the owner
  1192	                            owners = folder.get('owners', [])
```

### syft_client//platforms/google_org/gdrive_files.py:1272
```python
  1267	                            status, done = downloader.next_chunk()
  1268	                        
  1269	                        message_data = file_buffer.getvalue()
  1270	                        
  1271	                        # Store message info
  1272	                        message_id = file_name.replace('.tar.gz', '')
  1273	                        messages.append({
  1274	                            'message_id': message_id,
  1275	                            'data': message_data,
  1276	                            'file_id': file_id,
  1277	                            'file_name': file_name,
```

### syft_client//platforms/google_org/gdrive_files.py:1318
```python
  1313	                fields='name'
  1314	            ).execute()
  1315	            
  1316	            folder_name = folder_info['name']
  1317	            # Extract emails from folder name: syft_{sender}_to_{receiver}_outbox_inbox
  1318	            parts = folder_name.replace('syft_', '').replace('_outbox_inbox', '').split('_to_')
  1319	            if len(parts) == 2:
  1320	                sender_email = parts[0]
  1321	                my_email = parts[1]
  1322	                
  1323	                # Find or create archive folder
```

### syft_client//platforms/google_org/gsheets.py:202
```python
   197	            return False
   198	            
   199	        try:
   200	            # Create spreadsheet
   201	            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
   202	            spreadsheet_name = f"{self.SYFT_SHEET_PREFIX}{subject.replace(' ', '_')}_{timestamp}"
   203	            
   204	            spreadsheet = {
   205	                'properties': {
   206	                    'title': spreadsheet_name
   207	                }
```

### syft_client//platforms/google_org/gsheets.py:298
```python
   293	        
   294	        if not contacts:
   295	            return {}
   296	        
   297	        all_messages = {}
   298	        my_email = self.email.replace('@', '_at_').replace('.', '_')
   299	        
   300	        for peer_email in contacts:
   301	            try:
   302	                their_email = peer_email.replace('@', '_at_').replace('.', '_')
   303	                sheet_name = f"syft_{their_email}_to_{my_email}_messages"
```

### syft_client//platforms/google_org/gsheets.py:302
```python
   297	        all_messages = {}
   298	        my_email = self.email.replace('@', '_at_').replace('.', '_')
   299	        
   300	        for peer_email in contacts:
   301	            try:
   302	                their_email = peer_email.replace('@', '_at_').replace('.', '_')
   303	                sheet_name = f"syft_{their_email}_to_{my_email}_messages"
   304	                
   305	                # Find the sheet
   306	                sheet_id = self._find_message_sheet(sheet_name, from_email=peer_email)
   307	                if not sheet_id:
```

### syft_client//platforms/google_org/gsheets.py:810
```python
   805	        - Outgoing: syft_{my_email}_to_{their_email}_messages
   806	        - Incoming: syft_{their_email}_to_{my_email}_messages (if possible)
   807	        """
   808	        try:
   809	            # Create outgoing message sheet name
   810	            my_email = self.email.replace('@', '_at_').replace('.', '_')
   811	            their_email = email.replace('@', '_at_').replace('.', '_')
   812	            outgoing_sheet_name = f"syft_{my_email}_to_{their_email}_messages"
   813	            
   814	            # Get or create the outgoing message sheet
   815	            sheet_id = self._get_or_create_message_sheet(outgoing_sheet_name, recipient_email=email)
```

### syft_client//platforms/google_org/gsheets.py:811
```python
   806	        - Incoming: syft_{their_email}_to_{my_email}_messages (if possible)
   807	        """
   808	        try:
   809	            # Create outgoing message sheet name
   810	            my_email = self.email.replace('@', '_at_').replace('.', '_')
   811	            their_email = email.replace('@', '_at_').replace('.', '_')
   812	            outgoing_sheet_name = f"syft_{my_email}_to_{their_email}_messages"
   813	            
   814	            # Get or create the outgoing message sheet
   815	            sheet_id = self._get_or_create_message_sheet(outgoing_sheet_name, recipient_email=email)
   816	            
```

### syft_client//platforms/google_org/gsheets.py:840
```python
   835	        """
   836	        Remove a peer by revoking access to message sheets.
   837	        """
   838	        try:
   839	            removed = False
   840	            my_email = self.email.replace('@', '_at_').replace('.', '_')
   841	            their_email = email.replace('@', '_at_').replace('.', '_')
   842	            
   843	            # Find outgoing message sheet
   844	            outgoing_sheet_name = f"syft_{my_email}_to_{their_email}_messages"
   845	            sheet_id = self._find_message_sheet(outgoing_sheet_name)
```

### syft_client//platforms/google_org/gsheets.py:841
```python
   836	        Remove a peer by revoking access to message sheets.
   837	        """
   838	        try:
   839	            removed = False
   840	            my_email = self.email.replace('@', '_at_').replace('.', '_')
   841	            their_email = email.replace('@', '_at_').replace('.', '_')
   842	            
   843	            # Find outgoing message sheet
   844	            outgoing_sheet_name = f"syft_{my_email}_to_{their_email}_messages"
   845	            sheet_id = self._find_message_sheet(outgoing_sheet_name)
   846	            
```

### syft_client//platforms/google_org/gsheets.py:889
```python
   884	        
   885	        Returns email addresses extracted from sheet names.
   886	        """
   887	        try:
   888	            contacts = set()
   889	            my_email = self.email.replace('@', '_at_').replace('.', '_')
   890	            
   891	            # Search for outgoing message sheets I created
   892	            query = f"name contains 'syft_{my_email}_to_' and name contains '_messages' and mimeType='application/vnd.google-apps.spreadsheet' and 'me' in owners and trashed=false"
   893	            results = self.drive_service.files().list(
   894	                q=query,
```

### syft_client//platforms/google_org/gsheets.py:904
```python
   899	            for file in results.get('files', []):
   900	                # Extract recipient email from sheet name
   901	                # Format: syft_{my_email}_to_{their_email}_messages
   902	                parts = file['name'].split('_to_')
   903	                if len(parts) == 2 and parts[1].endswith('_messages'):
   904	                    their_email = parts[1].replace('_messages', '')
   905	                    # Convert back to email format
   906	                    their_email = their_email.replace('_at_', '@').replace('_', '.')
   907	                    contacts.add(their_email)
   908	            
   909	            # Also search for incoming message sheets shared with me
```

### syft_client//platforms/google_org/gsheets.py:906
```python
   901	                # Format: syft_{my_email}_to_{their_email}_messages
   902	                parts = file['name'].split('_to_')
   903	                if len(parts) == 2 and parts[1].endswith('_messages'):
   904	                    their_email = parts[1].replace('_messages', '')
   905	                    # Convert back to email format
   906	                    their_email = their_email.replace('_at_', '@').replace('_', '.')
   907	                    contacts.add(their_email)
   908	            
   909	            # Also search for incoming message sheets shared with me
   910	            query = f"name contains '_to_{my_email}_messages' and mimeType='application/vnd.google-apps.spreadsheet' and sharedWithMe and trashed=false"
   911	            results = self.drive_service.files().list(
```

### syft_client//platforms/google_org/gsheets.py:921
```python
   916	            
   917	            for file in results.get('files', []):
   918	                # Extract sender email from sheet name
   919	                # Format: syft_{their_email}_to_{my_email}_messages
   920	                if file['name'].startswith('syft_') and f'_to_{my_email}_messages' in file['name']:
   921	                    their_email = file['name'].replace('syft_', '').replace(f'_to_{my_email}_messages', '')
   922	                    # Convert back to email format
   923	                    their_email = their_email.replace('_at_', '@').replace('_', '.')
   924	                    contacts.add(their_email)
   925	            
   926	            return list(contacts)
```

### syft_client//platforms/google_org/gsheets.py:923
```python
   918	                # Extract sender email from sheet name
   919	                # Format: syft_{their_email}_to_{my_email}_messages
   920	                if file['name'].startswith('syft_') and f'_to_{my_email}_messages' in file['name']:
   921	                    their_email = file['name'].replace('syft_', '').replace(f'_to_{my_email}_messages', '')
   922	                    # Convert back to email format
   923	                    their_email = their_email.replace('_at_', '@').replace('_', '.')
   924	                    contacts.add(their_email)
   925	            
   926	            return list(contacts)
   927	            
   928	        except Exception:
```

### syft_client//platforms/google_org/gsheets.py:951
```python
   946	            
   947	            # Base64 encode the data
   948	            encoded_data = base64.b64encode(archive_data).decode('utf-8')
   949	            
   950	            # Create sheet name following gdrive_unified.py pattern
   951	            my_email = self.email.replace('@', '_at_').replace('.', '_')
   952	            their_email = recipient.replace('@', '_at_').replace('.', '_')
   953	            sheet_name = f"syft_{my_email}_to_{their_email}_messages"
   954	            
   955	            # Get or create the message sheet
   956	            sheet_id = self._get_or_create_message_sheet(sheet_name, recipient_email=recipient)
```

### syft_client//platforms/google_org/gsheets.py:952
```python
   947	            # Base64 encode the data
   948	            encoded_data = base64.b64encode(archive_data).decode('utf-8')
   949	            
   950	            # Create sheet name following gdrive_unified.py pattern
   951	            my_email = self.email.replace('@', '_at_').replace('.', '_')
   952	            their_email = recipient.replace('@', '_at_').replace('.', '_')
   953	            sheet_name = f"syft_{my_email}_to_{their_email}_messages"
   954	            
   955	            # Get or create the message sheet
   956	            sheet_id = self._get_or_create_message_sheet(sheet_name, recipient_email=recipient)
   957	            if not sheet_id:
```

### syft_client//platforms/google_org/gsheets.py:1000
```python
   995	    def _find_contact_sheet(self, email: str) -> Optional[Dict[str, Any]]:
   996	        """
   997	        Legacy method - now we use message sheets instead of peer sheets.
   998	        Redirects to find outgoing message sheet.
   999	        """
  1000	        my_email = self.email.replace('@', '_at_').replace('.', '_')
  1001	        their_email = email.replace('@', '_at_').replace('.', '_')
  1002	        sheet_name = f"syft_{my_email}_to_{their_email}_messages"
  1003	        
  1004	        sheet_id = self._find_message_sheet(sheet_name)
  1005	        if sheet_id:
```

### syft_client//platforms/google_org/gsheets.py:1001
```python
   996	        """
   997	        Legacy method - now we use message sheets instead of peer sheets.
   998	        Redirects to find outgoing message sheet.
   999	        """
  1000	        my_email = self.email.replace('@', '_at_').replace('.', '_')
  1001	        their_email = email.replace('@', '_at_').replace('.', '_')
  1002	        sheet_name = f"syft_{my_email}_to_{their_email}_messages"
  1003	        
  1004	        sheet_id = self._find_message_sheet(sheet_name)
  1005	        if sheet_id:
  1006	            return {
```

### syft_client//platforms/google_org/gsheets.py:1027
```python
  1022	        - outbox_inbox: Outgoing message sheet (syft_me_to_them_messages)
  1023	        - pending: Incoming message sheet (syft_them_to_me_messages)
  1024	        """
  1025	        from ...sync.peer_resource import PeerResource
  1026	        
  1027	        my_email = self.email.replace('@', '_at_').replace('.', '_')
  1028	        their_email = email.replace('@', '_at_').replace('.', '_')
  1029	        
  1030	        # Find outgoing sheet
  1031	        outgoing_sheet_name = f"syft_{my_email}_to_{their_email}_messages"
  1032	        outgoing_sheet_id = self._find_message_sheet(outgoing_sheet_name)
```

### syft_client//platforms/google_org/gsheets.py:1028
```python
  1023	        - pending: Incoming message sheet (syft_them_to_me_messages)
  1024	        """
  1025	        from ...sync.peer_resource import PeerResource
  1026	        
  1027	        my_email = self.email.replace('@', '_at_').replace('.', '_')
  1028	        their_email = email.replace('@', '_at_').replace('.', '_')
  1029	        
  1030	        # Find outgoing sheet
  1031	        outgoing_sheet_name = f"syft_{my_email}_to_{their_email}_messages"
  1032	        outgoing_sheet_id = self._find_message_sheet(outgoing_sheet_name)
  1033	        outgoing_sheet = None
```

### syft_client//platforms/google_org/gsheets.py:1104
```python
  1099	            for sheet in shared_sheets:
  1100	                name = sheet['name']
  1101	                
  1102	                # Check if it follows syft message sheet pattern: syft_{sender}_to_{receiver}_messages
  1103	                if '_to_' in name and name.startswith('syft_') and name.endswith('_messages'):
  1104	                    parts = name.replace('_messages', '').split('_to_')
  1105	                    if len(parts) == 2:
  1106	                        sender = parts[0].replace('syft_', '')
  1107	                        receiver = parts[1]
  1108	                        
  1109	                        # If they're sharing with us and not already a contact
```

### syft_client//platforms/google_org/gsheets.py:1106
```python
  1101	                
  1102	                # Check if it follows syft message sheet pattern: syft_{sender}_to_{receiver}_messages
  1103	                if '_to_' in name and name.startswith('syft_') and name.endswith('_messages'):
  1104	                    parts = name.replace('_messages', '').split('_to_')
  1105	                    if len(parts) == 2:
  1106	                        sender = parts[0].replace('syft_', '')
  1107	                        receiver = parts[1]
  1108	                        
  1109	                        # If they're sharing with us and not already a contact
  1110	                        if receiver == my_email and sender not in existing_contacts:
  1111	                            # Verify it's from the owner
```

### syft_client//platforms/google_org/gsheets.py:1139
```python
  1134	            # Try both naming patterns
  1135	            sheet_names = [
  1136	                # New pattern with @ and . 
  1137	                f"syft_{sender_email}_to_{my_email}_outbox_inbox",
  1138	                # Legacy pattern with underscores and _messages suffix
  1139	                f"syft_{sender_email.replace('@', '_at_').replace('.', '_')}_to_{my_email.replace('@', '_at_').replace('.', '_')}_messages"
  1140	            ]
  1141	            
  1142	            sheet = None
  1143	            sheet_id = None
  1144	            
```

### syft_client//platforms/google_personal/wizard.py:34
```python
    29	def find_credentials(email: Optional[str] = None) -> Optional[Path]:
    30	    """Search for existing credentials.json in all possible locations"""
    31	    possible_paths = []
    32	    
    33	    if email:
    34	        safe_email = email.replace('@', '_at_').replace('.', '_')
    35	        possible_paths.append(Path.home() / ".syft" / safe_email / "credentials.json")
    36	    
    37	    possible_paths.extend([
    38	        Path.home() / ".syft" / "credentials.json",
    39	        Path.home() / ".syft" / "google_oauth" / "credentials.json",
```

### syft_client//platforms/google_personal/wizard.py:619
```python
   614	        break
   615	    
   616	    # Copy to correct location
   617	    target_dir = Path.home() / ".syft"
   618	    if state.email:
   619	        safe_email = state.email.replace('@', '_at_').replace('.', '_')
   620	        target_dir = target_dir / safe_email
   621	    
   622	    target_dir.mkdir(parents=True, exist_ok=True)
   623	    target_path = target_dir / "credentials.json"
   624	    
```

### syft_client//platforms/google_personal/wizard.py:915
```python
   910	        file_path, project_id = found_creds
   911	        
   912	        # Copy to the correct location
   913	        target_dir = Path.home() / ".syft"
   914	        if email:
   915	            safe_email = email.replace('@', '_at_').replace('.', '_')
   916	            target_dir = target_dir / safe_email
   917	        
   918	        target_dir.mkdir(parents=True, exist_ok=True)
   919	        target_path = target_dir / "credentials.json"
   920	        
```

### syft_client//platforms/google_personal/gforms.py:190
```python
   185	            return False
   186	            
   187	        try:
   188	            # Create form
   189	            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
   190	            form_title = f"SyftClient_{subject.replace(' ', '_')}_{timestamp}"
   191	            
   192	            form = {
   193	                "info": {
   194	                    "title": form_title,
   195	                    "document_title": form_title
```

### syft_client//platforms/google_personal/gdrive_files.py:247
```python
   242	                mime_type = 'application/octet-stream'
   243	                extension = '.pkl'
   244	            
   245	            # Create filename
   246	            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
   247	            filename = f"syft_{subject.replace(' ', '_')}_{timestamp}{extension}"
   248	            
   249	            # Upload file
   250	            file_metadata = {
   251	                'name': filename,
   252	                'parents': [self._folder_id] if self._folder_id else []
```

### syft_client//platforms/google_personal/gdrive_files.py:1181
```python
  1176	                
  1177	                # Check if it follows syft folder pattern
  1178	                if '_to_' in name and name.startswith('syft_'):
  1179	                    parts = name.split('_to_')
  1180	                    if len(parts) == 2:
  1181	                        sender = parts[0].replace('syft_', '')
  1182	                        recipient_with_suffix = parts[1]
  1183	                        
  1184	                        # Remove suffixes to get clean email
  1185	                        recipient = recipient_with_suffix
  1186	                        for suffix in ['_outbox_inbox', '_outbox', '_pending', '_archive']:
```

### syft_client//platforms/google_personal/gdrive_files.py:1187
```python
  1182	                        recipient_with_suffix = parts[1]
  1183	                        
  1184	                        # Remove suffixes to get clean email
  1185	                        recipient = recipient_with_suffix
  1186	                        for suffix in ['_outbox_inbox', '_outbox', '_pending', '_archive']:
  1187	                            recipient = recipient.replace(suffix, '')
  1188	                        
  1189	                        # If they're sharing with us and not already a contact
  1190	                        if recipient == my_email and sender not in existing_contacts:
  1191	                            # Verify it's from the owner
  1192	                            owners = folder.get('owners', [])
```

### syft_client//platforms/google_personal/gdrive_files.py:1272
```python
  1267	                            status, done = downloader.next_chunk()
  1268	                        
  1269	                        message_data = file_buffer.getvalue()
  1270	                        
  1271	                        # Store message info
  1272	                        message_id = file_name.replace('.tar.gz', '')
  1273	                        messages.append({
  1274	                            'message_id': message_id,
  1275	                            'data': message_data,
  1276	                            'file_id': file_id,
  1277	                            'file_name': file_name,
```

### syft_client//platforms/google_personal/gdrive_files.py:1318
```python
  1313	                fields='name'
  1314	            ).execute()
  1315	            
  1316	            folder_name = folder_info['name']
  1317	            # Extract emails from folder name: syft_{sender}_to_{receiver}_outbox_inbox
  1318	            parts = folder_name.replace('syft_', '').replace('_outbox_inbox', '').split('_to_')
  1319	            if len(parts) == 2:
  1320	                sender_email = parts[0]
  1321	                my_email = parts[1]
  1322	                
  1323	                # Find or create archive folder
```

### syft_client//platforms/google_personal/gsheets.py:202
```python
   197	            return False
   198	            
   199	        try:
   200	            # Create spreadsheet
   201	            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
   202	            spreadsheet_name = f"{self.SYFT_SHEET_PREFIX}{subject.replace(' ', '_')}_{timestamp}"
   203	            
   204	            spreadsheet = {
   205	                'properties': {
   206	                    'title': spreadsheet_name
   207	                }
```

### syft_client//platforms/google_personal/gsheets.py:298
```python
   293	        
   294	        if not contacts:
   295	            return {}
   296	        
   297	        all_messages = {}
   298	        my_email = self.email.replace('@', '_at_').replace('.', '_')
   299	        
   300	        for peer_email in contacts:
   301	            try:
   302	                their_email = peer_email.replace('@', '_at_').replace('.', '_')
   303	                sheet_name = f"syft_{their_email}_to_{my_email}_messages"
```

### syft_client//platforms/google_personal/gsheets.py:302
```python
   297	        all_messages = {}
   298	        my_email = self.email.replace('@', '_at_').replace('.', '_')
   299	        
   300	        for peer_email in contacts:
   301	            try:
   302	                their_email = peer_email.replace('@', '_at_').replace('.', '_')
   303	                sheet_name = f"syft_{their_email}_to_{my_email}_messages"
   304	                
   305	                # Find the sheet
   306	                sheet_id = self._find_message_sheet(sheet_name, from_email=peer_email)
   307	                if not sheet_id:
```

### syft_client//platforms/google_personal/gsheets.py:810
```python
   805	        - Outgoing: syft_{my_email}_to_{their_email}_messages
   806	        - Incoming: syft_{their_email}_to_{my_email}_messages (if possible)
   807	        """
   808	        try:
   809	            # Create outgoing message sheet name
   810	            my_email = self.email.replace('@', '_at_').replace('.', '_')
   811	            their_email = email.replace('@', '_at_').replace('.', '_')
   812	            outgoing_sheet_name = f"syft_{my_email}_to_{their_email}_messages"
   813	            
   814	            # Get or create the outgoing message sheet
   815	            sheet_id = self._get_or_create_message_sheet(outgoing_sheet_name, recipient_email=email)
```

### syft_client//platforms/google_personal/gsheets.py:811
```python
   806	        - Incoming: syft_{their_email}_to_{my_email}_messages (if possible)
   807	        """
   808	        try:
   809	            # Create outgoing message sheet name
   810	            my_email = self.email.replace('@', '_at_').replace('.', '_')
   811	            their_email = email.replace('@', '_at_').replace('.', '_')
   812	            outgoing_sheet_name = f"syft_{my_email}_to_{their_email}_messages"
   813	            
   814	            # Get or create the outgoing message sheet
   815	            sheet_id = self._get_or_create_message_sheet(outgoing_sheet_name, recipient_email=email)
   816	            
```

### syft_client//platforms/google_personal/gsheets.py:840
```python
   835	        """
   836	        Remove a peer by revoking access to message sheets.
   837	        """
   838	        try:
   839	            removed = False
   840	            my_email = self.email.replace('@', '_at_').replace('.', '_')
   841	            their_email = email.replace('@', '_at_').replace('.', '_')
   842	            
   843	            # Find outgoing message sheet
   844	            outgoing_sheet_name = f"syft_{my_email}_to_{their_email}_messages"
   845	            sheet_id = self._find_message_sheet(outgoing_sheet_name)
```

### syft_client//platforms/google_personal/gsheets.py:841
```python
   836	        Remove a peer by revoking access to message sheets.
   837	        """
   838	        try:
   839	            removed = False
   840	            my_email = self.email.replace('@', '_at_').replace('.', '_')
   841	            their_email = email.replace('@', '_at_').replace('.', '_')
   842	            
   843	            # Find outgoing message sheet
   844	            outgoing_sheet_name = f"syft_{my_email}_to_{their_email}_messages"
   845	            sheet_id = self._find_message_sheet(outgoing_sheet_name)
   846	            
```

### syft_client//platforms/google_personal/gsheets.py:889
```python
   884	        
   885	        Returns email addresses extracted from sheet names.
   886	        """
   887	        try:
   888	            contacts = set()
   889	            my_email = self.email.replace('@', '_at_').replace('.', '_')
   890	            
   891	            # Search for outgoing message sheets I created
   892	            query = f"name contains 'syft_{my_email}_to_' and name contains '_messages' and mimeType='application/vnd.google-apps.spreadsheet' and 'me' in owners and trashed=false"
   893	            results = self.drive_service.files().list(
   894	                q=query,
```

### syft_client//platforms/google_personal/gsheets.py:904
```python
   899	            for file in results.get('files', []):
   900	                # Extract recipient email from sheet name
   901	                # Format: syft_{my_email}_to_{their_email}_messages
   902	                parts = file['name'].split('_to_')
   903	                if len(parts) == 2 and parts[1].endswith('_messages'):
   904	                    their_email = parts[1].replace('_messages', '')
   905	                    # Convert back to email format
   906	                    their_email = their_email.replace('_at_', '@').replace('_', '.')
   907	                    contacts.add(their_email)
   908	            
   909	            # Also search for incoming message sheets shared with me
```

### syft_client//platforms/google_personal/gsheets.py:906
```python
   901	                # Format: syft_{my_email}_to_{their_email}_messages
   902	                parts = file['name'].split('_to_')
   903	                if len(parts) == 2 and parts[1].endswith('_messages'):
   904	                    their_email = parts[1].replace('_messages', '')
   905	                    # Convert back to email format
   906	                    their_email = their_email.replace('_at_', '@').replace('_', '.')
   907	                    contacts.add(their_email)
   908	            
   909	            # Also search for incoming message sheets shared with me
   910	            query = f"name contains '_to_{my_email}_messages' and mimeType='application/vnd.google-apps.spreadsheet' and sharedWithMe and trashed=false"
   911	            results = self.drive_service.files().list(
```

### syft_client//platforms/google_personal/gsheets.py:921
```python
   916	            
   917	            for file in results.get('files', []):
   918	                # Extract sender email from sheet name
   919	                # Format: syft_{their_email}_to_{my_email}_messages
   920	                if file['name'].startswith('syft_') and f'_to_{my_email}_messages' in file['name']:
   921	                    their_email = file['name'].replace('syft_', '').replace(f'_to_{my_email}_messages', '')
   922	                    # Convert back to email format
   923	                    their_email = their_email.replace('_at_', '@').replace('_', '.')
   924	                    contacts.add(their_email)
   925	            
   926	            return list(contacts)
```

### syft_client//platforms/google_personal/gsheets.py:923
```python
   918	                # Extract sender email from sheet name
   919	                # Format: syft_{their_email}_to_{my_email}_messages
   920	                if file['name'].startswith('syft_') and f'_to_{my_email}_messages' in file['name']:
   921	                    their_email = file['name'].replace('syft_', '').replace(f'_to_{my_email}_messages', '')
   922	                    # Convert back to email format
   923	                    their_email = their_email.replace('_at_', '@').replace('_', '.')
   924	                    contacts.add(their_email)
   925	            
   926	            return list(contacts)
   927	            
   928	        except Exception:
```

### syft_client//platforms/google_personal/gsheets.py:951
```python
   946	            
   947	            # Base64 encode the data
   948	            encoded_data = base64.b64encode(archive_data).decode('utf-8')
   949	            
   950	            # Create sheet name following gdrive_unified.py pattern
   951	            my_email = self.email.replace('@', '_at_').replace('.', '_')
   952	            their_email = recipient.replace('@', '_at_').replace('.', '_')
   953	            sheet_name = f"syft_{my_email}_to_{their_email}_messages"
   954	            
   955	            # Get or create the message sheet
   956	            sheet_id = self._get_or_create_message_sheet(sheet_name, recipient_email=recipient)
```

### syft_client//platforms/google_personal/gsheets.py:952
```python
   947	            # Base64 encode the data
   948	            encoded_data = base64.b64encode(archive_data).decode('utf-8')
   949	            
   950	            # Create sheet name following gdrive_unified.py pattern
   951	            my_email = self.email.replace('@', '_at_').replace('.', '_')
   952	            their_email = recipient.replace('@', '_at_').replace('.', '_')
   953	            sheet_name = f"syft_{my_email}_to_{their_email}_messages"
   954	            
   955	            # Get or create the message sheet
   956	            sheet_id = self._get_or_create_message_sheet(sheet_name, recipient_email=recipient)
   957	            if not sheet_id:
```

### syft_client//platforms/google_personal/gsheets.py:1000
```python
   995	    def _find_contact_sheet(self, email: str) -> Optional[Dict[str, Any]]:
   996	        """
   997	        Legacy method - now we use message sheets instead of peer sheets.
   998	        Redirects to find outgoing message sheet.
   999	        """
  1000	        my_email = self.email.replace('@', '_at_').replace('.', '_')
  1001	        their_email = email.replace('@', '_at_').replace('.', '_')
  1002	        sheet_name = f"syft_{my_email}_to_{their_email}_messages"
  1003	        
  1004	        sheet_id = self._find_message_sheet(sheet_name)
  1005	        if sheet_id:
```

### syft_client//platforms/google_personal/gsheets.py:1001
```python
   996	        """
   997	        Legacy method - now we use message sheets instead of peer sheets.
   998	        Redirects to find outgoing message sheet.
   999	        """
  1000	        my_email = self.email.replace('@', '_at_').replace('.', '_')
  1001	        their_email = email.replace('@', '_at_').replace('.', '_')
  1002	        sheet_name = f"syft_{my_email}_to_{their_email}_messages"
  1003	        
  1004	        sheet_id = self._find_message_sheet(sheet_name)
  1005	        if sheet_id:
  1006	            return {
```

### syft_client//platforms/google_personal/gsheets.py:1027
```python
  1022	        - outbox_inbox: Outgoing message sheet (syft_me_to_them_messages)
  1023	        - pending: Incoming message sheet (syft_them_to_me_messages)
  1024	        """
  1025	        from ...sync.peer_resource import PeerResource
  1026	        
  1027	        my_email = self.email.replace('@', '_at_').replace('.', '_')
  1028	        their_email = email.replace('@', '_at_').replace('.', '_')
  1029	        
  1030	        # Find outgoing sheet
  1031	        outgoing_sheet_name = f"syft_{my_email}_to_{their_email}_messages"
  1032	        outgoing_sheet_id = self._find_message_sheet(outgoing_sheet_name)
```

### syft_client//platforms/google_personal/gsheets.py:1028
```python
  1023	        - pending: Incoming message sheet (syft_them_to_me_messages)
  1024	        """
  1025	        from ...sync.peer_resource import PeerResource
  1026	        
  1027	        my_email = self.email.replace('@', '_at_').replace('.', '_')
  1028	        their_email = email.replace('@', '_at_').replace('.', '_')
  1029	        
  1030	        # Find outgoing sheet
  1031	        outgoing_sheet_name = f"syft_{my_email}_to_{their_email}_messages"
  1032	        outgoing_sheet_id = self._find_message_sheet(outgoing_sheet_name)
  1033	        outgoing_sheet = None
```

### syft_client//platforms/google_personal/gsheets.py:1104
```python
  1099	            for sheet in shared_sheets:
  1100	                name = sheet['name']
  1101	                
  1102	                # Check if it follows syft message sheet pattern: syft_{sender}_to_{receiver}_messages
  1103	                if '_to_' in name and name.startswith('syft_') and name.endswith('_messages'):
  1104	                    parts = name.replace('_messages', '').split('_to_')
  1105	                    if len(parts) == 2:
  1106	                        sender = parts[0].replace('syft_', '')
  1107	                        receiver = parts[1]
  1108	                        
  1109	                        # If they're sharing with us and not already a contact
```

### syft_client//platforms/google_personal/gsheets.py:1106
```python
  1101	                
  1102	                # Check if it follows syft message sheet pattern: syft_{sender}_to_{receiver}_messages
  1103	                if '_to_' in name and name.startswith('syft_') and name.endswith('_messages'):
  1104	                    parts = name.replace('_messages', '').split('_to_')
  1105	                    if len(parts) == 2:
  1106	                        sender = parts[0].replace('syft_', '')
  1107	                        receiver = parts[1]
  1108	                        
  1109	                        # If they're sharing with us and not already a contact
  1110	                        if receiver == my_email and sender not in existing_contacts:
  1111	                            # Verify it's from the owner
```

### syft_client//platforms/google_personal/gsheets.py:1139
```python
  1134	            # Try both naming patterns
  1135	            sheet_names = [
  1136	                # New pattern with @ and . 
  1137	                f"syft_{sender_email}_to_{my_email}_outbox_inbox",
  1138	                # Legacy pattern with underscores and _messages suffix
  1139	                f"syft_{sender_email.replace('@', '_at_').replace('.', '_')}_to_{my_email.replace('@', '_at_').replace('.', '_')}_messages"
  1140	            ]
  1141	            
  1142	            sheet = None
  1143	            sheet_id = None
  1144	            
```

### syft_client//platforms/transport_base.py:172
```python
   167	        if verbose:
   168	            from rich.console import Console
   169	            from rich.panel import Panel
   170	            
   171	            console = Console()
   172	            transport_name = self.__class__.__name__.replace('Transport', '').lower()
   173	            
   174	            # Get platform name if available
   175	            platform_path = "client.platforms.<platform>"
   176	            if hasattr(self, '_platform_client') and self._platform_client:
   177	                platform_name = getattr(self._platform_client, 'platform', '<platform>')
```

### syft_client//platforms/transport_base.py:241
```python
   236	        main_table = Table(show_header=False, show_edge=False, box=None, padding=0)
   237	        main_table.add_column("Attribute", style="bold cyan")
   238	        main_table.add_column("Value")
   239	        
   240	        # Get the transport name (e.g., 'gmail', 'gdrive_files')
   241	        transport_name = self.__class__.__name__.replace('Transport', '').lower()
   242	        if 'gmail' in transport_name:
   243	            transport_name = 'gmail'
   244	        elif 'gdrive' in transport_name.lower():
   245	            transport_name = 'gdrive_files'
   246	        elif 'gsheets' in transport_name.lower():
```

### syft_client//platforms/transport_base.py:347
```python
   342	            print(f"Setup verified: {self._setup_verified}")
   343	    
   344	    def enable_api(self) -> None:
   345	        """Guide user through enabling the API for this transport"""
   346	        # Get transport name
   347	        transport_name = self.__class__.__name__.replace('Transport', '').lower()
   348	        if 'gdrive' in transport_name:
   349	            transport_name = 'gdrive_files'
   350	        
   351	        # Get project_id from platform client if available
   352	        project_id = None
```

### syft_client//platforms/transport_base.py:362
```python
   357	        self.__class__.enable_api_static(transport_name, self.email, project_id)
   358	    
   359	    def disable_api(self) -> None:
   360	        """Show instructions for disabling the API for this transport"""
   361	        # Get transport name
   362	        transport_name = self.__class__.__name__.replace('Transport', '').lower()
   363	        if 'gdrive' in transport_name:
   364	            transport_name = 'gdrive_files'
   365	        
   366	        # Get project_id from platform client if available
   367	        project_id = None
```

### syft_client//platforms/transport_base.py:663
```python
   658	                                    # Use atomic replacement to prevent watcher from seeing deletion
   659	                                    # Create temp file with timestamp to ensure uniqueness
   660	                                    temp_dest = dest.with_suffix(f'.tmp.{int(time.time() * 1000000)}')
   661	                                    shutil.move(str(item), str(temp_dest))
   662	                                    # Atomic replace (on most filesystems)
   663	                                    temp_dest.replace(dest)
   664	                                else:
   665	                                    # No existing file, just move normally
   666	                                    shutil.move(str(item), str(dest))
   667	                            
   668	                            if verbose:
```

### syft_client//platforms/transport_base.py:743
```python
   738	    def transport_name(self) -> str:
   739	        """
   740	        Get the name of this transport (e.g., 'gdrive_files', 'gsheets')
   741	        """
   742	        # Default implementation based on class name
   743	        name = self.__class__.__name__.replace('Transport', '').lower()
   744	        if 'gdrive' in name:
   745	            return 'gdrive_files'
   746	        elif 'gsheets' in name:
   747	            return 'gsheets'
   748	        elif 'gmail' in name:
```

### syft_client//platforms/transport_base.py:784
```python
   779	                    # Use atomic replacement to prevent watcher from seeing deletion
   780	                    import time
   781	                    temp_dest = d.with_suffix(f'.tmp.{int(time.time() * 1000000)}')
   782	                    shutil.move(str(s), str(temp_dest))
   783	                    # Atomic replace (on most filesystems)
   784	                    temp_dest.replace(d)
   785	                else:
   786	                    # No existing file, just move normally
   787	                    shutil.move(str(s), str(d))
   788	    
   789	    def send_to(self, archive_path: str, recipient: str, message_id: Optional[str] = None) -> bool:
```

### syft_client//platforms/base.py:74
```python
    69	        
    70	        return attrs
    71	    
    72	    def __init__(self, email: str, **kwargs):
    73	        self.email = email
    74	        self.platform = self.__class__.__name__.replace('Client', '').lower()
    75	        self._transport_instances = {}  # transport_name -> instance
    76	        # Store any additional kwargs for subclasses that need them
    77	        self.verbose = kwargs.get('verbose', False)
    78	        self._current_environment = None  # Cached environment
    79	    
```

### syft_client//platforms/base.py:82
```python
    77	        self.verbose = kwargs.get('verbose', False)
    78	        self._current_environment = None  # Cached environment
    79	    
    80	    def _sanitize_email(self) -> str:
    81	        """Sanitize email for use in file paths"""
    82	        return self.email.replace('@', '_at_').replace('.', '_')
    83	        
    84	    def authenticate(self) -> Dict[str, Any]:
    85	        """
    86	        Authenticate the user with the platform.
    87	        
```

### syft_client//platforms/base.py:96
```python
    91	        Raises:
    92	            NotImplementedError: If platform login not yet supported
    93	        """
    94	        # Check if this platform has implemented authentication
    95	        if self.login_complexity == -1:
    96	            platform_name = self.platform.replace('client', '')
    97	            raise NotImplementedError(
    98	                f"\nLogin for {platform_name} is not yet supported.\n\n"
    99	                f"This platform requires additional development to enable authentication.\n"
   100	                f"Currently supported platforms with working authentication:\n"
   101	                f"  • smtp - Generic SMTP/IMAP email (implemented)\n"
```

### syft_client//platforms/base.py:208
```python
   203	            Transport instance or None if creation fails
   204	        """
   205	        try:
   206	            # Import transport module dynamically
   207	            # Convert transport name to module name (e.g., GmailTransport -> gmail)
   208	            module_name = transport_name.replace('Transport', '').lower()
   209	            
   210	            # Special cases for module names
   211	            module_map = {
   212	                'smtpemail': 'email',
   213	                'gdrive_files': 'gdrive_files',
```

### syft_client//auth/wallets/local_file.py:38
```python
    33	        self.base_dir = Path(config.get('base_dir', Path.home() / '.syft'))
    34	    
    35	    def _get_token_dir(self, account: str) -> Path:
    36	        """Get token directory for an account"""
    37	        # Sanitize account for filesystem
    38	        safe_account = account.replace('@', '_at_').replace('.', '_')
    39	        return self.base_dir / safe_account / 'tokens'
    40	    
    41	    def _get_token_path(self, service: str, account: str) -> Path:
    42	        """Get path to token file"""
    43	        return self._get_token_dir(account) / f"{service}.json"
```

### syft_client//auth/wallets/local_file.py:191
```python
   186	                token_dir = account_dir / 'tokens'
   187	                if not token_dir.exists():
   188	                    continue
   189	                
   190	                # Restore account from directory name
   191	                account = account_dir.name.replace('_at_', '@').replace('_', '.')
   192	                
   193	                # List token files
   194	                for token_file in token_dir.glob('*.json'):
   195	                    token_service = token_file.stem
   196	                    
```

### syft_client//sync/peer_model.py:190
```python
   185	        return cls(**data)
   186	    
   187	    def save(self, directory: Path):
   188	        """Save peer to disk"""
   189	        directory.mkdir(parents=True, exist_ok=True)
   190	        file_path = directory / f"{self.email.replace('@', '_at_').replace('.', '_')}.json"
   191	        with open(file_path, 'w') as f:
   192	            json.dump(self.to_dict(), f, indent=2)
   193	    
   194	    @classmethod
   195	    def load(cls, file_path: Path) -> 'Peer':
```

### syft_client//sync/watcher/watcher_manager.py:16
```python
    11	    """Manages file watchers for the client"""
    12	    
    13	    def __init__(self, client):
    14	        self.client = client
    15	        self._server = None
    16	        self._server_name = f"watcher_sender_{client.email.replace('@', '_').replace('.', '_')}"
    17	    
    18	    def start(self, paths: Optional[List[str]] = None, 
    19	              exclude_patterns: Optional[List[str]] = None,
    20	              bidirectional: bool = True,
    21	              check_interval: int = 30,
```

### syft_client//sync/watcher/watcher_manager.py:102
```python
    97	        try:
    98	            import syft_serve as ss
    99	            for server in ss.servers:
   100	                if server.name.startswith("watcher_sender_"):
   101	                    # Extract email from server name
   102	                    email_part = server.name.replace("watcher_sender_", "")
   103	                    email = email_part.replace("_at_", "@").replace("_", ".")
   104	                    
   105	                    watchers.append({
   106	                        "email": email,
   107	                        "server_name": server.name,
```

### syft_client//sync/watcher/watcher_manager.py:103
```python
    98	            import syft_serve as ss
    99	            for server in ss.servers:
   100	                if server.name.startswith("watcher_sender_"):
   101	                    # Extract email from server name
   102	                    email_part = server.name.replace("watcher_sender_", "")
   103	                    email = email_part.replace("_at_", "@").replace("_", ".")
   104	                    
   105	                    watchers.append({
   106	                        "email": email,
   107	                        "server_name": server.name,
   108	                        "server_url": server.url,
```

### syft_client//sync/watcher/file_watcher.py:19
```python
    14	        raise ImportError("syft-serve is required for file watching. Install with: pip install syft-serve")
    15	    
    16	    import requests
    17	    
    18	    # Create unique server name based on email
    19	    server_name = f"watcher_sender_{email.replace('@', '_').replace('.', '_')}"
    20	    
    21	    # Check if endpoint already exists
    22	    existing_servers = list(ss.servers)
    23	    for server in existing_servers:
    24	        if server.name == server_name:
```

### syft_client//sync/watcher/file_watcher.py:205
```python
   200	        import syft_serve as ss
   201	    except ImportError:
   202	        raise ImportError("syft-serve is required. Install with: pip install syft-serve")
   203	    
   204	    # Create server name to look for
   205	    server_name = f"watcher_sender_{email.replace('@', '_').replace('.', '_')}"
   206	    
   207	    # Find and terminate the specific server
   208	    existing_servers = list(ss.servers)
   209	    for server in existing_servers:
   210	        if server.name == server_name:
```

### syft_client//sync/discovery.py:179
```python
   174	        return None
   175	    
   176	    def save_discovery_cache(self, peer: Peer):
   177	        """Save discovered capabilities to cache"""
   178	        cache_dir = self._get_discovery_cache_dir()
   179	        cache_file = cache_dir / f"{peer.email.replace('@', '_at_')}_discovery.json"
   180	        
   181	        try:
   182	            discovery_data = {
   183	                'email': peer.email,
   184	                'platform': peer.platform,
```

### syft_client//sync/discovery.py:199
```python
   194	                print(f"⚠️  Could not save discovery cache for {peer.email}: {e}")
   195	    
   196	    def load_discovery_cache(self, email: str) -> Optional[Dict[str, Any]]:
   197	        """Load discovered capabilities from cache"""
   198	        cache_dir = self._get_discovery_cache_dir()
   199	        cache_file = cache_dir / f"{email.replace('@', '_at_')}_discovery.json"
   200	        
   201	        if cache_file.exists():
   202	            try:
   203	                with open(cache_file, 'r') as f:
   204	                    return json.load(f)
```

### syft_client//sync/sync_services.py:48
```python
    43	        except ImportError:
    44	            # syft-serve not installed, skip service management
    45	            return
    46	        
    47	        # Create expected server name
    48	        server_name = f"watcher_sender_{self.client.email.replace('@', '_').replace('.', '_')}"
    49	        
    50	        # Check if it exists
    51	        existing_servers = list(ss.servers)
    52	        for server in existing_servers:
    53	            if server.name == server_name:
```

### syft_client//sync/sync_services.py:70
```python
    65	        except ImportError:
    66	            # syft-serve not installed, skip service management
    67	            return
    68	        
    69	        # Create expected server name
    70	        server_name = f"receiver_{self.client.email.replace('@', '_').replace('.', '_')}"
    71	        
    72	        # Check if it exists
    73	        existing_servers = list(ss.servers)
    74	        for server in existing_servers:
    75	            if server.name == server_name:
```

### syft_client//sync/peers.py:335
```python
   330	                print(f"\n✅ Peer {email} removed from {len(successful_removals)} transport(s)")
   331	            
   332	            # Remove peer file
   333	            try:
   334	                peers_dir = self._get_peers_directory()
   335	                file_name = f"{email.replace('@', '_at_').replace('.', '_')}.json"
   336	                file_path = peers_dir / file_name
   337	                if file_path.exists():
   338	                    file_path.unlink()
   339	            except:
   340	                pass
```

### syft_client//sync/peers.py:462
```python
   457	        return self._peers_dir
   458	    
   459	    def _load_or_create_peer(self, email: str) -> Peer:
   460	        """Load peer from disk or create new one"""
   461	        peers_dir = self._get_peers_directory()
   462	        file_name = f"{email.replace('@', '_at_').replace('.', '_')}.json"
   463	        file_path = peers_dir / file_name
   464	        
   465	        if file_path.exists():
   466	            try:
   467	                peer = Peer.load(file_path)
```

### syft_client//sync/receiver/receiver.py:31
```python
    26	        raise ImportError("syft-serve is required for receiver. Install with: pip install syft-serve")
    27	    
    28	    import requests
    29	    
    30	    # Create unique server name based on email
    31	    server_name = f"receiver_{email.replace('@', '_').replace('.', '_')}"
    32	    
    33	    # Check if endpoint already exists
    34	    existing_servers = list(ss.servers)
    35	    for server in existing_servers:
    36	        if server.name == server_name:
```

### syft_client//sync/receiver/receiver.py:294
```python
   289	        import syft_serve as ss
   290	    except ImportError:
   291	        raise ImportError("syft-serve is required. Install with: pip install syft-serve")
   292	    
   293	    # Create server name to look for
   294	    server_name = f"receiver_{email.replace('@', '_').replace('.', '_')}"
   295	    
   296	    # Find and terminate the specific server
   297	    existing_servers = list(ss.servers)
   298	    for server in existing_servers:
   299	        if server.name == server_name:
```

### syft_client//sync/receiver/receiver_manager.py:16
```python
    11	    """Manages the inbox receiver for the client"""
    12	    
    13	    def __init__(self, client):
    14	        self.client = client
    15	        self._server = None
    16	        self._server_name = f"receiver_{client.email.replace('@', '_').replace('.', '_')}"
    17	    
    18	    def start(self, check_interval: int = 10,
    19	              process_immediately: bool = True,
    20	              transports: Optional[List[str]] = None,
    21	              auto_accept: bool = True,
```

### syft_client//sync/receiver/receiver_manager.py:171
```python
   166	        try:
   167	            import syft_serve as ss
   168	            for server in ss.servers:
   169	                if server.name.startswith("receiver_"):
   170	                    # Extract email from server name
   171	                    email_part = server.name.replace("receiver_", "")
   172	                    email = email_part.replace("_at_", "@").replace("_", ".")
   173	                    
   174	                    receivers.append({
   175	                        "email": email,
   176	                        "server_name": server.name,
```

### syft_client//sync/receiver/receiver_manager.py:172
```python
   167	            import syft_serve as ss
   168	            for server in ss.servers:
   169	                if server.name.startswith("receiver_"):
   170	                    # Extract email from server name
   171	                    email_part = server.name.replace("receiver_", "")
   172	                    email = email_part.replace("_at_", "@").replace("_", ".")
   173	                    
   174	                    receivers.append({
   175	                        "email": email,
   176	                        "server_name": server.name,
   177	                        "server_url": server.url,
```

## shutil.move() calls

### syft_client//platforms/transport_base.py:651
```python
   646	                                if dest.exists():
   647	                                    # Merge directories instead of replacing
   648	                                    self._merge_directories(str(item), str(dest))
   649	                                else:
   650	                                    import shutil
   651	                                    shutil.move(str(item), str(dest))
   652	                            else:
   653	                                # For files, use atomic replace to avoid triggering deletion events
   654	                                import shutil
   655	                                import time
   656	                                
```

### syft_client//platforms/transport_base.py:661
```python
   656	                                
   657	                                if dest.exists():
   658	                                    # Use atomic replacement to prevent watcher from seeing deletion
   659	                                    # Create temp file with timestamp to ensure uniqueness
   660	                                    temp_dest = dest.with_suffix(f'.tmp.{int(time.time() * 1000000)}')
   661	                                    shutil.move(str(item), str(temp_dest))
   662	                                    # Atomic replace (on most filesystems)
   663	                                    temp_dest.replace(dest)
   664	                                else:
   665	                                    # No existing file, just move normally
   666	                                    shutil.move(str(item), str(dest))
```

### syft_client//platforms/transport_base.py:666
```python
   661	                                    shutil.move(str(item), str(temp_dest))
   662	                                    # Atomic replace (on most filesystems)
   663	                                    temp_dest.replace(dest)
   664	                                else:
   665	                                    # No existing file, just move normally
   666	                                    shutil.move(str(item), str(dest))
   667	                            
   668	                            if verbose:
   669	                                print(f"   📥 Extracted: {dest.name}")
   670	                    
   671	                        # Add to results
```

### syft_client//platforms/transport_base.py:782
```python
   777	                # For files, use atomic replace to avoid triggering deletion events
   778	                if d.exists():
   779	                    # Use atomic replacement to prevent watcher from seeing deletion
   780	                    import time
   781	                    temp_dest = d.with_suffix(f'.tmp.{int(time.time() * 1000000)}')
   782	                    shutil.move(str(s), str(temp_dest))
   783	                    # Atomic replace (on most filesystems)
   784	                    temp_dest.replace(d)
   785	                else:
   786	                    # No existing file, just move normally
   787	                    shutil.move(str(s), str(d))
```

### syft_client//platforms/transport_base.py:787
```python
   782	                    shutil.move(str(s), str(temp_dest))
   783	                    # Atomic replace (on most filesystems)
   784	                    temp_dest.replace(d)
   785	                else:
   786	                    # No existing file, just move normally
   787	                    shutil.move(str(s), str(d))
   788	    
   789	    def send_to(self, archive_path: str, recipient: str, message_id: Optional[str] = None) -> bool:
   790	        """
   791	        Base implementation for sending messages. Transport-specific classes should override
   792	        _send_archive_via_transport() to provide the actual sending logic.
```

### syft_client//sync/receiver/message_processor.py:281
```python
   276	            archive_name = f"{message_id}_{source.name}"
   277	            target = peer_archive / archive_name
   278	            
   279	            # Move to archive
   280	            if source.exists():
   281	                shutil.move(str(source), str(target))
   282	                
   283	        except Exception as e:
   284	            if self.verbose:
   285	                print(f"Warning: Could not archive message: {e}")```

## Cleanup functions

### syft_client//platforms/google_org/client.py:351
```python
   346	                    
   347	                    # Get project_id from platform client if available
   348	                    project_id = getattr(self._platform_client, 'project_id', None)
   349	                    transport_class.disable_api_static(self._transport_name, self._platform_client.email, project_id)
   350	            
   351	            def test(self, test_data: str = "test123", cleanup: bool = True):
   352	                """Test transport - requires initialization first"""
   353	                if not self._setup_called or not self._real_transport:
   354	                    print(f"❌ Transport '{self._transport_name}' is not initialized")
   355	                    print(f"   Please call .init() first to initialize the transport")
   356	                    return {"success": False, "error": "Transport not initialized"}
```

### syft_client//platforms/google_org/client.py:360
```python
   355	                    print(f"   Please call .init() first to initialize the transport")
   356	                    return {"success": False, "error": "Transport not initialized"}
   357	                
   358	                # Delegate to real transport
   359	                if hasattr(self._real_transport, 'test'):
   360	                    return self._real_transport.test(test_data=test_data, cleanup=cleanup)
   361	                else:
   362	                    return {"success": False, "error": f"Transport '{self._transport_name}' does not support test()"}
   363	            
   364	            def __getattr__(self, name):
   365	                # List of attributes that should be accessible without initialization
```

### syft_client//platforms/google_org/gmail.py:467
```python
   462	    
   463	    def send_notification(self, recipient: str, message: str, subject: str = "Notification") -> bool:
   464	        """Send human-readable notification email"""
   465	        return self.send(recipient, message, subject, is_notification=True)
   466	    
   467	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   468	        """Test Gmail transport by sending an email to self with test data
   469	        
   470	        Args:
   471	            test_data: Data to include in the test email
   472	            cleanup: If True, delete the test email after creation (default: True)
```

### syft_client//platforms/google_org/gmail.py:472
```python
   467	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   468	        """Test Gmail transport by sending an email to self with test data
   469	        
   470	        Args:
   471	            test_data: Data to include in the test email
   472	            cleanup: If True, delete the test email after creation (default: True)
   473	            
   474	        Returns:
   475	            Dictionary with 'success' (bool) and 'url' (str) if successful
   476	        """
   477	        if not self.gmail_service:
```

### syft_client//platforms/google_org/gmail.py:513
```python
   508	                            userId='me',
   509	                            id=message_id,
   510	                            body={'removeLabelIds': ['UNREAD']}
   511	                        ).execute()
   512	                        
   513	                        # Delete the email if cleanup is requested
   514	                        if cleanup:
   515	                            try:
   516	                                self.gmail_service.users().messages().trash(
   517	                                    userId='me',
   518	                                    id=message_id
```

### syft_client//platforms/google_org/gmail.py:514
```python
   509	                            id=message_id,
   510	                            body={'removeLabelIds': ['UNREAD']}
   511	                        ).execute()
   512	                        
   513	                        # Delete the email if cleanup is requested
   514	                        if cleanup:
   515	                            try:
   516	                                self.gmail_service.users().messages().trash(
   517	                                    userId='me',
   518	                                    id=message_id
   519	                                ).execute()
```

### syft_client//platforms/google_org/gmail.py:541
```python
   536	                encoded_query = urllib.parse.quote(search_query)
   537	                # Use authuser parameter instead of /u/0/ to handle multiple accounts
   538	                url = f"https://mail.google.com/mail/?authuser={urllib.parse.quote(self.email)}#search/{encoded_query}"
   539	                
   540	                print(f"✅ Gmail test successful! Email sent to {self.email}")
   541	                if cleanup:
   542	                    print("   Email has been deleted as requested (re-run test(cleanup=False) to see the email yourself.)")
   543	                
   544	                return {"success": True, "url": url}
   545	            else:
   546	                print("❌ Gmail test failed: Unable to send email")
```

### syft_client//platforms/google_org/gmail.py:542
```python
   537	                # Use authuser parameter instead of /u/0/ to handle multiple accounts
   538	                url = f"https://mail.google.com/mail/?authuser={urllib.parse.quote(self.email)}#search/{encoded_query}"
   539	                
   540	                print(f"✅ Gmail test successful! Email sent to {self.email}")
   541	                if cleanup:
   542	                    print("   Email has been deleted as requested (re-run test(cleanup=False) to see the email yourself.)")
   543	                
   544	                return {"success": True, "url": url}
   545	            else:
   546	                print("❌ Gmail test failed: Unable to send email")
   547	                return {"success": False, "error": "Failed to send test email"}
```

### syft_client//platforms/google_org/gforms.py:395
```python
   390	            return f"https://docs.google.com/forms/d/{form_id}/viewform"
   391	            
   392	        except:
   393	            return None
   394	    
   395	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   396	        """Test Google Forms transport by creating a test form with test data
   397	        
   398	        Args:
   399	            test_data: Data to include in the test form
   400	            cleanup: If True, delete the test form after creation (default: True)
```

### syft_client//platforms/google_org/gforms.py:400
```python
   395	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   396	        """Test Google Forms transport by creating a test form with test data
   397	        
   398	        Args:
   399	            test_data: Data to include in the test form
   400	            cleanup: If True, delete the test form after creation (default: True)
   401	            
   402	        Returns:
   403	            Dictionary with 'success' (bool) and 'url' (str) if successful
   404	        """
   405	        if not self.forms_service:
```

### syft_client//platforms/google_org/gforms.py:497
```python
   492	                formId=form_id, body=update
   493	            ).execute()
   494	            
   495	            form_url = f"https://docs.google.com/forms/d/{form_id}/viewform"
   496	            
   497	            # Delete the form if cleanup is requested
   498	            if cleanup and form_id:
   499	                try:
   500	                    # Small delay to ensure form is accessible before deletion
   501	                    import time
   502	                    time.sleep(1)
```

### syft_client//platforms/google_org/gforms.py:498
```python
   493	            ).execute()
   494	            
   495	            form_url = f"https://docs.google.com/forms/d/{form_id}/viewform"
   496	            
   497	            # Delete the form if cleanup is requested
   498	            if cleanup and form_id:
   499	                try:
   500	                    # Small delay to ensure form is accessible before deletion
   501	                    import time
   502	                    time.sleep(1)
   503	                    
```

### syft_client//platforms/google_org/gforms.py:524
```python
   519	                except Exception:
   520	                    pass
   521	            
   522	            # Return the form URL
   523	            print(f"✅ Google Forms test successful! Form created with 3 test questions")
   524	            if cleanup:
   525	                print("   Form has been deleted as requested")
   526	            
   527	            return {"success": True, "url": form_url}
   528	            
   529	        except Exception as e:
```

### syft_client//platforms/google_org/gdrive_files.py:400
```python
   395	            return folder.get('webViewLink')
   396	            
   397	        except:
   398	            return None
   399	    
   400	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   401	        """Test Google Drive transport by creating a test file with test data
   402	        
   403	        Args:
   404	            test_data: Data to include in the test file
   405	            cleanup: If True, delete the test file after creation (default: True)
```

### syft_client//platforms/google_org/gdrive_files.py:405
```python
   400	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   401	        """Test Google Drive transport by creating a test file with test data
   402	        
   403	        Args:
   404	            test_data: Data to include in the test file
   405	            cleanup: If True, delete the test file after creation (default: True)
   406	            
   407	        Returns:
   408	            Dictionary with 'success' (bool) and 'url' (str) if successful
   409	        """
   410	        if not self.drive_service:
```

### syft_client//platforms/google_org/gdrive_files.py:454
```python
   449	            ).execute()
   450	            
   451	            file_id = file.get('id')
   452	            web_link = file.get('webViewLink')
   453	            
   454	            # Delete the file if cleanup is requested
   455	            if cleanup and file_id:
   456	                try:
   457	                    # Small delay to ensure file is accessible before deletion
   458	                    import time
   459	                    time.sleep(1)
```

### syft_client//platforms/google_org/gdrive_files.py:455
```python
   450	            
   451	            file_id = file.get('id')
   452	            web_link = file.get('webViewLink')
   453	            
   454	            # Delete the file if cleanup is requested
   455	            if cleanup and file_id:
   456	                try:
   457	                    # Small delay to ensure file is accessible before deletion
   458	                    import time
   459	                    time.sleep(1)
   460	                    
```

### syft_client//platforms/google_org/gdrive_files.py:474
```python
   469	                    except Exception:
   470	                        pass
   471	            
   472	            # Return the web view link
   473	            print(f"✅ Google Drive test successful! File created in {self.SYFT_FOLDER if self._folder_id else 'root'}")
   474	            if cleanup:
   475	                print("   File has been deleted as requested")
   476	            
   477	            return {"success": True, "url": web_link}
   478	            
   479	        except Exception as e:
```

### syft_client//platforms/google_org/gsheets.py:684
```python
   679	            return None
   680	            
   681	        except Exception:
   682	            return None
   683	    
   684	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   685	        """Test Google Sheets transport by creating a test spreadsheet with test data
   686	        
   687	        Args:
   688	            test_data: Data to include in the test spreadsheet
   689	            cleanup: If True, delete the test spreadsheet after creation (default: True)
```

### syft_client//platforms/google_org/gsheets.py:689
```python
   684	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   685	        """Test Google Sheets transport by creating a test spreadsheet with test data
   686	        
   687	        Args:
   688	            test_data: Data to include in the test spreadsheet
   689	            cleanup: If True, delete the test spreadsheet after creation (default: True)
   690	            
   691	        Returns:
   692	            Dictionary with 'success' (bool) and 'url' (str) if successful
   693	        """
   694	        if not self.sheets_service or not self.drive_service:
```

### syft_client//platforms/google_org/gsheets.py:769
```python
   764	                body={'requests': requests}
   765	            ).execute()
   766	            
   767	            spreadsheet_url = spreadsheet.get('spreadsheetUrl')
   768	            
   769	            # Delete the spreadsheet if cleanup is requested
   770	            if cleanup and spreadsheet_id:
   771	                try:
   772	                    # Small delay to ensure spreadsheet is accessible before deletion
   773	                    import time
   774	                    time.sleep(1)
```

### syft_client//platforms/google_org/gsheets.py:770
```python
   765	            ).execute()
   766	            
   767	            spreadsheet_url = spreadsheet.get('spreadsheetUrl')
   768	            
   769	            # Delete the spreadsheet if cleanup is requested
   770	            if cleanup and spreadsheet_id:
   771	                try:
   772	                    # Small delay to ensure spreadsheet is accessible before deletion
   773	                    import time
   774	                    time.sleep(1)
   775	                    
```

### syft_client//platforms/google_org/gsheets.py:790
```python
   785	                    except Exception:
   786	                        pass
   787	            
   788	            # Return the spreadsheet URL
   789	            print(f"✅ Google Sheets test successful! Spreadsheet created with test data")
   790	            if cleanup:
   791	                print("   Spreadsheet has been deleted as requested")
   792	            
   793	            return {"success": True, "url": spreadsheet_url}
   794	            
   795	        except Exception as e:
```

### syft_client//platforms/google_personal/client.py:418
```python
   413	                    module_path, class_name = transport_map[self._transport_name]
   414	                    module = __import__(module_path, fromlist=[class_name])
   415	                    transport_class = getattr(module, class_name)
   416	                    transport_class.disable_api_static(self._transport_name, self._platform_client.email)
   417	            
   418	            def test(self, test_data: str = "test123", cleanup: bool = True):
   419	                """Test transport - requires initialization first"""
   420	                if not self._setup_called or not self._real_transport:
   421	                    print(f"❌ Transport '{self._transport_name}' is not initialized")
   422	                    print(f"   Please call .init() first to initialize the transport")
   423	                    return {"success": False, "error": "Transport not initialized"}
```

### syft_client//platforms/google_personal/client.py:427
```python
   422	                    print(f"   Please call .init() first to initialize the transport")
   423	                    return {"success": False, "error": "Transport not initialized"}
   424	                
   425	                # Delegate to real transport
   426	                if hasattr(self._real_transport, 'test'):
   427	                    return self._real_transport.test(test_data=test_data, cleanup=cleanup)
   428	                else:
   429	                    return {"success": False, "error": f"Transport '{self._transport_name}' does not support test()"}
   430	            
   431	            def __getattr__(self, name):
   432	                # List of attributes that should be accessible without initialization
```

### syft_client//platforms/google_personal/gmail.py:467
```python
   462	    
   463	    def send_notification(self, recipient: str, message: str, subject: str = "Notification") -> bool:
   464	        """Send human-readable notification email"""
   465	        return self.send(recipient, message, subject, is_notification=True)
   466	    
   467	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   468	        """Test Gmail transport by sending an email to self with test data
   469	        
   470	        Args:
   471	            test_data: Data to include in the test email
   472	            cleanup: If True, delete the test email after creation (default: True)
```

### syft_client//platforms/google_personal/gmail.py:472
```python
   467	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   468	        """Test Gmail transport by sending an email to self with test data
   469	        
   470	        Args:
   471	            test_data: Data to include in the test email
   472	            cleanup: If True, delete the test email after creation (default: True)
   473	            
   474	        Returns:
   475	            Dictionary with 'success' (bool) and 'url' (str) if successful
   476	        """
   477	        if not self.gmail_service:
```

### syft_client//platforms/google_personal/gmail.py:513
```python
   508	                            userId='me',
   509	                            id=message_id,
   510	                            body={'removeLabelIds': ['UNREAD']}
   511	                        ).execute()
   512	                        
   513	                        # Delete the email if cleanup is requested
   514	                        if cleanup:
   515	                            try:
   516	                                self.gmail_service.users().messages().trash(
   517	                                    userId='me',
   518	                                    id=message_id
```

### syft_client//platforms/google_personal/gmail.py:514
```python
   509	                            id=message_id,
   510	                            body={'removeLabelIds': ['UNREAD']}
   511	                        ).execute()
   512	                        
   513	                        # Delete the email if cleanup is requested
   514	                        if cleanup:
   515	                            try:
   516	                                self.gmail_service.users().messages().trash(
   517	                                    userId='me',
   518	                                    id=message_id
   519	                                ).execute()
```

### syft_client//platforms/google_personal/gmail.py:541
```python
   536	                encoded_query = urllib.parse.quote(search_query)
   537	                # Use authuser parameter instead of /u/0/ to handle multiple accounts
   538	                url = f"https://mail.google.com/mail/?authuser={urllib.parse.quote(self.email)}#search/{encoded_query}"
   539	                
   540	                print(f"✅ Gmail test successful! Email sent to {self.email}")
   541	                if cleanup:
   542	                    print("   Email has been deleted as requested (re-run test(cleanup=False) to see the email yourself.)")
   543	                
   544	                return {"success": True, "url": url}
   545	            else:
   546	                print("❌ Gmail test failed: Unable to send email")
```

### syft_client//platforms/google_personal/gmail.py:542
```python
   537	                # Use authuser parameter instead of /u/0/ to handle multiple accounts
   538	                url = f"https://mail.google.com/mail/?authuser={urllib.parse.quote(self.email)}#search/{encoded_query}"
   539	                
   540	                print(f"✅ Gmail test successful! Email sent to {self.email}")
   541	                if cleanup:
   542	                    print("   Email has been deleted as requested (re-run test(cleanup=False) to see the email yourself.)")
   543	                
   544	                return {"success": True, "url": url}
   545	            else:
   546	                print("❌ Gmail test failed: Unable to send email")
   547	                return {"success": False, "error": "Failed to send test email"}
```

### syft_client//platforms/google_personal/gforms.py:384
```python
   379	            return f"https://docs.google.com/forms/d/{form_id}/viewform"
   380	            
   381	        except:
   382	            return None
   383	    
   384	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   385	        """Test Google Forms transport by creating a test form with test data
   386	        
   387	        Args:
   388	            test_data: Data to include in the test form
   389	            cleanup: If True, delete the test form after creation (default: True)
```

### syft_client//platforms/google_personal/gforms.py:389
```python
   384	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   385	        """Test Google Forms transport by creating a test form with test data
   386	        
   387	        Args:
   388	            test_data: Data to include in the test form
   389	            cleanup: If True, delete the test form after creation (default: True)
   390	            
   391	        Returns:
   392	            Dictionary with 'success' (bool) and 'url' (str) if successful
   393	        """
   394	        if not self.forms_service:
```

### syft_client//platforms/google_personal/gforms.py:486
```python
   481	                formId=form_id, body=update
   482	            ).execute()
   483	            
   484	            form_url = f"https://docs.google.com/forms/d/{form_id}/viewform"
   485	            
   486	            # Delete the form if cleanup is requested
   487	            if cleanup and form_id:
   488	                try:
   489	                    # Small delay to ensure form is accessible before deletion
   490	                    import time
   491	                    time.sleep(1)
```

### syft_client//platforms/google_personal/gforms.py:487
```python
   482	            ).execute()
   483	            
   484	            form_url = f"https://docs.google.com/forms/d/{form_id}/viewform"
   485	            
   486	            # Delete the form if cleanup is requested
   487	            if cleanup and form_id:
   488	                try:
   489	                    # Small delay to ensure form is accessible before deletion
   490	                    import time
   491	                    time.sleep(1)
   492	                    
```

### syft_client//platforms/google_personal/gforms.py:513
```python
   508	                except Exception:
   509	                    pass
   510	            
   511	            # Return the form URL
   512	            print(f"✅ Google Forms test successful! Form created with 3 test questions")
   513	            if cleanup:
   514	                print("   Form has been deleted as requested")
   515	            
   516	            return {"success": True, "url": form_url}
   517	            
   518	        except Exception as e:
```

### syft_client//platforms/google_personal/gdrive_files.py:400
```python
   395	            return folder.get('webViewLink')
   396	            
   397	        except:
   398	            return None
   399	    
   400	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   401	        """Test Google Drive transport by creating a test file with test data
   402	        
   403	        Args:
   404	            test_data: Data to include in the test file
   405	            cleanup: If True, delete the test file after creation (default: True)
```

### syft_client//platforms/google_personal/gdrive_files.py:405
```python
   400	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   401	        """Test Google Drive transport by creating a test file with test data
   402	        
   403	        Args:
   404	            test_data: Data to include in the test file
   405	            cleanup: If True, delete the test file after creation (default: True)
   406	            
   407	        Returns:
   408	            Dictionary with 'success' (bool) and 'url' (str) if successful
   409	        """
   410	        if not self.drive_service:
```

### syft_client//platforms/google_personal/gdrive_files.py:454
```python
   449	            ).execute()
   450	            
   451	            file_id = file.get('id')
   452	            web_link = file.get('webViewLink')
   453	            
   454	            # Delete the file if cleanup is requested
   455	            if cleanup and file_id:
   456	                try:
   457	                    # Small delay to ensure file is accessible before deletion
   458	                    import time
   459	                    time.sleep(1)
```

### syft_client//platforms/google_personal/gdrive_files.py:455
```python
   450	            
   451	            file_id = file.get('id')
   452	            web_link = file.get('webViewLink')
   453	            
   454	            # Delete the file if cleanup is requested
   455	            if cleanup and file_id:
   456	                try:
   457	                    # Small delay to ensure file is accessible before deletion
   458	                    import time
   459	                    time.sleep(1)
   460	                    
```

### syft_client//platforms/google_personal/gdrive_files.py:474
```python
   469	                    except Exception:
   470	                        pass
   471	            
   472	            # Return the web view link
   473	            print(f"✅ Google Drive test successful! File created in {self.SYFT_FOLDER if self._folder_id else 'root'}")
   474	            if cleanup:
   475	                print("   File has been deleted as requested")
   476	            
   477	            return {"success": True, "url": web_link}
   478	            
   479	        except Exception as e:
```

### syft_client//platforms/google_personal/gsheets.py:684
```python
   679	            return None
   680	            
   681	        except Exception:
   682	            return None
   683	    
   684	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   685	        """Test Google Sheets transport by creating a test spreadsheet with test data
   686	        
   687	        Args:
   688	            test_data: Data to include in the test spreadsheet
   689	            cleanup: If True, delete the test spreadsheet after creation (default: True)
```

### syft_client//platforms/google_personal/gsheets.py:689
```python
   684	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   685	        """Test Google Sheets transport by creating a test spreadsheet with test data
   686	        
   687	        Args:
   688	            test_data: Data to include in the test spreadsheet
   689	            cleanup: If True, delete the test spreadsheet after creation (default: True)
   690	            
   691	        Returns:
   692	            Dictionary with 'success' (bool) and 'url' (str) if successful
   693	        """
   694	        if not self.sheets_service or not self.drive_service:
```

### syft_client//platforms/google_personal/gsheets.py:769
```python
   764	                body={'requests': requests}
   765	            ).execute()
   766	            
   767	            spreadsheet_url = spreadsheet.get('spreadsheetUrl')
   768	            
   769	            # Delete the spreadsheet if cleanup is requested
   770	            if cleanup and spreadsheet_id:
   771	                try:
   772	                    # Small delay to ensure spreadsheet is accessible before deletion
   773	                    import time
   774	                    time.sleep(1)
```

### syft_client//platforms/google_personal/gsheets.py:770
```python
   765	            ).execute()
   766	            
   767	            spreadsheet_url = spreadsheet.get('spreadsheetUrl')
   768	            
   769	            # Delete the spreadsheet if cleanup is requested
   770	            if cleanup and spreadsheet_id:
   771	                try:
   772	                    # Small delay to ensure spreadsheet is accessible before deletion
   773	                    import time
   774	                    time.sleep(1)
   775	                    
```

### syft_client//platforms/google_personal/gsheets.py:790
```python
   785	                    except Exception:
   786	                        pass
   787	            
   788	            # Return the spreadsheet URL
   789	            print(f"✅ Google Sheets test successful! Spreadsheet created with test data")
   790	            if cleanup:
   791	                print("   Spreadsheet has been deleted as requested")
   792	            
   793	            return {"success": True, "url": spreadsheet_url}
   794	            
   795	        except Exception as e:
```

### syft_client//auth/wallets/local_file.py:225
```python
   220	            return True
   221	            
   222	        except Exception:
   223	            return False
   224	    
   225	    def cleanup_old_tokens(self, service: str, account: str, keep_count: int = 5) -> None:
   226	        """
   227	        Clean up old token backups (if implementing versioning).
   228	        
   229	        This is a utility method for future use if we want to keep
   230	        multiple versions of tokens.
```

### syft_client//sync/watcher/file_watcher.py:103
```python
    98	        # Create observer and start watching
    99	        observer = Observer()
   100	        observer.schedule(handler, str(watch_path), recursive=True)
   101	        observer.start()
   102	        
   103	        # Store observer reference for cleanup
   104	        current_module = sys.modules[__name__]
   105	        current_module.observer = observer
   106	        
   107	        # Register cleanup function
   108	        def cleanup_observer():
```

### syft_client//sync/watcher/file_watcher.py:107
```python
   102	        
   103	        # Store observer reference for cleanup
   104	        current_module = sys.modules[__name__]
   105	        current_module.observer = observer
   106	        
   107	        # Register cleanup function
   108	        def cleanup_observer():
   109	            current_module = sys.modules[__name__]
   110	            if hasattr(current_module, 'observer') and current_module.observer:
   111	                print(f"Stopping file watcher for {email}...", flush=True)
   112	                current_module.observer.stop()
```

### syft_client//sync/watcher/file_watcher.py:108
```python
   103	        # Store observer reference for cleanup
   104	        current_module = sys.modules[__name__]
   105	        current_module.observer = observer
   106	        
   107	        # Register cleanup function
   108	        def cleanup_observer():
   109	            current_module = sys.modules[__name__]
   110	            if hasattr(current_module, 'observer') and current_module.observer:
   111	                print(f"Stopping file watcher for {email}...", flush=True)
   112	                current_module.observer.stop()
   113	                current_module.observer.join()
```

### syft_client//sync/watcher/file_watcher.py:116
```python
   111	                print(f"Stopping file watcher for {email}...", flush=True)
   112	                current_module.observer.stop()
   113	                current_module.observer.join()
   114	                print(f"File watcher stopped.", flush=True)
   115	        
   116	        atexit.register(cleanup_observer)
   117	        
   118	        # Also start inbox polling for bidirectional sync
   119	        def poll_inbox():
   120	            while True:
   121	                try:
```

### syft_client//sync/peers.py:327
```python
   322	                        except Exception as e:
   323	                            failed_removals.append(f"{platform_name}.{attr_name}")
   324	                            if self.client.verbose:
   325	                                print(f"   ❌ Error on {platform_name}.{attr_name}: {e}")
   326	        
   327	        # Summary and cleanup
   328	        if successful_removals:
   329	            if self.client.verbose:
   330	                print(f"\n✅ Peer {email} removed from {len(successful_removals)} transport(s)")
   331	            
   332	            # Remove peer file
```

### syft_client//sync/message.py:187
```python
   182	        archive_path = self.message_root / f"{self.message_id}.tar.gz"
   183	        if archive_path.exists():
   184	            return archive_path.stat().st_size
   185	        return 0
   186	    
   187	    def cleanup(self):
   188	        """Clean up temporary message files"""
   189	        try:
   190	            # Remove message directory
   191	            if self.message_dir.exists():
   192	                shutil.rmtree(self.message_dir)
```

## Functions with 'delete' in name

### syft_client//platforms/google_org/gmail.py:472
```python
   467	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   468	        """Test Gmail transport by sending an email to self with test data
   469	        
   470	        Args:
   471	            test_data: Data to include in the test email
   472	            cleanup: If True, delete the test email after creation (default: True)
   473	            
   474	        Returns:
   475	            Dictionary with 'success' (bool) and 'url' (str) if successful
   476	        """
   477	        if not self.gmail_service:
```

### syft_client//platforms/google_org/gmail.py:521
```python
   516	                                self.gmail_service.users().messages().trash(
   517	                                    userId='me',
   518	                                    id=message_id
   519	                                ).execute()
   520	                            except Exception:
   521	                                # If deletion fails, try to permanently delete
   522	                                try:
   523	                                    self.gmail_service.users().messages().delete(
   524	                                        userId='me',
   525	                                        id=message_id
   526	                                    ).execute()
```

### syft_client//platforms/google_org/gmail.py:523
```python
   518	                                    id=message_id
   519	                                ).execute()
   520	                            except Exception:
   521	                                # If deletion fails, try to permanently delete
   522	                                try:
   523	                                    self.gmail_service.users().messages().delete(
   524	                                        userId='me',
   525	                                        id=message_id
   526	                                    ).execute()
   527	                                except Exception:
   528	                                    pass
```

### syft_client//platforms/google_org/gmail.py:542
```python
   537	                # Use authuser parameter instead of /u/0/ to handle multiple accounts
   538	                url = f"https://mail.google.com/mail/?authuser={urllib.parse.quote(self.email)}#search/{encoded_query}"
   539	                
   540	                print(f"✅ Gmail test successful! Email sent to {self.email}")
   541	                if cleanup:
   542	                    print("   Email has been deleted as requested (re-run test(cleanup=False) to see the email yourself.)")
   543	                
   544	                return {"success": True, "url": url}
   545	            else:
   546	                print("❌ Gmail test failed: Unable to send email")
   547	                return {"success": False, "error": "Failed to send test email"}
```

### syft_client//platforms/google_org/gforms.py:400
```python
   395	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   396	        """Test Google Forms transport by creating a test form with test data
   397	        
   398	        Args:
   399	            test_data: Data to include in the test form
   400	            cleanup: If True, delete the test form after creation (default: True)
   401	            
   402	        Returns:
   403	            Dictionary with 'success' (bool) and 'url' (str) if successful
   404	        """
   405	        if not self.forms_service:
```

### syft_client//platforms/google_org/gforms.py:504
```python
   499	                try:
   500	                    # Small delay to ensure form is accessible before deletion
   501	                    import time
   502	                    time.sleep(1)
   503	                    
   504	                    # Note: Forms API doesn't have a delete method, so we'll need to use Drive API
   505	                    # Forms are stored in Drive, so we can delete them using the Drive API
   506	                    # However, we need to check if Drive service is available
   507	                    if hasattr(self, 'drive_service') and self.drive_service:
   508	                        try:
   509	                            self.drive_service.files().delete(fileId=form_id).execute()
```

### syft_client//platforms/google_org/gforms.py:505
```python
   500	                    # Small delay to ensure form is accessible before deletion
   501	                    import time
   502	                    time.sleep(1)
   503	                    
   504	                    # Note: Forms API doesn't have a delete method, so we'll need to use Drive API
   505	                    # Forms are stored in Drive, so we can delete them using the Drive API
   506	                    # However, we need to check if Drive service is available
   507	                    if hasattr(self, 'drive_service') and self.drive_service:
   508	                        try:
   509	                            self.drive_service.files().delete(fileId=form_id).execute()
   510	                        except Exception:
```

### syft_client//platforms/google_org/gforms.py:509
```python
   504	                    # Note: Forms API doesn't have a delete method, so we'll need to use Drive API
   505	                    # Forms are stored in Drive, so we can delete them using the Drive API
   506	                    # However, we need to check if Drive service is available
   507	                    if hasattr(self, 'drive_service') and self.drive_service:
   508	                        try:
   509	                            self.drive_service.files().delete(fileId=form_id).execute()
   510	                        except Exception:
   511	                            # If deletion fails, try moving to trash
   512	                            try:
   513	                                self.drive_service.files().update(
   514	                                    fileId=form_id,
```

### syft_client//platforms/google_org/gforms.py:525
```python
   520	                    pass
   521	            
   522	            # Return the form URL
   523	            print(f"✅ Google Forms test successful! Form created with 3 test questions")
   524	            if cleanup:
   525	                print("   Form has been deleted as requested")
   526	            
   527	            return {"success": True, "url": form_url}
   528	            
   529	        except Exception as e:
   530	            print(f"❌ Google Forms test failed: {e}")
```

### syft_client//platforms/google_org/gdrive_files.py:405
```python
   400	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   401	        """Test Google Drive transport by creating a test file with test data
   402	        
   403	        Args:
   404	            test_data: Data to include in the test file
   405	            cleanup: If True, delete the test file after creation (default: True)
   406	            
   407	        Returns:
   408	            Dictionary with 'success' (bool) and 'url' (str) if successful
   409	        """
   410	        if not self.drive_service:
```

### syft_client//platforms/google_org/gdrive_files.py:461
```python
   456	                try:
   457	                    # Small delay to ensure file is accessible before deletion
   458	                    import time
   459	                    time.sleep(1)
   460	                    
   461	                    self.drive_service.files().delete(fileId=file_id).execute()
   462	                except Exception:
   463	                    # If deletion fails, try moving to trash
   464	                    try:
   465	                        self.drive_service.files().update(
   466	                            fileId=file_id,
```

### syft_client//platforms/google_org/gdrive_files.py:475
```python
   470	                        pass
   471	            
   472	            # Return the web view link
   473	            print(f"✅ Google Drive test successful! File created in {self.SYFT_FOLDER if self._folder_id else 'root'}")
   474	            if cleanup:
   475	                print("   File has been deleted as requested")
   476	            
   477	            return {"success": True, "url": web_link}
   478	            
   479	        except Exception as e:
   480	            print(f"❌ Google Drive test failed: {e}")
```

### syft_client//platforms/google_org/gdrive_files.py:603
```python
   598	        
   599	        This revokes access to:
   600	        1. The outbox_inbox folder (where you send messages)
   601	        2. The archive folder (where they store processed messages)
   602	        
   603	        Note: This doesn't delete the folders, just removes their access
   604	        
   605	        Args:
   606	            email: Email address of the peer to remove
   607	            verbose: Whether to print status messages
   608	            
```

### syft_client//platforms/google_org/gdrive_files.py:638
```python
   633	                        fields="permissions(id, emailAddress, role)"
   634	                    ).execute()
   635	                    
   636	                    for perm in permissions.get('permissions', []):
   637	                        if perm.get('emailAddress', '').lower() == email.lower():
   638	                            self.drive_service.permissions().delete(
   639	                                fileId=outbox_id,
   640	                                permissionId=perm['id']
   641	                            ).execute()
   642	                            folders_processed += 1
   643	                            if verbose:
```

### syft_client//platforms/google_org/gdrive_files.py:663
```python
   658	                        fields="permissions(id, emailAddress, role)"
   659	                    ).execute()
   660	                    
   661	                    for perm in permissions.get('permissions', []):
   662	                        if perm.get('emailAddress', '').lower() == email.lower():
   663	                            self.drive_service.permissions().delete(
   664	                                fileId=archive_id,
   665	                                permissionId=perm['id']
   666	                            ).execute()
   667	                            folders_processed += 1
   668	                            if verbose:
```

### syft_client//platforms/google_org/gsheets.py:429
```python
   424	                
   425	                # Delete from messages tab (in reverse order to maintain row numbers)
   426	                requests = []
   427	                for row_num in sorted(row_numbers, reverse=True):
   428	                    requests.append({
   429	                        'deleteDimension': {
   430	                            'range': {
   431	                                'sheetId': messages_sheet_id,
   432	                                'dimension': 'ROWS',
   433	                                'startIndex': row_num - 1,  # 0-indexed
   434	                                'endIndex': row_num
```

### syft_client//platforms/google_org/gsheets.py:689
```python
   684	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   685	        """Test Google Sheets transport by creating a test spreadsheet with test data
   686	        
   687	        Args:
   688	            test_data: Data to include in the test spreadsheet
   689	            cleanup: If True, delete the test spreadsheet after creation (default: True)
   690	            
   691	        Returns:
   692	            Dictionary with 'success' (bool) and 'url' (str) if successful
   693	        """
   694	        if not self.sheets_service or not self.drive_service:
```

### syft_client//platforms/google_org/gsheets.py:776
```python
   771	                try:
   772	                    # Small delay to ensure spreadsheet is accessible before deletion
   773	                    import time
   774	                    time.sleep(1)
   775	                    
   776	                    # Use Drive API to delete the spreadsheet
   777	                    self.drive_service.files().delete(fileId=spreadsheet_id).execute()
   778	                except Exception:
   779	                    # If deletion fails, try moving to trash
   780	                    try:
   781	                        self.drive_service.files().update(
```

### syft_client//platforms/google_org/gsheets.py:777
```python
   772	                    # Small delay to ensure spreadsheet is accessible before deletion
   773	                    import time
   774	                    time.sleep(1)
   775	                    
   776	                    # Use Drive API to delete the spreadsheet
   777	                    self.drive_service.files().delete(fileId=spreadsheet_id).execute()
   778	                except Exception:
   779	                    # If deletion fails, try moving to trash
   780	                    try:
   781	                        self.drive_service.files().update(
   782	                            fileId=spreadsheet_id,
```

### syft_client//platforms/google_org/gsheets.py:791
```python
   786	                        pass
   787	            
   788	            # Return the spreadsheet URL
   789	            print(f"✅ Google Sheets test successful! Spreadsheet created with test data")
   790	            if cleanup:
   791	                print("   Spreadsheet has been deleted as requested")
   792	            
   793	            return {"success": True, "url": spreadsheet_url}
   794	            
   795	        except Exception as e:
   796	            print(f"❌ Google Sheets test failed: {e}")
```

### syft_client//platforms/google_org/gsheets.py:857
```python
   852	                        fields='permissions(id,emailAddress)'
   853	                    ).execute()
   854	                    
   855	                    for perm in permissions.get('permissions', []):
   856	                        if perm.get('emailAddress', '').lower() == email.lower():
   857	                            self.drive_service.permissions().delete(
   858	                                fileId=sheet_id,
   859	                                permissionId=perm['id']
   860	                            ).execute()
   861	                            removed = True
   862	                            if verbose:
```

### syft_client//platforms/google_personal/gmail.py:472
```python
   467	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   468	        """Test Gmail transport by sending an email to self with test data
   469	        
   470	        Args:
   471	            test_data: Data to include in the test email
   472	            cleanup: If True, delete the test email after creation (default: True)
   473	            
   474	        Returns:
   475	            Dictionary with 'success' (bool) and 'url' (str) if successful
   476	        """
   477	        if not self.gmail_service:
```

### syft_client//platforms/google_personal/gmail.py:521
```python
   516	                                self.gmail_service.users().messages().trash(
   517	                                    userId='me',
   518	                                    id=message_id
   519	                                ).execute()
   520	                            except Exception:
   521	                                # If deletion fails, try to permanently delete
   522	                                try:
   523	                                    self.gmail_service.users().messages().delete(
   524	                                        userId='me',
   525	                                        id=message_id
   526	                                    ).execute()
```

### syft_client//platforms/google_personal/gmail.py:523
```python
   518	                                    id=message_id
   519	                                ).execute()
   520	                            except Exception:
   521	                                # If deletion fails, try to permanently delete
   522	                                try:
   523	                                    self.gmail_service.users().messages().delete(
   524	                                        userId='me',
   525	                                        id=message_id
   526	                                    ).execute()
   527	                                except Exception:
   528	                                    pass
```

### syft_client//platforms/google_personal/gmail.py:542
```python
   537	                # Use authuser parameter instead of /u/0/ to handle multiple accounts
   538	                url = f"https://mail.google.com/mail/?authuser={urllib.parse.quote(self.email)}#search/{encoded_query}"
   539	                
   540	                print(f"✅ Gmail test successful! Email sent to {self.email}")
   541	                if cleanup:
   542	                    print("   Email has been deleted as requested (re-run test(cleanup=False) to see the email yourself.)")
   543	                
   544	                return {"success": True, "url": url}
   545	            else:
   546	                print("❌ Gmail test failed: Unable to send email")
   547	                return {"success": False, "error": "Failed to send test email"}
```

### syft_client//platforms/google_personal/gforms.py:389
```python
   384	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   385	        """Test Google Forms transport by creating a test form with test data
   386	        
   387	        Args:
   388	            test_data: Data to include in the test form
   389	            cleanup: If True, delete the test form after creation (default: True)
   390	            
   391	        Returns:
   392	            Dictionary with 'success' (bool) and 'url' (str) if successful
   393	        """
   394	        if not self.forms_service:
```

### syft_client//platforms/google_personal/gforms.py:493
```python
   488	                try:
   489	                    # Small delay to ensure form is accessible before deletion
   490	                    import time
   491	                    time.sleep(1)
   492	                    
   493	                    # Note: Forms API doesn't have a delete method, so we'll need to use Drive API
   494	                    # Forms are stored in Drive, so we can delete them using the Drive API
   495	                    # However, we need to check if Drive service is available
   496	                    if hasattr(self, 'drive_service') and self.drive_service:
   497	                        try:
   498	                            self.drive_service.files().delete(fileId=form_id).execute()
```

### syft_client//platforms/google_personal/gforms.py:494
```python
   489	                    # Small delay to ensure form is accessible before deletion
   490	                    import time
   491	                    time.sleep(1)
   492	                    
   493	                    # Note: Forms API doesn't have a delete method, so we'll need to use Drive API
   494	                    # Forms are stored in Drive, so we can delete them using the Drive API
   495	                    # However, we need to check if Drive service is available
   496	                    if hasattr(self, 'drive_service') and self.drive_service:
   497	                        try:
   498	                            self.drive_service.files().delete(fileId=form_id).execute()
   499	                        except Exception:
```

### syft_client//platforms/google_personal/gforms.py:498
```python
   493	                    # Note: Forms API doesn't have a delete method, so we'll need to use Drive API
   494	                    # Forms are stored in Drive, so we can delete them using the Drive API
   495	                    # However, we need to check if Drive service is available
   496	                    if hasattr(self, 'drive_service') and self.drive_service:
   497	                        try:
   498	                            self.drive_service.files().delete(fileId=form_id).execute()
   499	                        except Exception:
   500	                            # If deletion fails, try moving to trash
   501	                            try:
   502	                                self.drive_service.files().update(
   503	                                    fileId=form_id,
```

### syft_client//platforms/google_personal/gforms.py:514
```python
   509	                    pass
   510	            
   511	            # Return the form URL
   512	            print(f"✅ Google Forms test successful! Form created with 3 test questions")
   513	            if cleanup:
   514	                print("   Form has been deleted as requested")
   515	            
   516	            return {"success": True, "url": form_url}
   517	            
   518	        except Exception as e:
   519	            print(f"❌ Google Forms test failed: {e}")
```

### syft_client//platforms/google_personal/gdrive_files.py:405
```python
   400	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   401	        """Test Google Drive transport by creating a test file with test data
   402	        
   403	        Args:
   404	            test_data: Data to include in the test file
   405	            cleanup: If True, delete the test file after creation (default: True)
   406	            
   407	        Returns:
   408	            Dictionary with 'success' (bool) and 'url' (str) if successful
   409	        """
   410	        if not self.drive_service:
```

### syft_client//platforms/google_personal/gdrive_files.py:461
```python
   456	                try:
   457	                    # Small delay to ensure file is accessible before deletion
   458	                    import time
   459	                    time.sleep(1)
   460	                    
   461	                    self.drive_service.files().delete(fileId=file_id).execute()
   462	                except Exception:
   463	                    # If deletion fails, try moving to trash
   464	                    try:
   465	                        self.drive_service.files().update(
   466	                            fileId=file_id,
```

### syft_client//platforms/google_personal/gdrive_files.py:475
```python
   470	                        pass
   471	            
   472	            # Return the web view link
   473	            print(f"✅ Google Drive test successful! File created in {self.SYFT_FOLDER if self._folder_id else 'root'}")
   474	            if cleanup:
   475	                print("   File has been deleted as requested")
   476	            
   477	            return {"success": True, "url": web_link}
   478	            
   479	        except Exception as e:
   480	            print(f"❌ Google Drive test failed: {e}")
```

### syft_client//platforms/google_personal/gdrive_files.py:603
```python
   598	        
   599	        This revokes access to:
   600	        1. The outbox_inbox folder (where you send messages)
   601	        2. The archive folder (where they store processed messages)
   602	        
   603	        Note: This doesn't delete the folders, just removes their access
   604	        
   605	        Args:
   606	            email: Email address of the peer to remove
   607	            verbose: Whether to print status messages
   608	            
```

### syft_client//platforms/google_personal/gdrive_files.py:638
```python
   633	                        fields="permissions(id, emailAddress, role)"
   634	                    ).execute()
   635	                    
   636	                    for perm in permissions.get('permissions', []):
   637	                        if perm.get('emailAddress', '').lower() == email.lower():
   638	                            self.drive_service.permissions().delete(
   639	                                fileId=outbox_id,
   640	                                permissionId=perm['id']
   641	                            ).execute()
   642	                            folders_processed += 1
   643	                            if verbose:
```

### syft_client//platforms/google_personal/gdrive_files.py:663
```python
   658	                        fields="permissions(id, emailAddress, role)"
   659	                    ).execute()
   660	                    
   661	                    for perm in permissions.get('permissions', []):
   662	                        if perm.get('emailAddress', '').lower() == email.lower():
   663	                            self.drive_service.permissions().delete(
   664	                                fileId=archive_id,
   665	                                permissionId=perm['id']
   666	                            ).execute()
   667	                            folders_processed += 1
   668	                            if verbose:
```

### syft_client//platforms/google_personal/gsheets.py:429
```python
   424	                
   425	                # Delete from messages tab (in reverse order to maintain row numbers)
   426	                requests = []
   427	                for row_num in sorted(row_numbers, reverse=True):
   428	                    requests.append({
   429	                        'deleteDimension': {
   430	                            'range': {
   431	                                'sheetId': messages_sheet_id,
   432	                                'dimension': 'ROWS',
   433	                                'startIndex': row_num - 1,  # 0-indexed
   434	                                'endIndex': row_num
```

### syft_client//platforms/google_personal/gsheets.py:689
```python
   684	    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
   685	        """Test Google Sheets transport by creating a test spreadsheet with test data
   686	        
   687	        Args:
   688	            test_data: Data to include in the test spreadsheet
   689	            cleanup: If True, delete the test spreadsheet after creation (default: True)
   690	            
   691	        Returns:
   692	            Dictionary with 'success' (bool) and 'url' (str) if successful
   693	        """
   694	        if not self.sheets_service or not self.drive_service:
```

### syft_client//platforms/google_personal/gsheets.py:776
```python
   771	                try:
   772	                    # Small delay to ensure spreadsheet is accessible before deletion
   773	                    import time
   774	                    time.sleep(1)
   775	                    
   776	                    # Use Drive API to delete the spreadsheet
   777	                    self.drive_service.files().delete(fileId=spreadsheet_id).execute()
   778	                except Exception:
   779	                    # If deletion fails, try moving to trash
   780	                    try:
   781	                        self.drive_service.files().update(
```

### syft_client//platforms/google_personal/gsheets.py:777
```python
   772	                    # Small delay to ensure spreadsheet is accessible before deletion
   773	                    import time
   774	                    time.sleep(1)
   775	                    
   776	                    # Use Drive API to delete the spreadsheet
   777	                    self.drive_service.files().delete(fileId=spreadsheet_id).execute()
   778	                except Exception:
   779	                    # If deletion fails, try moving to trash
   780	                    try:
   781	                        self.drive_service.files().update(
   782	                            fileId=spreadsheet_id,
```

### syft_client//platforms/google_personal/gsheets.py:791
```python
   786	                        pass
   787	            
   788	            # Return the spreadsheet URL
   789	            print(f"✅ Google Sheets test successful! Spreadsheet created with test data")
   790	            if cleanup:
   791	                print("   Spreadsheet has been deleted as requested")
   792	            
   793	            return {"success": True, "url": spreadsheet_url}
   794	            
   795	        except Exception as e:
   796	            print(f"❌ Google Sheets test failed: {e}")
```

### syft_client//platforms/google_personal/gsheets.py:857
```python
   852	                        fields='permissions(id,emailAddress)'
   853	                    ).execute()
   854	                    
   855	                    for perm in permissions.get('permissions', []):
   856	                        if perm.get('emailAddress', '').lower() == email.lower():
   857	                            self.drive_service.permissions().delete(
   858	                                fileId=sheet_id,
   859	                                permissionId=perm['id']
   860	                            ).execute()
   861	                            removed = True
   862	                            if verbose:
```

### syft_client//platforms/transport_base.py:525
```python
   520	                        if verbose:
   521	                            print(f"   🗑️  Processing deletion message")
   522	                        
   523	                        # Process each deletion
   524	                        for item in deletion_manifest.get('items', []):
   525	                            path_to_delete = download_path / item['path']
   526	                            
   527	                            # FIRST: Record in sync history to prevent echo
   528	                            if sync_history:
   529	                                # Pre-record deletion with hash if file still exists
   530	                                file_hash = None
```

### syft_client//platforms/transport_base.py:531
```python
   526	                            
   527	                            # FIRST: Record in sync history to prevent echo
   528	                            if sync_history:
   529	                                # Pre-record deletion with hash if file still exists
   530	                                file_hash = None
   531	                                if path_to_delete.exists() and path_to_delete.is_file():
   532	                                    try:
   533	                                        file_hash = sync_history.compute_file_hash(str(path_to_delete))
   534	                                    except:
   535	                                        pass
   536	                                
```

### syft_client//platforms/transport_base.py:533
```python
   528	                            if sync_history:
   529	                                # Pre-record deletion with hash if file still exists
   530	                                file_hash = None
   531	                                if path_to_delete.exists() and path_to_delete.is_file():
   532	                                    try:
   533	                                        file_hash = sync_history.compute_file_hash(str(path_to_delete))
   534	                                    except:
   535	                                        pass
   536	                                
   537	                                try:
   538	                                    sync_history.record_sync(
```

### syft_client//platforms/transport_base.py:539
```python
   534	                                    except:
   535	                                        pass
   536	                                
   537	                                try:
   538	                                    sync_history.record_sync(
   539	                                        str(path_to_delete),
   540	                                        message_id,
   541	                                        sender_email,
   542	                                        self.transport_name,
   543	                                        'incoming',
   544	                                        0,  # Size is 0 for deletions
```

### syft_client//platforms/transport_base.py:546
```python
   541	                                        sender_email,
   542	                                        self.transport_name,
   543	                                        'incoming',
   544	                                        0,  # Size is 0 for deletions
   545	                                        file_hash=file_hash,
   546	                                        operation='delete'  # Mark this as a deletion
   547	                                    )
   548	                                    if verbose:
   549	                                        print(f"   📝 Recorded incoming deletion for {path_to_delete}")
   550	                                except Exception as e:
   551	                                    # This is ok - file may already be gone
```

### syft_client//platforms/transport_base.py:549
```python
   544	                                        0,  # Size is 0 for deletions
   545	                                        file_hash=file_hash,
   546	                                        operation='delete'  # Mark this as a deletion
   547	                                    )
   548	                                    if verbose:
   549	                                        print(f"   📝 Recorded incoming deletion for {path_to_delete}")
   550	                                except Exception as e:
   551	                                    # This is ok - file may already be gone
   552	                                    if verbose:
   553	                                        print(f"   ℹ️  Could not record deletion (file may already be gone): {e}")
   554	                            
```

### syft_client//platforms/transport_base.py:556
```python
   551	                                    # This is ok - file may already be gone
   552	                                    if verbose:
   553	                                        print(f"   ℹ️  Could not record deletion (file may already be gone): {e}")
   554	                            
   555	                            # THEN: Delete the file/directory
   556	                            if path_to_delete.exists():
   557	                                if path_to_delete.is_dir():
   558	                                    shutil.rmtree(path_to_delete)
   559	                                    if verbose:
   560	                                        print(f"   🗑️  Deleted directory: {path_to_delete.name}")
   561	                                else:
```

### syft_client//platforms/transport_base.py:557
```python
   552	                                    if verbose:
   553	                                        print(f"   ℹ️  Could not record deletion (file may already be gone): {e}")
   554	                            
   555	                            # THEN: Delete the file/directory
   556	                            if path_to_delete.exists():
   557	                                if path_to_delete.is_dir():
   558	                                    shutil.rmtree(path_to_delete)
   559	                                    if verbose:
   560	                                        print(f"   🗑️  Deleted directory: {path_to_delete.name}")
   561	                                else:
   562	                                    path_to_delete.unlink()
```

### syft_client//platforms/transport_base.py:558
```python
   553	                                        print(f"   ℹ️  Could not record deletion (file may already be gone): {e}")
   554	                            
   555	                            # THEN: Delete the file/directory
   556	                            if path_to_delete.exists():
   557	                                if path_to_delete.is_dir():
   558	                                    shutil.rmtree(path_to_delete)
   559	                                    if verbose:
   560	                                        print(f"   🗑️  Deleted directory: {path_to_delete.name}")
   561	                                else:
   562	                                    path_to_delete.unlink()
   563	                                    if verbose:
```

### syft_client//platforms/transport_base.py:560
```python
   555	                            # THEN: Delete the file/directory
   556	                            if path_to_delete.exists():
   557	                                if path_to_delete.is_dir():
   558	                                    shutil.rmtree(path_to_delete)
   559	                                    if verbose:
   560	                                        print(f"   🗑️  Deleted directory: {path_to_delete.name}")
   561	                                else:
   562	                                    path_to_delete.unlink()
   563	                                    if verbose:
   564	                                        print(f"   🗑️  Deleted file: {path_to_delete.name}")
   565	                            else:
```

### syft_client//platforms/transport_base.py:562
```python
   557	                                if path_to_delete.is_dir():
   558	                                    shutil.rmtree(path_to_delete)
   559	                                    if verbose:
   560	                                        print(f"   🗑️  Deleted directory: {path_to_delete.name}")
   561	                                else:
   562	                                    path_to_delete.unlink()
   563	                                    if verbose:
   564	                                        print(f"   🗑️  Deleted file: {path_to_delete.name}")
   565	                            else:
   566	                                if verbose:
   567	                                    print(f"   ℹ️  Already deleted: {path_to_delete.name}")
```

### syft_client//platforms/transport_base.py:564
```python
   559	                                    if verbose:
   560	                                        print(f"   🗑️  Deleted directory: {path_to_delete.name}")
   561	                                else:
   562	                                    path_to_delete.unlink()
   563	                                    if verbose:
   564	                                        print(f"   🗑️  Deleted file: {path_to_delete.name}")
   565	                            else:
   566	                                if verbose:
   567	                                    print(f"   ℹ️  Already deleted: {path_to_delete.name}")
   568	                        
   569	                        # Add to results
```

### syft_client//platforms/transport_base.py:567
```python
   562	                                    path_to_delete.unlink()
   563	                                    if verbose:
   564	                                        print(f"   🗑️  Deleted file: {path_to_delete.name}")
   565	                            else:
   566	                                if verbose:
   567	                                    print(f"   ℹ️  Already deleted: {path_to_delete.name}")
   568	                        
   569	                        # Add to results
   570	                        downloaded_messages.append({
   571	                            'id': message_id,
   572	                            'timestamp': deletion_manifest.get('timestamp', ''),
```

### syft_client//platforms/transport_base.py:575
```python
   570	                        downloaded_messages.append({
   571	                            'id': message_id,
   572	                            'timestamp': deletion_manifest.get('timestamp', ''),
   573	                            'size': 0,
   574	                            'metadata': metadata,
   575	                            'operation': 'delete',
   576	                            'deleted_items': deletion_manifest.get('items', [])
   577	                        })
   578	                        
   579	                        # Mark for archiving
   580	                        messages_to_archive.append(message_info)
```

### syft_client//platforms/transport_base.py:576
```python
   571	                            'id': message_id,
   572	                            'timestamp': deletion_manifest.get('timestamp', ''),
   573	                            'size': 0,
   574	                            'metadata': metadata,
   575	                            'operation': 'delete',
   576	                            'deleted_items': deletion_manifest.get('items', [])
   577	                        })
   578	                        
   579	                        # Mark for archiving
   580	                        messages_to_archive.append(message_info)
   581	                    
```

### syft_client//auth/wallets/base.py:44
```python
    39	            Token data if found, None otherwise
    40	        """
    41	        raise NotImplementedError
    42	    
    43	    @abstractmethod
    44	    def delete_token(self, service: str, account: str) -> bool:
    45	        """
    46	        Delete a token from the wallet.
    47	        
    48	        Args:
    49	            service: Service name
```

### syft_client//auth/wallets/local_file.py:150
```python
   145	            
   146	        except Exception as e:
   147	            print(f"Failed to update token metadata: {e}")
   148	            return False
   149	    
   150	    def delete_token(self, service: str, account: str) -> bool:
   151	        """Delete a token file"""
   152	        try:
   153	            token_path = self._get_token_path(service, account)
   154	            
   155	            if token_path.exists():
```

### syft_client//auth/wallets/local_file.py:170
```python
   165	                    account_dir.rmdir()
   166	            
   167	            return True
   168	            
   169	        except Exception as e:
   170	            print(f"Failed to delete token: {e}")
   171	            return False
   172	    
   173	    def list_tokens(self, service: Optional[str] = None) -> List[str]:
   174	        """List all stored tokens"""
   175	        tokens = []
```

### syft_client//syft_client.py:434
```python
   429	    def send_deletion_to_peers(self, path: str) -> Dict[str, bool]:
   430	        """
   431	        Send deletion message to all peers
   432	        
   433	        Args:
   434	            path: Path to the deleted file (supports syft:// URLs)
   435	            
   436	        Returns:
   437	            Dict mapping peer emails to success status
   438	        """
   439	        return self.sync.send_deletion_to_peers(path)
```

### syft_client//syft_client.py:446
```python
   441	    def send_deletion(self, path: str, recipient: str) -> bool:
   442	        """
   443	        Send deletion message to specific recipient
   444	        
   445	        Args:
   446	            path: Path to the deleted file (supports syft:// URLs)
   447	            recipient: Email address of recipient
   448	            
   449	        Returns:
   450	            True if successful
   451	        """
```

### syft_client//syft_client.py:1105
```python
  1100	        if not wallet_dir.exists():
  1101	            print("No wallet directory found at ~/.syft")
  1102	            return True
  1103	        
  1104	        if confirm:
  1105	            # Show what will be deleted
  1106	            print(f"\n⚠️  WARNING: This will delete all stored credentials!")
  1107	            print(f"\nWallet directory: {wallet_dir}")
  1108	            
  1109	            # Count files that will be deleted
  1110	            file_count = sum(1 for _ in wallet_dir.rglob('*') if _.is_file())
```

### syft_client//syft_client.py:1106
```python
  1101	            print("No wallet directory found at ~/.syft")
  1102	            return True
  1103	        
  1104	        if confirm:
  1105	            # Show what will be deleted
  1106	            print(f"\n⚠️  WARNING: This will delete all stored credentials!")
  1107	            print(f"\nWallet directory: {wallet_dir}")
  1108	            
  1109	            # Count files that will be deleted
  1110	            file_count = sum(1 for _ in wallet_dir.rglob('*') if _.is_file())
  1111	            if file_count > 0:
```

### syft_client//syft_client.py:1109
```python
  1104	        if confirm:
  1105	            # Show what will be deleted
  1106	            print(f"\n⚠️  WARNING: This will delete all stored credentials!")
  1107	            print(f"\nWallet directory: {wallet_dir}")
  1108	            
  1109	            # Count files that will be deleted
  1110	            file_count = sum(1 for _ in wallet_dir.rglob('*') if _.is_file())
  1111	            if file_count > 0:
  1112	                print(f"Files to be deleted: {file_count}")
  1113	                
  1114	                # Show some example files
```

### syft_client//syft_client.py:1112
```python
  1107	            print(f"\nWallet directory: {wallet_dir}")
  1108	            
  1109	            # Count files that will be deleted
  1110	            file_count = sum(1 for _ in wallet_dir.rglob('*') if _.is_file())
  1111	            if file_count > 0:
  1112	                print(f"Files to be deleted: {file_count}")
  1113	                
  1114	                # Show some example files
  1115	                example_files = list(wallet_dir.rglob('*'))[:5]
  1116	                for f in example_files:
  1117	                    if f.is_file():
```

### syft_client//syft_client.py:1122
```python
  1117	                    if f.is_file():
  1118	                        print(f"  - {f.relative_to(wallet_dir)}")
  1119	                if file_count > 5:
  1120	                    print(f"  ... and {file_count - 5} more files")
  1121	            
  1122	            response = input("\nAre you sure you want to delete all wallet data? (yes/no): ")
  1123	            if response.lower() != 'yes':
  1124	                print("Wallet reset cancelled.")
  1125	                return False
  1126	        
  1127	        try:
```

### syft_client//syft_client.py:1130
```python
  1125	                return False
  1126	        
  1127	        try:
  1128	            # Delete the entire wallet directory
  1129	            shutil.rmtree(wallet_dir)
  1130	            print(f"\n✓ Wallet directory deleted: {wallet_dir}")
  1131	            print("All stored credentials have been removed.")
  1132	            print("\nYou will need to authenticate again on your next login.")
  1133	            return True
  1134	        except Exception as e:
  1135	            print(f"\n✗ Error deleting wallet: {e}")
```

### syft_client//sync/sender.py:243
```python
   238	    def prepare_deletion_message(self, path: str, recipient: str, temp_dir: str) -> Optional[Tuple[str, str, int]]:
   239	        """
   240	        Prepare a SyftMessage archive for deletion
   241	        
   242	        Args:
   243	            path: Path to the deleted file (supports syft:// URLs)
   244	            recipient: Email address of the recipient
   245	            temp_dir: Temporary directory to create the message in
   246	            
   247	        Returns:
   248	            Tuple of (message_id, archive_path, archive_size) if successful, None otherwise
```

### syft_client//sync/sender.py:257
```python
   252	        
   253	        # Get relative path from SyftBox root
   254	        relative_path = self.paths.get_relative_syftbox_path(resolved_path)
   255	        if not relative_path:
   256	            # If file is not in SyftBox, use the full path as relative
   257	            # This can happen if file was already deleted
   258	            relative_path = resolved_path
   259	        
   260	        try:
   261	            # Create SyftMessage
   262	            message = SyftMessage.create(
```

### syft_client//sync/sender.py:270
```python
   265	                message_root=Path(temp_dir)
   266	            )
   267	            
   268	            # Create deletion manifest
   269	            deletion_manifest = {
   270	                "operation": "delete",
   271	                "items": [{
   272	                    "path": relative_path,
   273	                    "timestamp": time.time(),
   274	                    "deleted_by": self.client.email
   275	                }]
```

### syft_client//sync/sender.py:274
```python
   269	            deletion_manifest = {
   270	                "operation": "delete",
   271	                "items": [{
   272	                    "path": relative_path,
   273	                    "timestamp": time.time(),
   274	                    "deleted_by": self.client.email
   275	                }]
   276	            }
   277	            
   278	            # Write deletion manifest to message directory
   279	            manifest_path = Path(temp_dir) / message.message_id / "deletion_manifest.json"
```

### syft_client//sync/sender.py:305
```python
   300	    def send_deletion(self, path: str, recipient: str) -> bool:
   301	        """
   302	        Send a deletion message for a file to a specific recipient
   303	        
   304	        Args:
   305	            path: Path to the deleted file (supports syft:// URLs)
   306	            recipient: Email address of the recipient
   307	            
   308	        Returns:
   309	            True if successful, False otherwise
   310	        """
```

### syft_client//sync/sender.py:335
```python
   330	    def send_deletion_to_peers(self, path: str) -> Dict[str, bool]:
   331	        """
   332	        Send deletion message to all peers
   333	        
   334	        Args:
   335	            path: Path to the deleted file (supports syft:// URLs)
   336	            
   337	        Returns:
   338	            Dict mapping peer emails to success status
   339	        """
   340	        # Get list of peers
```

### syft_client//sync/transport_capabilities.py:69
```python
    64	        max_file_size=25 * 1024 * 1024,  # 25MB attachment limit
    65	        typical_latency_ms=2000,
    66	        min_latency_ms=500,
    67	        max_latency_ms=10000,
    68	        supports_batch=True,  # Multiple attachments
    69	        supports_deletion=False,  # Email can't delete files
    70	        requires_auth=["https://www.googleapis.com/auth/gmail.send"],
    71	        platform_required="google"
    72	    ),
    73	    
    74	    "dropbox": TransportCapabilities(
```

### syft_client//sync/watcher/event_handler.py:26
```python
    21	    
    22	    def on_modified(self, event):
    23	        if not event.is_directory:
    24	            self._handle_file_event(event, "modified")
    25	    
    26	    def on_deleted(self, event):
    27	        if not event.is_directory:
    28	            self._handle_file_event(event, "deleted")
    29	    
    30	    def _handle_file_event(self, event, event_type):
    31	        """Process a file system event"""
```

### syft_client//sync/watcher/event_handler.py:28
```python
    23	        if not event.is_directory:
    24	            self._handle_file_event(event, "modified")
    25	    
    26	    def on_deleted(self, event):
    27	        if not event.is_directory:
    28	            self._handle_file_event(event, "deleted")
    29	    
    30	    def _handle_file_event(self, event, event_type):
    31	        """Process a file system event"""
    32	        # Skip hidden files (starting with .)
    33	        filename = os.path.basename(event.src_path)
```

### syft_client//sync/watcher/event_handler.py:53
```python
    48	        # Skip if in .syft_sync directory
    49	        if '.syft_sync' in event.src_path:
    50	            return
    51	        
    52	        # For deletions, we can't check file content (it's gone)
    53	        if event_type != "deleted":
    54	            # Check if this file change is from a recent sync to prevent echo
    55	            threshold = int(os.environ.get('SYFT_SYNC_ECHO_THRESHOLD', '60'))
    56	            
    57	            # Debug logging
    58	            if self.verbose:
```

### syft_client//sync/watcher/event_handler.py:74
```python
    69	                        print(f"✋ Skipping echo: {filename} (was recently received)", flush=True)
    70	                    return
    71	        
    72	        # Send the file or deletion to all peers
    73	        try:
    74	            if event_type == "deleted":
    75	                if self.verbose:
    76	                    print(f"Sending deletion: {filename}", flush=True)
    77	                
    78	                # Check if this deletion was recently synced from a peer (don't echo back)
    79	                threshold = int(os.environ.get('SYFT_SYNC_ECHO_THRESHOLD', '60'))
```

### syft_client//sync/watcher/event_handler.py:81
```python
    76	                    print(f"Sending deletion: {filename}", flush=True)
    77	                
    78	                # Check if this deletion was recently synced from a peer (don't echo back)
    79	                threshold = int(os.environ.get('SYFT_SYNC_ECHO_THRESHOLD', '60'))
    80	                if threshold > 0:
    81	                    # Check if file exists in sync history (it won't exist if deleted, but sync history might have it)
    82	                    # We need to check if this was a recent incoming deletion
    83	                    is_recent_deletion = False
    84	                    try:
    85	                        # Try to check with the file that might not exist
    86	                        # This will use the path-only lookup in sync history
```

### syft_client//sync/watcher/event_handler.py:91
```python
    86	                        # This will use the path-only lookup in sync history
    87	                        is_recent_deletion = self.sync_history.is_recent_sync(
    88	                            event.src_path, 
    89	                            direction='incoming', 
    90	                            threshold_seconds=threshold,
    91	                            operation='delete'
    92	                        )
    93	                    except:
    94	                        pass
    95	                    
    96	                    if is_recent_deletion:
```

### syft_client//sync/watcher/event_handler.py:98
```python
    93	                    except:
    94	                        pass
    95	                    
    96	                    if is_recent_deletion:
    97	                        if self.verbose:
    98	                            print(f"✋ Skipping deletion echo: {filename} (was recently deleted by peer)", flush=True)
    99	                        return
   100	                
   101	                
   102	                # Send deletion to all peers
   103	                results = self.client.send_deletion_to_peers(event.src_path)
```

### syft_client//sync/watcher/event_handler.py:116
```python
   111	                            message_id,
   112	                            peer_email,
   113	                            "auto",  # Transport will be selected automatically
   114	                            "outgoing",
   115	                            0,  # Size is 0 for deletions
   116	                            operation='delete'  # Mark as deletion
   117	                        )
   118	                
   119	                # Report results
   120	                successful = sum(1 for success in results.values() if success)
   121	                total = len(results)
```

### syft_client//sync/watcher/sync_history.py:62
```python
    57	        Args:
    58	            file_path: Path to the file to check
    59	            direction: Optional direction to check ('incoming' or 'outgoing'). 
    60	                      If None, checks any recent sync regardless of direction.
    61	            threshold_seconds: Time window to consider as "recent"
    62	            operation: Optional operation type to check ('sync' or 'delete').
    63	                      If None, checks any operation type.
    64	            
    65	        Returns:
    66	            True if file was recently synced in the specified direction
    67	        """
```

### syft_client//sync/watcher/sync_history.py:73
```python
    68	        try:
    69	            print(f"   🔍 Checking sync history for: {file_path}, direction={direction}, operation={operation}", flush=True)
    70	            
    71	            # For deletion checks, we need to look through ALL metadata files
    72	            # since we can't compute the hash of a non-existent file
    73	            if operation == 'delete' and not os.path.exists(file_path):
    74	                print(f"      File doesn't exist, checking all metadata for deletion history", flush=True)
    75	                
    76	                # Get relative path for comparison
    77	                try:
    78	                    relative_path = os.path.relpath(file_path, self.syftbox_dir)
```

### syft_client//sync/watcher/sync_history.py:96
```python
    91	                    with open(metadata_path, "r") as f:
    92	                        metadata = json.load(f)
    93	                    
    94	                    # Check if this metadata is for our file
    95	                    if metadata.get("file_path") == file_path or metadata.get("file_path") == relative_path:
    96	                        print(f"      Found metadata for deleted file", flush=True)
    97	                        
    98	                        # Check sync history
    99	                        sync_history = metadata.get("sync_history", [])
   100	                        current_time = time.time()
   101	                        
```

### syft_client//sync/watcher/sync_history.py:105
```python
   100	                        current_time = time.time()
   101	                        
   102	                        for sync in reversed(sync_history):
   103	                            if direction and sync.get("direction") != direction:
   104	                                continue
   105	                            if sync.get("operation", "sync") != "delete":
   106	                                continue
   107	                            
   108	                            sync_time = sync.get("timestamp", 0)
   109	                            age = current_time - sync_time
   110	                            print(f"      Found {direction} delete, age: {age:.1f}s", flush=True)
```

### syft_client//sync/watcher/sync_history.py:110
```python
   105	                            if sync.get("operation", "sync") != "delete":
   106	                                continue
   107	                            
   108	                            sync_time = sync.get("timestamp", 0)
   109	                            age = current_time - sync_time
   110	                            print(f"      Found {direction} delete, age: {age:.1f}s", flush=True)
   111	                            if age < threshold_seconds:
   112	                                return True
   113	                        
   114	                        # Found the file but no recent deletion
   115	                        return False
```

### syft_client//sync/watcher/sync_history.py:118
```python
   113	                        
   114	                        # Found the file but no recent deletion
   115	                        return False
   116	                
   117	                # File not found in any metadata
   118	                print(f"      No metadata found for deleted file", flush=True)
   119	                return False
   120	            
   121	            # For non-deletion or existing files, use normal hash lookup
   122	            if not os.path.exists(file_path):
   123	                print(f"      File doesn't exist and not checking for deletion", flush=True)
```

### syft_client//sync/watcher/sync_history.py:196
```python
   191	            peer_email: Email of the peer
   192	            transport: Transport used
   193	            direction: 'incoming' or 'outgoing'
   194	            file_size: Size of the file
   195	            file_hash: Optional pre-computed hash (useful when recording before file exists)
   196	            operation: Type of operation ('sync' or 'delete')
   197	        """
   198	        # Always print for debugging
   199	        import sys
   200	        print(f"📝 Recording sync: {file_path} direction={direction} peer={peer_email}", file=sys.stderr, flush=True)
   201	        
```

### syft_client//sync/peers.py:387
```python
   382	                        files_cleared += 1
   383	                        if verbose:
   384	                            print(f"   ✓ Deleted peer file: {file_path.name}")
   385	                    except Exception as e:
   386	                        if verbose:
   387	                            print(f"   ⚠️  Could not delete {file_path.name}: {e}")
   388	        except Exception as e:
   389	            if verbose:
   390	                print(f"   ⚠️  Error clearing peer files: {e}")
   391	        
   392	        # Clear discovery cache
```

### syft_client//sync/peers.py:404
```python
   399	                        files_cleared += 1
   400	                        if verbose:
   401	                            print(f"   ✓ Deleted discovery cache: {file_path.name}")
   402	                    except Exception as e:
   403	                        if verbose:
   404	                            print(f"   ⚠️  Could not delete {file_path.name}: {e}")
   405	        except Exception as e:
   406	            if verbose:
   407	                print(f"   ⚠️  Error clearing discovery cache: {e}")
   408	        
   409	        if verbose and files_cleared > 0:
```

### syft_client//sync/message.py:114
```python
   109	    def add_deletion_marker(self, path: str) -> bool:
   110	        """
   111	        Add a deletion marker for a file/folder
   112	        
   113	        Args:
   114	            path: Path that was deleted (relative to SyftBox)
   115	            
   116	        Returns:
   117	            True if successful
   118	        """
   119	        self.metadata['deletion'] = True
```

### syft_client//sync/message.py:120
```python
   115	            
   116	        Returns:
   117	            True if successful
   118	        """
   119	        self.metadata['deletion'] = True
   120	        self.metadata['deleted_path'] = path
   121	        self.metadata['deletion_time'] = datetime.now().isoformat()
   122	        return True
   123	    
   124	    def write_metadata(self) -> bool:
   125	        """
```

