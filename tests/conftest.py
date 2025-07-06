"""Test configuration and fixtures."""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os

from database import Base, User, ProxyConfig, Payment
from config import Settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db():
    """Create a test database with temporary file."""
    # Create temporary database file
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    database_url = f"sqlite+aiosqlite:///{temp_db.name}"
    engine = create_async_engine(database_url, echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session factory
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    yield async_session
    
    # Cleanup
    await engine.dispose()
    os.unlink(temp_db.name)


@pytest.fixture
async def db_session(test_db):
    """Create a database session for testing."""
    async with test_db() as session:
        yield session


@pytest.fixture
def test_settings():
    """Create test settings."""
    return Settings(
        bot_token="test_token",
        admin_ids="123456789",
        database_url="sqlite:///test.db",
        payment_provider_token="test_provider_token",
        proxy_servers="server1.test.com:443,server2.test.com:8080,server3.test.com",
        subscription_price=5.00,
        subscription_duration=30,
        mtg_secret="test_secret_12345678901234567890"
    )


@pytest.fixture
def mock_bot():
    """Create a mock bot instance."""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    bot.send_invoice = AsyncMock()
    bot.answer_pre_checkout_query = AsyncMock()
    return bot


@pytest.fixture
def mock_message():
    """Create a mock message."""
    message = MagicMock()
    message.from_user.id = 123456789
    message.from_user.username = "testuser"
    message.from_user.first_name = "Test"
    message.answer = AsyncMock()
    message.reply = AsyncMock()
    return message


@pytest.fixture
def mock_callback_query():
    """Create a mock callback query."""
    callback = MagicMock()
    callback.from_user.id = 123456789
    callback.from_user.username = "testuser" 
    callback.from_user.first_name = "Test"
    callback.answer = AsyncMock()
    callback.message = mock_message()
    callback.message.edit_text = AsyncMock()
    callback.data = "test_data"
    return callback


@pytest.fixture
def mock_successful_payment():
    """Create a mock successful payment."""
    payment = MagicMock()
    payment.total_amount = 500  # $5.00 in cents
    payment.currency = "RUB"
    payment.provider_payment_charge_id = "test_charge_id"
    return payment


@pytest.fixture
async def test_user(db_session):
    """Create a test user."""
    user = User(
        telegram_id=123456789,
        username="testuser",
        first_name="Test",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def subscribed_user(db_session):
    """Create a test user with active subscription."""
    user = User(
        telegram_id=987654321,
        username="subscriber",
        first_name="Subscriber",
        subscription_until=datetime.now(timezone.utc) + timedelta(days=15),
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def expired_user(db_session):
    """Create a test user with expired subscription."""
    user = User(
        telegram_id=111222333,
        username="expired",
        first_name="Expired",
        subscription_until=datetime.now(timezone.utc) - timedelta(days=1),
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def trial_user(db_session):
    """Create a test user who used trial."""
    user = User(
        telegram_id=444555666,
        username="trial",
        first_name="Trial",
        subscription_until=datetime.now(timezone.utc) - timedelta(hours=1),
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_proxy_config(db_session, subscribed_user):
    """Create a test proxy configuration."""
    config = ProxyConfig(
        user_id=subscribed_user.id,
        proxy_secret="test_secret_32_chars_long_here",
        server_address="test.server.com",
        port=443
    )
    db_session.add(config)
    await db_session.commit()
    await db_session.refresh(config)
    return config


@pytest.fixture
async def test_payment(db_session, subscribed_user):
    """Create a test payment."""
    payment = Payment(
        user_id=subscribed_user.id,
        amount=5.00,
        currency="RUB",
        status="completed",
        provider_payment_id="test_payment_id"
    )
    db_session.add(payment)
    await db_session.commit()
    await db_session.refresh(payment)
    return payment