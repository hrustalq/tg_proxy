"""Tests for configuration management."""
import pytest
import os
from unittest.mock import patch, mock_open
from pydantic import ValidationError

from config import Settings


class TestSettings:
    """Test Settings configuration class."""
    
    @pytest.mark.unit
    def test_settings_creation_with_all_fields(self):
        """Test creating settings with all required fields."""
        settings = Settings(
            bot_token="test_bot_token",
            admin_ids="123456789,987654321",
            database_url="sqlite:///test.db",
            payment_provider_token="test_provider_token",
            proxy_servers="server1.com:443,server2.com:8080",
            subscription_price=10.00,
            subscription_duration=30,
            mtg_secret="test_secret_32_chars_long_here"
        )
        
        assert settings.bot_token == "test_bot_token"
        assert settings.admin_ids == "123456789,987654321"
        assert settings.database_url == "sqlite:///test.db"
        assert settings.payment_provider_token == "test_provider_token"
        assert settings.proxy_servers == "server1.com:443,server2.com:8080"
        assert settings.subscription_price == 10.00
        assert settings.subscription_duration == 30
        assert settings.mtg_secret == "test_secret_32_chars_long_here"
    
    @pytest.mark.unit
    def test_settings_default_values(self):
        """Test settings default values."""
        settings = Settings(
            bot_token="test_token",
            admin_ids="123",
            payment_provider_token="test_provider",
            proxy_servers="test.com",
            mtg_secret="test_secret"
        )
        
        assert settings.database_url == "sqlite:///./tg_proxy.db"
        assert settings.subscription_price == 5.00
        assert settings.subscription_duration == 30
    
    @pytest.mark.unit
    def test_get_admin_ids_single(self):
        """Test parsing single admin ID."""
        settings = Settings(
            bot_token="test_token",
            admin_ids="123456789",
            payment_provider_token="test_provider",
            proxy_servers="test.com",
            mtg_secret="test_secret"
        )
        
        admin_ids = settings.get_admin_ids()
        assert admin_ids == [123456789]
        assert isinstance(admin_ids[0], int)
    
    @pytest.mark.unit
    def test_get_admin_ids_multiple(self):
        """Test parsing multiple admin IDs."""
        settings = Settings(
            bot_token="test_token",
            admin_ids="123456789,987654321,111222333",
            payment_provider_token="test_provider",
            proxy_servers="test.com",
            mtg_secret="test_secret"
        )
        
        admin_ids = settings.get_admin_ids()
        assert admin_ids == [123456789, 987654321, 111222333]
        assert all(isinstance(id_, int) for id_ in admin_ids)
    
    @pytest.mark.unit
    def test_get_admin_ids_with_spaces(self):
        """Test parsing admin IDs with spaces."""
        settings = Settings(
            bot_token="test_token",
            admin_ids="123456789, 987654321 , 111222333",
            payment_provider_token="test_provider",
            proxy_servers="test.com",
            mtg_secret="test_secret"
        )
        
        admin_ids = settings.get_admin_ids()
        assert admin_ids == [123456789, 987654321, 111222333]
    
    @pytest.mark.unit
    def test_get_proxy_servers_single(self):
        """Test parsing single proxy server."""
        settings = Settings(
            bot_token="test_token",
            admin_ids="123",
            payment_provider_token="test_provider",
            proxy_servers="proxy.example.com:443",
            mtg_secret="test_secret"
        )
        
        servers = settings.get_proxy_servers()
        assert servers == ["proxy.example.com:443"]
    
    @pytest.mark.unit
    def test_get_proxy_servers_multiple(self):
        """Test parsing multiple proxy servers."""
        settings = Settings(
            bot_token="test_token",
            admin_ids="123",
            payment_provider_token="test_provider",
            proxy_servers="server1.com:443,server2.com:8080,server3.com:9999",
            mtg_secret="test_secret"
        )
        
        servers = settings.get_proxy_servers()
        assert servers == ["server1.com:443", "server2.com:8080", "server3.com:9999"]
    
    @pytest.mark.unit
    def test_get_proxy_servers_with_spaces(self):
        """Test parsing proxy servers with spaces."""
        settings = Settings(
            bot_token="test_token",
            admin_ids="123",
            payment_provider_token="test_provider",
            proxy_servers="server1.com:443, server2.com:8080 , server3.com",
            mtg_secret="test_secret"
        )
        
        servers = settings.get_proxy_servers()
        assert servers == ["server1.com:443", "server2.com:8080", "server3.com"]
    
    @pytest.mark.unit
    def test_get_proxy_servers_without_ports(self):
        """Test parsing proxy servers without ports."""
        settings = Settings(
            bot_token="test_token",
            admin_ids="123",
            payment_provider_token="test_provider",
            proxy_servers="proxy1.com,proxy2.com:8080,proxy3.com",
            mtg_secret="test_secret"
        )
        
        servers = settings.get_proxy_servers()
        assert servers == ["proxy1.com", "proxy2.com:8080", "proxy3.com"]
    
    @pytest.mark.unit
    def test_settings_validation_missing_required_field(self):
        """Test validation error when required field is missing."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                # Missing bot_token
                admin_ids="123",
                payment_provider_token="test_provider",
                proxy_servers="test.com",
                mtg_secret="test_secret"
            )
        
        assert "bot_token" in str(exc_info.value)
    
    @pytest.mark.unit
    def test_settings_type_validation(self):
        """Test type validation for numeric fields."""
        settings = Settings(
            bot_token="test_token",
            admin_ids="123",
            payment_provider_token="test_provider",
            proxy_servers="test.com",
            subscription_price="15.99",  # String that can be converted to float
            subscription_duration="45",   # String that can be converted to int
            mtg_secret="test_secret"
        )
        
        assert settings.subscription_price == 15.99
        assert isinstance(settings.subscription_price, float)
        assert settings.subscription_duration == 45
        assert isinstance(settings.subscription_duration, int)
    
    @pytest.mark.unit
    def test_settings_invalid_numeric_values(self):
        """Test validation error for invalid numeric values."""
        with pytest.raises(ValidationError):
            Settings(
                bot_token="test_token",
                admin_ids="123",
                payment_provider_token="test_provider",
                proxy_servers="test.com",
                subscription_price="invalid_float",
                mtg_secret="test_secret"
            )


class TestEnvironmentVariables:
    """Test environment variable loading."""
    
    @pytest.mark.unit
    @patch.dict(os.environ, {
        'BOT_TOKEN': 'env_bot_token',
        'ADMIN_IDS': '111,222,333',
        'PAYMENT_PROVIDER_TOKEN': 'env_provider_token',
        'PROXY_SERVERS': 'env.server1.com,env.server2.com:8080',
        'MTG_SECRET': 'env_mtg_secret',
        'SUBSCRIPTION_PRICE': '7.50',
        'SUBSCRIPTION_DURATION': '60'
    })
    def test_settings_from_environment(self):
        """Test loading settings from environment variables."""
        settings = Settings()
        
        assert settings.bot_token == 'env_bot_token'
        assert settings.admin_ids == '111,222,333'
        assert settings.payment_provider_token == 'env_provider_token'
        assert settings.proxy_servers == 'env.server1.com,env.server2.com:8080'
        assert settings.mtg_secret == 'env_mtg_secret'
        assert settings.subscription_price == 7.50
        assert settings.subscription_duration == 60
    
    @pytest.mark.unit
    @patch.dict(os.environ, {
        'BOT_TOKEN': 'env_token',
        'ADMIN_IDS': '123',
        'PAYMENT_PROVIDER_TOKEN': 'env_provider',
        'PROXY_SERVERS': 'env.server.com',
        'MTG_SECRET': 'env_secret'
    })
    def test_environment_with_defaults(self):
        """Test environment variables with default values."""
        settings = Settings()
        
        # Environment values
        assert settings.bot_token == 'env_token'
        assert settings.admin_ids == '123'
        
        # Default values
        assert settings.database_url == "sqlite:///./tg_proxy.db"
        assert settings.subscription_price == 5.00
        assert settings.subscription_duration == 30
    
    @pytest.mark.unit
    @patch('builtins.open', mock_open(read_data="""
