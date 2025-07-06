from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    bot_token: str
    admin_ids: List[int]
    database_url: str = "sqlite:///./tg_proxy.db"
    payment_provider_token: str
    proxy_servers: List[str]
    subscription_price: float = 5.00
    subscription_duration: int = 30
    mtg_secret: str
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        
    @classmethod
    def parse_comma_separated(cls, value: str) -> List[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",")]
        return value


settings = Settings()