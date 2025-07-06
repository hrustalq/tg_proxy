# Telegram Proxy Bot

A Telegram bot that provides MTProto proxy access through subscription management using the latest MTG (nineseconds/mtg:2) proxy implementation.

## Features

- 🔒 Secure MTProto proxy protocol with MTG v2
- 💰 Subscription-based access model
- 🎁 Free trial for new users
- 🌍 Multiple server locations
- ⚡ High-speed connections
- 📱 Easy-to-use Telegram interface
- 📊 Real-time proxy monitoring with Prometheus
- 🛡️ Built-in security features (anti-replay, blocklists)

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd tg_proxy
cp .env.example .env
```

### 2. Generate MTG Secret

```bash
# Generate a new MTG secret for your domain
docker run --rm nineseconds/mtg:2 generate-secret your-domain.com
```

### 3. Configure Environment

Edit `.env` file with your values:

```bash
# Telegram Bot Configuration
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321
PAYMENT_PROVIDER_TOKEN=your_payment_provider_token
PROXY_SERVERS=your-server.com:443

# MTG Proxy Configuration  
MTG_SECRET=ee473ce5d4958eb5f968c87680a23854a0676f6f676c652e636f6d  # Use generated secret
MTG_HOST_PORT=443  # External port
MTG_BIND_PORT=3128  # Internal port

# Optional: Telegram API for monitoring
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
```

### 4. Deploy with Docker

```bash
# Start all services (MTG proxy, bot, Prometheus)
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

## MTG Proxy Configuration

The MTG proxy is configured via `mtg/config.toml` with advanced features:

- **Anti-replay protection**: Prevents replay attacks
- **IP blocklists**: Automatic blocking of malicious IPs
- **Domain fronting**: Enhanced camouflage
- **Prometheus metrics**: Real-time monitoring
- **DNS-over-HTTPS**: Secure DNS resolution

## Bot Commands

### User Commands
- `/start` - Start the bot and see subscription options
- `/config` - Get proxy configuration (requires active subscription)
- `/status` - Check subscription status
- `/help` - Show available commands

### Admin Commands
- `/admin` - Access admin panel
- `/users` - Manage users
- `/servers` - Manage proxy servers
- `/payments` - View payment statistics

## Proxy Features

### MTG v2 Advantages
- Resource efficient (low memory footprint)
- Single secret authentication
- Native blocklist support
- Proxy chaining (SOCKS5)
- Built-in monitoring
- Auto-updating IP blocklists

### Security Features
- Encrypted MTProto protocol
- Anti-replay attack protection
- IP-based filtering
- Domain fronting camouflage
- Regular blocklist updates

## Monitoring & Metrics

### Prometheus Metrics
Access metrics at `http://localhost:9090` for:
- Client connections
- Telegram server connections
- Traffic volume
- Security events
- Performance metrics

### Available Metrics
- `mtg_client_connections` - Active client connections
- `mtg_telegram_connections` - Connections to Telegram
- `mtg_domain_fronting_connections` - Domain fronting usage
- `mtg_replay_attacks` - Blocked replay attacks
- `mtg_concurrency_limited` - Rate-limited connections

### Health Checks
- MTG proxy health monitoring
- Automatic service restart on failure
- Real-time status in bot interface

## Development Setup

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run database migrations
python -c "from database import init_db; init_db()"

# Start the bot
python main.py
```

### Testing

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html
```

## Production Deployment

### Security Checklist
- [ ] Use strong MTG secret generated for your domain
- [ ] Configure firewall rules
- [ ] Enable IP blocklists
- [ ] Set up monitoring alerts
- [ ] Regular secret rotation
- [ ] Backup configuration

### Scaling
```bash
# Scale bot instances
docker-compose up -d --scale telegram-bot=3

# Scale proxy servers (if using multiple)
# Add servers to PROXY_SERVERS in .env
```

### Backup
```bash
# Backup database
docker exec telegram-bot cp /app/tg_proxy.db /backup/

# Backup configuration
cp .env mtg/config.toml /backup/
```

## Troubleshooting

### Common Issues

1. **Connection Failed**
   ```bash
   # Check MTG proxy status
   docker-compose logs mtg-proxy
   
   # Test connectivity
   curl http://localhost:8080/metrics
   ```

2. **Invalid Secret**
   ```bash
   # Regenerate secret
   docker run --rm nineseconds/mtg:2 generate-secret your-domain.com
   ```

3. **Memory Issues**
   ```bash
   # Check resource usage
   docker stats
   
   # Reduce MTG buffer sizes in config.toml
   ```

### Debug Mode
```bash
# Enable debug logging
export MTG_DEBUG=true
docker-compose up -d
```

## Documentation

For detailed setup instructions, see:
- [MTG Setup Guide](docs/MTG_SETUP_GUIDE.md) - Complete MTG integration guide
- [MTG Secret Guide](docs/MTG_SECRET_GUIDE.md) - Secret generation and management
- [YooKassa Setup](docs/YOOKASSA_SETUP_GUIDE.md) - Payment integration

## Security Notice

This project is for educational and legitimate proxy use only. Users are responsible for compliance with local laws and regulations. The proxy should not be used for illegal activities.

## Support

- Check the [troubleshooting section](#troubleshooting)
- Review logs: `docker-compose logs -f`
- Monitor metrics: `http://localhost:9090`
- Verify MTG status: `http://localhost:8080/metrics`