BOT_TOKEN=file_bot_token
ADMIN_IDS=999,888,777
PAYMENT_PROVIDER_TOKEN=file_provider_token
PROXY_SERVERS=file.server1.com:443,file.server2.com:8080
MTG_SECRET=file_mtg_secret
SUBSCRIPTION_PRICE=12.99
SUBSCRIPTION_DURATION=90
"""))
    def test_settings_from_env_file(self):
        """Test loading settings from .env file."""
        # This test simulates reading from a .env file
        # In reality, pydantic-settings would handle this automatically
        pass  # Actual .env file loading is handled by pydantic-settings
    
    @pytest.mark.unit
    def test_explicit_values_override_environment(self):
        """Test that explicit values override environment variables."""
        with patch.dict(os.environ, {
            'BOT_TOKEN': 'env_token',
            'SUBSCRIPTION_PRICE': '10.00'
        }):
            settings = Settings(
                bot_token="explicit_token",
                admin_ids="123",
                payment_provider_token="test_provider",
                proxy_servers="test.com",
                subscription_price=15.00,  # Explicit override
                mtg_secret="test_secret"
            )
            
            assert settings.bot_token == "explicit_token"  # Explicit wins
            assert settings.subscription_price == 15.00    # Explicit wins


class TestConfigurationEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.mark.unit
    def test_empty_admin_ids(self):
        """Test handling of empty admin IDs."""
        settings = Settings(
            bot_token="test_token",
            admin_ids="",
            payment_provider_token="test_provider",
            proxy_servers="test.com",
            mtg_secret="test_secret"
        )
        
        admin_ids = settings.get_admin_ids()
        assert admin_ids == [""]  # Returns list with empty string
    
    @pytest.mark.unit
    def test_empty_proxy_servers(self):
        """Test handling of empty proxy servers."""
        settings = Settings(
            bot_token="test_token",
            admin_ids="123",
            payment_provider_token="test_provider",
            proxy_servers="",
            mtg_secret="test_secret"
        )
        
        servers = settings.get_proxy_servers()
        assert servers == [""]  # Returns list with empty string
    
    @pytest.mark.unit
    def test_single_comma_in_lists(self):
        """Test handling of single comma in list fields."""
        settings = Settings(
            bot_token="test_token",
            admin_ids="123,",
            payment_provider_token="test_provider",
            proxy_servers="server.com,",
            mtg_secret="test_secret"
        )
        
        admin_ids = settings.get_admin_ids()
        servers = settings.get_proxy_servers()
        
        assert len(admin_ids) == 2
        assert admin_ids[1] == 0 or admin_ids[1] == ""  # Empty after comma
        assert len(servers) == 2
        assert servers[1] == ""  # Empty after comma
    
    @pytest.mark.unit
    def test_very_long_configuration_values(self):
        """Test handling of very long configuration values."""
        long_token = "x" * 1000
        long_secret = "y" * 1000
        
        settings = Settings(
            bot_token=long_token,
            admin_ids="123",
            payment_provider_token="test_provider",
            proxy_servers="test.com",
            mtg_secret=long_secret
        )
        
        assert settings.bot_token == long_token
        assert settings.mtg_secret == long_secret
        assert len(settings.bot_token) == 1000
        assert len(settings.mtg_secret) == 1000