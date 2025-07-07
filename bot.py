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
from database import get_db, User, ProxyConfig, Payment, ProxyServer
from config import settings
from mtg_proxy import mtg_proxy_manager, mtg_monitor
import secrets
import string

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.bot_token)
dp = Dispatcher()


def generate_proxy_secret() -> str:
    """Generate a random proxy secret"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))


def is_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    try:
        admin_ids = settings.get_admin_ids()
        logger.debug(f"Checking admin access for user {user_id}. Admin IDs: {admin_ids}")
        return user_id in admin_ids
    except Exception as e:
        logger.error(f"Error checking admin access: {e}")
        return False


def admin_required(func):
    """Decorator to require admin access"""
    async def wrapper(message_or_query, **kwargs):
        user_id = message_or_query.from_user.id
        if not is_admin(user_id):
            if hasattr(message_or_query, 'message'):
                # It's a CallbackQuery
                await message_or_query.answer("❌ Access denied. Admin privileges required.", show_alert=True)
            else:
                # It's a Message
                await message_or_query.answer("❌ Access denied. Admin privileges required.")
            return
        return await func(message_or_query)
    return wrapper


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
    price_text = f"{settings.subscription_price:.0f} {settings.currency}" if settings.currency == "RUB" else f"${settings.subscription_price}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Subscribe for {price_text}", callback_data="subscribe")],
        [InlineKeyboardButton(text="Get Free Trial", callback_data="free_trial")]
    ])
    return keyboard


def get_proxy_config_text(server_host: str = None) -> str:
    """Generate proxy configuration text using MTG proxy manager"""
    try:
        # Get MTG proxy configuration
        config_text = mtg_proxy_manager.get_proxy_config_text(server_host)
        
        # Add status information
        status_text = mtg_monitor.get_status_text()
        
        return f"{config_text}\n\n{status_text}"
    except Exception as e:
        logger.error(f"Error generating proxy config: {e}")
        return "❌ Error generating proxy configuration. Please try again later."


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
                    [InlineKeyboardButton(text=f"Extend Subscription (+{settings.subscription_price:.0f} {settings.currency})", callback_data="subscribe")]
                ])
            )
        else:
            await message.answer(
                f"Welcome to Telegram Proxy Bot, {user.first_name}! 🚀\n\n"
                "Get unlimited access to Telegram through our secure proxy servers.\n\n"
                f"💰 Subscription: {settings.subscription_price:.0f} {settings.currency}/{settings.subscription_duration} days\n"
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
        f"• Monthly subscription: {settings.subscription_price:.0f} {settings.currency}\n\n"
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
        
        # Get proxy servers from settings and use the first one as default
        proxy_servers = settings.get_proxy_servers()
        server_host = proxy_servers[0].split(':')[0] if proxy_servers else None
        
        config_text = get_proxy_config_text(server_host)
        await message.answer(
            config_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Refresh Config", callback_data="refresh_config")],
                [InlineKeyboardButton(text="Proxy Status", callback_data="proxy_status")]
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
            currency=settings.currency,
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
    # Create a modified message object with the correct user info
    message = callback_query.message
    message.from_user = callback_query.from_user
    await config_command(message)
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
        
        # Get proxy servers from settings and use the first one as default
        proxy_servers = settings.get_proxy_servers()
        server_host = proxy_servers[0].split(':')[0] if proxy_servers else None
        
        config_text = get_proxy_config_text(server_host)
        
        # Check if message content would be the same to avoid TelegramBadRequest
        current_text = callback_query.message.text or ""
        if current_text != config_text:
            await callback_query.message.edit_text(
                config_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Refresh Config", callback_data="refresh_config")],
                    [InlineKeyboardButton(text="Proxy Status", callback_data="proxy_status")]
                ])
            )
        else:
            # Message content is the same, just answer the callback
            await callback_query.answer("Configuration is already up to date!")
            return
    
    await callback_query.answer("Configuration refreshed!")


@dp.callback_query(lambda c: c.data == "proxy_status")
async def proxy_status_callback(callback_query: CallbackQuery):
    """Handle proxy status callback"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, callback_query.from_user.id)
        
        if not await is_user_subscribed(user):
            await callback_query.answer("Subscription expired!", show_alert=True)
            return
        
        # Get detailed status information
        status_text = mtg_monitor.get_status_text()
        
        # Check proxy health
        health_status = await mtg_monitor.health_check()
        health_emoji = "✅" if health_status else "❌"
        health_text = "Healthy" if health_status else "Unhealthy"
        
        full_status = f"{status_text}\n\n🏥 **Health Check:** {health_emoji} {health_text}"
        
        # Check if message content would be the same to avoid TelegramBadRequest
        current_text = callback_query.message.text or ""
        if current_text != full_status:
            await callback_query.message.edit_text(
                full_status,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Refresh Status", callback_data="proxy_status")],
                    [InlineKeyboardButton(text="🔙 Back to Config", callback_data="get_config")]
                ])
            )
        else:
            # Message content is the same, just answer the callback
            await callback_query.answer("Status is already up to date!")
            return
    
    await callback_query.answer("Status updated!")


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


