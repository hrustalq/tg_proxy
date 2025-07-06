# Complete Guide: Integrating MTG Proxy Server with Python using Docker Compose

This guide provides a comprehensive walkthrough for integrating the MTG (Telegram MTProto proxy) server into your Python project using Docker Compose, including all required configurations, environment variables, and management practices.

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Project Structure](#project-structure)
4. [Docker Compose Configuration](#docker-compose-configuration)
5. [MTG Configuration](#mtg-configuration)
6. [Python Integration](#python-integration)
7. [Environment Variables](#environment-variables)
8. [Management & Operations](#management--operations)
9. [Monitoring & Metrics](#monitoring--metrics)
10. [Security Considerations](#security-considerations)
11. [Troubleshooting](#troubleshooting)

## Overview

MTG is a highly-opinionated, lightweight MTPROTO proxy for Telegram that focuses on:
- Resource efficiency
- Easy deployment
- Single secret authentication
- Native blocklist support
- Proxy chaining capabilities (SOCKS5)
- Built-in monitoring (Prometheus/StatsD)

## Prerequisites

- Docker and Docker Compose installed
- Python 3.8+ environment
- Basic understanding of Docker networking
- A server with a public IP address (for production use)

## Project Structure

Create the following project structure:

```
your-project/
├── docker-compose.yml
├── mtg/
│   ├── config.toml
│   └── blocklist.txt (optional)
├── python/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
├── .env
└── README.md
```

## Docker Compose Configuration

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  mtg-proxy:
    image: nineseconds/mtg:2
    container_name: mtg-proxy
    restart: unless-stopped
    ports:
      - "${MTG_HOST_PORT:-443}:${MTG_BIND_PORT:-3128}"
    volumes:
      - ./mtg/config.toml:/config.toml:ro
      - ./mtg/blocklist.txt:/blocklist.txt:ro  # Optional
    command: run /config.toml
    networks:
      - mtg-network
    environment:
      - MTG_DEBUG=${MTG_DEBUG:-false}
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:8080/metrics"]
      interval: 30s
      timeout: 10s
      retries: 3

  python-app:
    build: 
      context: ./python
      dockerfile: Dockerfile
    container_name: python-app
    restart: unless-stopped
    depends_on:
      - mtg-proxy
    environment:
      - MTG_PROXY_HOST=mtg-proxy
      - MTG_PROXY_PORT=${MTG_BIND_PORT:-3128}
      - MTG_SECRET=${MTG_SECRET}
      - PYTHONUNBUFFERED=1
    volumes:
      - ./python:/app
    networks:
      - mtg-network
    command: python app.py

  # Optional: Prometheus for monitoring
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    restart: unless-stopped
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - mtg-network
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

networks:
  mtg-network:
    driver: bridge

volumes:
  prometheus-data:
```

## MTG Configuration

Create `mtg/config.toml`:

```toml
# Required: Secret for authentication (generate with: mtg generate-secret your-domain.com)
secret = "${MTG_SECRET}"

# Required: Bind address
bind-to = "0.0.0.0:3128"

# Optional: Concurrency settings
[network]
# Maximum concurrent connections
concurrency = 8192

# TCP buffer size
tcp-buffer = "16KB"

# Network timeout
timeout = "10s"

# IP preference: "prefer-ipv4", "prefer-ipv6", "only-ipv4", "only-ipv6"
prefer-ip = "prefer-ipv6"

# Optional: Domain fronting configuration
[domain-fronting]
# Port for domain fronting connections
port = 443

# Optional: DNS configuration
[dns]
# DNS-over-HTTPS resolver IP
doh-ip = "9.9.9.9"

# Optional: Defense settings
[defense]
# Anti-replay cache size
antireplay-cache-size = "1MB"

# Optional: Blocklist configuration
[defense.blocklist]
# Enable blocklist
enabled = true

# Path to blocklist file
files = ["/blocklist.txt"]

# Download blocklists from URLs
download-urls = [
    "https://iplists.firehol.org/files/firehol_level1.netset"
]

# Update interval for downloaded blocklists
update-each = "1h"

# Optional: Stats configuration
[stats]
# Enable statistics endpoint
enabled = true

# Stats bind address
bind-to = "0.0.0.0:8080"

# Optional: Prometheus configuration
[stats.prometheus]
# Enable Prometheus metrics
enabled = true

# Metrics endpoint
endpoint = "/metrics"

# Optional: StatsD configuration
[stats.statsd]
# Enable StatsD
enabled = false

# StatsD address
address = "statsd:8125"

# Metrics prefix
metric-prefix = "mtg"

# Tag format: "datadog", "influxdb", or ""
tag-format = ""

# Optional: Proxy chaining (SOCKS5)
[network.socks5]
# SOCKS5 proxy URL (optional)
# url = "socks5://user:pass@socks5-proxy:1080"
```

## Python Integration

Create `python/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
```

Create `python/requirements.txt`:

```txt
python-telegram-bot>=20.0
requests>=2.28.0
aiohttp>=3.8.0
pysocks>=1.7.1
python-dotenv>=0.19.0
telethon>=1.25.0  # For MTProto client
cryptg>=0.4  # For faster Telethon crypto
```

Create `python/app.py`:

```python
import os
import sys
import asyncio
import logging
import requests
from urllib.parse import urlparse, parse_qs
import base64
import json
from telethon import TelegramClient
from telethon.network import connection
from telethon.sessions import StringSession
import socks

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MTGProxyConnection(connection.ConnectionTcpMTProxyRandomizedIntermediate):
    """Custom MTProto connection class for MTG proxy"""
    pass

class MTGProxyManager:
    def __init__(self):
        self.proxy_host = os.getenv('MTG_PROXY_HOST', 'mtg-proxy')
        self.proxy_port = int(os.getenv('MTG_PROXY_PORT', '3128'))
        self.secret = os.getenv('MTG_SECRET', '')
        
        # Decode secret if it's in base64 or hex format
        self.decoded_secret = self._decode_secret(self.secret)
        
        # Telegram client credentials (you need to obtain these)
        self.api_id = int(os.getenv('TELEGRAM_API_ID', '0'))
        self.api_hash = os.getenv('TELEGRAM_API_HASH', '')
        
        logger.info(f"Initialized MTG Proxy Manager - Host: {self.proxy_host}:{self.proxy_port}")
    
    def _decode_secret(self, secret):
        """Decode MTG secret from hex or base64 format"""
        try:
            # Check if it's hex (starts with 'ee')
            if secret.startswith('ee'):
                return bytes.fromhex(secret)
            else:
                # Try base64
                return base64.b64decode(secret)
        except Exception as e:
            logger.error(f"Failed to decode secret: {e}")
            return None
    
    def get_proxy_info(self):
        """Get proxy information from MTG stats endpoint"""
        try:
            response = requests.get(f"http://{self.proxy_host}:8080/metrics")
            if response.status_code == 200:
                logger.info("Successfully retrieved proxy metrics")
                return response.text
        except Exception as e:
            logger.error(f"Failed to get proxy info: {e}")
        return None
    
    def parse_proxy_url(self, proxy_url):
        """Parse Telegram proxy URL"""
        parsed = urlparse(proxy_url)
        params = parse_qs(parsed.query)
        
        return {
            'server': params.get('server', [''])[0],
            'port': int(params.get('port', ['443'])[0]),
            'secret': params.get('secret', [''])[0]
        }
    
    async def create_telegram_client(self, session_string=None):
        """Create a Telegram client with MTG proxy"""
        if not self.api_id or not self.api_hash:
            logger.error("Telegram API credentials not configured")
            return None
        
        # Create client with proxy configuration
        client = TelegramClient(
            StringSession(session_string),
            self.api_id,
            self.api_hash,
            connection=MTGProxyConnection,
            proxy=(socks.SOCKS5, self.proxy_host, self.proxy_port)
        )
        
        return client
    
    async def test_connection(self):
        """Test the MTG proxy connection"""
        client = await self.create_telegram_client()
        
        try:
            await client.connect()
            if await client.is_user_authorized():
                logger.info("Successfully connected through MTG proxy")
                me = await client.get_me()
                logger.info(f"Logged in as: {me.username}")
                return True
            else:
                logger.warning("Connected but not authorized")
                return False
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
        finally:
            await client.disconnect()
    
    def generate_client_links(self):
        """Generate client connection links"""
        base_url = f"tg://proxy?server={self.proxy_host}&port={self.proxy_port}&secret={self.secret}"
        tme_url = f"https://t.me/proxy?server={self.proxy_host}&port={self.proxy_port}&secret={self.secret}"
        
        return {
            'tg_url': base_url,
            'tme_url': tme_url,
            'qr_code': f"https://api.qrserver.com/v1/create-qr-code/?data={tme_url}&size=300x300"
        }

class MTGMonitor:
    """Monitor MTG proxy metrics"""
    
    def __init__(self, proxy_host='mtg-proxy', stats_port=8080):
        self.proxy_host = proxy_host
        self.stats_port = stats_port
        self.metrics_url = f"http://{proxy_host}:{stats_port}/metrics"
    
    def get_metrics(self):
        """Fetch and parse Prometheus metrics"""
        try:
            response = requests.get(self.metrics_url)
            if response.status_code == 200:
                return self._parse_prometheus_metrics(response.text)
        except Exception as e:
            logger.error(f"Failed to fetch metrics: {e}")
        return {}
    
    def _parse_prometheus_metrics(self, metrics_text):
        """Parse Prometheus text format"""
        metrics = {}
        for line in metrics_text.split('\n'):
            if line.startswith('#') or not line.strip():
                continue
            
            parts = line.split(' ')
            if len(parts) >= 2:
                metric_name = parts[0].split('{')[0]
                metric_value = parts[-1]
                
                try:
                    metrics[metric_name] = float(metric_value)
                except ValueError:
                    pass
        
        return metrics
    
    def print_status(self):
        """Print current proxy status"""
        metrics = self.get_metrics()
        
        logger.info("=== MTG Proxy Status ===")
        logger.info(f"Client connections: {metrics.get('mtg_client_connections', 0)}")
        logger.info(f"Telegram connections: {metrics.get('mtg_telegram_connections', 0)}")
        logger.info(f"Domain fronting connections: {metrics.get('mtg_domain_fronting_connections', 0)}")
        logger.info(f"Replay attacks detected: {metrics.get('mtg_replay_attacks', 0)}")
        logger.info(f"Concurrency limited events: {metrics.get('mtg_concurrency_limited', 0)}")

async def main():
    """Main application entry point"""
    logger.info("Starting MTG Proxy Python Integration")
    
    # Initialize proxy manager
    proxy_manager = MTGProxyManager()
    
    # Generate and log client links
    links = proxy_manager.generate_client_links()
    logger.info(f"Client Links:")
    logger.info(f"  Telegram URL: {links['tg_url']}")
    logger.info(f"  Web URL: {links['tme_url']}")
    logger.info(f"  QR Code: {links['qr_code']}")
    
    # Initialize monitor
    monitor = MTGMonitor()
    
    # Run monitoring loop
    while True:
        try:
            # Print status
            monitor.print_status()
            
            # Test connection periodically
            if await proxy_manager.test_connection():
                logger.info("Proxy connection healthy")
            
            # Wait before next check
            await asyncio.sleep(60)
            
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
```

## Environment Variables

Create `.env` file:

```bash
# MTG Configuration
MTG_SECRET=ee473ce5d4958eb5f968c87680a23854a0676f6f676c652e636f6d  # Generate with: mtg generate-secret your-domain.com
MTG_HOST_PORT=443  # External port
MTG_BIND_PORT=3128  # Internal port
MTG_DEBUG=false

# Telegram API Configuration (obtain from https://my.telegram.org)
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# Optional: SOCKS5 Proxy for chaining
# SOCKS5_PROXY_URL=socks5://user:pass@proxy:1080

# Monitoring
PROMETHEUS_RETENTION=15d
```

## Management & Operations

### 1. Generate Secret

Generate a new secret for your proxy:

```bash
# Using Docker
docker run --rm nineseconds/mtg:2 generate-secret your-domain.com

# Using binary
mtg generate-secret your-domain.com
```

### 2. Start Services

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f mtg-proxy
```

### 3. Access Proxy Information

Get proxy connection details:

```bash
# Using Docker
docker exec mtg-proxy /mtg access /config.toml

# This returns JSON with connection URLs and QR codes
```

### 4. Update Blocklists

Blocklists are automatically updated based on the `update-each` configuration. To manually update:

```bash
# Restart the proxy to force blocklist update
docker-compose restart mtg-proxy
```

### 5. Scale Services

```bash
# Scale Python app instances
docker-compose up -d --scale python-app=3
```

## Monitoring & Metrics

### Prometheus Configuration

Create `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'mtg-proxy'
    static_configs:
      - targets: ['mtg-proxy:8080']
    metrics_path: '/metrics'
```

### Available Metrics

MTG provides the following metrics:

- `mtg_client_connections` - Current client connections (tagged by ip_family)
- `mtg_telegram_connections` - Connections to Telegram servers (tagged by telegram_ip, dc)
- `mtg_domain_fronting_connections` - Domain fronting connections
- `mtg_iplist_size` - Size of IP blocklist/allowlist
- `mtg_telegram_traffic` - Bytes transferred to/from Telegram
- `mtg_domain_fronting_traffic` - Bytes transferred via domain fronting
- `mtg_concurrency_limited` - Rejected connections due to concurrency limit
- `mtg_replay_attacks` - Detected replay attacks

### Grafana Dashboard

Example Grafana query for monitoring:

```promql
# Connection rate
rate(mtg_client_connections[5m])

# Traffic volume
rate(mtg_telegram_traffic[5m])

# Error rate
rate(mtg_replay_attacks[5m]) + rate(mtg_concurrency_limited[5m])
```

## Security Considerations

### 1. Secret Management

- Never commit secrets to version control
- Use environment variables or secrets management systems
- Rotate secrets periodically
- Choose domain names wisely (match your VPS provider)

### 2. Network Security

```yaml
# Add firewall rules in docker-compose.yml
services:
  mtg-proxy:
    # ... other config ...
    sysctls:
      - net.ipv4.ip_forward=1
      - net.ipv6.conf.all.forwarding=1
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

### 3. IP Filtering

Configure IP allowlist/blocklist in `config.toml`:

```toml
[defense.allowlist]
enabled = true
files = ["/allowlist.txt"]

[defense.blocklist]
enabled = true
files = ["/blocklist.txt"]
download-urls = [
    "https://iplists.firehol.org/files/firehol_level1.netset",
    "https://iplists.firehol.org/files/firehol_level2.netset"
]
```

### 4. Rate Limiting

Configure concurrency limits:

```toml
[network]
concurrency = 1000  # Adjust based on your server capacity
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   ```bash
   # Check if MTG is running
   docker-compose ps
   
   # Check logs
   docker-compose logs mtg-proxy
   ```

2. **Secret Format Issues**
   ```bash
   # Verify secret format
   echo $MTG_SECRET | xxd
   ```

3. **Network Connectivity**
   ```bash
   # Test internal connectivity
   docker-compose exec python-app ping mtg-proxy
   
   # Check exposed ports
   docker-compose port mtg-proxy 3128
   ```

4. **High Memory Usage**
   ```toml
   # Reduce buffer sizes and cache
   [network]
   tcp-buffer = "4KB"
   
   [defense]
   antireplay-cache-size = "512KB"
   ```

### Debug Mode

Enable debug logging:

```bash
# In .env
MTG_DEBUG=true

# Or in docker-compose.yml
environment:
  - MTG_DEBUG=true
```

### Health Checks

Implement health checks in your Python app:

```python
async def health_check():
    """Check if MTG proxy is healthy"""
    try:
        response = requests.get(f"http://mtg-proxy:8080/metrics", timeout=5)
        return response.status_code == 200
    except:
        return False
```

## Production Deployment

### 1. Use Docker Swarm or Kubernetes

Example Docker Swarm deployment:

```yaml
version: '3.8'

services:
  mtg-proxy:
    image: nineseconds/mtg:2
    deploy:
      replicas: 2
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
```

### 2. Enable TLS/SSL

Use a reverse proxy like Nginx:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://mtg-proxy:3128;
        proxy_set_header Host $host;
    }
}
```

### 3. Backup Configuration

```bash
# Backup script
#!/bin/bash
backup_dir="/backups/mtg"
mkdir -p $backup_dir

# Backup configs
docker cp mtg-proxy:/config.toml $backup_dir/config.toml.$(date +%Y%m%d)

# Backup metrics
curl -s http://localhost:8080/metrics > $backup_dir/metrics.$(date +%Y%m%d)
```

## Conclusion

This guide provides a complete setup for integrating MTG proxy with Python applications using Docker Compose. The configuration is production-ready with monitoring, security features, and proper error handling. Adjust the settings based on your specific requirements and scale.

Remember to:
- Keep your secrets secure
- Monitor your proxy metrics
- Update regularly
- Use appropriate domain names for better camouflage
- Implement proper error handling in your Python applications