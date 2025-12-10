# Logging Integration Guide

This document explains how to integrate `syft-notify` logs with centralized logging systems.

## Log File Locations

```
~/.syft-creds/
├── syft-notify.log           # Main daemon output
├── syft-notify.error.log     # Error output (stderr)
├── syft-notify.log.1         # Rotated log (1-7 kept)
└── notification_state.json   # State tracking (not for logging)
```

## Log Format

Logs use standard Python logging format:

```
2025-12-08 12:00:00 - root - INFO - 🔔 Starting notification daemon...
2025-12-08 12:01:00 - root - INFO - 📧 Sending new job notification to DO...
2025-12-08 12:01:05 - root - INFO -    ✅ Sent and marked as notified
```

## Integration Methods

### 1. Filebeat (Elastic Stack)

Forward logs to Elasticsearch via Filebeat.

**Install Filebeat:**

```bash
curl -L -O https://artifacts.elastic.co/downloads/beats/filebeat/filebeat-8.11.0-linux-x86_64.tar.gz
tar xzvf filebeat-8.11.0-linux-x86_64.tar.gz
cd filebeat-8.11.0-linux-x86_64/
```

**Configure `filebeat.yml`:**

```yaml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /home/*//.syft-creds/syft-notify.log
      - /home/*//.syft-creds/syft-notify.error.log
    fields:
      service: syft-notify
      environment: production
    multiline:
      pattern: '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
      negate: true
      match: after

output.elasticsearch:
  hosts: ['localhost:9200']
  index: 'syft-notify-%{+yyyy.MM.dd}'

setup.kibana:
  host: 'localhost:5601'
```

**Start Filebeat:**

```bash
./filebeat -e -c filebeat.yml
```

### 2. Fluentd

Collect and forward logs to various destinations.

**Install Fluentd:**

```bash
curl -L https://toolbelt.treasuredata.com/sh/install-ubuntu-jammy-fluent-package5-lts.sh | sh
```

**Configure `/etc/fluent/fluent.conf`:**

```xml
<source>
  @type tail
  path /home/*/.syft-creds/syft-notify.log
  pos_file /var/log/fluent/syft-notify.log.pos
  tag syft.notify
  <parse>
    @type regexp
    expression /^(?<time>[^ ]+ [^ ]+) - (?<logger>[^ ]+) - (?<level>[^ ]+) - (?<message>.*)$/
    time_format %Y-%m-%d %H:%M:%S
  </parse>
</source>

<match syft.notify>
  @type forward
  <server>
    host log-server.example.com
    port 24224
  </server>
</match>
```

**Start Fluentd:**

```bash
sudo systemctl start fluentd
sudo systemctl enable fluentd
```

### 3. Syslog

Forward logs to a syslog server (rsyslog/syslog-ng).

**Configure rsyslog (`/etc/rsyslog.d/syft-notify.conf`):**

```
$ModLoad imfile
$InputFilePollInterval 10

# Monitor syft-notify logs
$InputFileName /home/*/.syft-creds/syft-notify.log
$InputFileTag syft-notify:
$InputFileStateFile syft-notify-state
$InputFileSeverity info
$InputRunFileMonitor

# Forward to remote syslog
*.* @@remote-syslog-server:514
```

**Restart rsyslog:**

```bash
sudo systemctl restart rsyslog
```

### 4. Promtail (Grafana Loki)

Send logs to Grafana Loki for visualization.

**Install Promtail:**

```bash
curl -O -L "https://github.com/grafana/loki/releases/download/v2.9.0/promtail-linux-amd64.zip"
unzip promtail-linux-amd64.zip
chmod +x promtail-linux-amd64
```

**Configure `promtail-config.yaml`:**

```yaml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://localhost:3100/loki/api/v1/push

scrape_configs:
  - job_name: syft-notify
    static_configs:
      - targets:
          - localhost
        labels:
          job: syft-notify
          __path__: /home/*/.syft-creds/syft-notify*.log
```

**Start Promtail:**

```bash
./promtail-linux-amd64 -config.file=promtail-config.yaml
```

### 5. CloudWatch Logs (AWS)

Send logs to AWS CloudWatch.

**Install CloudWatch agent:**

```bash
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb
```

**Configure `/opt/aws/amazon-cloudwatch-agent/etc/config.json`:**

