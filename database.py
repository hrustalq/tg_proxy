from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from datetime import datetime, timezone
from config import settings
import os
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255))
    first_name = Column(String(255))
    subscription_until = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    proxy_configs = relationship("ProxyConfig", back_populates="user")
    payments = relationship("Payment", back_populates="user")


class ProxyConfig(Base):
    __tablename__ = "proxy_configs"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    proxy_secret = Column(String(255), nullable=False)
    server_address = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="proxy_configs")


class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="RUB")
    status = Column(String(50), default="pending")
    provider_payment_id = Column(String(255))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="payments")


class ProxyServer(Base):
    __tablename__ = "proxy_servers"
    
    id = Column(Integer, primary_key=True)
    address = Column(String(255), nullable=False, unique=True)
    port = Column(Integer, nullable=False, default=443)
    is_active = Column(Boolean, default=True)
    description = Column(String(500))
    location = Column(String(100))
    max_users = Column(Integer, default=1000)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# Database setup
if settings.database_url.startswith("sqlite"):
    engine = create_async_engine(settings.database_url.replace("sqlite://", "sqlite+aiosqlite://"))
else:
    engine = create_async_engine(settings.database_url)

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    # Ensure database directory exists for SQLite
    if settings.database_url.startswith("sqlite"):
        # Extract path from database URL
        db_path = settings.database_url.replace("sqlite:///", "").replace("sqlite://", "")
        if db_path.startswith("./"):
            db_path = db_path[2:]  # Remove ./ prefix
        
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")
        
        # Create empty file if it doesn't exist
        if not os.path.exists(db_path):
            open(db_path, 'a').close()
            logger.info(f"Created database file: {db_path}")
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def get_db():
    async with async_session() as session:
        yield session