# ====== ADMIN COMMANDS ======

@dp.message(Command("admin"))
@admin_required
async def admin_command(message: Message):
    """Admin panel main menu"""
    admin_text = (
        "🔐 **Admin Panel**\n\n"
        "**Server Management:**\n"
        "/admin_servers - Manage proxy servers\n"
        "/admin_stats - View bot statistics\n"
        "/admin_users - User management\n"
        "/admin_payments - Payment overview\n\n"
        "**Quick Actions:**\n"
        "• Add/Remove servers\n"
        "• Monitor server status\n"
        "• View user statistics\n"
        "• Check payment reports"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖥️ Manage Servers", callback_data="admin_servers")],
        [InlineKeyboardButton(text="📊 View Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Manage Users", callback_data="admin_users")],
        [InlineKeyboardButton(text="💰 Payment Reports", callback_data="admin_payments")]
    ])
    
    await message.answer(admin_text, parse_mode="Markdown", reply_markup=keyboard)


@dp.message(Command("admin_servers"))
@admin_required
async def admin_servers_command(message: Message):
    """Manage proxy servers"""
    async for session in get_db():
        # Get all servers from database
        result = await session.execute(select(ProxyServer))
        servers = result.scalars().all()
        
        if not servers:
            # Initialize servers from config if database is empty
            config_servers = settings.get_proxy_servers()
            for server_str in config_servers:
                if ':' in server_str:
                    address, port = server_str.split(':', 1)
                    port = int(port)
                else:
                    address = server_str
                    port = 443
                
                server = ProxyServer(
                    address=address,
                    port=port,
                    is_active=True,
                    description=f"Server {address}"
                )
                session.add(server)
            
            await session.commit()
            # Re-fetch servers
            result = await session.execute(select(ProxyServer))
            servers = result.scalars().all()
        
        # Build servers list
        servers_text = "🖥️ **Proxy Servers Management**\n\n"
        if servers:
            for i, server in enumerate(servers, 1):
                status = "✅ Active" if server.is_active else "❌ Inactive"
                servers_text += f"**Server {i}:**\n"
                servers_text += f"Address: `{server.address}:{server.port}`\n"
                servers_text += f"Status: {status}\n"
                servers_text += f"Description: {server.description or 'N/A'}\n"
                servers_text += f"Location: {server.location or 'N/A'}\n"
                servers_text += f"Max Users: {server.max_users}\n\n"
        else:
            servers_text += "No servers configured.\n\n"
        
        servers_text += "Use the buttons below to manage servers:"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Server", callback_data="admin_add_server")],
            [InlineKeyboardButton(text="🗑️ Remove Server", callback_data="admin_remove_server")],
            [InlineKeyboardButton(text="⚙️ Configure Server", callback_data="admin_config_server")],
            [InlineKeyboardButton(text="🔄 Refresh List", callback_data="admin_refresh_servers")],
            [InlineKeyboardButton(text="🔙 Back to Admin", callback_data="admin_main")]
        ])
        
        await message.answer(servers_text, parse_mode="Markdown", reply_markup=keyboard)


