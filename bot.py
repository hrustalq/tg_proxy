import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import LabeledPrice, PreCheckoutQuery, BotCommand
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


async def setup_bot_commands():
    """Setup bot commands for autocompletion"""
    commands = [
        BotCommand(command="start", description="🚀 Запустить бота и открыть главное меню"),
        BotCommand(command="help", description="❓ Показать справку и доступные команды"),
        BotCommand(command="config", description="⚙️ Получить конфигурацию прокси"),
        BotCommand(command="status", description="📊 Проверить статус подписки")
    ]
    
    # Set commands for autocompletion
    await bot.set_my_commands(commands)
    
    # Set menu button to help users discover commands
    from aiogram.types import MenuButtonCommands
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    
    logger.info("Bot commands and menu button set up successfully")


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
            if isinstance(message_or_query, CallbackQuery):
                await message_or_query.answer("❌ Доступ запрещен. Требуются права администратора.", show_alert=True)
            else:
                await message_or_query.answer("❌ Доступ запрещен. Требуются права администратора.")
            return
        return await func(message_or_query, **kwargs)
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
        [InlineKeyboardButton(text=f"Подписаться за {price_text}", callback_data="subscribe")],
        [InlineKeyboardButton(text="Получить пробный период", callback_data="free_trial")]
    ])
    return keyboard


def get_proxy_config_text(server_host: str = None) -> str:
    """Generate proxy configuration text using MTG proxy manager"""
    try:
        # Get MTG proxy configuration
        config_text = mtg_proxy_manager.get_proxy_config_text(server_host)
        
        return f"{config_text}"
    except Exception as e:
        logger.error(f"Error generating proxy config: {e}")
        return "❌ Ошибка при генерации конфигурации прокси. Попробуйте позже."


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
                f"Добро пожаловать, {user.first_name}! 🎉\n\n"
                f"✅ Ваша подписка активна до {expiration_date}\n\n"
                "Используйте /config для получения настроек прокси.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Получить конфигурацию прокси", callback_data="get_config")],
                    [InlineKeyboardButton(text=f"Продлить подписку (+{settings.subscription_price:.0f} {settings.currency})", callback_data="subscribe")]
                ])
            )
        else:
            await message.answer(
                f"Добро пожаловать в Telegram Proxy Bot, {user.first_name}! 🚀\n\n"
                "Получите неограниченный доступ к Telegram через наши безопасные прокси-серверы.\n\n"
                f"💰 Подписка: {settings.subscription_price:.0f} {settings.currency}/{settings.subscription_duration} дней\n"
                "🔒 Безопасный протокол MTProto прокси\n"
                "🌍 Множество серверов в разных локациях\n"
                "⚡ Высокоскоростные соединения\n\n"
                "Выберите опцию ниже:",
                reply_markup=get_subscription_keyboard()
            )


