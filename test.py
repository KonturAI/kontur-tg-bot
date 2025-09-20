import asyncio
import aiohttp
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer


async def test_local_server():
    # Replace with your NEW bot token from @BotFather
    BOT_TOKEN = "7601862716:AAEYmoWKPJnEWG5q2cy6AlKDGDGlFcBWBCQ"

    print("\n2. Тестируем локальный сервер...")
    session = AiohttpSession(api=TelegramAPIServer.from_base('https://kontur-media.ru/telegram-bot-api'))
    local_bot = Bot(token=BOT_TOKEN, session=session)

    local_bot = Bot(
        token=BOT_TOKEN,
        base_url="https://kontur-media.ru/telegram-bot-api/bot{token}/{method}",
        local_mode=True
    )

    try:
        me = await local_bot.get_me()
        print(f"✅ Локальный сервер работает: @{me.username}")

        # Test sending message
        chat_id = "5667467611"
        message = await local_bot.send_message(
            chat_id=chat_id,
            text="🔧 Тест локального Telegram Bot API сервера"
        )
        print(f"✅ Сообщение отправлено через локальный сервер: {message.message_id}")

    except Exception as e:
        print(f"❌ Ошибка локального сервера: {e}")
        print("Возможные причины:")
        print("- Локальный сервер недоступен")
        print("- Неверный base_url")
        print("- Проблемы с SSL сертификатом")

    finally:
        await local_bot.session.close()


if __name__ == "__main__":
    asyncio.run(test_local_server())