@dp.message(Command("admin_stats"))
@admin_required
async def admin_stats_command(message: Message):
    """View bot statistics"""
    async for session in get_db():
        # Get user statistics
        total_users_result = await session.execute(select(User))
        total_users = len(total_users_result.scalars().all())
        
        active_users_result = await session.execute(
            select(User).where(User.subscription_until > datetime.now(timezone.utc))
        )
        active_subscribers = len(active_users_result.scalars().all())
        
        # Get payment statistics
        payments_result = await session.execute(
            select(Payment).where(Payment.status == "completed")
        )
        completed_payments = payments_result.scalars().all()
        total_revenue = sum(p.amount for p in completed_payments)
        
        # Get server statistics
        servers_result = await session.execute(select(ProxyServer))
        all_servers = servers_result.scalars().all()
        active_servers = [s for s in all_servers if s.is_active]
        
        # Get proxy config statistics
        configs_result = await session.execute(select(ProxyConfig))
        total_configs = len(configs_result.scalars().all())
        
        stats_text = (
            "📊 **Bot Statistics**\n\n"
            f"**Users:**\n"
            f"• Total Users: {total_users}\n"
            f"• Active Subscribers: {active_subscribers}\n"
            f"• Subscription Rate: {(active_subscribers/total_users*100) if total_users > 0 else 0:.1f}%\n\n"
            f"**Revenue:**\n"
            f"• Total Payments: {len(completed_payments)}\n"
            f"• Total Revenue: ${total_revenue:.2f}\n"
            f"• Average Payment: ${(total_revenue/len(completed_payments)) if completed_payments else 0:.2f}\n\n"
            f"**Infrastructure:**\n"
            f"• Total Servers: {len(all_servers)}\n"
            f"• Active Servers: {len(active_servers)}\n"
            f"• Total Proxy Configs: {total_configs}\n"
            f"• Configs per User: {(total_configs/active_subscribers) if active_subscribers > 0 else 0:.1f}\n\n"
            f"**Server Status:**\n"
        )
        
        for server in all_servers:
            status = "🟢" if server.is_active else "🔴"
            stats_text += f"{status} {server.address}:{server.port}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh Stats", callback_data="admin_refresh_stats")],
            [InlineKeyboardButton(text="📈 Detailed Report", callback_data="admin_detailed_stats")],
            [InlineKeyboardButton(text="🔙 Back to Admin", callback_data="admin_main")]
        ])
        
        await message.answer(stats_text, parse_mode="Markdown", reply_markup=keyboard)


@dp.message(Command("admin_users"))
@admin_required
async def admin_users_command(message: Message):
    """User management panel"""
    async for session in get_db():
        # Get recent users
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(10)
        )
        recent_users = result.scalars().all()
        
        users_text = "👥 **User Management**\n\n"
        users_text += "**Recent Users (Last 10):**\n\n"
        
        for user in recent_users:
            subscription_status = "✅" if await is_user_subscribed(user) else "❌"
            username = user.username or "N/A"
            users_text += f"ID: {user.telegram_id}\n"
            users_text += f"Name: {user.first_name} (@{username})\n"
            users_text += f"Subscribed: {subscription_status}\n"
            if user.subscription_until:
                users_text += f"Expires: {user.subscription_until.strftime('%Y-%m-%d %H:%M')}\n"
            users_text += f"Joined: {user.created_at.strftime('%Y-%m-%d')}\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Search User", callback_data="admin_search_user")],
            [InlineKeyboardButton(text="🚫 Block User", callback_data="admin_block_user")],
            [InlineKeyboardButton(text="✅ Unblock User", callback_data="admin_unblock_user")],
            [InlineKeyboardButton(text="🎁 Grant Subscription", callback_data="admin_grant_sub")],
            [InlineKeyboardButton(text="🔙 Back to Admin", callback_data="admin_main")]
        ])
        
        await message.answer(users_text, parse_mode="Markdown", reply_markup=keyboard)