@dp.message(Command("help"))
async def help_command(message: Message):
    """Handle /help command"""
    help_text = (
        "🤖 **Команды Telegram Proxy Bot**\n\n"
        "💡 **Совет:** Наберите `/` чтобы увидеть все доступные команды!\n\n"
        "**Основные команды:**\n"
        "🚀 `/start` - Приветственное сообщение и главное меню\n"
        "⚙️ `/config` - Получить конфигурацию прокси\n"
        "📊 `/status` - Проверить статус подписки\n"
        "❓ `/help` - Показать это сообщение с справкой\n\n"
        "🔗 **Возможности:**\n"
        "• Безопасный протокол MTProto прокси\n"
        "• Множество серверов в разных локациях\n"
        "• Высокоскоростные соединения\n"
        "• 30-дневный бесплатный пробный период для новых пользователей\n"
        f"• Месячная подписка: {settings.subscription_price:.0f} {settings.currency}\n\n"
        "💡 **Быстрые действия:**\n"
        "• Используйте кнопки для удобной навигации\n"
        "• Нажмите на ссылки tg:// для мгновенной настройки\n"
        "• Обновляйте конфигурации для лучшей безопасности"
    )
    
    async for session in get_db():
        user = await get_user_by_telegram_id(session, message.from_user.id)
        
        # Add admin commands section for admin users
        if is_admin(message.from_user.id):
            admin_help = (
                "\n\n🔐 **Команды администратора:**\n"
                "• `/admin` - Панель администратора\n"
                "• `/admin_servers` - Управление прокси-серверами\n"
                "• `/admin_stats` - Просмотр статистики бота\n"
                "• `/admin_users` - Управление пользователями\n"
                "• `/admin_payments` - Обзор платежей"
            )
            help_text += admin_help
        
        if await is_user_subscribed(user):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Получить конфигурацию прокси", callback_data="get_config")],
                [InlineKeyboardButton(text="Проверить статус", callback_data="check_status")]
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
                f"📊 **Статус подписки**\n\n"
                f"✅ Статус: Активна\n"
                f"📅 Истекает: {expiration_date}\n"
                f"⏰ Осталось времени: {days_left} дней, {hours_left} часов\n\n"
                "Используйте /config для получения настроек прокси.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Получить конфигурацию прокси", callback_data="get_config")],
                    [InlineKeyboardButton(text="Продлить подписку", callback_data="subscribe")]
                ])
            )
        else:
            if user.subscription_until:
                await message.answer(
                    f"📊 **Статус подписки**\n\n"
                    f"❌ Статус: Истекла\n"
                    f"📅 Истекла: {user.subscription_until.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                    "Подпишитесь для восстановления доступа к прокси-серверам.",
                    parse_mode="Markdown",
                    reply_markup=get_subscription_keyboard()
                )
            else:
                await message.answer(
                    f"📊 **Статус подписки**\n\n"
                    f"❌ Статус: Нет подписки\n\n"
                    "Подпишитесь или попробуйте бесплатный пробный период для доступа к прокси-серверам.",
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
                    f"❌ Ваша подписка истекла {expired_date}\n\n"
                    "Пожалуйста, подпишитесь для восстановления доступа к конфигурациям прокси.",
                    reply_markup=get_subscription_keyboard()
                )
            else:
                await message.answer(
                    "❌ У вас нет активной подписки.\n\n"
                    "Пожалуйста, подпишитесь или попробуйте бесплатный пробный период для доступа к конфигурациям прокси.",
                    reply_markup=get_subscription_keyboard()
                )
            return
        
        # Get proxy servers from settings and use the first one as default
        proxy_servers = settings.get_proxy_servers()
        server_host = proxy_servers[0].split(':')[0] if proxy_servers else None
        
        config_text = get_proxy_config_text(server_host)
        
        # Get Telegram proxy URL for the button
        telegram_proxy_url = mtg_proxy_manager.get_telegram_proxy_url(server_host)
        
        await message.answer(
            config_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📱 Открыть в Telegram", url=telegram_proxy_url)],
                [InlineKeyboardButton(text="Обновить конфигурацию", callback_data="refresh_config")],
                [InlineKeyboardButton(text="Статус прокси", callback_data="proxy_status")]
            ])
        )


@dp.callback_query(lambda c: c.data == "subscribe")
async def subscribe_callback(callback_query: CallbackQuery):
    """Handle subscription callback"""
    try:
        prices = [LabeledPrice(label="Subscription", amount=int(settings.subscription_price * 100))]
        
        await bot.send_invoice(
            chat_id=callback_query.from_user.id,
            title="Подписка на Telegram Proxy",
            description=f"Получите {settings.subscription_duration} дней доступа к премиум прокси-серверам",
            provider_token=settings.payment_provider_token,
            currency=settings.currency,
            prices=prices,
            payload=f"subscription_{callback_query.from_user.id}"
        )
        
        await callback_query.answer("Счёт на оплату отправлен! Пожалуйста, завершите платёж.")
        
    except Exception as e:
        logger.error(f"Error sending invoice: {e}")
        await callback_query.answer("Ошибка при создании счёта на оплату. Пожалуйста, попробуйте позже.", show_alert=True)


