"""Tests for payment processing functionality."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from bot import successful_payment, pre_checkout_query
from database import User, Payment


class TestSuccessfulPayment:
    """Test successful payment handler (US-010, US-004)."""
    
    @pytest.mark.integration
    async def test_successful_payment_new_subscription(self, db_session, test_user, test_settings):
        """Test US-010: First payment creates new subscription."""
        # Create mock message with payment
        mock_message = MagicMock()
        mock_message.from_user.id = test_user.telegram_id
        mock_message.successful_payment.total_amount = 500  # $5.00 in cents
        mock_message.successful_payment.currency = "RUB"
        mock_message.successful_payment.provider_payment_charge_id = "charge_123"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await successful_payment(mock_message)
        
        # Verify payment was recorded
        result = await db_session.execute(
            select(Payment).where(Payment.user_id == test_user.id)
        )
        payment = result.scalar_one_or_none()
        
        assert payment is not None
        assert payment.amount == 5.00  # Converted from cents
        assert payment.currency == "RUB"
        assert payment.status == "completed"
        assert payment.provider_payment_id == "charge_123"
        
        # Verify subscription was created
        await db_session.refresh(test_user)
        assert test_user.subscription_until is not None
        assert test_user.subscription_until > datetime.now(timezone.utc)
        
        # Should be 30 days from now (test settings default)
        expected_duration = timedelta(days=30)
        actual_duration = test_user.subscription_until - datetime.now(timezone.utc)
        # Allow 1 minute tolerance for test execution time
        assert abs(actual_duration.total_seconds() - expected_duration.total_seconds()) < 60
        
        # Verify confirmation message
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Payment successful" in call_args
        assert "subscription is now active until" in call_args
    
    @pytest.mark.integration
    async def test_successful_payment_extend_subscription(self, db_session, subscribed_user, test_settings):
        """Test US-004: Payment extends existing subscription."""
        original_expiry = subscribed_user.subscription_until
        
        # Create mock message with payment
        mock_message = MagicMock()
        mock_message.from_user.id = subscribed_user.telegram_id
        mock_message.successful_payment.total_amount = 1000  # $10.00 in cents
        mock_message.successful_payment.currency = "RUB"
        mock_message.successful_payment.provider_payment_charge_id = "charge_456"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await successful_payment(mock_message)
        
        # Verify payment was recorded
        result = await db_session.execute(
            select(Payment).where(Payment.user_id == subscribed_user.id)
        )
        payments = result.scalars().all()
        
        # Should have the new payment
        new_payment = next(p for p in payments if p.provider_payment_id == "charge_456")
        assert new_payment.amount == 10.00
        assert new_payment.status == "completed"
        
        # Verify subscription was extended
        await db_session.refresh(subscribed_user)
        assert subscribed_user.subscription_until > original_expiry
        
        # Should be original + 30 days
        expected_expiry = original_expiry + timedelta(days=30)
        time_diff = abs((subscribed_user.subscription_until - expected_expiry).total_seconds())
        assert time_diff < 60  # 1 minute tolerance
    
    @pytest.mark.integration
    async def test_successful_payment_expired_subscription_renewal(self, db_session, expired_user, test_settings):
        """Test US-004: Payment after expiration starts fresh subscription."""
        original_expiry = expired_user.subscription_until
        current_time = datetime.now(timezone.utc)
        
        # Create mock message with payment
        mock_message = MagicMock()
        mock_message.from_user.id = expired_user.telegram_id
        mock_message.successful_payment.total_amount = 500
        mock_message.successful_payment.currency = "RUB"
        mock_message.successful_payment.provider_payment_charge_id = "charge_789"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await successful_payment(mock_message)
        
        # Verify subscription starts fresh (not extended from expired date)
        await db_session.refresh(expired_user)
        
        # New expiry should be ~30 days from now, not from original expiry
        expected_expiry = current_time + timedelta(days=30)
        time_diff = abs((expired_user.subscription_until - expected_expiry).total_seconds())
        assert time_diff < 60  # 1 minute tolerance
        
        # Should definitely be after the original expired date
        assert expired_user.subscription_until > original_expiry
    
    @pytest.mark.integration
    async def test_successful_payment_amount_conversion(self, db_session, test_user, test_settings):
        """Test US-010: Payment amount properly converted from cents."""
        mock_message = MagicMock()
        mock_message.from_user.id = test_user.telegram_id
        mock_message.successful_payment.total_amount = 1599  # $15.99 in cents
        mock_message.successful_payment.currency = "USD"
        mock_message.successful_payment.provider_payment_charge_id = "charge_999"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await successful_payment(mock_message)
        
        # Verify amount was converted correctly
        result = await db_session.execute(
            select(Payment).where(Payment.user_id == test_user.id)
        )
        payment = result.scalar_one_or_none()
        
        assert payment.amount == 15.99  # Converted from 1599 cents
        assert payment.currency == "USD"
    
    @pytest.mark.integration
    async def test_successful_payment_timezone_handling(self, db_session, test_user, test_settings):
        """Test US-010: Payment creates timezone-aware subscription dates."""
        mock_message = MagicMock()
        mock_message.from_user.id = test_user.telegram_id
        mock_message.successful_payment.total_amount = 500
        mock_message.successful_payment.currency = "RUB"
        mock_message.successful_payment.provider_payment_charge_id = "charge_tz"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await successful_payment(mock_message)
        
        # Verify subscription date is timezone-aware
        await db_session.refresh(test_user)
        assert test_user.subscription_until is not None
        assert test_user.subscription_until.tzinfo is not None
        assert test_user.subscription_until.tzinfo == timezone.utc


class TestPreCheckoutQuery:
    """Test pre-checkout query handler (US-009)."""
    
    @pytest.mark.unit
    async def test_pre_checkout_query_approval(self):
        """Test US-009: All pre-checkout queries are approved."""
        mock_pre_checkout = MagicMock()
        mock_pre_checkout.id = "pre_checkout_123"
        
        mock_bot = AsyncMock()
        
        with patch('bot.bot', mock_bot):
            await pre_checkout_query(mock_pre_checkout)
        
        # Verify pre-checkout was approved
        mock_bot.answer_pre_checkout_query.assert_called_once_with(
            "pre_checkout_123", ok=True
        )


class TestPaymentEdgeCases:
    """Test edge cases in payment processing."""
    
    @pytest.mark.integration
    async def test_successful_payment_zero_amount(self, db_session, test_user, test_settings):
        """Test payment with zero amount."""
        mock_message = MagicMock()
        mock_message.from_user.id = test_user.telegram_id
        mock_message.successful_payment.total_amount = 0
        mock_message.successful_payment.currency = "RUB"
        mock_message.successful_payment.provider_payment_charge_id = "charge_zero"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await successful_payment(mock_message)
        
        # Verify payment was still recorded
        result = await db_session.execute(
            select(Payment).where(Payment.user_id == test_user.id)
        )
        payment = result.scalar_one_or_none()
        
        assert payment is not None
        assert payment.amount == 0.00
        
        # Should still create subscription
        await db_session.refresh(test_user)
        assert test_user.subscription_until is not None
    
    @pytest.mark.integration
    async def test_successful_payment_large_amount(self, db_session, test_user, test_settings):
        """Test payment with very large amount."""
        mock_message = MagicMock()
        mock_message.from_user.id = test_user.telegram_id
        mock_message.successful_payment.total_amount = 999999  # $9999.99
        mock_message.successful_payment.currency = "RUB"
        mock_message.successful_payment.provider_payment_charge_id = "charge_large"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await successful_payment(mock_message)
        
        # Verify large amount was handled correctly
        result = await db_session.execute(
            select(Payment).where(Payment.user_id == test_user.id)
        )
        payment = result.scalar_one_or_none()
        
        assert payment.amount == 9999.99
        assert payment.status == "completed"
    
    @pytest.mark.integration
    async def test_successful_payment_missing_provider_id(self, db_session, test_user, test_settings):
        """Test payment without provider payment ID."""
        mock_message = MagicMock()
        mock_message.from_user.id = test_user.telegram_id
        mock_message.successful_payment.total_amount = 500
        mock_message.successful_payment.currency = "RUB"
        mock_message.successful_payment.provider_payment_charge_id = None
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await successful_payment(mock_message)
        
        # Verify payment was still recorded
        result = await db_session.execute(
            select(Payment).where(Payment.user_id == test_user.id)
        )
        payment = result.scalar_one_or_none()
        
        assert payment is not None
        assert payment.provider_payment_id is None
        assert payment.status == "completed"
    
    @pytest.mark.integration
    async def test_multiple_payments_same_user(self, db_session, test_user, test_settings):
        """Test multiple payments for the same user."""
        payments_data = [
            {"amount": 500, "charge_id": "charge_1"},
            {"amount": 1000, "charge_id": "charge_2"},
            {"amount": 750, "charge_id": "charge_3"}
        ]
        
        subscription_expiry_dates = []
        
        for payment_data in payments_data:
            mock_message = MagicMock()
            mock_message.from_user.id = test_user.telegram_id
            mock_message.successful_payment.total_amount = payment_data["amount"]
            mock_message.successful_payment.currency = "RUB"
            mock_message.successful_payment.provider_payment_charge_id = payment_data["charge_id"]
            mock_message.answer = AsyncMock()
            
            with patch('bot.get_db') as mock_get_db, \
                 patch('bot.settings', test_settings):
                mock_get_db.return_value.__aenter__.return_value = db_session
                mock_get_db.return_value.__aexit__ = AsyncMock()
                
                await successful_payment(mock_message)
            
            # Record subscription expiry after each payment
            await db_session.refresh(test_user)
            subscription_expiry_dates.append(test_user.subscription_until)
        
        # Verify all payments were recorded
        result = await db_session.execute(
            select(Payment).where(Payment.user_id == test_user.id)
        )
        payments = result.scalars().all()
        
        assert len(payments) == 3
        charge_ids = [p.provider_payment_id for p in payments]
        assert "charge_1" in charge_ids
        assert "charge_2" in charge_ids
        assert "charge_3" in charge_ids
        
        # Verify subscription was extended each time
        for i in range(1, len(subscription_expiry_dates)):
            assert subscription_expiry_dates[i] > subscription_expiry_dates[i-1]
        
        # Final subscription should be ~90 days from start (3 x 30 days)
        first_payment_time = payments[0].created_at
        final_expiry = subscription_expiry_dates[-1]
        
        # Convert naive datetime to timezone-aware for comparison
        if first_payment_time.tzinfo is None:
            first_payment_time = first_payment_time.replace(tzinfo=timezone.utc)
        
        total_duration = final_expiry - first_payment_time
        expected_duration = timedelta(days=90)  # 3 payments × 30 days each
        
        # Allow some tolerance for test execution time
        assert abs(total_duration.total_seconds() - expected_duration.total_seconds()) < 300  # 5 minutes


class TestPaymentIntegrationWithUserStories:
    """Test payment integration with specific user stories."""
    
    @pytest.mark.integration
    async def test_payment_enables_proxy_access(self, db_session, test_user, test_settings):
        """Test that payment immediately enables proxy access."""
        # User starts without subscription
        from bot import is_user_subscribed
        assert await is_user_subscribed(test_user) is False
        
        # Process payment
        mock_message = MagicMock()
        mock_message.from_user.id = test_user.telegram_id
        mock_message.successful_payment.total_amount = 500
        mock_message.successful_payment.currency = "RUB"
        mock_message.successful_payment.provider_payment_charge_id = "enable_access"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await successful_payment(mock_message)
        
        # User should now have access
        await db_session.refresh(test_user)
        assert await is_user_subscribed(test_user) is True
    
    @pytest.mark.integration
    async def test_payment_confirmation_message_format(self, db_session, test_user, test_settings):
        """Test US-010: Payment confirmation message format."""
        mock_message = MagicMock()
        mock_message.from_user.id = test_user.telegram_id
        mock_message.successful_payment.total_amount = 500
        mock_message.successful_payment.currency = "RUB"
        mock_message.successful_payment.provider_payment_charge_id = "confirm_test"
        mock_message.answer = AsyncMock()
        
        with patch('bot.get_db') as mock_get_db, \
             patch('bot.settings', test_settings):
            mock_get_db.return_value.__aenter__.return_value = db_session
            mock_get_db.return_value.__aexit__ = AsyncMock()
            
            await successful_payment(mock_message)
        
        # Verify confirmation message format
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        
        assert "Payment successful" in call_args
        assert "subscription is now active until" in call_args
        assert "UTC" in call_args
        assert "/config" in call_args
        
        # Verify keyboard has config button
        keyboard = mock_message.answer.call_args[1]['reply_markup']
        assert keyboard is not None
        config_button = keyboard.inline_keyboard[0][0]
        assert "Config" in config_button.text
        assert config_button.callback_data == "get_config"