@dp.message(Command("admin_payments"))
@admin_required
async def admin_payments_command(message: Message):
    """Payment reports and management"""
    async for session in get_db():
        # Get recent payments
        result = await session.execute(
            select(Payment).order_by(Payment.created_at.desc()).limit(10)
        )
        recent_payments = result.scalars().all()
        
        # Get payment summary
        completed_result = await session.execute(
            select(Payment).where(Payment.status == "completed")
        )
        completed_payments = completed_result.scalars().all()
        
        pending_result = await session.execute(
            select(Payment).where(Payment.status == "pending")
        )
        pending_payments = pending_result.scalars().all()
        
        total_revenue = sum(p.amount for p in completed_payments)
        pending_amount = sum(p.amount for p in pending_payments)
        
        payments_text = (
            "💰 **Payment Management**\n\n"
            f"**Summary:**\n"
            f"• Total Revenue: ${total_revenue:.2f}\n"
            f"• Completed Payments: {len(completed_payments)}\n"
            f"• Pending Payments: {len(pending_payments)} (${pending_amount:.2f})\n\n"
            f"**Recent Payments:**\n\n"
        )
        
        for payment in recent_payments:
            status_emoji = "✅" if payment.status == "completed" else "⏳"
            payments_text += f"{status_emoji} ${payment.amount:.2f} {payment.currency}\n"
            payments_text += f"User ID: {payment.user_id}\n"
            payments_text += f"Date: {payment.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            payments_text += f"Provider ID: {payment.provider_payment_id or 'N/A'}\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Payment Analytics", callback_data="admin_payment_analytics")],
            [InlineKeyboardButton(text="🔍 Search Payment", callback_data="admin_search_payment")],
            [InlineKeyboardButton(text="💸 Refund Payment", callback_data="admin_refund_payment")],
            [InlineKeyboardButton(text="🔙 Back to Admin", callback_data="admin_main")]
        ])
        
        await message.answer(payments_text, parse_mode="Markdown", reply_markup=keyboard)


# ====== ADMIN CALLBACK HANDLERS ======

@dp.callback_query(lambda c: c.data == "admin_servers")
@admin_required
async def admin_servers_callback(callback_query: CallbackQuery):
    """Handle admin servers callback"""
    await admin_servers_command(callback_query.message)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "admin_stats")
@admin_required
async def admin_stats_callback(callback_query: CallbackQuery):
    """Handle admin stats callback"""
    await admin_stats_command(callback_query.message)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "admin_users")
@admin_required
async def admin_users_callback(callback_query: CallbackQuery):
    """Handle admin users callback"""
    await admin_users_command(callback_query.message)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "admin_payments")
@admin_required
async def admin_payments_callback(callback_query: CallbackQuery):
    """Handle admin payments callback"""
    await admin_payments_command(callback_query.message)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "admin_main")
@admin_required
async def admin_main_callback(callback_query: CallbackQuery):
    """Handle return to admin main menu"""
    await admin_command(callback_query.message)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "admin_add_server")