```json
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/home/*/.syft-creds/syft-notify.log",
            "log_group_name": "/syftbox/notify",
            "log_stream_name": "{instance_id}-notify",
            "timezone": "UTC"
          }
        ]
      }
    }
  }
}
```

**Start agent:**

```bash
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -s \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/config.json
```

### 6. Google Cloud Logging

Forward logs to Google Cloud Logging.

**Install Ops Agent:**

```bash
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install
```

**Configure `/etc/google-cloud-ops-agent/config.yaml`:**

```yaml
logging:
  receivers:
    syft_notify:
      type: files
      include_paths:
        - /home/*/.syft-creds/syft-notify.log
  service:
    pipelines:
      default_pipeline:
        receivers: [syft_notify]
```

**Restart agent:**

```bash
sudo systemctl restart google-cloud-ops-agent
```

## Log Parsing

### Python Regex Pattern

```python
import re

log_pattern = r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (?P<logger>\S+) - (?P<level>\S+) - (?P<message>.*)$'

with open('~/.syft-creds/syft-notify.log') as f:
    for line in f:
        match = re.match(log_pattern, line)
        if match:
            print(match.groupdict())
```

### Grok Pattern (for Logstash)

```
%{TIMESTAMP_ISO8601:timestamp} - %{NOTSPACE:logger} - %{LOGLEVEL:level} - %{GREEDYDATA:message}
```

## Structured Logging (Future Enhancement)

For better integration with log aggregators, you can modify the daemon to output JSON logs:

```python
# In daemon_manager.py, change the formatter:

formatter = logging.Formatter(
    '{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S",
)
```

This outputs:

```json
{
  "timestamp": "2025-12-08T12:00:00",
  "logger": "root",
  "level": "INFO",
  "message": "🔔 Starting daemon..."
}
```

## Alerting

### Example: Alert on Errors

**With Elasticsearch/Kibana:**

1. Create a watcher:
   ```json
   {
     "trigger": {
       "schedule": {
         "interval": "5m"
       }
     },
     "input": {
       "search": {
         "request": {
           "indices": ["syft-notify-*"],
           "body": {
             "query": {
               "bool": {
                 "must": [
                   {
                     "match": {
                       "level": "ERROR"
                     }
                   },
                   {
                     "range": {
                       "timestamp": {
                         "gte": "now-5m"
                       }
                     }
                   }
                 ]
               }
             }
           }
         }
       }
     },
     "actions": {
       "send_email": {
         "email": {
           "to": "ops@example.com",
           "subject": "syft-notify errors detected",
           "body": "{{ctx.payload.hits.total.value}} errors in the last 5 minutes"
         }
       }
     }
   }
   ```

**With simple grep + cron:**

```bash
#!/bin/bash
# alert_on_errors.sh

LOG_FILE="$HOME/.syft-creds/syft-notify.log"
ERROR_COUNT=$(tail -n 1000 "$LOG_FILE" | grep -c "ERROR")

if [ "$ERROR_COUNT" -gt 0 ]; then
    echo "Found $ERROR_COUNT errors in syft-notify logs" | mail -s "syft-notify Alert" ops@example.com
fi
```

Add to crontab:

```bash
*/5 * * * * /path/to/alert_on_errors.sh
```

## Log Retention

### Built-in Rotation

The daemon automatically rotates logs:

- Max file size: 10 MB
- Keep 7 old files
- Total storage: ~80 MB

### External Rotation with logrotate

```bash
# /etc/logrotate.d/syft-notify

/home/*/.syft-creds/syft-notify*.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
    create 0644 $USER $USER
    postrotate
        syft-notify restart > /dev/null 2>&1 || true
    endscript
}
```

## Monitoring Metrics

Extract metrics from logs for dashboards:

```bash
# Count notifications sent per hour
grep "✅ Sent and marked as notified" ~/.syft-creds/syft-notify.log | \
  awk '{print $1" "$2}' | \
  cut -d':' -f1 | \
  uniq -c

# Count errors per day
grep "ERROR" ~/.syft-creds/syft-notify.log | \
  awk '{print $1}' | \
  uniq -c
```

## Best Practices

1. **Monitor log file size**: Set up alerts if logs grow too large
2. **Compress old logs**: Use gzip to save disk space
3. **Secure log files**: Restrict permissions (`chmod 600 ~/.syft-creds/*.log`)
4. **Test log forwarding**: Verify logs reach your aggregator
5. **Set up alerts**: Get notified of errors immediately
6. **Regular cleanup**: Archive/delete very old logs
