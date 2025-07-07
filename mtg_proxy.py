import os
import asyncio
import logging
import requests
import base64
import json
from urllib.parse import urlparse, parse_qs
from typing import Dict, Optional, Any
from telethon import TelegramClient
from telethon.network import connection
from telethon.sessions import StringSession
import socks
from config import settings

logger = logging.getLogger(__name__)


class MTGProxyConnection(connection.ConnectionTcpMTProxyRandomizedIntermediate):
    """Custom MTProto connection class for MTG proxy"""
    pass


class MTGProxyManager:
    """Manager for MTG proxy operations"""
    
    def __init__(self):
        self.proxy_host = os.getenv('MTG_PROXY_HOST', 'mtg-proxy')  # Internal Docker host
        self.proxy_port = settings.mtg_bind_port
        self.secret = settings.mtg_secret
        
        # Decode secret if it's in base64 or hex format
        self.decoded_secret = self._decode_secret(self.secret)
        
        # Telegram client credentials
        self.api_id = settings.telegram_api_id
        self.api_hash = settings.telegram_api_hash
        
        # External host for client connections
        proxy_servers = settings.get_proxy_servers()
        self.external_host = proxy_servers[0].split(':')[0] if proxy_servers else "localhost"
        
        logger.info(f"Initialized MTG Proxy Manager - Internal: {self.proxy_host}:{self.proxy_port}, External: {self.external_host}:{settings.mtg_host_port}")
    
    def _decode_secret(self, secret: str) -> Optional[bytes]:
        """Decode MTG secret from hex or base64 format"""
        try:
            # Check if it's hex (starts with 'ee' for MTG)
            if secret.startswith('ee'):
                return bytes.fromhex(secret)
            else:
                # Try base64
                return base64.b64decode(secret)
        except Exception as e:
            logger.error(f"Failed to decode secret: {e}")
            return None
    
    def get_proxy_info(self) -> Optional[str]:
        """Get proxy information from MTG stats endpoint"""
        try:
            response = requests.get(f"http://{self.proxy_host}:8080/metrics", timeout=5)
            if response.status_code == 200:
                logger.info("Successfully retrieved proxy metrics")
                return response.text
        except Exception as e:
            logger.error(f"Failed to get proxy info: {e}")
        return None
    
    def parse_proxy_url(self, proxy_url: str) -> Dict[str, Any]:
        """Parse Telegram proxy URL"""
        parsed = urlparse(proxy_url)
        params = parse_qs(parsed.query)
        
        return {
            'server': params.get('server', [''])[0],
            'port': int(params.get('port', ['443'])[0]),
            'secret': params.get('secret', [''])[0]
        }
    
    async def create_telegram_client(self, session_string: Optional[str] = None) -> Optional[TelegramClient]:
        """Create a Telegram client with MTG proxy"""
        if not self.api_id or not self.api_hash:
            logger.error("Telegram API credentials not configured")
            return None
        
        # Create client with proxy configuration
        client = TelegramClient(
            StringSession(session_string) if session_string else StringSession(),
            self.api_id,
            self.api_hash,
            connection=MTGProxyConnection,
            proxy=(socks.SOCKS5, self.proxy_host, self.proxy_port)
        )
        
        return client
    
    async def test_connection(self) -> bool:
        """Test the MTG proxy connection"""
        if not self.api_id or not self.api_hash:
            logger.warning("Cannot test connection without Telegram API credentials")
            return False
            
        client = await self.create_telegram_client()
        if not client:
            return False
        
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
    
    def generate_client_links(self, server_host: Optional[str] = None) -> Dict[str, str]:
        """Generate client connection links"""
        # Use provided server_host or fallback to external host
        host = server_host or self.external_host
        port = settings.mtg_host_port
        
        base_url = f"tg://proxy?server={host}&port={port}&secret={self.secret}"
        tme_url = f"https://t.me/proxy?server={host}&port={port}&secret={self.secret}"
        
        return {
            'tg_url': base_url,
            'tme_url': tme_url,
            'qr_code': f"https://api.qrserver.com/v1/create-qr-code/?data={tme_url}&size=300x300"
        }
    
    def get_proxy_config_text(self, server_host: Optional[str] = None) -> str:
        """Generate proxy configuration text for users"""
        # Use provided server_host or fallback to external host
        host = server_host or self.external_host
        port = settings.mtg_host_port
        
        return f"""🔒 **Конфигурация MTProto прокси**

**Сервер:** `{host}`
**Порт:** `{port}`
**Секретный ключ:** `{self.secret}`

**Быстрые ссылки для подключения:**
• [Открыть в Telegram](tg://proxy?server={host}&port={port}&secret={self.secret})

**Ручная настройка:**
1. Откройте настройки Telegram
2. Перейдите в "Данные и память" > "Настройки прокси"
3. Добавить прокси > MTProto
4. Введите данные сервера выше

**QR код:** [Создать QR код](https://api.qrserver.com/v1/create-qr-code/?data=https://t.me/proxy?server={host}&port={port}&secret={self.secret}&size=300x300)
"""


class MTGMonitor:
    """Monitor MTG proxy metrics"""
    
    def __init__(self, proxy_host: str = 'mtg-proxy', stats_port: int = 8080):
        self.proxy_host = proxy_host
        self.stats_port = stats_port
        self.metrics_url = f"http://{proxy_host}:{stats_port}/metrics"
    
    def get_metrics(self) -> Dict[str, float]:
        """Fetch and parse Prometheus metrics"""
        try:
            response = requests.get(self.metrics_url, timeout=5)
            if response.status_code == 200:
                return self._parse_prometheus_metrics(response.text)
        except Exception as e:
            logger.error(f"Failed to fetch metrics: {e}")
        return {}
    
    def _parse_prometheus_metrics(self, metrics_text: str) -> Dict[str, float]:
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
    
    def get_status_text(self) -> str:
        """Get formatted status text"""
        metrics = self.get_metrics()
        
        if not metrics:
            return "❌ **Статус прокси:** Недоступен"
        
        status_text = "📊 **Статус MTG прокси**\n\n"
        status_text += f"🔌 **Подключения клиентов:** {int(metrics.get('mtg_client_connections', 0))}\n"
        status_text += f"📡 **Подключения к Telegram:** {int(metrics.get('mtg_telegram_connections', 0))}\n"
        status_text += f"🌐 **Domain Fronting:** {int(metrics.get('mtg_domain_fronting_connections', 0))}\n"
        status_text += f"🛡️ **Заблокировано replay-атак:** {int(metrics.get('mtg_replay_attacks', 0))}\n"
        status_text += f"⚠️ **Ограничено по конкуренции:** {int(metrics.get('mtg_concurrency_limited', 0))}\n"
        
        return status_text
    
    async def health_check(self) -> bool:
        """Check if MTG proxy is healthy"""
        try:
            response = requests.get(self.metrics_url, timeout=5)
            return response.status_code == 200
        except:
            return False


# Global instances
mtg_proxy_manager = MTGProxyManager()
mtg_monitor = MTGMonitor()