@dp.callback_query(lambda c: c.data == "free_trial")
async def free_trial_callback(callback_query: CallbackQuery):
    """Handle free trial callback"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, callback_query.from_user.id)
        
        if await is_user_subscribed(user):
            await callback_query.answer("У вас уже есть активная подписка!", show_alert=True)
            return
        
        # Check if user already had a trial (US-002: cannot get multiple free trials)
        if user.subscription_until:
            await callback_query.answer("Бесплатный пробный период доступен только один раз на пользователя!", show_alert=True)
            return
        
        # Give 30 day free trial
        user.subscription_until = datetime.now(timezone.utc) + timedelta(days=30)
        await session.commit()
        
        expiration_time = user.subscription_until.strftime('%Y-%m-%d %H:%M UTC')
        await callback_query.message.edit_text(
            "🎉 Бесплатный пробный период активирован!\n\n"
            f"Теперь у вас есть 30 дней бесплатного доступа до {expiration_time}.\n\n"
            "Используйте /config для получения настроек прокси.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Получить конфигурацию прокси", callback_data="get_config")]
            ])
        )
    
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "get_config")
async def get_config_callback(callback_query: CallbackQuery):
    """Handle get config callback"""
    try:
        # Create a modified message object with the correct user info
        message = callback_query.message
        message.from_user = callback_query.from_user
        await config_command(message)
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in get_config_callback: {e}")
        await callback_query.answer("❌ Ошибка при получении конфигурации", show_alert=True)


@dp.callback_query(lambda c: c.data == "check_status")
async def check_status_callback(callback_query: CallbackQuery):
    """Handle check status callback"""
    try:
        message = callback_query.message
        message.from_user = callback_query.from_user
        await status_command(message)
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in check_status_callback: {e}")
        await callback_query.answer("❌ Ошибка при проверке статуса", show_alert=True)


@dp.callback_query(lambda c: c.data == "refresh_config")
async def refresh_config_callback(callback_query: CallbackQuery):
    """Handle refresh config callback"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, callback_query.from_user.id)
        
        if not await is_user_subscribed(user):
            await callback_query.answer("Подписка истекла!", show_alert=True)
            return
        
        # Get proxy servers from settings and use the first one as default
        proxy_servers = settings.get_proxy_servers()
        server_host = proxy_servers[0].split(':')[0] if proxy_servers else None
        
        config_text = get_proxy_config_text(server_host)
        
        # Get Telegram proxy URL for the button
        telegram_proxy_url = mtg_proxy_manager.get_telegram_proxy_url(server_host)
        
        # Check if message content would be the same to avoid TelegramBadRequest
        current_text = callback_query.message.text or ""
        if current_text != config_text:
            await callback_query.message.edit_text(
                config_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📱 Открыть в Telegram", url=telegram_proxy_url)],
                    [InlineKeyboardButton(text="Обновить конфигурацию", callback_data="refresh_config")],
                    [InlineKeyboardButton(text="Статус прокси", callback_data="proxy_status")]
                ])
            )
        else:
            # Message content is the same, just answer the callback
            await callback_query.answer("Конфигурация уже обновлена!")
            return
    
    await callback_query.answer("Конфигурация обновлена!")


@dp.callback_query(lambda c: c.data == "proxy_status")
async def proxy_status_callback(callback_query: CallbackQuery):
    """Handle proxy status callback"""
    async for session in get_db():
        user = await get_user_by_telegram_id(session, callback_query.from_user.id)
        
        if not await is_user_subscribed(user):
            await callback_query.answer("Подписка истекла!", show_alert=True)
            return
        
        # Get detailed status information
        status_text = mtg_monitor.get_status_text()
        
        # Check proxy health
        health_status = await mtg_monitor.health_check()
        health_emoji = "✅" if health_status else "❌"
        health_text = "Работает" if health_status else "Не работает"
        
        full_status = f"{status_text}\n\n🏥 **Проверка работоспособности:** {health_emoji} {health_text}"
        
        # Check if message content would be the same to avoid TelegramBadRequest
        current_text = callback_query.message.text or ""
        if current_text != full_status:
            await callback_query.message.edit_text(
                full_status,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Обновить статус", callback_data="proxy_status")],
                    [InlineKeyboardButton(text="🔙 Вернуться к конфигурации", callback_data="get_config")]
                ])
            )
        else:
            # Message content is the same, just answer the callback
            await callback_query.answer("Статус уже обновлён!")
            return
    
    await callback_query.answer("Статус обновлён!")


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
            f"✅ Платёж успешно завершён!\n\n"
            f"Ваша подписка активна до {user.subscription_until.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
            "Используйте /config для получения настроек прокси.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Получить конфигурацию прокси", callback_data="get_config")]
            ])
        )


