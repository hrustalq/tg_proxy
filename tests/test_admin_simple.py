"""Simplified tests for admin functionality."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy import select

from database import User, ProxyServer, Payment, ProxyConfig


class TestAdminAuthentication:
    """Test admin authentication."""
    
    def test_is_admin_function_exists(self):
        """Test that is_admin function can be imported."""
        from bot import is_admin
        assert callable(is_admin)
    
    def test_admin_required_decorator_exists(self):
        """Test that admin_required decorator can be imported."""
        from bot import admin_required
        assert callable(admin_required)


class TestProxyServerModel:
    """Test ProxyServer database model."""
    
    @pytest.mark.asyncio
    async def test_create_proxy_server(self, db_session):
        """Test creating a new proxy server."""
        server = ProxyServer(
            address="test.example.com",
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
        assert server.address == "test.example.com"
        assert server.port == 443
        assert server.description == "Test Server"
        assert server.location == "US"
        assert server.max_users == 500
        assert server.is_active is True
        assert server.created_at is not None
        assert server.updated_at is not None
    
    @pytest.mark.asyncio
    async def test_proxy_server_default_values(self, db_session):
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
    
    @pytest.mark.asyncio
    async def test_proxy_server_queries(self, db_session):
        """Test querying proxy servers."""
        # Create test servers
        server1 = ProxyServer(address="active.com", is_active=True)
        server2 = ProxyServer(address="inactive.com", is_active=False)
        
        db_session.add_all([server1, server2])
        await db_session.commit()
        
        # Query active servers
        result = await db_session.execute(
            select(ProxyServer).where(ProxyServer.is_active == True)
        )
        active_servers = result.scalars().all()
        
        assert len(active_servers) == 1
        assert active_servers[0].address == "active.com"
        
        # Query all servers
        result = await db_session.execute(select(ProxyServer))
        all_servers = result.scalars().all()
        
        assert len(all_servers) == 2


class TestAdminCommands:
    """Test admin command functionality."""
    
    @pytest.mark.asyncio
    async def test_admin_commands_import(self):
        """Test that admin commands can be imported."""
        from bot import (
            admin_command, admin_servers_command, admin_stats_command,
            admin_users_command, admin_payments_command
        )
        
        assert callable(admin_command)
        assert callable(admin_servers_command)
        assert callable(admin_stats_command)
        assert callable(admin_users_command)
        assert callable(admin_payments_command)
    
    @pytest.mark.asyncio 
    async def test_server_add_command_import(self):
        """Test that server add command can be imported."""
        from bot import handle_server_add_command
        assert callable(handle_server_add_command)
    
    @pytest.mark.asyncio
    async def test_grant_sub_command_import(self):
        """Test that grant subscription command can be imported."""
        from bot import handle_grant_sub_command
        assert callable(handle_grant_sub_command)


class TestServerAddFunctionality:
    """Test server_add command functionality."""
    
    @pytest.mark.asyncio
    async def test_server_creation_logic(self, db_session):
        """Test the logic of creating a server directly."""
        # Simulate what server_add command does
        address = "new.server.com"
        port = 8080
        description = "Test Server"
        
        # Check if server exists (should not)
        result = await db_session.execute(
            select(ProxyServer).where(ProxyServer.address == address)
        )
        existing_server = result.scalar_one_or_none()
        assert existing_server is None
        
        # Create new server
        server = ProxyServer(
            address=address,
            port=port,
            description=description,
            is_active=True
        )
        db_session.add(server)
        await db_session.commit()
        await db_session.refresh(server)
        
        # Verify server was created
        assert server.id is not None
        assert server.address == address
        assert server.port == port
        assert server.description == description
        assert server.is_active is True
    
    @pytest.mark.asyncio
    async def test_duplicate_server_prevention(self, db_session):
        """Test that duplicate servers are prevented."""
        address = "duplicate.com"
        
        # Create first server
        server1 = ProxyServer(address=address, port=443)
        db_session.add(server1)
        await db_session.commit()
        
        # Try to create duplicate
        server2 = ProxyServer(address=address, port=8080)
        db_session.add(server2)
        
        # This should raise an integrity error due to unique constraint
        with pytest.raises(Exception):
            await db_session.commit()


class TestGrantSubFunctionality:
    """Test grant_sub command functionality."""
    
    @pytest.mark.asyncio
    async def test_grant_subscription_logic(self, db_session):
        """Test the logic of granting subscription directly."""
        # Create test user
        user = User(telegram_id=123456, first_name="Test", username="test")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Simulate granting subscription
        days = 30
        current_time = datetime.now(timezone.utc)
        
        # User has no existing subscription
        assert user.subscription_until is None
        
        # Grant new subscription
        user.subscription_until = current_time + timedelta(days=days)
        await db_session.commit()
        
        # Verify subscription was granted
        await db_session.refresh(user)
        assert user.subscription_until is not None
        
        # Check subscription duration
        expected_expiry = current_time + timedelta(days=days)
        time_diff = abs((user.subscription_until - expected_expiry).total_seconds())
        assert time_diff < 60  # Within 1 minute tolerance
    
    @pytest.mark.asyncio
    async def test_extend_existing_subscription(self, db_session):
        """Test extending existing subscription."""
        # Create user with existing subscription
        current_expiry = datetime.now(timezone.utc) + timedelta(days=10)
        user = User(
            telegram_id=789012,
            first_name="Existing",
            subscription_until=current_expiry
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Extend subscription by 15 days
        additional_days = 15
        user.subscription_until = current_expiry + timedelta(days=additional_days)
        await db_session.commit()
        
        # Verify extension
        await db_session.refresh(user)
        expected_expiry = current_expiry + timedelta(days=additional_days)
        time_diff = abs((user.subscription_until - expected_expiry).total_seconds())
        assert time_diff < 60  # Within 1 minute tolerance


class TestAdminStatistics:
    """Test admin statistics functionality."""
    
    @pytest.mark.asyncio
    async def test_statistics_data_collection(self, db_session):
        """Test collecting statistics data."""
        # Create test data
        
        # Users with different subscription states
        user1 = User(
            telegram_id=111,
            subscription_until=datetime.now(timezone.utc) + timedelta(days=5)
        )
        user2 = User(
            telegram_id=222,
            subscription_until=datetime.now(timezone.utc) - timedelta(days=1)
        )
        user3 = User(telegram_id=333, subscription_until=None)
        
        # Payments
        payment1 = Payment(user_id=1, amount=5.00, status="completed")
        payment2 = Payment(user_id=2, amount=5.00, status="pending")
        payment3 = Payment(user_id=1, amount=5.00, status="completed")
        
        # Servers
        server1 = ProxyServer(address="active1.com", is_active=True)
        server2 = ProxyServer(address="active2.com", is_active=True)
        server3 = ProxyServer(address="inactive.com", is_active=False)
        
        # Proxy configs
        config1 = ProxyConfig(user_id=1, proxy_secret="secret1", server_address="test1.com", port=443)
        config2 = ProxyConfig(user_id=1, proxy_secret="secret2", server_address="test2.com", port=443)
        
        db_session.add_all([
            user1, user2, user3, payment1, payment2, payment3,
            server1, server2, server3, config1, config2
        ])
        await db_session.commit()
        
        # Collect statistics
        
        # Total users
        total_users_result = await db_session.execute(select(User))
        total_users = len(total_users_result.scalars().all())
        assert total_users == 3
        
        # Active subscribers
        active_users_result = await db_session.execute(
            select(User).where(User.subscription_until > datetime.now(timezone.utc))
        )
        active_subscribers = len(active_users_result.scalars().all())
        assert active_subscribers == 1
        
        # Payment statistics
        completed_payments_result = await db_session.execute(
            select(Payment).where(Payment.status == "completed")
        )
        completed_payments = completed_payments_result.scalars().all()
        total_revenue = sum(p.amount for p in completed_payments)
        assert len(completed_payments) == 2
        assert total_revenue == 10.00
        
        # Server statistics
        servers_result = await db_session.execute(select(ProxyServer))
        all_servers = servers_result.scalars().all()
        active_servers = [s for s in all_servers if s.is_active]
        assert len(all_servers) == 3
        assert len(active_servers) == 2
        
        # Config statistics
        configs_result = await db_session.execute(select(ProxyConfig))
        total_configs = len(configs_result.scalars().all())
        assert total_configs == 2


class TestServerManagement:
    """Test server management operations."""
    
    @pytest.mark.asyncio
    async def test_server_toggle_logic(self, db_session):
        """Test server activation/deactivation logic."""
        # Create test server
        server = ProxyServer(address="toggle.test.com", port=443, is_active=True)
        db_session.add(server)
        await db_session.commit()
        await db_session.refresh(server)
        
        # Verify initial state
        assert server.is_active is True
        
        # Toggle to inactive
        server.is_active = not server.is_active
        server.updated_at = datetime.now(timezone.utc)
        await db_session.commit()
        
        # Verify toggle
        await db_session.refresh(server)
        assert server.is_active is False
        
        # Toggle back to active
        server.is_active = not server.is_active
        server.updated_at = datetime.now(timezone.utc)
        await db_session.commit()
        
        # Verify second toggle
        await db_session.refresh(server)
        assert server.is_active is True
    
    @pytest.mark.asyncio
    async def test_server_removal_logic(self, db_session):
        """Test server removal (deactivation) logic."""
        # Create test server
        server = ProxyServer(address="remove.test.com", port=443, is_active=True)
        db_session.add(server)
        await db_session.commit()
        await db_session.refresh(server)
        
        # Verify initial state
        assert server.is_active is True
        
        # Simulate removal (deactivation)
        server.is_active = False
        await db_session.commit()
        
        # Verify deactivation (not deletion)
        await db_session.refresh(server)
        assert server.is_active is False
        assert server.id is not None  # Server still exists


class TestAdminIntegration:
    """Integration tests for admin functionality."""
    
    @pytest.mark.asyncio
    async def test_complete_workflow_simulation(self, db_session):
        """Test a complete admin workflow simulation."""
        # 1. Create initial data
        user = User(telegram_id=555666, first_name="Workflow", username="workflow")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # 2. Add server
        server = ProxyServer(
            address="workflow.server.com",
            port=8080,
            description="Workflow Test Server",
            is_active=True
        )
        db_session.add(server)
        await db_session.commit()
        await db_session.refresh(server)
        
        # 3. Grant subscription
        days = 30
        current_time = datetime.now(timezone.utc)
        user.subscription_until = current_time + timedelta(days=days)
        await db_session.commit()
        
        # 4. Create proxy config
        config = ProxyConfig(
            user_id=user.id,
            proxy_secret="workflow_secret_32_chars_long",
            server_address=server.address,
            port=server.port
        )
        db_session.add(config)
        await db_session.commit()
        
        # 5. Create payment record
        payment = Payment(
            user_id=user.id,
            amount=5.00,
            currency="RUB",
            status="completed",
            provider_payment_id="workflow_payment_123"
        )
        db_session.add(payment)
        await db_session.commit()
        
        # 6. Verify complete workflow
        
        # Check user has subscription
        await db_session.refresh(user)
        assert user.subscription_until is not None
        assert user.subscription_until > datetime.now(timezone.utc)
        
        # Check server exists and is active
        await db_session.refresh(server)
        assert server.is_active is True
        assert server.address == "workflow.server.com"
        
        # Check proxy config exists
        result = await db_session.execute(
            select(ProxyConfig).where(ProxyConfig.user_id == user.id)
        )
        configs = result.scalars().all()
        assert len(configs) == 1
        assert configs[0].server_address == server.address
        
        # Check payment recorded
        result = await db_session.execute(
            select(Payment).where(Payment.user_id == user.id)
        )
        payments = result.scalars().all()
        assert len(payments) == 1
        assert payments[0].status == "completed"
        assert payments[0].amount == 5.00
        
        # 7. Simulate server management
        
        # Toggle server status
        server.is_active = False
        await db_session.commit()
        await db_session.refresh(server)
        assert server.is_active is False
        
        # Reactivate server
        server.is_active = True
        await db_session.commit()
        await db_session.refresh(server)
        assert server.is_active is True


class TestAdminCallbacks:
    """Test admin callback handlers."""
    
    def test_callback_handlers_import(self):
        """Test that callback handlers can be imported."""
        try:
            from bot import (
                admin_servers_callback, admin_stats_callback,
                admin_users_callback, admin_payments_callback,
                admin_add_server_callback, admin_grant_sub_callback
            )
            # If we can import them, that's a good sign
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import admin callback handlers: {e}")


# Test summary and coverage validation
class TestAdminTestCoverage:
    """Validate admin test coverage."""
    
    def test_admin_function_coverage(self):
        """Test that all major admin functions are covered."""
        # This test ensures we have coverage for the main admin functionality
        
        try:
            # Core admin functions
            from bot import is_admin, admin_required
            
            # Admin commands
            from bot import (
                admin_command, admin_servers_command, admin_stats_command,
                admin_users_command, admin_payments_command
            )
            
            # Admin handlers
            from bot import handle_server_add_command, handle_grant_sub_command
            
            # Verify all imports successful
            functions = [
                is_admin, admin_required, admin_command, admin_servers_command,
                admin_stats_command, admin_users_command, admin_payments_command,
                handle_server_add_command, handle_grant_sub_command
            ]
            
            for func in functions:
                assert callable(func), f"Function {func.__name__} is not callable"
            
        except ImportError as e:
            pytest.fail(f"Failed to import admin functions: {e}")
    
    def test_database_model_coverage(self):
        """Test that ProxyServer model is properly tested."""
        from database import ProxyServer
        
        # Verify model has expected attributes
        expected_attributes = [
            'id', 'address', 'port', 'is_active', 'description',
            'location', 'max_users', 'created_at', 'updated_at'
        ]
        
        for attr in expected_attributes:
            assert hasattr(ProxyServer, attr), f"ProxyServer missing attribute: {attr}"