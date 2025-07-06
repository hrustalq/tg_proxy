"""Tests for utility functions from bot.py."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from bot import (
    generate_proxy_secret, 
    is_user_subscribed, 
    get_subscription_keyboard,
    get_proxy_config_text,
    get_user_by_telegram_id
)
from database import User, ProxyConfig


class TestGenerateProxySecret:
    """Test proxy secret generation."""
    
    @pytest.mark.unit
    def test_generates_32_character_secret(self):
        """Test that generated secret is 32 characters long."""
        secret = generate_proxy_secret()
        assert len(secret) == 32
    
    @pytest.mark.unit
    def test_generates_alphanumeric_secret(self):
        """Test that generated secret contains only alphanumeric characters."""
        secret = generate_proxy_secret()
        assert secret.isalnum()
    
    @pytest.mark.unit
    def test_generates_unique_secrets(self):
        """Test that multiple calls generate different secrets."""
        secret1 = generate_proxy_secret()
        secret2 = generate_proxy_secret()
        assert secret1 != secret2
    
    @pytest.mark.unit
    def test_secret_format_consistency(self):
        """Test that secrets consistently meet format requirements."""
        for _ in range(10):
            secret = generate_proxy_secret()
            assert len(secret) == 32
            assert secret.isalnum()


class TestIsUserSubscribed:
    """Test subscription validation logic."""
    
    @pytest.mark.unit
    async def test_user_without_subscription_until(self):
        """Test user with no subscription_until date."""
        user = User(telegram_id=123, subscription_until=None)
        result = await is_user_subscribed(user)
        assert result is False
    
    @pytest.mark.unit
    async def test_user_with_active_subscription(self):
        """Test user with active subscription."""
        future_date = datetime.now(timezone.utc) + timedelta(days=10)
        user = User(telegram_id=123, subscription_until=future_date)
        result = await is_user_subscribed(user)
        assert result is True
    
    @pytest.mark.unit
    async def test_user_with_expired_subscription(self):
        """Test user with expired subscription."""
        past_date = datetime.now(timezone.utc) - timedelta(days=1)
        user = User(telegram_id=123, subscription_until=past_date)
        result = await is_user_subscribed(user)
        assert result is False
    
    @pytest.mark.unit
    async def test_user_with_subscription_expiring_soon(self):
        """Test user with subscription expiring in 1 hour."""
        near_future = datetime.now(timezone.utc) + timedelta(hours=1)
        user = User(telegram_id=123, subscription_until=near_future)
        result = await is_user_subscribed(user)
        assert result is True
    
    @pytest.mark.unit
    async def test_timezone_naive_subscription_date(self):
        """Test handling of timezone-naive subscription dates."""
        # Simulate old data without timezone info
        naive_future = datetime.utcnow() + timedelta(days=5)
        user = User(telegram_id=123, subscription_until=naive_future)
        result = await is_user_subscribed(user)
        assert result is True
    
    @pytest.mark.unit
    async def test_timezone_aware_subscription_date(self):
        """Test handling of timezone-aware subscription dates."""
        aware_future = datetime.now(timezone.utc) + timedelta(days=5)
        user = User(telegram_id=123, subscription_until=aware_future)
        result = await is_user_subscribed(user)
        assert result is True


class TestGetSubscriptionKeyboard:
    """Test subscription keyboard generation."""
    
    @pytest.mark.unit
    @patch('bot.settings')
    def test_subscription_keyboard_structure(self, mock_settings):
        """Test that subscription keyboard has correct structure."""
        mock_settings.subscription_price = 5.99
        keyboard = get_subscription_keyboard()
        
        assert keyboard.inline_keyboard is not None
        assert len(keyboard.inline_keyboard) == 2  # Two rows
        assert len(keyboard.inline_keyboard[0]) == 1  # Subscribe button
        assert len(keyboard.inline_keyboard[1]) == 1  # Free trial button
    
    @pytest.mark.unit
    @patch('bot.settings')
    def test_subscription_button_text(self, mock_settings):
        """Test subscription button contains price."""
        mock_settings.subscription_price = 10.00
        keyboard = get_subscription_keyboard()
        
        subscribe_button = keyboard.inline_keyboard[0][0]
        assert "$10.0" in subscribe_button.text
        assert subscribe_button.callback_data == "subscribe"
    
    @pytest.mark.unit
    def test_free_trial_button(self):
        """Test free trial button."""
        keyboard = get_subscription_keyboard()
        trial_button = keyboard.inline_keyboard[1][0]
        
        assert "Free Trial" in trial_button.text
        assert trial_button.callback_data == "free_trial"


class TestGetProxyConfigText:
    """Test proxy configuration text generation."""
    
    @pytest.mark.unit
    def test_empty_config_list(self):
        """Test text generation with empty config list."""
        result = get_proxy_config_text([])
        assert result == "No proxy configurations available."
    
    @pytest.mark.unit
    @patch('bot.settings')
    def test_single_config_text(self, mock_settings):
        """Test text generation with single config."""
        mock_settings.mtg_secret = "test_mtg_secret"
        
        config = ProxyConfig(
            proxy_secret="test_secret_32_chars_long_here",
            server_address="test.server.com",
            port=443
        )
        
        result = get_proxy_config_text([config])
        
        assert "🔗 Your Proxy Configurations:" in result
        assert "Server 1:" in result
        assert "test.server.com" in result
        assert "443" in result
        assert "test_secret_32_chars_long_here" in result
        assert "test_mtg_secret" in result
        assert "tg://proxy?" in result
        assert "Setup Instructions:" in result
    
    @pytest.mark.unit
    @patch('bot.settings')
    def test_multiple_configs_text(self, mock_settings):
        """Test text generation with multiple configs."""
        mock_settings.mtg_secret = "test_mtg_secret"
        
        configs = [
            ProxyConfig(
                proxy_secret="secret1_32_chars_long_here_test",
                server_address="server1.test.com",
                port=443
            ),
            ProxyConfig(
                proxy_secret="secret2_32_chars_long_here_test",
                server_address="server2.test.com",
                port=8080
            )
        ]
        
        result = get_proxy_config_text(configs)
        
        assert "Server 1:" in result
        assert "Server 2:" in result
        assert "server1.test.com" in result
        assert "server2.test.com" in result
        assert "443" in result
        assert "8080" in result
        assert "secret1_32_chars_long_here_test" in result
        assert "secret2_32_chars_long_here_test" in result
    
    @pytest.mark.unit
    @patch('bot.settings')
    def test_config_text_format(self, mock_settings):
        """Test that config text includes all required fields."""
        mock_settings.mtg_secret = "test_secret"
        
        config = ProxyConfig(
            proxy_secret="proxy_secret_here",
            server_address="example.com",
            port=9999
        )
        
        result = get_proxy_config_text([config])
        
        # Check required fields are present
        assert "Server:" in result
        assert "Port:" in result
        assert "Secret:" in result
        assert "MTG Secret:" in result
        assert "Direct Link:" in result
        
        # Check tg:// link format
        expected_link = "tg://proxy?server=example.com&port=9999&secret=proxy_secret_here"
        assert expected_link in result


class TestGetUserByTelegramId:
    """Test user retrieval and creation."""
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_get_existing_user(self, db_session, test_user):
        """Test retrieving existing user."""
        result = await get_user_by_telegram_id(db_session, test_user.telegram_id)
        
        assert result.id == test_user.id
        assert result.telegram_id == test_user.telegram_id
        assert result.username == test_user.username
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_create_new_user(self, db_session):
        """Test creating new user when not exists."""
        new_telegram_id = 999888777
        
        result = await get_user_by_telegram_id(db_session, new_telegram_id)
        
        assert result.telegram_id == new_telegram_id
        assert result.id is not None
        assert result.is_active is True
        assert result.subscription_until is None
    
    @pytest.mark.unit
    @pytest.mark.database
    async def test_user_creation_persistence(self, db_session):
        """Test that created user persists in database."""
        telegram_id = 777666555
        
        # First call creates user
        user1 = await get_user_by_telegram_id(db_session, telegram_id)
        
        # Second call retrieves same user
        user2 = await get_user_by_telegram_id(db_session, telegram_id)
        
        assert user1.id == user2.id
        assert user1.telegram_id == user2.telegram_id