# ====== ADMIN COMMANDS ======

@dp.message(Command("admin"))
@admin_required
async def admin_command(message: Message):
    """Admin panel main menu"""
    admin_text = (
        "🔐 **Панель администратора**\n\n"
        "**Доступные команды:**\n"
        "`/admin_servers` - Управление прокси-серверами\n"
        "`/admin_stats` - Просмотр статистики бота\n"
        "`/admin_users` - Управление пользователями\n"
        "`/admin_payments` - Обзор платежей\n\n"
        "**Быстрые действия:**\n"
        "• Добавить/удалить серверы\n"
        "• Мониторинг статуса серверов\n"
        "• Просмотр статистики пользователей\n"
        "• Проверка отчётов о платежах"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖥️ Управление серверами", callback_data="admin_servers")],
        [InlineKeyboardButton(text="📊 Просмотр статистики", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users")],
        [InlineKeyboardButton(text="💰 Отчёты о платежах", callback_data="admin_payments")]
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
        servers_text = "🖥️ **Управление прокси-серверами**\n\n"
        if servers:
            for i, server in enumerate(servers, 1):
                status = "✅ Активен" if server.is_active else "❌ Неактивен"
                servers_text += f"**Сервер {i}:**\n"
                servers_text += f"Адрес: `{server.address}:{server.port}`\n"
                servers_text += f"Статус: {status}\n"
                servers_text += f"Описание: {server.description or 'Н/Д'}\n"
                servers_text += f"Местоположение: {server.location or 'Н/Д'}\n"
                servers_text += f"Макс. пользователей: {server.max_users}\n\n"
        else:
            servers_text += "Серверы не настроены.\n\n"
        
        servers_text += "Используйте кнопки ниже для управления серверами:"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить сервер", callback_data="admin_add_server")],
            [InlineKeyboardButton(text="🗑️ Удалить сервер", callback_data="admin_remove_server")],
            [InlineKeyboardButton(text="⚙️ Настроить сервер", callback_data="admin_config_server")],
            [InlineKeyboardButton(text="🔄 Обновить список", callback_data="admin_refresh_servers")],
            [InlineKeyboardButton(text="🔙 Назад к админ-панели", callback_data="admin_main")]
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
            "📊 **Статистика бота**\n\n"
            f"**Пользователи:**\n"
            f"• Всего пользователей: {total_users}\n"
            f"• Активных подписчиков: {active_subscribers}\n"
            f"• Процент подписки: {(active_subscribers/total_users*100) if total_users > 0 else 0:.1f}%\n\n"
            f"**Доходы:**\n"
            f"• Всего платежей: {len(completed_payments)}\n"
            f"• Общий доход: ${total_revenue:.2f}\n"
            f"• Средний платёж: ${(total_revenue/len(completed_payments)) if completed_payments else 0:.2f}\n\n"
            f"**Инфраструктура:**\n"
            f"• Всего серверов: {len(all_servers)}\n"
            f"• Активных серверов: {len(active_servers)}\n"
            f"• Всего конфигураций прокси: {total_configs}\n"
            f"• Конфигураций на пользователя: {(total_configs/active_subscribers) if active_subscribers > 0 else 0:.1f}\n\n"
            f"**Статус серверов:**\n"
        )
        
        for server in all_servers:
            status = "🟢" if server.is_active else "🔴"
            stats_text += f"{status} {server.address}:{server.port}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить статистику", callback_data="admin_refresh_stats")],
            [InlineKeyboardButton(text="📈 Подробный отчёт", callback_data="admin_detailed_stats")],
            [InlineKeyboardButton(text="🔙 Назад к админ-панели", callback_data="admin_main")]
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
        
        users_text = "👥 **Управление пользователями**\n\n"
        users_text += "**Недавние пользователи (последние 10):**\n\n"
        
        for user in recent_users:
            subscription_status = "✅" if await is_user_subscribed(user) else "❌"
            username = user.username or "Н/Д"
            users_text += f"ID: {user.telegram_id}\n"
            users_text += f"Имя: {user.first_name} (@{username})\n"
            users_text += f"Подписан: {subscription_status}\n"
            if user.subscription_until:
                users_text += f"Истекает: {user.subscription_until.strftime('%Y-%m-%d %H:%M')}\n"
            users_text += f"Присоединился: {user.created_at.strftime('%Y-%m-%d')}\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin_search_user")],
            [InlineKeyboardButton(text="🚫 Заблокировать пользователя", callback_data="admin_block_user")],
            [InlineKeyboardButton(text="✅ Разблокировать пользователя", callback_data="admin_unblock_user")],
            [InlineKeyboardButton(text="🎁 Предоставить подписку", callback_data="admin_grant_sub")],
            [InlineKeyboardButton(text="🔙 Назад к админ-панели", callback_data="admin_main")]
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
            "💰 **Управление платежами**\n\n"
            f"**Сводка:**\n"
            f"• Общий доход: ${total_revenue:.2f}\n"
            f"• Завершённые платежи: {len(completed_payments)}\n"
            f"• Ожидающие платежи: {len(pending_payments)} (${pending_amount:.2f})\n\n"
            f"**Недавние платежи:**\n\n"
        )
        
        for payment in recent_payments:
            status_emoji = "✅" if payment.status == "completed" else "⏳"
            payments_text += f"{status_emoji} ${payment.amount:.2f} {payment.currency}\n"
            payments_text += f"ID пользователя: {payment.user_id}\n"
            payments_text += f"Дата: {payment.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            payments_text += f"ID провайдера: {payment.provider_payment_id or 'Н/Д'}\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Аналитика платежей", callback_data="admin_payment_analytics")],
            [InlineKeyboardButton(text="🔍 Найти платёж", callback_data="admin_search_payment")],
            [InlineKeyboardButton(text="💸 Возврат платежа", callback_data="admin_refund_payment")],
            [InlineKeyboardButton(text="🔙 Назад к админ-панели", callback_data="admin_main")]
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
        "🖥️ **Добавить новый прокси-сервер**\n\n"
        "Для добавления нового сервера отправьте сообщение в следующем формате:\n"
        "**server_add <адрес> <порт> [описание]**\n\n"
        "Примеры:\n"
        "• `server_add proxy.example.com 443 Основной сервер`\n"
        "• `server_add 192.168.1.100 8080 Локальный тестовый сервер`\n\n"
        "Сервер будет добавлен в базу данных и станет доступен пользователям.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к серверам", callback_data="admin_servers")]
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
                "🖥️ **Удалить прокси-сервер**\n\n"
                "❌ Нет активных серверов для удаления.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад к серверам", callback_data="admin_servers")]
                ])
            )
            await callback_query.answer()
            return
        
        keyboard_buttons = []
        for server in active_servers:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"❌ Удалить {server.address}:{server.port}",
                    callback_data=f"admin_remove_server_{server.id}"
                )
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 Back to Servers", callback_data="admin_servers")
        ])
        
        await callback_query.message.edit_text(
            "🖥️ **Удалить прокси-сервер**\n\n"
            "⚠️ **Внимание:** Удаление сервера отключит его для всех пользователей.\n\n"
            "Выберите сервер для удаления:",
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
            await callback_query.answer("Сервер не найден!", show_alert=True)
            return
        
        # Deactivate server instead of deleting
        server.is_active = False
        await session.commit()
        
        await callback_query.message.edit_text(
            f"✅ **Сервер успешно удален**\n\n"
            f"Сервер `{server.address}:{server.port}` был деактивирован.\n"
            f"Пользователи больше не будут получать конфигурации для этого сервера.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад к серверам", callback_data="admin_servers")]
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
            await callback_query.answer("Сервер не найден!", show_alert=True)
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
            await callback_query.answer("Сервер не найден!", show_alert=True)
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
                "❌ Неверный формат. Используйте: `server_add <адрес> <порт> [описание]`",
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
                    f"❌ Сервер `{address}` уже существует в базе данных.",
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
                f"✅ **Сервер успешно добавлен**\n\n"
                f"Адрес: `{address}:{port}`\n"
                f"Описание: {description}\n"
                f"Статус: Активен\n\n"
                f"Сервер теперь доступен для пользовательских конфигураций.",
                parse_mode="Markdown"
            )
    
    except ValueError:
        await message.answer(
            "❌ Неверный номер порта. Пожалуйста, используйте правильное целое число.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error adding server: {e}")
        await message.answer(
            "❌ Ошибка при добавлении сервера. Пожалуйста, попробуйте снова.",
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
                "❌ Неверный формат. Используйте: `grant_sub <user_id> <дни>`",
                parse_mode="Markdown"
            )
            return
        
        user_id = int(parts[1])
        days = int(parts[2])
        
        if days <= 0:
            await message.answer(
                "❌ Количество дней должно быть положительным числом.",
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
                    f"❌ Пользователь с ID `{user_id}` не найден.",
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
                f"✅ **Подписка предоставлена**\n\n"
                f"Пользователь: {user.first_name} (@{user.username or 'Н/Д'})\n"
                f"Telegram ID: `{user_id}`\n"
                f"Добавлено дней: {days}\n"
                f"Истекает: {expiry_date}\n\n"
                f"Пользователь теперь имеет доступ к конфигурациям прокси.",
                parse_mode="Markdown"
            )
    
    except ValueError:
        await message.answer(
            "❌ Неверный ID пользователя или количество дней. Пожалуйста, используйте правильные целые числа.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error granting subscription: {e}")
        await message.answer(
            "❌ Ошибка при предоставлении подписки. Пожалуйста, попробуйте снова.",
            parse_mode="Markdown"
        )


