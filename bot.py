import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import LabeledPrice, PreCheckoutQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, User, ProxyConfig, Payment
from config import settings
import secrets
import string

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.bot_token)
dp = Dispatcher()


def generate_proxy_secret() -> str:
    """Generate a random proxy secret"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User:
    """Get user by Telegram ID, create if not exists"""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(telegram_id=telegram_id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    
    return user


async def is_user_subscribed(user: User) -> bool:
    """Check if user has active subscription"""
    if not user.subscription_until:
        return False
    
    # Handle both timezone-aware and timezone-naive datetimes
    current_time = datetime.now(timezone.utc)
    if user.subscription_until.tzinfo is None:
        # If the stored datetime is naive, treat it as UTC
        subscription_time = user.subscription_until.replace(tzinfo=timezone.utc)
    else:
        subscription_time = user.subscription_until
    
    return current_time < subscription_time


def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """Get subscription keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Subscribe for ${settings.subscription_price}", callback_data="subscribe")],
        [InlineKeyboardButton(text="Get Free Trial", callback_data="free_trial")]
    ])
    return keyboard


def get_proxy_config_text(proxy_configs: List[ProxyConfig]) -> str:
    """Generate proxy configuration text"""
    if not proxy_configs:
        return "No proxy configurations available."
    
    config_text = "🔗 Your Proxy Configurations:\n\n"
    for i, config in enumerate(proxy_configs, 1):
        config_text += f"**Server {i}:**\n"
        config_text += f"Server: `{config.server_address}`\n"
        config_text += f"Port: `{config.port}`\n"
        config_text += f"Secret: `{config.proxy_secret}`\n"
        config_text += f"MTG Secret: `{settings.mtg_secret}`\n"
        config_text += f"Direct Link: `tg://proxy?server={config.server_address}&port={config.port}&secret={config.proxy_secret}`\n\n"
    
    config_text += "📱 **Setup Instructions:**\n"
    config_text += "1. Click on any Direct Link above\n"
    config_text += "2. Or manually add proxy in Telegram settings\n"
    config_text += "3. Works with all official Telegram clients\n\n"
    
    return config_text


@dp.message(CommandStart())
async def start_command(message: Message):
    """Handle /start command"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)
        user.username = message.from_user.username
        user.first_name = message.from_user.first_name
        await session.commit()
        
        if await is_user_subscribed(user):
            expiration_date = user.subscription_until.strftime('%Y-%m-%d %H:%M UTC')
            await message.answer(
                f"Welcome back, {user.first_name}! 🎉\n\n"
                f"✅ Your subscription is active until {expiration_date}\n\n"
                "Use /config to get your proxy settings.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Get Proxy Config", callback_data="get_config")],
                    [InlineKeyboardButton(text=f"Extend Subscription (+${settings.subscription_price})", callback_data="subscribe")]
                ])
            )
        else:
            await message.answer(
                f"Welcome to Telegram Proxy Bot, {user.first_name}! 🚀\n\n"
                "Get unlimited access to Telegram through our secure proxy servers.\n\n"
                f"💰 Subscription: ${settings.subscription_price}/{settings.subscription_duration} days\n"
                "🔒 Secure MTProto proxy protocol\n"
                "🌍 Multiple server locations\n"
                "⚡ High-speed connections\n\n"
                "Choose an option below:",
                reply_markup=get_subscription_keyboard()
            )


@dp.message(Command("help"))
async def help_command(message: Message):
    """Handle /help command"""
    help_text = (
        "🤖 **Telegram Proxy Bot Commands**\n\n"
        "/start - Welcome message and main menu\n"
        "/config - Get your proxy configuration\n"
        "/status - Check subscription status\n"
        "/help - Show this help message\n\n"
        "🔗 **Features:**\n"
        "• Secure MTProto proxy protocol\n"
        "• Multiple server locations\n"
        "• High-speed connections\n"
        "• 1-day free trial for new users\n"
        f"• Monthly subscription: ${settings.subscription_price}\n\n"
        "💡 **Quick Actions:**\n"
        "• Use buttons for easy navigation\n"
        "• Click tg:// links for instant setup\n"
        "• Refresh configs for better security"
    )
    
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)
        
        if await is_user_subscribed(user):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Get Proxy Config", callback_data="get_config")],
                [InlineKeyboardButton(text="Check Status", callback_data="check_status")]
            ])
        else:
            keyboard = get_subscription_keyboard()
        
        await message.answer(help_text, parse_mode="Markdown", reply_markup=keyboard)


@dp.message(Command("status"))
async def status_command(message: Message):
    """Handle /status command - check subscription status"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)
        
        if await is_user_subscribed(user):
            expiration_date = user.subscription_until.strftime('%Y-%m-%d %H:%M UTC')
            
            # Handle timezone-aware calculation
            current_time = datetime.now(timezone.utc)
            if user.subscription_until.tzinfo is None:
                subscription_time = user.subscription_until.replace(tzinfo=timezone.utc)
            else:
                subscription_time = user.subscription_until
            
            time_left = subscription_time - current_time
            days_left = time_left.days
            hours_left = time_left.seconds // 3600
            
            await message.answer(
                f"📊 **Subscription Status**\n\n"
                f"✅ Status: Active\n"
                f"📅 Expires: {expiration_date}\n"
                f"⏰ Time Left: {days_left} days, {hours_left} hours\n\n"
                "Use /config to get your proxy settings.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Get Proxy Config", callback_data="get_config")],
                    [InlineKeyboardButton(text="Extend Subscription", callback_data="subscribe")]
                ])
            )
        else:
            if user.subscription_until:
                await message.answer(
                    f"📊 **Subscription Status**\n\n"
                    f"❌ Status: Expired\n"
                    f"📅 Expired: {user.subscription_until.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                    "Subscribe to regain access to proxy servers.",
                    parse_mode="Markdown",
                    reply_markup=get_subscription_keyboard()
                )
            else:
                await message.answer(
                    f"📊 **Subscription Status**\n\n"
                    f"❌ Status: No subscription\n\n"
                    "Subscribe or try free trial to access proxy servers.",
                    parse_mode="Markdown",
                    reply_markup=get_subscription_keyboard()
                )


