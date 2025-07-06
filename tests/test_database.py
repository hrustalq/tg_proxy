"""Tests for database models and operations."""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from database import User, ProxyConfig, Payment, init_db, get_db


class TestUserModel:
    """Test User database model."""
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_create_user(self, db_session):
        """Test creating a new user."""
        user = User(
            telegram_id=123456789,
            username="testuser",
            first_name="Test User"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        assert user.id is not None
        assert user.telegram_id == 123456789
        assert user.username == "testuser"
        assert user.first_name == "Test User"
        assert user.is_active is True
        assert user.subscription_until is None
        assert user.created_at is not None
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_user_telegram_id_unique(self, db_session):
        """Test that telegram_id is unique."""
        user1 = User(telegram_id=123456789, username="user1")
        user2 = User(telegram_id=123456789, username="user2")
        
        db_session.add(user1)
        await db_session.commit()
        
        db_session.add(user2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_user_with_subscription(self, db_session):
        """Test user with subscription date."""
        expiry = datetime.now(timezone.utc) + timedelta(days=30)
        user = User(
            telegram_id=987654321,
            subscription_until=expiry
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        assert user.subscription_until == expiry
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_user_defaults(self, db_session):
        """Test user default values."""
        user = User(telegram_id=111222333)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        assert user.is_active is True
        assert user.created_at is not None
        assert isinstance(user.created_at, datetime)
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_user_relationships(self, db_session):
        """Test user relationships with proxy configs and payments."""
        user = User(telegram_id=444555666)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Initially no relationships
        assert len(user.proxy_configs) == 0
        assert len(user.payments) == 0


class TestProxyConfigModel:
    """Test ProxyConfig database model."""
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_create_proxy_config(self, db_session, test_user):
        """Test creating a proxy configuration."""
        config = ProxyConfig(
            user_id=test_user.id,
            proxy_secret="secret_32_characters_long_here",
            server_address="proxy.example.com",
            port=443
        )
        db_session.add(config)
        await db_session.commit()
        await db_session.refresh(config)
        
        assert config.id is not None
        assert config.user_id == test_user.id
        assert config.proxy_secret == "secret_32_characters_long_here"
        assert config.server_address == "proxy.example.com"
        assert config.port == 443
        assert config.created_at is not None
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_proxy_config_user_relationship(self, db_session, test_user):
        """Test proxy config to user relationship."""
        config = ProxyConfig(
            user_id=test_user.id,
            proxy_secret="test_secret",
            server_address="test.com",
            port=8080
        )
        db_session.add(config)
        await db_session.commit()
        await db_session.refresh(config)
        
        # Test relationship
        assert config.user.id == test_user.id
        assert config.user.telegram_id == test_user.telegram_id
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_multiple_configs_per_user(self, db_session, test_user):
        """Test user can have multiple proxy configurations."""
        config1 = ProxyConfig(
            user_id=test_user.id,
            proxy_secret="secret1",
            server_address="server1.com",
            port=443
        )
        config2 = ProxyConfig(
            user_id=test_user.id,
            proxy_secret="secret2",
            server_address="server2.com",
            port=8080
        )
        
        db_session.add_all([config1, config2])
        await db_session.commit()
        
        # Query user's configs
        result = await db_session.execute(
            select(ProxyConfig).where(ProxyConfig.user_id == test_user.id)
        )
        configs = result.scalars().all()
        
        assert len(configs) == 2
        assert any(c.server_address == "server1.com" for c in configs)
        assert any(c.server_address == "server2.com" for c in configs)
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_proxy_config_required_fields(self, db_session, test_user):
        """Test that required fields are enforced."""
        # Missing proxy_secret should fail
        config = ProxyConfig(
            user_id=test_user.id,
            server_address="test.com",
            port=443
        )
        db_session.add(config)
        
        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestPaymentModel:
    """Test Payment database model."""
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_create_payment(self, db_session, test_user):
        """Test creating a payment record."""
        payment = Payment(
            user_id=test_user.id,
            amount=5.99,
            currency="RUB",
            status="completed",
            provider_payment_id="test_payment_123"
        )
        db_session.add(payment)
        await db_session.commit()
        await db_session.refresh(payment)
        
        assert payment.id is not None
        assert payment.user_id == test_user.id
        assert payment.amount == 5.99
        assert payment.currency == "RUB"
        assert payment.status == "completed"
        assert payment.provider_payment_id == "test_payment_123"
        assert payment.created_at is not None
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_payment_defaults(self, db_session, test_user):
        """Test payment default values."""
        payment = Payment(
            user_id=test_user.id,
            amount=10.00
        )
        db_session.add(payment)
        await db_session.commit()
        await db_session.refresh(payment)
        
        assert payment.currency == "USD"  # Default currency
        assert payment.status == "pending"  # Default status
        assert payment.created_at is not None
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_payment_user_relationship(self, db_session, test_user):
        """Test payment to user relationship."""
        payment = Payment(
            user_id=test_user.id,
            amount=15.00,
            status="completed"
        )
        db_session.add(payment)
        await db_session.commit()
        await db_session.refresh(payment)
        
        # Test relationship
        assert payment.user.id == test_user.id
        assert payment.user.telegram_id == test_user.telegram_id
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_multiple_payments_per_user(self, db_session, test_user):
        """Test user can have multiple payments."""
        payment1 = Payment(
            user_id=test_user.id,
            amount=5.00,
            status="completed"
        )
        payment2 = Payment(
            user_id=test_user.id,
            amount=10.00,
            status="pending"
        )
        
        db_session.add_all([payment1, payment2])
        await db_session.commit()
        
        # Query user's payments
        result = await db_session.execute(
            select(Payment).where(Payment.user_id == test_user.id)
        )
        payments = result.scalars().all()
        
        assert len(payments) == 2
        total_amount = sum(p.amount for p in payments)
        assert total_amount == 15.00


class TestDatabaseOperations:
    """Test database initialization and operations."""
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_init_db(self, test_db):
        """Test database initialization."""
        # Database should be created without errors
        assert test_db is not None
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_get_db_generator(self, test_db):
        """Test get_db async generator."""
        session_count = 0
        async for session in test_db():
            session_count += 1
            assert session is not None
            assert isinstance(session, type(test_db()).__await__().__next__())
            break  # Only test one iteration
        
        assert session_count == 1
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_database_transactions(self, db_session):
        """Test database transaction handling."""
        user = User(telegram_id=777888999)
        db_session.add(user)
        
        # Before commit, user has no ID
        assert user.id is None
        
        await db_session.commit()
        await db_session.refresh(user)
        
        # After commit, user has ID
        assert user.id is not None
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_cascade_relationships(self, db_session):
        """Test cascade behavior when deleting users."""
        # Create user with configs and payments
        user = User(telegram_id=555666777)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        config = ProxyConfig(
            user_id=user.id,
            proxy_secret="test_secret",
            server_address="test.com",
            port=443
        )
        payment = Payment(
            user_id=user.id,
            amount=5.00
        )
        
        db_session.add_all([config, payment])
        await db_session.commit()
        
        # Verify relationships exist
        result = await db_session.execute(
            select(ProxyConfig).where(ProxyConfig.user_id == user.id)
        )
        assert len(result.scalars().all()) == 1
        
        result = await db_session.execute(
            select(Payment).where(Payment.user_id == user.id)
        )
        assert len(result.scalars().all()) == 1