@admin_required
async def admin_add_server_callback(callback_query: CallbackQuery):
    """Handle add server callback"""
    await callback_query.message.edit_text(
        "🖥️ **Add New Proxy Server**\n\n"
        "To add a new server, send a message in this format:\n"
        "**server_add <address> <port> [description]**\n\n"
        "Examples:\n"
        "• `server_add proxy.example.com 443 Main Server`\n"
        "• `server_add 192.168.1.100 8080 Local Test Server`\n\n"
        "The server will be added to the database and made available to users.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Servers", callback_data="admin_servers")]
        ])
    )
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "admin_remove_server")
@admin_required
async def admin_remove_server_callback(callback_query: CallbackQuery):
    """Handle remove server callback"""
    async for session in get_db():
        result = await session.execute(select(ProxyServer).where(ProxyServer.is_active == True))
        active_servers = result.scalars().all()
        
        if not active_servers:
            await callback_query.message.edit_text(
                "🖥️ **Remove Proxy Server**\n\n"
                "❌ No active servers to remove.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Back to Servers", callback_data="admin_servers")]
                ])
            )
            await callback_query.answer()
            return
        
        keyboard_buttons = []
        for server in active_servers:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"❌ Remove {server.address}:{server.port}",
                    callback_data=f"admin_remove_server_{server.id}"
                )
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 Back to Servers", callback_data="admin_servers")
        ])
        
        await callback_query.message.edit_text(
            "🖥️ **Remove Proxy Server**\n\n"
            "⚠️ **Warning:** Removing a server will disable it for all users.\n\n"
            "Select a server to remove:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("admin_remove_server_"))
@admin_required
async def admin_remove_server_confirm_callback(callback_query: CallbackQuery):
    """Handle server removal confirmation"""
    server_id = int(callback_query.data.split("_")[-1])
    
    async for session in get_db():
        result = await session.execute(select(ProxyServer).where(ProxyServer.id == server_id))
        server = result.scalar_one_or_none()
        
        if not server:
            await callback_query.answer("Server not found!", show_alert=True)
            return
        
        # Deactivate server instead of deleting
        server.is_active = False
        await session.commit()
        
        await callback_query.message.edit_text(
            f"✅ **Server Removed Successfully**\n\n"
            f"Server `{server.address}:{server.port}` has been deactivated.\n"
            f"Users will no longer receive configurations for this server.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back to Servers", callback_data="admin_servers")]
            ])
        )
    
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "admin_config_server")
@admin_required
async def admin_config_server_callback(callback_query: CallbackQuery):
    """Handle server configuration callback"""
    async for session in get_db():
        result = await session.execute(select(ProxyServer))
        servers = result.scalars().all()
        
        if not servers:
            await callback_query.message.edit_text(
                "🖥️ **Configure Proxy Server**\n\n"
                "❌ No servers to configure.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Back to Servers", callback_data="admin_servers")]
                ])
            )
            await callback_query.answer()
            return
        
        keyboard_buttons = []
        for server in servers:
            status = "✅" if server.is_active else "❌"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{status} Config {server.address}:{server.port}",
                    callback_data=f"admin_config_server_{server.id}"
                )
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 Back to Servers", callback_data="admin_servers")
        ])
        
        await callback_query.message.edit_text(
            "🖥️ **Configure Proxy Server**\n\n"
            "Select a server to configure:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("admin_config_server_"))
@admin_required
async def admin_config_server_detail_callback(callback_query: CallbackQuery):
    """Handle individual server configuration"""
    server_id = int(callback_query.data.split("_")[-1])
    
    async for session in get_db():
        result = await session.execute(select(ProxyServer).where(ProxyServer.id == server_id))
        server = result.scalar_one_or_none()
        
        if not server:
            await callback_query.answer("Server not found!", show_alert=True)
            return
        
        status = "✅ Active" if server.is_active else "❌ Inactive"
        config_text = (
            f"⚙️ **Server Configuration**\n\n"
            f"**Address:** `{server.address}:{server.port}`\n"
            f"**Status:** {status}\n"
            f"**Description:** {server.description or 'N/A'}\n"
            f"**Location:** {server.location or 'N/A'}\n"
            f"**Max Users:** {server.max_users}\n"
            f"**Created:** {server.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"**Updated:** {server.updated_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Use the buttons below to modify this server:"
        )
        
        toggle_text = "🔴 Deactivate" if server.is_active else "🟢 Activate"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=f"admin_toggle_server_{server.id}")],
            [InlineKeyboardButton(text="📝 Edit Description", callback_data=f"admin_edit_server_{server.id}")],
            [InlineKeyboardButton(text="🔙 Back to Config", callback_data="admin_config_server")]
        ])
        
        await callback_query.message.edit_text(
            config_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("admin_toggle_server_"))
@admin_required
async def admin_toggle_server_callback(callback_query: CallbackQuery):
    """Handle server activation/deactivation toggle"""
    server_id = int(callback_query.data.split("_")[-1])
    
    async for session in get_db():
        result = await session.execute(select(ProxyServer).where(ProxyServer.id == server_id))
        server = result.scalar_one_or_none()
        
        if not server:
            await callback_query.answer("Server not found!", show_alert=True)
            return
        
        # Toggle server status
        server.is_active = not server.is_active
        server.updated_at = datetime.now(timezone.utc)
        await session.commit()
        
        status = "activated" if server.is_active else "deactivated"
        await callback_query.answer(f"Server {status} successfully!")
        
        # Refresh the configuration view
        await admin_config_server_detail_callback(callback_query)


@dp.callback_query(lambda c: c.data == "admin_refresh_servers")
@admin_required
async def admin_refresh_servers_callback(callback_query: CallbackQuery):
    """Handle refresh servers list callback"""
    await admin_servers_command(callback_query.message)
    await callback_query.answer("Servers list refreshed!")


@dp.callback_query(lambda c: c.data == "admin_refresh_stats")
@admin_required
async def admin_refresh_stats_callback(callback_query: CallbackQuery):
    """Handle refresh stats callback"""
    await admin_stats_command(callback_query.message)
    await callback_query.answer("Statistics refreshed!")


