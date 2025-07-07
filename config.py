from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    bot_token: str
    admin_ids: str
    database_url: str = "sqlite:///./tg_proxy.db"
    payment_provider_token: str
    proxy_servers: str
    subscription_price: float = 5.00
    subscription_duration: int = 30
    currency: str = "RUB"
    
    # MTG Proxy Configuration
    mtg_secret: str
    mtg_host_port: int = 443
    mtg_bind_port: int = 3128
    mtg_debug: bool = False
    
    # Telegram API Configuration
    telegram_api_id: Optional[int] = None
    telegram_api_hash: Optional[str] = None
    
    # Optional: SOCKS5 Proxy for chaining
    socks5_proxy_url: Optional[str] = None
    
    # Monitoring
    prometheus_retention: str = "15d"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )
    
    def get_admin_ids(self) -> List[int]:
        return [int(item.strip()) for item in self.admin_ids.split(",")]
    
    def get_proxy_servers(self) -> List[str]:
        return [item.strip() for item in self.proxy_servers.split(",")]


settings = Settings()