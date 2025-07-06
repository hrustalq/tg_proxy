# Telegram Proxy Bot

A Telegram bot that provides MTProto proxy access through subscription management.

## Features

- 🔒 Secure MTProto proxy protocol
- 💰 Subscription-based access model
- 🎁 Free trial for new users
- 🌍 Multiple server locations
- ⚡ High-speed connections
- 📱 Easy-to-use Telegram interface

## Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd tg_proxy
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

4. **Run the bot**
   ```bash
   python main.py
   ```

## Docker Deployment

1. **Build and run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

2. **View logs**
   ```bash
   docker-compose logs -f
   ```

## Configuration

Edit the `.env` file with your configuration:

- `BOT_TOKEN`: Your Telegram bot token from @BotFather
- `ADMIN_IDS`: Comma-separated list of admin Telegram IDs
- `PAYMENT_PROVIDER_TOKEN`: Payment provider token for Telegram payments
- `PROXY_SERVERS`: Comma-separated list of proxy servers (host:port)
- `MTG_SECRET`: Secret for MTG proxy server

## Bot Commands

- `/start` - Start the bot and see subscription options
- `/config` - Get proxy configuration (requires active subscription)

## Proxy Setup

The bot uses MTG (9seconds) proxy implementation. The proxy server runs on port 3128 and provides statistics on port 8080.

## Payment Integration

The bot supports Telegram Bot Payments API for subscription management. Users can:
- Subscribe for monthly access
- Get a free 1-day trial
- Automatic proxy configuration generation

## Security

- All proxy configurations use unique secrets
- Database stores encrypted user data
- Admin-only access to sensitive operations
- Regular security updates recommended

## Monitoring

- Proxy statistics available at `http://localhost:8080`
- Bot logs all important events
- Database tracks all payments and subscriptions

## License

This project is for educational purposes only. Ensure compliance with local laws and regulations.