# ====== MISSING ADMIN HANDLERS ======

@dp.callback_query(lambda c: c.data == "admin_detailed_stats")
@admin_required
async def admin_detailed_stats_callback(callback_query: CallbackQuery):
    """Handle detailed stats callback"""
    async for session in get_db():
        try:
            # Get detailed statistics
            total_users_result = await session.execute(select(User))
            all_users = total_users_result.scalars().all()
            
            active_users_result = await session.execute(
                select(User).where(User.subscription_until > datetime.now(timezone.utc))
            )
            active_users = active_users_result.scalars().all()
            
            payments_result = await session.execute(
                select(Payment).where(Payment.status == "completed")
            )
            payments = payments_result.scalars().all()
            
            # Calculate detailed metrics
            total_users = len(all_users)
            active_subscribers = len(active_users)
            total_revenue = sum(p.amount for p in payments)
            
            # Get user statistics by creation date
            recent_users = [u for u in all_users if u.created_at > datetime.now(timezone.utc) - timedelta(days=7)]
            
            # Get payment statistics
            recent_payments = [p for p in payments if p.created_at > datetime.now(timezone.utc) - timedelta(days=7)]
            
            detailed_text = (
                f"📈 **Подробная статистика**\n\n"
                f"**Пользователи:**\n"
                f"• Всего пользователей: {total_users}\n"
                f"• Активных подписчиков: {active_subscribers}\n"
                f"• Новых за неделю: {len(recent_users)}\n"
                f"• Процент конверсии: {(active_subscribers/total_users*100) if total_users > 0 else 0:.1f}%\n\n"
                f"**Доходы:**\n"
                f"• Общий доход: ${total_revenue:.2f}\n"
                f"• Доход за неделю: ${sum(p.amount for p in recent_payments):.2f}\n"
                f"• Средний платёж: ${(total_revenue/len(payments)) if payments else 0:.2f}\n"
                f"• Платежей за неделю: {len(recent_payments)}\n\n"
                f"**Тренды:**\n"
                f"• Рост пользователей: {(len(recent_users)/7):.1f} в день\n"
                f"• Рост доходов: ${(sum(p.amount for p in recent_payments)/7):.2f} в день\n"
            )
            
            await callback_query.message.edit_text(
                detailed_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_detailed_stats")],
                    [InlineKeyboardButton(text="🔙 Назад к статистике", callback_data="admin_stats")]
                ])
            )
        except Exception as e:
            logger.error(f"Error in detailed stats: {e}")
            await callback_query.answer("❌ Ошибка при получении детальной статистики", show_alert=True)
    
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "admin_search_user")
@admin_required
async def admin_search_user_callback(callback_query: CallbackQuery):
    """Handle search user callback"""
    await callback_query.message.edit_text(
        "🔍 **Поиск пользователя**\n\n"
        "Для поиска пользователя отправьте сообщение в формате:\n"
        "**search_user <user_id>**\n\n"
        "Пример:\n"
        "• `search_user 123456789`\n\n"
        "Будет показана информация о пользователе и его подписке.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к пользователям", callback_data="admin_users")]
        ])
    )
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "admin_block_user")
@admin_required
async def admin_block_user_callback(callback_query: CallbackQuery):
    """Handle block user callback"""
    await callback_query.message.edit_text(
        "🚫 **Заблокировать пользователя**\n\n"
        "Для блокировки пользователя отправьте сообщение в формате:\n"
        "**block_user <user_id>**\n\n"
        "Пример:\n"
        "• `block_user 123456789`\n\n"
        "Пользователь будет заблокирован и не сможет использовать бота.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к пользователям", callback_data="admin_users")]
        ])
    )
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "admin_unblock_user")
@admin_required
async def admin_unblock_user_callback(callback_query: CallbackQuery):
    """Handle unblock user callback"""
    await callback_query.message.edit_text(
        "✅ **Разблокировать пользователя**\n\n"
        "Для разблокировки пользователя отправьте сообщение в формате:\n"
        "**unblock_user <user_id>**\n\n"
        "Пример:\n"
        "• `unblock_user 123456789`\n\n"
        "Пользователь будет разблокирован и сможет снова использовать бота.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к пользователям", callback_data="admin_users")]
        ])
    )
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "admin_payment_analytics")
@admin_required
async def admin_payment_analytics_callback(callback_query: CallbackQuery):
    """Handle payment analytics callback"""
    async for session in get_db():
        try:
            # Get payment analytics
            payments_result = await session.execute(
                select(Payment).where(Payment.status == "completed")
            )
            payments = payments_result.scalars().all()
            
            if not payments:
                await callback_query.message.edit_text(
                    "📊 **Аналитика платежей**\n\n"
                    "❌ Нет данных о завершённых платежах.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔙 Назад к платежам", callback_data="admin_payments")]
                    ])
                )
                await callback_query.answer()
                return
            
            # Calculate analytics
            total_revenue = sum(p.amount for p in payments)
            avg_payment = total_revenue / len(payments)
            
            # Payment by currency
            currency_stats = {}
            for payment in payments:
                currency = payment.currency
                if currency not in currency_stats:
                    currency_stats[currency] = {"count": 0, "total": 0}
                currency_stats[currency]["count"] += 1
                currency_stats[currency]["total"] += payment.amount
            
            # Recent payments (last 30 days)
            recent_payments = [p for p in payments if p.created_at > datetime.now(timezone.utc) - timedelta(days=30)]
            
            analytics_text = (
                f"📊 **Аналитика платежей**\n\n"
                f"**Общая статистика:**\n"
                f"• Всего платежей: {len(payments)}\n"
                f"• Общий доход: ${total_revenue:.2f}\n"
                f"• Средний платёж: ${avg_payment:.2f}\n"
                f"• Платежей за 30 дней: {len(recent_payments)}\n\n"
                f"**По валютам:**\n"
            )
            
            for currency, stats in currency_stats.items():
                analytics_text += f"• {currency}: {stats['count']} платежей, ${stats['total']:.2f}\n"
            
            await callback_query.message.edit_text(
                analytics_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_payment_analytics")],
                    [InlineKeyboardButton(text="🔙 Назад к платежам", callback_data="admin_payments")]
                ])
            )
        except Exception as e:
            logger.error(f"Error in payment analytics: {e}")
            await callback_query.answer("❌ Ошибка при получении аналитики платежей", show_alert=True)
    
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "admin_search_payment")
@admin_required
async def admin_search_payment_callback(callback_query: CallbackQuery):
    """Handle search payment callback"""
    await callback_query.message.edit_text(
        "🔍 **Поиск платежа**\n\n"
        "Для поиска платежа отправьте сообщение в формате:\n"
        "**search_payment <payment_id>**\n\n"
        "Пример:\n"
        "• `search_payment 123`\n\n"
        "Будет показана информация о платеже и связанном пользователе.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к платежам", callback_data="admin_payments")]
        ])
    )
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "admin_refund_payment")
@admin_required
async def admin_refund_payment_callback(callback_query: CallbackQuery):
    """Handle refund payment callback"""
    await callback_query.message.edit_text(
        "💸 **Возврат платежа**\n\n"
        "Для возврата платежа отправьте сообщение в формате:\n"
        "**refund_payment <payment_id>**\n\n"
        "Пример:\n"
        "• `refund_payment 123`\n\n"
        "⚠️ **Внимание:** Возврат платежа отменит подписку пользователя.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к платежам", callback_data="admin_payments")]
        ])
    )
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("admin_edit_server_"))
@admin_required
async def admin_edit_server_callback(callback_query: CallbackQuery):
    """Handle edit server callback"""
    server_id = int(callback_query.data.split("_")[-1])
    
    await callback_query.message.edit_text(
        f"📝 **Редактировать сервер**\n\n"
        f"Для редактирования описания сервера отправьте сообщение в формате:\n"
        f"**edit_server {server_id} <новое_описание>**\n\n"
        f"Пример:\n"
        f"• `edit_server {server_id} Основной сервер США`\n\n"
        f"Описание сервера будет обновлено.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к настройкам", callback_data=f"admin_config_server_{server_id}")]
        ])
    )
    await callback_query.answer()


