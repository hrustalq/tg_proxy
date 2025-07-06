import asyncio
import logging
from datetime import datetime, timedelta
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
    return datetime.utcnow() < user.subscription_until


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
        config_text += f"Link: `tg://proxy?server={config.server_address}&port={config.port}&secret={config.proxy_secret}`\n\n"
    
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
            await message.answer(
                f"Welcome back, {user.first_name}! 🎉\n\n"
                "Your subscription is active. Use /config to get your proxy settings.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Get Proxy Config", callback_data="get_config")]
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


@dp.message(Command("config"))
async def config_command(message: Message):
    """Handle /config command"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)
        
        if not await is_user_subscribed(user):
            await message.answer(
                "❌ You don't have an active subscription.\n\n"
                "Please subscribe to get access to proxy configurations.",
                reply_markup=get_subscription_keyboard()
            )
            return
        
        result = await session.execute(select(ProxyConfig).where(ProxyConfig.user_id == user.id))
        proxy_configs = result.scalars().all()
        
        if not proxy_configs:
            # Create proxy configs for the user
            for i, server in enumerate(settings.proxy_servers):
                server_address, port = server.split(':')
                proxy_config = ProxyConfig(
                    user_id=user.id,
                    proxy_secret=generate_proxy_secret(),
                    server_address=server_address,
                    port=int(port)
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
    prices = [LabeledPrice(label="Subscription", amount=int(settings.subscription_price * 100))]
    
    await bot.send_invoice(
        chat_id=callback_query.from_user.id,
        title="Telegram Proxy Subscription",
        description=f"Get {settings.subscription_duration} days access to premium proxy servers",
        provider_token=settings.payment_provider_token,
        currency="USD",
        prices=prices,
        payload=f"subscription_{callback_query.from_user.id}"
    )
    
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "free_trial")
async def free_trial_callback(callback_query: CallbackQuery):
    """Handle free trial callback"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, callback_query.from_user.id)
        
        if user.subscription_until and user.subscription_until > datetime.utcnow():
            await callback_query.answer("You already have an active subscription!", show_alert=True)
            return
        
        # Give 1 day free trial
        user.subscription_until = datetime.utcnow() + timedelta(days=1)
        await session.commit()
        
        await callback_query.message.edit_text(
            "🎉 Free trial activated!\n\n"
            "You now have 1 day of free access. Use /config to get your proxy settings.",
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


@dp.callback_query(lambda c: c.data == "refresh_config")
async def refresh_config_callback(callback_query: CallbackQuery):
    """Handle refresh config callback"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, callback_query.from_user.id)
        
        if not await is_user_subscribed(user):
            await callback_query.answer("Subscription expired!", show_alert=True)
            return
        
        # Delete old configs and create new ones
        await session.execute(select(ProxyConfig).where(ProxyConfig.user_id == user.id))
        await session.commit()
        
        for server in settings.proxy_servers:
            server_address, port = server.split(':')
            proxy_config = ProxyConfig(
                user_id=user.id,
                proxy_secret=generate_proxy_secret(),
                server_address=server_address,
                port=int(port)
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
        if user.subscription_until and user.subscription_until > datetime.utcnow():
            user.subscription_until += timedelta(days=settings.subscription_duration)
        else:
            user.subscription_until = datetime.utcnow() + timedelta(days=settings.subscription_duration)
        
        await session.commit()
        
        await message.answer(
            f"✅ Payment successful!\n\n"
            f"Your subscription is now active until {user.subscription_until.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
            "Use /config to get your proxy settings.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Get Proxy Config", callback_data="get_config")]
            ])
        )