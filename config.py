from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    bot_token: str
    admin_ids: str
    database_url: str = "sqlite:///./tg_proxy.db"
    payment_provider_token: str
    proxy_servers: str
    subscription_price: float = 5.00
    subscription_duration: int = 30
    mtg_secret: str
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )
    
    def get_admin_ids(self) -> List[int]:
        return [int(item.strip()) for item in self.admin_ids.split(",")]
    
    def get_proxy_servers(self) -> List[str]:
        return [item.strip() for item in self.proxy_servers.split(",")]


settings = Settings()