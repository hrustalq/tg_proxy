"""Tests for admin functionality and server management."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, Mock, patch

from aiogram.types import Message, CallbackQuery, User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot import (
    is_admin, admin_required, admin_command, admin_servers_command,
    admin_stats_command, admin_users_command, admin_payments_command,
    handle_server_add_command, handle_grant_sub_command
)
from database import User, ProxyServer, Payment, ProxyConfig
from config import settings


class TestAdminAuthentication:
    """Test admin authentication and authorization."""
    
    @pytest.mark.unit
    def test_is_admin_with_valid_admin_id(self):
        """Test admin identification with valid admin ID."""
        with patch.object(settings, 'get_admin_ids', return_value=[123456, 789012]):
            assert is_admin(123456) is True
            assert is_admin(789012) is True
    
    @pytest.mark.unit
    def test_is_admin_with_invalid_admin_id(self):
        """Test admin identification with non-admin ID."""
        with patch.object(settings, 'get_admin_ids', return_value=[123456, 789012]):
            assert is_admin(999999) is False
            assert is_admin(111111) is False
    
    @pytest.mark.unit
    def test_is_admin_with_exception(self):
        """Test admin identification when config fails."""
        with patch.object(settings, 'get_admin_ids', side_effect=Exception("Config error")):
            assert is_admin(123456) is False
    
    @pytest.mark.unit
    async def test_admin_required_decorator_allows_admin(self):
        """Test admin_required decorator allows admin users."""
        @admin_required
        async def test_function(message):
            return "success"
        
        # Mock message with admin user
        mock_message = Mock()
        mock_message.from_user.id = 123456
        mock_message.answer = AsyncMock()
        
        with patch('bot.is_admin', return_value=True):
            result = await test_function(mock_message)
            assert result == "success"
            mock_message.answer.assert_not_called()
    
    @pytest.mark.unit
    async def test_admin_required_decorator_blocks_non_admin(self):
        """Test admin_required decorator blocks non-admin users."""
        @admin_required
        async def test_function(message):
            return "success"
        
        # Mock message with non-admin user
        mock_message = Mock()
        mock_message.from_user.id = 999999
        mock_message.answer = AsyncMock()
        
        with patch('bot.is_admin', return_value=False):
            result = await test_function(mock_message)
            assert result is None
            mock_message.answer.assert_called_once_with("❌ Access denied. Admin privileges required.")
    
    @pytest.mark.unit
    async def test_admin_required_decorator_blocks_callback_query(self):
        """Test admin_required decorator blocks non-admin callback queries."""
        @admin_required
        async def test_function(callback_query):
            return "success"
        
        # Mock callback query with non-admin user
        mock_callback = Mock()
        mock_callback.from_user.id = 999999
        mock_callback.answer = AsyncMock()
        
        with patch('bot.is_admin', return_value=False):
            result = await test_function(mock_callback)
            assert result is None
            mock_callback.answer.assert_called_once_with("❌ Access denied. Admin privileges required.", show_alert=True)


class TestProxyServerModel:
    """Test ProxyServer database model."""
    
    @pytest.mark.database
    async def test_create_proxy_server(self, db_session: AsyncSession):
        """Test creating a new proxy server."""
        server = ProxyServer(
            address="proxy.example.com",
            port=443,
            description="Test Server",
            location="US",
            max_users=500,
            is_active=True
        )
        
        db_session.add(server)
        await db_session.commit()
        await db_session.refresh(server)
        
        assert server.id is not None
        assert server.address == "proxy.example.com"
        assert server.port == 443
        assert server.description == "Test Server"
        assert server.location == "US"
        assert server.max_users == 500
        assert server.is_active is True
        assert server.created_at is not None
        assert server.updated_at is not None
    
    @pytest.mark.database
    async def test_proxy_server_unique_address(self, db_session: AsyncSession):
        """Test that proxy server addresses must be unique."""
        server1 = ProxyServer(address="proxy.test.com", port=443)
        server2 = ProxyServer(address="proxy.test.com", port=8080)
        
        db_session.add(server1)
        await db_session.commit()
        
        db_session.add(server2)
        with pytest.raises(Exception):  # Should raise integrity error
            await db_session.commit()
    
    @pytest.mark.database
    async def test_proxy_server_default_values(self, db_session: AsyncSession):
        """Test proxy server default values."""
        server = ProxyServer(address="default.test.com")
        
        db_session.add(server)
        await db_session.commit()
        await db_session.refresh(server)
        
        assert server.port == 443  # Default port
        assert server.is_active is True  # Default active
        assert server.max_users == 1000  # Default max users
        assert server.description is None
        assert server.location is None


class TestAdminCommands:
    """Test admin command handlers."""
    
    @pytest.mark.integration
    async def test_admin_command_creates_main_panel(self):
        """Test admin command creates main admin panel."""
        mock_message = Mock()
        mock_message.answer = AsyncMock()
        
        with patch('bot.is_admin', return_value=True):
            await admin_command(mock_message)
            
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args
            assert "🔐 **Admin Panel**" in call_args[0][0]
            assert "reply_markup" in call_args[1]
    
    @pytest.mark.integration
    async def test_admin_servers_command_initializes_from_config(self, db_session: AsyncSession):
        """Test admin_servers_command initializes servers from config."""
        mock_message = Mock()
        mock_message.answer = AsyncMock()
        
        # Mock get_proxy_servers to return test servers
        with patch.object(settings, 'get_proxy_servers', return_value=["server1.com:443", "server2.com"]):
            with patch('bot.get_db', return_value=[db_session]):
                with patch('bot.is_admin', return_value=True):
                    await admin_servers_command(mock_message)
        
        # Verify servers were created in database
        result = await db_session.execute(select(ProxyServer))
        servers = result.scalars().all()
        
        assert len(servers) == 2
        assert servers[0].address == "server1.com"
        assert servers[0].port == 443
        assert servers[1].address == "server2.com"
        assert servers[1].port == 443  # Default port
    
    @pytest.mark.integration
    async def test_admin_stats_command_shows_statistics(self, db_session: AsyncSession):
        """Test admin_stats_command displays bot statistics."""
        # Create test data
        user1 = User(telegram_id=111, subscription_until=datetime.now(timezone.utc) + timedelta(days=5))
        user2 = User(telegram_id=222, subscription_until=datetime.now(timezone.utc) - timedelta(days=1))
        user3 = User(telegram_id=333, subscription_until=None)
        
        payment1 = Payment(user_id=1, amount=5.00, status="completed")
        payment2 = Payment(user_id=2, amount=5.00, status="pending")
        
        server1 = ProxyServer(address="active.com", is_active=True)
        server2 = ProxyServer(address="inactive.com", is_active=False)
        
        db_session.add_all([user1, user2, user3, payment1, payment2, server1, server2])
        await db_session.commit()
        
        mock_message = Mock()
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                await admin_stats_command(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        stats_text = call_args[0][0]
        
        assert "📊 **Bot Statistics**" in stats_text
        assert "Total Users: 3" in stats_text
        assert "Active Subscribers: 1" in stats_text
        assert "Total Revenue: $5.00" in stats_text
        assert "Total Servers: 2" in stats_text
        assert "Active Servers: 1" in stats_text
    
    @pytest.mark.integration
    async def test_admin_users_command_shows_recent_users(self, db_session: AsyncSession):
        """Test admin_users_command displays recent users."""
        # Create test users
        for i in range(12):  # More than 10 to test limit
            user = User(
                telegram_id=1000 + i,
                first_name=f"User{i}",
                username=f"user{i}",
                subscription_until=datetime.now(timezone.utc) + timedelta(days=i) if i % 2 == 0 else None
            )
            db_session.add(user)
        
        await db_session.commit()
        
        mock_message = Mock()
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                with patch('bot.is_user_subscribed', side_effect=lambda u: u.subscription_until is not None):
                    await admin_users_command(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        users_text = call_args[0][0]
        
        assert "👥 **User Management**" in users_text
        assert "Recent Users (Last 10):" in users_text
        # Should show only 10 users even though 12 were created
        assert users_text.count("ID: ") == 10
    
    @pytest.mark.integration
    async def test_admin_payments_command_shows_payment_data(self, db_session: AsyncSession):
        """Test admin_payments_command displays payment information."""
        # Create test payments
        for i in range(5):
            payment = Payment(
                user_id=1,
                amount=5.00 + i,
                currency="RUB",
                status="completed" if i % 2 == 0 else "pending",
                provider_payment_id=f"pay_{i}"
            )
            db_session.add(payment)
        
        await db_session.commit()
        
        mock_message = Mock()
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                await admin_payments_command(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        payments_text = call_args[0][0]
        
        assert "💰 **Payment Management**" in payments_text
        assert "Total Revenue:" in payments_text
        assert "Completed Payments: 3" in payments_text
        assert "Pending Payments: 2" in payments_text


class TestServerAddCommand:
    """Test server_add command functionality."""
    
    @pytest.mark.integration
    async def test_server_add_valid_command(self, db_session: AsyncSession):
        """Test adding a server with valid command."""
        mock_message = Mock()
        mock_message.text = "server_add proxy.new.com 8080 New Test Server"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                await handle_server_add_command(mock_message)
        
        # Verify server was added to database
        result = await db_session.execute(select(ProxyServer).where(ProxyServer.address == "proxy.new.com"))
        server = result.scalar_one_or_none()
        
        assert server is not None
        assert server.address == "proxy.new.com"
        assert server.port == 8080
        assert server.description == "New Test Server"
        assert server.is_active is True
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "✅ **Server Added Successfully**" in call_args[0][0]
    
    @pytest.mark.integration
    async def test_server_add_minimal_command(self, db_session: AsyncSession):
        """Test adding a server with minimal information."""
        mock_message = Mock()
        mock_message.text = "server_add minimal.com 443"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                await handle_server_add_command(mock_message)
        
        result = await db_session.execute(select(ProxyServer).where(ProxyServer.address == "minimal.com"))
        server = result.scalar_one_or_none()
        
        assert server is not None
        assert server.address == "minimal.com"
        assert server.port == 443
        assert server.description == "Server minimal.com"  # Auto-generated description
    
    @pytest.mark.integration
    async def test_server_add_duplicate_address(self, db_session: AsyncSession):
        """Test adding a server with duplicate address."""
        # Add initial server
        existing_server = ProxyServer(address="existing.com", port=443)
        db_session.add(existing_server)
        await db_session.commit()
        
        mock_message = Mock()
        mock_message.text = "server_add existing.com 8080"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                await handle_server_add_command(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "❌ Server `existing.com` already exists" in call_args[0][0]
    
    @pytest.mark.unit
    async def test_server_add_invalid_format(self):
        """Test server_add with invalid command format."""
        mock_message = Mock()
        mock_message.text = "server_add incomplete"
        mock_message.answer = AsyncMock()
        
        with patch('bot.is_admin', return_value=True):
            await handle_server_add_command(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "❌ Invalid format" in call_args[0][0]
    
    @pytest.mark.unit
    async def test_server_add_invalid_port(self):
        """Test server_add with invalid port number."""
        mock_message = Mock()
        mock_message.text = "server_add test.com invalid_port"
        mock_message.answer = AsyncMock()
        
        with patch('bot.is_admin', return_value=True):
            await handle_server_add_command(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "❌ Invalid port number" in call_args[0][0]


class TestGrantSubCommand:
    """Test grant_sub command functionality."""
    
    @pytest.mark.integration
    async def test_grant_sub_new_subscription(self, db_session: AsyncSession):
        """Test granting subscription to user without existing subscription."""
        # Create test user
        user = User(telegram_id=555555, first_name="Test", username="testuser")
        db_session.add(user)
        await db_session.commit()
        
        mock_message = Mock()
        mock_message.text = "grant_sub 555555 30"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                await handle_grant_sub_command(mock_message)
        
        # Refresh user to get updated data
        await db_session.refresh(user)
        
        assert user.subscription_until is not None
        # Subscription should be approximately 30 days from now
        expected_expiry = datetime.now(timezone.utc) + timedelta(days=30)
        time_diff = abs((user.subscription_until - expected_expiry).total_seconds())
        assert time_diff < 60  # Within 1 minute tolerance
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "✅ **Subscription Granted**" in call_args[0][0]
        assert "Days Added: 30" in call_args[0][0]
    
    @pytest.mark.integration
    async def test_grant_sub_extend_existing(self, db_session: AsyncSession):
        """Test extending existing active subscription."""
        # Create user with existing subscription
        current_expiry = datetime.now(timezone.utc) + timedelta(days=10)
        user = User(telegram_id=666666, first_name="Existing", subscription_until=current_expiry)
        db_session.add(user)
        await db_session.commit()
        
        mock_message = Mock()
        mock_message.text = "grant_sub 666666 15"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                await handle_grant_sub_command(mock_message)
        
        await db_session.refresh(user)
        
        # Should extend existing subscription by 15 days
        expected_expiry = current_expiry + timedelta(days=15)
        time_diff = abs((user.subscription_until - expected_expiry).total_seconds())
        assert time_diff < 60  # Within 1 minute tolerance
    
    @pytest.mark.integration
    async def test_grant_sub_user_not_found(self, db_session: AsyncSession):
        """Test granting subscription to non-existent user."""
        mock_message = Mock()
        mock_message.text = "grant_sub 999999 30"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                await handle_grant_sub_command(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "❌ User with ID `999999` not found" in call_args[0][0]
    
    @pytest.mark.unit
    async def test_grant_sub_invalid_format(self):
        """Test grant_sub with invalid command format."""
        mock_message = Mock()
        mock_message.text = "grant_sub 123456"  # Missing days
        mock_message.answer = AsyncMock()
        
        with patch('bot.is_admin', return_value=True):
            await handle_grant_sub_command(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "❌ Invalid format" in call_args[0][0]
    
    @pytest.mark.unit
    async def test_grant_sub_negative_days(self):
        """Test grant_sub with negative days."""
        mock_message = Mock()
        mock_message.text = "grant_sub 123456 -5"
        mock_message.answer = AsyncMock()
        
        with patch('bot.is_admin', return_value=True):
            await handle_grant_sub_command(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "❌ Days must be a positive number" in call_args[0][0]
    
    @pytest.mark.unit
    async def test_grant_sub_invalid_user_id(self):
        """Test grant_sub with invalid user ID format."""
        mock_message = Mock()
        mock_message.text = "grant_sub invalid_id 30"
        mock_message.answer = AsyncMock()
        
        with patch('bot.is_admin', return_value=True):
            await handle_grant_sub_command(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "❌ Invalid user ID or days" in call_args[0][0]


class TestAdminCallbackHandlers:
    """Test admin callback query handlers."""
    
    @pytest.mark.unit
    async def test_admin_servers_callback(self):
        """Test admin_servers callback handler."""
        mock_callback = Mock()
        mock_callback.message = Mock()
        mock_callback.answer = AsyncMock()
        
        with patch('bot.admin_servers_command') as mock_command:
            with patch('bot.is_admin', return_value=True):
                from bot import admin_servers_callback
                await admin_servers_callback(mock_callback)
        
        mock_command.assert_called_once_with(mock_callback.message)
        mock_callback.answer.assert_called_once()
    
    @pytest.mark.unit
    async def test_admin_stats_callback(self):
        """Test admin_stats callback handler."""
        mock_callback = Mock()
        mock_callback.message = Mock()
        mock_callback.answer = AsyncMock()
        
        with patch('bot.admin_stats_command') as mock_command:
            with patch('bot.is_admin', return_value=True):
                from bot import admin_stats_callback
                await admin_stats_callback(mock_callback)
        
        mock_command.assert_called_once_with(mock_callback.message)
        mock_callback.answer.assert_called_once()
    
    @pytest.mark.integration
    async def test_admin_add_server_callback_shows_instructions(self):
        """Test admin_add_server callback shows instructions."""
        mock_callback = Mock()
        mock_callback.message = Mock()
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()
        
        with patch('bot.is_admin', return_value=True):
            from bot import admin_add_server_callback
            await admin_add_server_callback(mock_callback)
        
        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args
        assert "🖥️ **Add New Proxy Server**" in call_args[0][0]
        assert "server_add <address> <port>" in call_args[0][0]
        mock_callback.answer.assert_called_once()
    
    @pytest.mark.integration
    async def test_admin_grant_sub_callback_shows_instructions(self):
        """Test admin_grant_sub callback shows instructions."""
        mock_callback = Mock()
        mock_callback.message = Mock()
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()
        
        with patch('bot.is_admin', return_value=True):
            from bot import admin_grant_sub_callback
            await admin_grant_sub_callback(mock_callback)
        
        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args
        assert "🎁 **Grant Subscription**" in call_args[0][0]
        assert "grant_sub <user_id> <days>" in call_args[0][0]
        mock_callback.answer.assert_called_once()


class TestServerManagementOperations:
    """Test server management operations."""
    
    @pytest.mark.integration
    async def test_server_toggle_activation(self, db_session: AsyncSession):
        """Test server activation/deactivation toggle."""
        # Create test server
        server = ProxyServer(address="toggle.test.com", port=443, is_active=True)
        db_session.add(server)
        await db_session.commit()
        await db_session.refresh(server)
        
        mock_callback = Mock()
        mock_callback.data = f"admin_toggle_server_{server.id}"
        mock_callback.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                with patch('bot.admin_config_server_detail_callback') as mock_refresh:
                    from bot import admin_toggle_server_callback
                    await admin_toggle_server_callback(mock_callback)
        
        # Verify server status was toggled
        await db_session.refresh(server)
        assert server.is_active is False  # Should be deactivated
        
        mock_callback.answer.assert_called_once()
        call_args = mock_callback.answer.call_args
        assert "deactivated successfully" in call_args[0][0]
        mock_refresh.assert_called_once_with(mock_callback)
    
    @pytest.mark.integration
    async def test_server_removal_deactivation(self, db_session: AsyncSession):
        """Test server removal (deactivation)."""
        # Create test server
        server = ProxyServer(address="remove.test.com", port=443, is_active=True)
        db_session.add(server)
        await db_session.commit()
        await db_session.refresh(server)
        
        mock_callback = Mock()
        mock_callback.data = f"admin_remove_server_{server.id}"
        mock_callback.message = Mock()
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                from bot import admin_remove_server_confirm_callback
                await admin_remove_server_confirm_callback(mock_callback)
        
        # Verify server was deactivated (not deleted)
        await db_session.refresh(server)
        assert server.is_active is False
        
        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args
        assert "✅ **Server Removed Successfully**" in call_args[0][0]
        assert "deactivated" in call_args[0][0]


class TestAdminErrorHandling:
    """Test admin functionality error handling."""
    
    @pytest.mark.unit
    async def test_server_add_database_error(self):
        """Test server_add handles database errors gracefully."""
        mock_message = Mock()
        mock_message.text = "server_add error.com 443"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db', side_effect=Exception("Database error")):
            with patch('bot.is_admin', return_value=True):
                with patch('bot.logger') as mock_logger:
                    await handle_server_add_command(mock_message)
        
        mock_logger.error.assert_called_once()
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "❌ Error adding server" in call_args[0][0]
    
    @pytest.mark.unit
    async def test_grant_sub_database_error(self):
        """Test grant_sub handles database errors gracefully."""
        mock_message = Mock()
        mock_message.text = "grant_sub 123456 30"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db', side_effect=Exception("Database error")):
            with patch('bot.is_admin', return_value=True):
                with patch('bot.logger') as mock_logger:
                    await handle_grant_sub_command(mock_message)
        
        mock_logger.error.assert_called_once()
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "❌ Error granting subscription" in call_args[0][0]
    
    @pytest.mark.integration
    async def test_server_toggle_not_found(self):
        """Test server toggle handles non-existent server."""
        mock_callback = Mock()
        mock_callback.data = "admin_toggle_server_99999"  # Non-existent ID
        mock_callback.answer = AsyncMock()
        
        with patch('bot.get_db') as mock_db:
            mock_session = AsyncMock()
            mock_session.execute.return_value.scalar_one_or_none.return_value = None
            mock_db.return_value = [mock_session]
            
            with patch('bot.is_admin', return_value=True):
                from bot import admin_toggle_server_callback
                await admin_toggle_server_callback(mock_callback)
        
        mock_callback.answer.assert_called_once_with("Server not found!", show_alert=True)


class TestAdminIntegration:
    """Integration tests for admin functionality."""
    
    @pytest.mark.integration
    async def test_complete_server_management_workflow(self, db_session: AsyncSession):
        """Test complete server management workflow."""
        # 1. Add server via command
        add_message = Mock()
        add_message.text = "server_add workflow.com 8080 Workflow Test"
        add_message.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                await handle_server_add_command(add_message)
        
        # Verify server was added
        result = await db_session.execute(select(ProxyServer).where(ProxyServer.address == "workflow.com"))
        server = result.scalar_one_or_none()
        assert server is not None
        assert server.is_active is True
        
        # 2. View servers list
        list_message = Mock()
        list_message.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                await admin_servers_command(list_message)
        
        call_args = list_message.answer.call_args
        assert "workflow.com:8080" in call_args[0][0]
        assert "✅ Active" in call_args[0][0]
        
        # 3. Toggle server status
        toggle_callback = Mock()
        toggle_callback.data = f"admin_toggle_server_{server.id}"
        toggle_callback.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                with patch('bot.admin_config_server_detail_callback'):
                    from bot import admin_toggle_server_callback
                    await admin_toggle_server_callback(toggle_callback)
        
        # Verify server was deactivated
        await db_session.refresh(server)
        assert server.is_active is False
    
    @pytest.mark.integration
    async def test_complete_user_management_workflow(self, db_session: AsyncSession):
        """Test complete user management workflow."""
        # 1. Create test user
        user = User(telegram_id=777777, first_name="Workflow", username="workflow")
        db_session.add(user)
        await db_session.commit()
        
        # 2. Grant subscription
        grant_message = Mock()
        grant_message.text = "grant_sub 777777 15"
        grant_message.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                await handle_grant_sub_command(grant_message)
        
        # Verify subscription was granted
        await db_session.refresh(user)
        assert user.subscription_until is not None
        
        # 3. View users list
        users_message = Mock()
        users_message.answer = AsyncMock()
        
        with patch('bot.get_db', return_value=[db_session]):
            with patch('bot.is_admin', return_value=True):
                with patch('bot.is_user_subscribed', return_value=True):
                    await admin_users_command(users_message)
        
        call_args = users_message.answer.call_args
        assert "ID: 777777" in call_args[0][0]
        assert "Workflow (@workflow)" in call_args[0][0]
        assert "Subscribed: ✅" in call_args[0][0]