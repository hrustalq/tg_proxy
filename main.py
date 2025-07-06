import asyncio
import logging
from bot import bot, dp
from database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main function to run the bot"""
    logger.info("Starting Telegram Proxy Bot...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Start polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())