@dp.callback_query(lambda c: c.data == "admin_grant_sub")
@admin_required
async def admin_grant_sub_callback(callback_query: CallbackQuery):
    """Handle grant subscription callback"""
    await callback_query.message.edit_text(
        "🎁 **Grant Subscription**\n\n"
        "To grant a subscription to a user, send a message in this format:\n"
        "**grant_sub <user_id> <days>**\n\n"
        "Examples:\n"
        "• `grant_sub 123456789 30` - Grant 30 days\n"
        "• `grant_sub 987654321 7` - Grant 7 days\n\n"
        "The subscription will be added to the user's account.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Users", callback_data="admin_users")]
        ])
    )
    await callback_query.answer()


# ====== ADMIN COMMAND HANDLERS ======

@dp.message(lambda message: message.text and message.text.startswith("server_add "))
@admin_required
async def handle_server_add_command(message: Message):
    """Handle server_add command"""
    try:
        parts = message.text.split(" ", 3)
        if len(parts) < 3:
            await message.answer(
                "❌ Invalid format. Use: `server_add <address> <port> [description]`",
                parse_mode="Markdown"
            )
            return
        
        address = parts[1]
        port = int(parts[2])
        description = parts[3] if len(parts) > 3 else f"Server {address}"
        
        async for session in get_db():
            # Check if server already exists
            result = await session.execute(
                select(ProxyServer).where(ProxyServer.address == address)
            )
            existing_server = result.scalar_one_or_none()
            
            if existing_server:
                await message.answer(
                    f"❌ Server `{address}` already exists in the database.",
                    parse_mode="Markdown"
                )
                return
            
            # Create new server
            server = ProxyServer(
                address=address,
                port=port,
                description=description,
                is_active=True
            )
            session.add(server)
            await session.commit()
            
            await message.answer(
                f"✅ **Server Added Successfully**\n\n"
                f"Address: `{address}:{port}`\n"
                f"Description: {description}\n"
                f"Status: Active\n\n"
                f"The server is now available for user configurations.",
                parse_mode="Markdown"
            )
    
    except ValueError:
        await message.answer(
            "❌ Invalid port number. Please use a valid integer.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error adding server: {e}")
        await message.answer(
            "❌ Error adding server. Please try again.",
            parse_mode="Markdown"
        )


@dp.message(lambda message: message.text and message.text.startswith("grant_sub "))
@admin_required
async def handle_grant_sub_command(message: Message):
    """Handle grant_sub command"""
    try:
        parts = message.text.split(" ")
        if len(parts) != 3:
            await message.answer(
                "❌ Invalid format. Use: `grant_sub <user_id> <days>`",
                parse_mode="Markdown"
            )
            return
        
        user_id = int(parts[1])
        days = int(parts[2])
        
        if days <= 0:
            await message.answer(
                "❌ Days must be a positive number.",
                parse_mode="Markdown"
            )
            return
        
        async for session in get_db():
            # Find user by telegram_id
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await message.answer(
                    f"❌ User with ID `{user_id}` not found.",
                    parse_mode="Markdown"
                )
                return
            
            # Grant subscription
            current_time = datetime.now(timezone.utc)
            if user.subscription_until and user.subscription_until > current_time:
                # Extend existing subscription
                user.subscription_until += timedelta(days=days)
            else:
                # Create new subscription
                user.subscription_until = current_time + timedelta(days=days)
            
            await session.commit()
            
            expiry_date = user.subscription_until.strftime('%Y-%m-%d %H:%M UTC')
            await message.answer(
                f"✅ **Subscription Granted**\n\n"
                f"User: {user.first_name} (@{user.username or 'N/A'})\n"
                f"Telegram ID: `{user_id}`\n"
                f"Days Added: {days}\n"
                f"Expires: {expiry_date}\n\n"
                f"The user now has access to proxy configurations.",
                parse_mode="Markdown"
            )
    
    except ValueError:
        await message.answer(
            "❌ Invalid user ID or days. Please use valid integers.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error granting subscription: {e}")
        await message.answer(
            "❌ Error granting subscription. Please try again.",
            parse_mode="Markdown"
        )