@dp.message(Command("config"))
async def config_command(message: Message):
    """Handle /config command"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)
        
        if not await is_user_subscribed(user):
            if user.subscription_until:
                expired_date = user.subscription_until.strftime('%Y-%m-%d %H:%M UTC')
                await message.answer(
                    f"❌ Your subscription expired on {expired_date}\n\n"
                    "Please subscribe to regain access to proxy configurations.",
                    reply_markup=get_subscription_keyboard()
                )
            else:
                await message.answer(
                    "❌ You don't have an active subscription.\n\n"
                    "Please subscribe or try free trial to get access to proxy configurations.",
                    reply_markup=get_subscription_keyboard()
                )
            return
        
        result = await session.execute(select(ProxyConfig).where(ProxyConfig.user_id == user.id))
        proxy_configs = result.scalars().all()
        
        if not proxy_configs:
            # Create proxy configs for the user
            for i, server in enumerate(settings.get_proxy_servers()):
                if ':' in server:
                    server_address, port = server.split(':', 1)
                    port = int(port)
                else:
                    server_address = server
                    port = 443  # Default MTProto port
                
                proxy_config = ProxyConfig(
                    user_id=user.id,
                    proxy_secret=generate_proxy_secret(),
                    server_address=server_address,
                    port=port
                )
                session.add(proxy_config)
            
            await session.commit()
            result = await session.execute(select(ProxyConfig).where(ProxyConfig.user_id == user.id))
            proxy_configs = result.scalars().all()
        
        config_text = get_proxy_config_text(proxy_configs)
        await message.answer(
            config_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Refresh Config", callback_data="refresh_config")]
            ])
        )


@dp.callback_query(lambda c: c.data == "subscribe")
async def subscribe_callback(callback_query: CallbackQuery):
    """Handle subscription callback"""
    try:
        prices = [LabeledPrice(label="Subscription", amount=int(settings.subscription_price * 100))]
        
        await bot.send_invoice(
            chat_id=callback_query.from_user.id,
            title="Telegram Proxy Subscription",
            description=f"Get {settings.subscription_duration} days access to premium proxy servers",
            provider_token=settings.payment_provider_token,
            currency="RUB",  # YooKassa typically uses RUB
            prices=prices,
            payload=f"subscription_{callback_query.from_user.id}"
        )
        
        await callback_query.answer("Payment invoice sent! Please complete the payment.")
        
    except Exception as e:
        logger.error(f"Error sending invoice: {e}")
        await callback_query.answer("Error creating payment invoice. Please try again later.", show_alert=True)


@dp.callback_query(lambda c: c.data == "free_trial")
async def free_trial_callback(callback_query: CallbackQuery):
    """Handle free trial callback"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, callback_query.from_user.id)
        
        if await is_user_subscribed(user):
            await callback_query.answer("You already have an active subscription!", show_alert=True)
            return
        
        # Check if user already had a trial (US-002: cannot get multiple free trials)
        if user.subscription_until:
            await callback_query.answer("Free trial is only available once per user!", show_alert=True)
            return
        
        # Give 1 day free trial
        user.subscription_until = datetime.now(timezone.utc) + timedelta(days=1)
        await session.commit()
        
        expiration_time = user.subscription_until.strftime('%Y-%m-%d %H:%M UTC')
        await callback_query.message.edit_text(
            "🎉 Free trial activated!\n\n"
            f"You now have 1 day of free access until {expiration_time}.\n\n"
            "Use /config to get your proxy settings.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Get Proxy Config", callback_data="get_config")]
            ])
        )
    
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "get_config")
async def get_config_callback(callback_query: CallbackQuery):
    """Handle get config callback"""
    await config_command(callback_query.message)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "check_status")