# ====== FALLBACK HANDLERS ======

@dp.message(lambda message: message.text and message.text.startswith('/'))
async def handle_unknown_command(message: Message):
    """Handle unknown commands with helpful message"""
    command = message.text.split()[0]  # Get just the command part
    
    # Check if user is admin to provide appropriate command list
    user_is_admin = is_admin(message.from_user.id)
    
    unknown_command_text = (
        f"❓ **Неизвестная команда: `{command}`**\n\n"
        "Я не распознаю эту команду. Вот доступные команды:\n\n"
        "**Основные команды:**\n"
        "• `/start` - Запустить бота и открыть главное меню\n"
        "• `/help` - Показать справку и доступные команды\n"
        "• `/config` - Получить конфигурацию прокси\n"
        "• `/status` - Проверить статус подписки\n"
    )
    
    # Add admin commands for admin users
    if user_is_admin:
        unknown_command_text += (
            "\n**Команды администратора:**\n"
            "• `/admin` - Панель администратора\n"
            "• `/admin_servers` - Управление прокси-серверами\n"
            "• `/admin_stats` - Просмотр статистики бота\n"
            "• `/admin_users` - Управление пользователями\n"
            "• `/admin_payments` - Обзор платежей\n"
        )
    
    unknown_command_text += "\n💡 **Совет:** Наберите `/` чтобы увидеть команды с автодополнением!"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Показать справку", callback_data="show_help")],
        [InlineKeyboardButton(text="🚀 Перейти в главное меню", callback_data="show_start")]
    ])
    
    await message.answer(unknown_command_text, parse_mode="Markdown", reply_markup=keyboard)


