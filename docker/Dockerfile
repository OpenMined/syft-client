FROM python:3.12-slim

RUN pip install uv

# Install syft-client from PyPI and attestation server deps
COPY docker/requirements.txt /tmp/requirements.txt
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install syft-client && \
    uv pip install -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt
ENV PATH="/opt/venv/bin:$PATH"

# Copy attestation server code
WORKDIR /app
COPY docker/attestation_server.py .
COPY docker/entrypoint.sh .
RUN chmod +x entrypoint.sh

# Confidential Spaces expects port 8080
# Note: runs as root because the TEE attestation socket
# at /run/container_launcher/teeserver.sock is root-owned.
# In a TEE, security comes from hardware isolation, not container user permissions.
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