async def check_status_callback(callback_query: CallbackQuery):
    """Handle check status callback"""
    await status_command(callback_query.message)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "refresh_config")
async def refresh_config_callback(callback_query: CallbackQuery):
    """Handle refresh config callback"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, callback_query.from_user.id)
        
        if not await is_user_subscribed(user):
            await callback_query.answer("Subscription expired!", show_alert=True)
            return
        
        # Delete old configs and create new ones
        result = await session.execute(select(ProxyConfig).where(ProxyConfig.user_id == user.id))
        old_configs = result.scalars().all()
        for config in old_configs:
            await session.delete(config)
        await session.flush()  # Ensure deletions are processed before inserts
        
        for server in settings.get_proxy_servers():
            if ':' in server:
                server_address, port = server.split(':', 1)
                port = int(port)
            else:
                server_address = server
                port = 443  # Default MTProto port
                
            proxy_config = ProxyConfig(
                user_id=user.id,
                proxy_secret=generate_proxy_secret(),
                server_address=server_address,
                port=port
            )
            session.add(proxy_config)
        
        await session.commit()
        
        result = await session.execute(select(ProxyConfig).where(ProxyConfig.user_id == user.id))
        proxy_configs = result.scalars().all()
        
        config_text = get_proxy_config_text(proxy_configs)
        await callback_query.message.edit_text(
            config_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Refresh Config", callback_data="refresh_config")]
            ])
        )
    
    await callback_query.answer("Configuration refreshed!")


@dp.pre_checkout_query()
async def pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    """Handle pre-checkout query"""
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message(lambda message: message.successful_payment)
async def successful_payment(message: Message):
    """Handle successful payment"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)
        
        # Record payment
        payment = Payment(
            user_id=user.id,
            amount=message.successful_payment.total_amount / 100,
            currency=message.successful_payment.currency,
            status="completed",
            provider_payment_id=message.successful_payment.provider_payment_charge_id
        )
        session.add(payment)
        
        # Extend subscription
        current_time = datetime.now(timezone.utc)
        if user.subscription_until:
            # Handle timezone-aware comparison
            if user.subscription_until.tzinfo is None:
                subscription_time = user.subscription_until.replace(tzinfo=timezone.utc)
            else:
                subscription_time = user.subscription_until
                
            if subscription_time > current_time:
                # Extend existing subscription
                user.subscription_until = subscription_time + timedelta(days=settings.subscription_duration)
            else:
                # Start new subscription
                user.subscription_until = current_time + timedelta(days=settings.subscription_duration)
        else:
            # First subscription
            user.subscription_until = current_time + timedelta(days=settings.subscription_duration)
        
        await session.commit()
        
        await message.answer(
            f"✅ Payment successful!\n\n"
            f"Your subscription is now active until {user.subscription_until.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
            "Use /config to get your proxy settings.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Get Proxy Config", callback_data="get_config")]
            ])
        )