@dp.callback_query(lambda c: c.data == "show_help")
async def show_help_callback(callback_query: CallbackQuery):
    """Handle show help callback from unknown command handler"""
    # Create a message object for the help command
    message = callback_query.message
    message.from_user = callback_query.from_user
    await help_command(message)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "show_start")
async def show_start_callback(callback_query: CallbackQuery):
    """Handle show start callback from unknown command handler"""
    # Create a message object for the start command
    message = callback_query.message
    message.from_user = callback_query.from_user
    await start_command(message)
    await callback_query.answer()


@dp.message()
async def handle_text_message(message: Message):
    """Handle any other text messages with guidance"""
    guidance_text = (
        "👋 Привет! Я Telegram Proxy Bot.\n\n"
        "💡 **Чтобы начать:**\n"
        "• Наберите `/start` чтобы увидеть главное меню\n"
        "• Наберите `/help` чтобы увидеть все доступные команды\n"
        "• Наберите `/` чтобы увидеть команды с автодополнением\n\n"
        "🔧 **Быстрые действия:**"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Запустить бота", callback_data="show_start")],
        [InlineKeyboardButton(text="📋 Показать справку", callback_data="show_help")]
    ])
    
    await message.answer(guidance_text, parse_mode="Markdown", reply_markup=keyboard)