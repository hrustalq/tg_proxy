import asyncio
import logging
from bot import bot, dp, setup_bot_commands
from database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main function to run the bot"""
    logger.info("Запуск Telegram Proxy Bot...")
    
    # Initialize database
    await init_db()
    logger.info("База данных инициализирована")
    
    # Setup bot commands for autocompletion
    await setup_bot_commands()
    
    # Start polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())