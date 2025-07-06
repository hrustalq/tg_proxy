"""Integration tests for bot handlers."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from bot import (
    start_command, help_command, config_command, status_command,
    subscribe_callback, free_trial_callback, get_config_callback,
    refresh_config_callback, successful_payment
)
from database import User, ProxyConfig, Payment


class TestStartCommand:
    """Test /start command handler (US-001)."""
    
    @pytest.mark.integration
    async def test_start_command_new_user(self, db_session, mock_message, test_settings):
        """Test US-001: New user receives welcome message and registration."""
        mock_message.from_user.id = 999888777
        mock_message.from_user.username = "newuser"
        mock_message.from_user.first_name = "New"
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await start_command(mock_message)
        
        # Verify user was created
        result = await db_session.execute(
            select(User).where(User.telegram_id == 999888777)
        )
        user = result.scalar_one_or_none()
        
        assert user is not None
        assert user.telegram_id == 999888777
        assert user.username == "newuser"
        assert user.first_name == "New"
        
        # Verify welcome message was sent
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Welcome to Telegram Proxy Bot" in call_args
        assert "newuser" in call_args or "New" in call_args
        assert "$5.0" in call_args  # Price from test settings
    
    @pytest.mark.integration
    async def test_start_command_subscribed_user(self, db_session, subscribed_user, mock_message, test_settings):
        """Test US-001: Subscribed user receives different welcome message."""
        mock_message.from_user.id = subscribed_user.telegram_id
        mock_message.from_user.username = subscribed_user.username
        mock_message.from_user.first_name = subscribed_user.first_name
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await start_command(mock_message)
        
        # Verify welcome back message was sent
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Welcome back" in call_args
        assert "subscription is active until" in call_args
        
        # Verify keyboard has config and extend options
        keyboard = mock_message.answer.call_args[1]['reply_markup']
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) == 2
    
    @pytest.mark.integration
    async def test_start_command_updates_user_info(self, db_session, test_user, mock_message, test_settings):
        """Test US-001: Start command updates user information."""
        mock_message.from_user.id = test_user.telegram_id
        mock_message.from_user.username = "updated_username"
        mock_message.from_user.first_name = "Updated Name"
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await start_command(mock_message)
        
        # Verify user info was updated
        await db_session.refresh(test_user)
        assert test_user.username == "updated_username"
        assert test_user.first_name == "Updated Name"


class TestHelpCommand:
    """Test /help command handler (US-016)."""
    
    @pytest.mark.integration
    async def test_help_command_new_user(self, db_session, mock_message, test_settings):
        """Test US-016: Help command for new user."""
        mock_message.from_user.id = 888777666
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await help_command(mock_message)
        
        # Verify help message was sent
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Telegram Proxy Bot Commands" in call_args
        assert "/start" in call_args
        assert "/config" in call_args
        assert "/status" in call_args
        assert "/help" in call_args
        assert "$5.0" in call_args  # Price from test settings
    
    @pytest.mark.integration
    async def test_help_command_subscribed_user(self, db_session, subscribed_user, mock_message, test_settings):
        """Test US-016: Help command for subscribed user shows different options."""
        mock_message.from_user.id = subscribed_user.telegram_id
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await help_command(mock_message)
        
        # Verify help message and keyboard for subscribed user
        mock_message.answer.assert_called_once()
        keyboard = mock_message.answer.call_args[1]['reply_markup']
        assert keyboard is not None
        
        # Should have config and status buttons for subscribed users
        buttons_text = []
        for row in keyboard.inline_keyboard:
            for button in row:
                buttons_text.append(button.text)
        
        assert any("Config" in text for text in buttons_text)
        assert any("Status" in text for text in buttons_text)


class TestConfigCommand:
    """Test /config command handler (US-006, US-007, US-013)."""
    
    @pytest.mark.integration
    async def test_config_command_no_subscription(self, db_session, test_user, mock_message, test_settings):
        """Test US-006, US-013: Config command blocked for unsubscribed user."""
        mock_message.from_user.id = test_user.telegram_id
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await config_command(mock_message)
        
        # Verify access denied message
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "don't have an active subscription" in call_args
    
    @pytest.mark.integration
    async def test_config_command_expired_subscription(self, db_session, expired_user, mock_message, test_settings):
        """Test US-006, US-013: Config command blocked for expired user."""
        mock_message.from_user.id = expired_user.telegram_id
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await config_command(mock_message)
        
        # Verify expired subscription message
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "subscription expired" in call_args
    
    @pytest.mark.integration
    async def test_config_command_auto_generates_configs(self, db_session, subscribed_user, mock_message, test_settings):
        """Test US-007: Config command auto-generates proxy configurations."""
        mock_message.from_user.id = subscribed_user.telegram_id
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await config_command(mock_message)
        
        # Verify configs were created
        result = await db_session.execute(
            select(ProxyConfig).where(ProxyConfig.user_id == subscribed_user.id)
        )
        configs = result.scalars().all()
        
        # Should have configs for all servers in test settings
        expected_servers = test_settings.get_proxy_servers()
        assert len(configs) == len(expected_servers)
        
        # Verify config message was sent
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Your Proxy Configurations" in call_args
        assert "tg://proxy?" in call_args
    
    @pytest.mark.integration
    async def test_config_command_existing_configs(self, db_session, subscribed_user, test_proxy_config, mock_message, test_settings):
        """Test US-006: Config command shows existing configurations."""
        mock_message.from_user.id = subscribed_user.telegram_id
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await config_command(mock_message)
        
        # Verify existing config is shown
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert test_proxy_config.server_address in call_args
        assert str(test_proxy_config.port) in call_args
        assert test_proxy_config.proxy_secret in call_args


class TestStatusCommand:
    """Test /status command handler (US-005)."""
    
    @pytest.mark.integration
    async def test_status_command_active_subscription(self, db_session, subscribed_user, mock_message, test_settings):
        """Test US-005: Status command shows active subscription details."""
        mock_message.from_user.id = subscribed_user.telegram_id
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await status_command(mock_message)
        
        # Verify status message
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Status: Active" in call_args
        assert "Expires:" in call_args
        assert "Time Left:" in call_args
        assert "days" in call_args
    
    @pytest.mark.integration
    async def test_status_command_expired_subscription(self, db_session, expired_user, mock_message, test_settings):
        """Test US-005: Status command shows expired subscription."""
        mock_message.from_user.id = expired_user.telegram_id
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await status_command(mock_message)
        
        # Verify expired status message
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Status: Expired" in call_args
        assert "Expired:" in call_args
    
    @pytest.mark.integration
    async def test_status_command_no_subscription(self, db_session, test_user, mock_message, test_settings):
        """Test US-005: Status command shows no subscription."""
        mock_message.from_user.id = test_user.telegram_id
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await status_command(mock_message)
        
        # Verify no subscription message
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Status: No subscription" in call_args


class TestSubscribeCallback:
    """Test subscribe callback handler (US-003)."""
    
    @pytest.mark.integration
    async def test_subscribe_callback_sends_invoice(self, mock_callback_query, test_settings):
        """Test US-003: Subscribe callback sends payment invoice."""
        mock_bot = AsyncMock()
        
        with patch('bot.bot', mock_bot), \
             patch('bot.settings', test_settings):
            
            await subscribe_callback(mock_callback_query)
        
        # Verify invoice was sent
        mock_bot.send_invoice.assert_called_once()
        call_args = mock_bot.send_invoice.call_args
        
        assert call_args[1]['title'] == "Telegram Proxy Subscription"
        assert "30 days access" in call_args[1]['description']
        assert call_args[1]['currency'] == "RUB"
        assert call_args[1]['prices'][0].amount == 500  # $5.00 in cents
    
    @pytest.mark.integration
    async def test_subscribe_callback_error_handling(self, mock_callback_query, test_settings):
        """Test US-003: Subscribe callback handles errors gracefully."""
        mock_bot = AsyncMock()
        mock_bot.send_invoice.side_effect = Exception("Payment error")
        
        with patch('bot.bot', mock_bot), \
             patch('bot.settings', test_settings):
            
            await subscribe_callback(mock_callback_query)
        
        # Verify error was handled
        mock_callback_query.answer.assert_called_once()
        call_args = mock_callback_query.answer.call_args[0][0]
        assert "Error creating payment invoice" in call_args


class TestFreeTrialCallback:
    """Test free trial callback handler (US-002)."""
    
    @pytest.mark.integration
    async def test_free_trial_new_user(self, db_session, mock_callback_query, test_settings):
        """Test US-002: New user can activate free trial."""
        mock_callback_query.from_user.id = 555444333
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await free_trial_callback(mock_callback_query)
        
        # Verify user was created with trial
        result = await db_session.execute(
            select(User).where(User.telegram_id == 555444333)
        )
        user = result.scalar_one_or_none()
        
        assert user is not None
        assert user.subscription_until is not None
        assert user.subscription_until > datetime.now(timezone.utc)
        
        # Verify trial confirmation message
        mock_callback_query.message.edit_text.assert_called_once()
        call_args = mock_callback_query.message.edit_text.call_args[0][0]
        assert "Free trial activated" in call_args
    
    @pytest.mark.integration
    async def test_free_trial_already_subscribed(self, db_session, subscribed_user, mock_callback_query, test_settings):
        """Test US-002: Subscribed user cannot get trial."""
        mock_callback_query.from_user.id = subscribed_user.telegram_id
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await free_trial_callback(mock_callback_query)
        
        # Verify trial was denied
        mock_callback_query.answer.assert_called_once()
        call_args = mock_callback_query.answer.call_args[0][0]
        assert "already have an active subscription" in call_args
    
    @pytest.mark.integration
    async def test_free_trial_already_used(self, db_session, trial_user, mock_callback_query, test_settings):
        """Test US-002: User who used trial cannot get another."""
        mock_callback_query.from_user.id = trial_user.telegram_id
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await free_trial_callback(mock_callback_query)
        
        # Verify trial was denied
        mock_callback_query.answer.assert_called_once()
        call_args = mock_callback_query.answer.call_args[0][0]
        assert "only available once per user" in call_args


class TestRefreshConfigCallback:
    """Test refresh config callback handler (US-008)."""
    
    @pytest.mark.integration
    async def test_refresh_config_subscribed_user(self, db_session, subscribed_user, test_proxy_config, mock_callback_query, test_settings):
        """Test US-008: Subscribed user can refresh proxy secrets."""
        mock_callback_query.from_user.id = subscribed_user.telegram_id
        original_secret = test_proxy_config.proxy_secret
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await refresh_config_callback(mock_callback_query)
        
        # Verify old config was deleted and new ones created
        result = await db_session.execute(
            select(ProxyConfig).where(ProxyConfig.user_id == subscribed_user.id)
        )
        new_configs = result.scalars().all()
        
        # Should have new configs
        assert len(new_configs) > 0
        # Secrets should be different
        for config in new_configs:
            assert config.proxy_secret != original_secret
        
        # Verify refresh confirmation
        mock_callback_query.message.edit_text.assert_called_once()
        mock_callback_query.answer.assert_called_once()
        assert "Configuration refreshed" in mock_callback_query.answer.call_args[0][0]
    
    @pytest.mark.integration
    async def test_refresh_config_expired_user(self, db_session, expired_user, mock_callback_query, test_settings):
        """Test US-008: Expired user cannot refresh configs."""
        mock_callback_query.from_user.id = expired_user.telegram_id
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await refresh_config_callback(mock_callback_query)
        
        # Verify refresh was denied
        mock_callback_query.answer.assert_called_once()
        call_args = mock_callback_query.answer.call_args[0][0]
        assert "Subscription expired" in call_args