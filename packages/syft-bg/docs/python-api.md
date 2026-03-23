# Python Quickstart

The `syft_bg` package exposes a Python API for use in Jupyter notebooks, Colab, or scripts.

## Quickstart

Initialize syft-bg services programmatically. Creates the configuration file needed before starting services.
With credentials at `~/.syft-creds/config.yaml`. Get Credentials via [auth_docs](../../../docs/auth.md)

```python
import syft_bg
syft_bg.init(email="user@example.com", start=True)
```
This starts syft_bg in the background and also registers it with systemd

```python
syft_bg.status
```
prints
- what is the syftbox
- what is the user
- which peers are approved
- which auto approval jobs are there (filepaths)
- is email setup


```python
import syft_bg
result = syft_bg.auto_approve(contents=["main.py"], filenames=["params.json"], peers=["charlie@org.com"])
```
