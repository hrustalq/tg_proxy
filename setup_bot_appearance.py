#!/usr/bin/env python3
"""
Bot Appearance Setup Script
Enhances the bot's appearance for new users using aiogram
"""

import asyncio
import logging
from aiogram import Bot
from aiogram.types import BotCommand, MenuButtonCommands, BotDescription, BotShortDescription
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_bot_appearance():
    """Enhanced bot appearance setup for new users"""
    bot = Bot(token=settings.bot_token)
    
    try:
        # 1. Set bot commands for autocompletion
        commands = [
            BotCommand(command="start", description="🚀 Запустить бота и открыть главное меню"),
            BotCommand(command="help", description="❓ Показать справку и доступные команды"),
            BotCommand(command="config", description="⚙️ Получить конфигурацию прокси"),
            BotCommand(command="status", description="📊 Проверить статус подписки")
        ]
        
        await bot.set_my_commands(commands)
        logger.info("✅ Bot commands set successfully")
        
        # 2. Set menu button to help users discover commands
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("✅ Menu button configured")
        
        # 3. Set bot description (what users see in bot profile)
        bot_description = (
            "🔐 SafeSurf Telegram Proxy Bot - Ваш безопасный способ обхода блокировок\n\n"
            "🌟 Возможности:\n"
            "• Быстрый и безопасный MTProto прокси\n"
            "• Серверы в разных странах\n"
            "• 30-дневный бесплатный пробный период\n"
            "• Простая настройка одним кликом\n"
            "• Поддержка 24/7\n\n"
            "💡 Начните с команды /start для получения доступа к прокси-серверам!"
        )
        
        await bot.set_my_description(bot_description)
        logger.info("✅ Bot description set successfully")
        
        # 4. Set short description (appears in search results)
        short_description = (
            "🔐 Быстрый и безопасный Telegram прокси. "
            "30 дней бесплатно для новых пользователей!"
        )
        
        await bot.set_my_short_description(short_description)
        logger.info("✅ Bot short description set successfully")
        
        # 5. Set bot name (optional - usually set via @BotFather)
        try:
            await bot.set_my_name("SafeSurf Telegram Proxy Bot")
            logger.info("✅ Bot name set successfully")
        except Exception as e:
            logger.warning(f"⚠️ Could not set bot name: {e}")
        
        # 6. Get and display current bot info
        me = await bot.get_me()
        logger.info(f"🤖 Bot info: @{me.username} ({me.first_name})")
        
        # 7. Display current settings
        commands_list = await bot.get_my_commands()
        logger.info(f"📋 Configured commands: {len(commands_list)}")
        for cmd in commands_list:
            logger.info(f"   /{cmd.command} - {cmd.description}")
        
        # 8. Get current description
        current_description = await bot.get_my_description()
        logger.info(f"📝 Current description: {current_description.description[:100]}...")
        
        # 9. Get current short description
        current_short_description = await bot.get_my_short_description()
        logger.info(f"📄 Current short description: {current_short_description.short_description}")
        
        logger.info("🎉 Bot appearance setup completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error setting up bot appearance: {e}")
        raise
    finally:
        await bot.session.close()

async def main():
    """Main function to run the bot appearance setup"""
    print("🚀 Setting up bot appearance...")
    await setup_bot_appearance()
    print("✅ Bot appearance setup complete!")

if __name__ == "__main__":
    asyncio.run(main())