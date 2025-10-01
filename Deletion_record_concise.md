# Concise File Deletion Operations in syft-client


## syft_client//auth/wallets/local_file.py

**Line 156** (unlink):
```python
token_path.unlink()
```

**Line 218** (unlink):
```python
test_file.unlink()
```


## syft_client//platforms/transport_base.py

**Line 455** (unlink):
```python
temp_file.unlink()
```

**Line 558** (rmtree):
```python
shutil.rmtree(path_to_delete)
```

**Line 562** (unlink):
```python
path_to_delete.unlink()
```

**Line 663** (atomic_replace):
```python
temp_dest.replace(dest)
```

**Line 684** (unlink):
```python
temp_file.unlink()
```

**Line 687** (rmtree):
```python
shutil.rmtree(extracted_dir)
```

**Line 784** (atomic_replace):
```python
temp_dest.replace(d)
```


## syft_client//syft_client.py

**Line 1129** (rmtree):
```python
shutil.rmtree(wallet_dir)
```


## syft_client//sync/message.py

**Line 102** (rmtree):
```python
shutil.rmtree(dest)
```

**Line 192** (rmtree):
```python
shutil.rmtree(self.message_dir)
```

**Line 197** (unlink):
```python
archive_path.unlink()
```


## syft_client//sync/peers.py

**Line 338** (unlink):
```python
file_path.unlink()
```

**Line 381** (unlink):
```python
file_path.unlink()
```

**Line 398** (unlink):
```python
file_path.unlink()
```


## syft_client//sync/receiver/message_processor.py

**Line 119** (rmtree):
```python
shutil.rmtree(dest)
```

**Line 123** (unlink):
```python
dest.unlink()
```


## syft_client//sync/sender.py

**Line 161** (rmtree):
```python
shutil.rmtree(temp_dir)
```

**Line 328** (rmtree):
```python
shutil.rmtree(temp_dir)
```

