from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from pydantic import field_validator
import os

class Settings(BaseSettings):
    proxy_servers: List[str]
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )
        
    @field_validator('proxy_servers', mode='before')
    @classmethod
    def parse_comma_separated(cls, value):
        print(f"Validator called with value: {value}, type: {type(value)}")
        if isinstance(value, str):
            return [item.strip() for item in value.split(",")]
        return value

# Test with environment variable
os.environ["PROXY_SERVERS"] = "proxy.safesurf.tech"
try:
    settings = Settings()
    print(f"Success! proxy_servers: {settings.proxy_servers}")
except Exception as e:
    print(f"Error: {e}")