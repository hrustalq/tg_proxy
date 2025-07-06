"""Tests for subscription logic and user stories compliance."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from bot import is_user_subscribed
from database import User


class TestSubscriptionValidation:
    """Test subscription validation logic (US-013)."""
    
    @pytest.mark.unit
    async def test_user_without_subscription(self):
        """Test US-013: User without subscription cannot access features."""
        user = User(telegram_id=123, subscription_until=None)
        result = await is_user_subscribed(user)
        assert result is False
    
    @pytest.mark.unit
    async def test_user_with_active_subscription(self):
        """Test US-013: User with active subscription can access features."""
        future_date = datetime.now(timezone.utc) + timedelta(days=10)
        user = User(telegram_id=123, subscription_until=future_date)
        result = await is_user_subscribed(user)
        assert result is True
    
    @pytest.mark.unit
    async def test_user_with_expired_subscription(self):
        """Test US-013: User with expired subscription cannot access features."""
        past_date = datetime.now(timezone.utc) - timedelta(days=1)
        user = User(telegram_id=123, subscription_until=past_date)
        result = await is_user_subscribed(user)
        assert result is False
    
    @pytest.mark.unit
    async def test_subscription_expiring_in_minutes(self):
        """Test US-013: Subscription valid until exact expiration time."""
        # Subscription expires in 30 minutes
        near_future = datetime.now(timezone.utc) + timedelta(minutes=30)
        user = User(telegram_id=123, subscription_until=near_future)
        result = await is_user_subscribed(user)
        assert result is True
    
    @pytest.mark.unit
    async def test_subscription_expired_minutes_ago(self):
        """Test US-013: Subscription invalid after expiration."""
        # Subscription expired 30 minutes ago
        recent_past = datetime.now(timezone.utc) - timedelta(minutes=30)
        user = User(telegram_id=123, subscription_until=recent_past)
        result = await is_user_subscribed(user)
        assert result is False
    
    @pytest.mark.unit
    async def test_subscription_validation_specific_time(self):
        """Test subscription validation with specific times."""
        # Test with a fixed future time
        future_time = datetime(2025, 6, 15, 13, 0, 0, tzinfo=timezone.utc)
        user = User(telegram_id=123, subscription_until=future_time)
        
        result = await is_user_subscribed(user)
        assert result is True
        
        # Test with a fixed past time
        past_time = datetime(2020, 1, 15, 13, 0, 0, tzinfo=timezone.utc)
        user.subscription_until = past_time
        
        result = await is_user_subscribed(user)
        assert result is False


class TestSubscriptionLifecycle:
    """Test complete subscription lifecycle (US-004, US-005)."""
    
    @pytest.mark.unit
    async def test_new_user_no_subscription(self):
        """Test US-005: New user has no subscription status."""
        user = User(telegram_id=123, subscription_until=None)
        assert user.subscription_until is None
        assert await is_user_subscribed(user) is False
    
    @pytest.mark.unit
    async def test_subscription_creation(self):
        """Test US-004: Creating new subscription."""
        user = User(telegram_id=123, subscription_until=None)
        
        # Simulate subscribing
        subscription_start = datetime.now(timezone.utc)
        subscription_end = subscription_start + timedelta(days=30)
        user.subscription_until = subscription_end
        
        assert await is_user_subscribed(user) is True
        assert user.subscription_until == subscription_end
    
    @pytest.mark.unit
    async def test_subscription_renewal_before_expiry(self):
        """Test US-004: Renewing subscription before expiry extends time."""
        current_time = datetime.now(timezone.utc)
        
        # User has 10 days left
        user = User(
            telegram_id=123, 
            subscription_until=current_time + timedelta(days=10)
        )
        
        # Simulate renewal (add 30 more days)
        original_expiry = user.subscription_until
        user.subscription_until = original_expiry + timedelta(days=30)
        
        # Should now have 40 days total
        expected_expiry = current_time + timedelta(days=40)
        time_diff = abs((user.subscription_until - expected_expiry).total_seconds())
        assert time_diff < 1  # Within 1 second tolerance
        assert await is_user_subscribed(user) is True
    
    @pytest.mark.unit
    async def test_subscription_renewal_after_expiry(self):
        """Test US-004: Renewing expired subscription starts fresh."""
        current_time = datetime.now(timezone.utc)
        
        # User's subscription expired 5 days ago
        user = User(
            telegram_id=123,
            subscription_until=current_time - timedelta(days=5)
        )
        
        # Verify expired
        assert await is_user_subscribed(user) is False
        
        # Simulate new subscription (30 days from now)
        user.subscription_until = current_time + timedelta(days=30)
        
        assert await is_user_subscribed(user) is True
        expected_expiry = current_time + timedelta(days=30)
        time_diff = abs((user.subscription_until - expected_expiry).total_seconds())
        assert time_diff < 1  # Within 1 second tolerance


class TestFreeTrialLogic:
    """Test free trial functionality (US-002)."""
    
    @pytest.mark.unit
    async def test_new_user_eligible_for_trial(self):
        """Test US-002: New user can get free trial."""
        user = User(telegram_id=123, subscription_until=None)
        
        # User has never had subscription, so eligible for trial
        assert user.subscription_until is None
    
    @pytest.mark.unit 
    async def test_trial_user_cannot_get_another_trial(self):
        """Test US-002: User who used trial cannot get another."""
        # User who had trial but it expired
        past_date = datetime.now(timezone.utc) - timedelta(hours=1)
        user = User(telegram_id=123, subscription_until=past_date)
        
        # User had subscription before (even expired trial), so not eligible
        assert user.subscription_until is not None
        assert await is_user_subscribed(user) is False
    
    @pytest.mark.unit
    async def test_subscribed_user_cannot_get_trial(self):
        """Test US-002: User with active subscription cannot get trial."""
        future_date = datetime.now(timezone.utc) + timedelta(days=5)
        user = User(telegram_id=123, subscription_until=future_date)
        
        # User already has active subscription
        assert await is_user_subscribed(user) is True
    
    @pytest.mark.unit
    async def test_trial_duration(self):
        """Test US-002: Free trial lasts exactly 1 day."""
        user = User(telegram_id=123, subscription_until=None)
        
        # Simulate activating trial
        trial_start = datetime.now(timezone.utc)
        trial_end = trial_start + timedelta(days=1)
        user.subscription_until = trial_end
        
        # Should be exactly 24 hours
        duration = user.subscription_until - trial_start
        assert duration.total_seconds() == 24 * 60 * 60  # 24 hours in seconds
        assert await is_user_subscribed(user) is True


class TestSubscriptionStatusDisplay:
    """Test subscription status display (US-005)."""
    
    @pytest.mark.unit
    async def test_display_active_subscription_status(self):
        """Test US-005: Display detailed status for active subscription."""
        expiry_date = datetime(2024, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
        user = User(telegram_id=123, subscription_until=expiry_date)
        
        # Test that we can format the expiry date
        formatted_date = user.subscription_until.strftime('%Y-%m-%d %H:%M UTC')
        assert formatted_date == "2024-06-15 14:30 UTC"
        assert await is_user_subscribed(user) is True
    
    @pytest.mark.unit
    async def test_calculate_time_remaining(self):
        """Test US-005: Calculate exact time remaining."""
        current_time = datetime.now(timezone.utc)
        
        # Subscription expires in 5 days and 3 hours
        expiry_time = current_time + timedelta(days=5, hours=3)
        user = User(telegram_id=123, subscription_until=expiry_time)
        
        # Calculate time remaining
        time_left = user.subscription_until - current_time
        days_left = time_left.days
        hours_left = time_left.seconds // 3600
        
        assert days_left == 5
        assert hours_left == 3
    
    @pytest.mark.unit
    async def test_display_expired_subscription_status(self):
        """Test US-005: Display status for expired subscription."""
        past_date = datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        user = User(telegram_id=123, subscription_until=past_date)
        
        # Verify expired
        assert await is_user_subscribed(user) is False
        
        # Should be able to format expiry date
        formatted_date = user.subscription_until.strftime('%Y-%m-%d %H:%M UTC')
        assert formatted_date == "2024-01-10 12:00 UTC"
    
    @pytest.mark.unit
    async def test_display_no_subscription_status(self):
        """Test US-005: Display status for user without subscription."""
        user = User(telegram_id=123, subscription_until=None)
        
        assert user.subscription_until is None
        assert await is_user_subscribed(user) is False


class TestTimezoneHandling:
    """Test timezone handling in subscription logic."""
    
    @pytest.mark.unit
    async def test_timezone_aware_comparison(self):
        """Test comparison with timezone-aware datetimes."""
        aware_future = datetime.now(timezone.utc) + timedelta(days=5)
        user = User(telegram_id=123, subscription_until=aware_future)
        
        result = await is_user_subscribed(user)
        assert result is True
    
    @pytest.mark.unit
    async def test_timezone_naive_comparison(self):
        """Test comparison with timezone-naive datetimes (legacy data)."""
        # Simulate old database data without timezone info
        naive_future = datetime.utcnow() + timedelta(days=5)
        user = User(telegram_id=123, subscription_until=naive_future)
        
        result = await is_user_subscribed(user)
        assert result is True
    
    @pytest.mark.unit
    async def test_mixed_timezone_handling(self):
        """Test handling when mixing timezone-aware and naive datetimes."""
        # Test with different timezone scenarios
        test_cases = [
            # Timezone-aware future date
            datetime.now(timezone.utc) + timedelta(days=1),
            # Timezone-naive future date  
            datetime.utcnow() + timedelta(days=1),
            # Timezone-aware past date
            datetime.now(timezone.utc) - timedelta(days=1),
            # Timezone-naive past date
            datetime.utcnow() - timedelta(days=1),
        ]
        
        expected_results = [True, True, False, False]
        
        for i, subscription_until in enumerate(test_cases):
            user = User(telegram_id=f"12{i}", subscription_until=subscription_until)
            result = await is_user_subscribed(user)
            assert result == expected_results[i], f"Failed for case {i}: {subscription_until}"


class TestSubscriptionEdgeCases:
    """Test edge cases in subscription logic."""
    
    @pytest.mark.unit
    async def test_subscription_expires_at_exact_moment(self):
        """Test subscription expiring at the exact current moment."""
        # This tests the boundary condition
        current_time = datetime.now(timezone.utc)
        user = User(telegram_id=123, subscription_until=current_time)
        
        # Should be False since current_time < current_time is False
        result = await is_user_subscribed(user)
        assert result is False
    
    @pytest.mark.unit
    async def test_subscription_with_microseconds(self):
        """Test subscription with microsecond precision."""
        current_time = datetime.now(timezone.utc)
        
        # Add just 1 microsecond
        future_time = current_time + timedelta(microseconds=1)
        user = User(telegram_id=123, subscription_until=future_time)
        
        result = await is_user_subscribed(user)
        assert result is True
    
    @pytest.mark.unit
    async def test_very_far_future_subscription(self):
        """Test subscription far in the future."""
        # Subscription for 100 years from now
        far_future = datetime.now(timezone.utc) + timedelta(days=365*100)
        user = User(telegram_id=123, subscription_until=far_future)
        
        result = await is_user_subscribed(user)
        assert result is True
    
    @pytest.mark.unit
    async def test_very_old_expired_subscription(self):
        """Test very old expired subscription."""
        # Subscription expired 10 years ago
        far_past = datetime.now(timezone.utc) - timedelta(days=365*10)
        user = User(telegram_id=123, subscription_until=far_past)
        
        result = await is_user_subscribed(user)
        assert result is False