import asyncio
import nest_asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telethon import TelegramClient

# Применяем nest_asyncio для предотвращения ошибки "This event loop is already running"
nest_asyncio.apply()

# Данные с https://my.telegram.org
api_id = 25349084  
api_hash = '83d3769924a74543f25e67807fd0a6fd'
bot_token = '6958186056:AAFxlAPvOumHHvJNmpBZX52yUHtyE4z_qc4'

# Инициализация Telethon клиента от имени пользователя (не бота).
client = TelegramClient('+79222303887', api_id, api_hash)

# Обработчик для обычных сообщений: сохраняем ссылку в context.chat_data
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text and "t.me/" in text:
        link = text.strip()
        context.chat_data["channel_link"] = link
        await update.message.reply_text(
            f"Ссылка сохранена: {link}\nНажмите /parse для копирования последнего поста."
        )
    else:
        await update.message.reply_text("Пожалуйста, отправьте ссылку на публичный канал.")

# Обработчик команды /parse:
# Если переданы аргументы, используем их, иначе пытаемся взять сохраненную ссылку из context.chat_data.
async def parse_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if context.args:
        link = " ".join(context.args).strip()
    else:
        link = context.chat_data.get("channel_link")

    if not link or "t.me/" not in link:
        await update.message.reply_text("Сначала отправьте ссылку на публичный канал.")
        return

    try:
        # Извлекаем юзернейм из ссылки (ожидается формат t.me/username)
        channel_username = link.split("t.me/")[1].split()[0]
    except IndexError:
        await update.message.reply_text("Неверный формат ссылки.")
        return

    await update.message.reply_text(f"Получение последнего поста из канала @{channel_username}...")

    try:
        entity = await client.get_entity(channel_username)
        messages = await client.get_messages(entity, limit=1)
        if messages:
            msg = messages[0]
            text_msg = msg.text or "Нет текста"
            await context.bot.send_message(
                chat_id=chat_id, 
                text=f"Последний пост из @{channel_username}:\n\n{text_msg}"
            )
        else:
            await context.bot.send_message(chat_id=chat_id, text="Посты не найдены.")
    except Exception as e:
        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"Ошибка при получении данных: {e}"
        )

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "Привет!\n\n"
        "Я бот, который может копировать последний пост из публичного канала.\n"
        "Чтобы начать, отправь ссылку на канал (например, t.me/aaaitech), а затем вызови команду /parse."
    )
    await update.message.reply_text(welcome_text)

async def main():
    # Запуск Telethon клиента
    await client.start()
    
    # Создаем асинхронное приложение для бота
    app = Application.builder().token(bot_token).build()
    
    # Регистрируем обработчики:
    # - для текстовых сообщений (исключая команды) вызывается handle_message
    # - для команды /start
    # - для команды /parse
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("parse", parse_command))
    
    # Запуск long-polling, блокирующий выполнение до остановки бота.
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
