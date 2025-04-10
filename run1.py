    import asyncio
    import nest_asyncio
    import textwrap
    import re
    from aiogram import Bot, Dispatcher, types

    import aiohttp
    from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        ContextTypes,
        filters,
        ConversationHandler,
        JobQueue,
    )
    from telethon import TelegramClient
    from telegram import Message

    # Apply nest_asyncio for async loops
    nest_asyncio.apply()
    # Initialize bot
    dp = Dispatcher()
    # Configuration
    api_id = 25349084
    api_hash = "83d3769924a74543f25e67807fd0a6fd"
    bot_token = "6958186056:AAFxlAPvOumHHvJNmpBZX52yUHtyE4z_qc4"
    mistral_api_key = "qOD6O33rZUL7pAHzJnMZx5jD1MuttwSs"

    # Initialize Telethon client
    client = TelegramClient("+79222303887", api_id, api_hash)

    # States for conversation
    class State:
        SET_INTERVAL = 1  # Для обработки установки интервала

    # Keyboard setup
    settings_keyboard = ReplyKeyboardMarkup(
        [["/setinterval", "/parse"], ["/report", "/stop"]],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )

    class EnhancedNewsProcessor:
        def __init__(self, keywords: list = None):
            self.keywords = keywords or [
                "финансы", "акции", "нефть", "газ", "экономика",
                "курс", "биржа", "дивиденды", "криптовалюта", "инвестиции"
            ]

        def process_news(self, news: list, top_n: int = 5, sentences_in_summary: int = 3) -> list:
            processed = []
            for text in news:
                sentences = self._split_sentences(text)
                scored = [(s, self._calculate_interest_score(s)) for s in sentences]
                scored.sort(key=lambda x: x[1], reverse=True)
                processed.append([s[0] for s in scored[:sentences_in_summary]])
            return self._group_similar(processed, top_n)

        def _split_sentences(self, text: str) -> list:
            text = re.sub(r"http\S+|www\S+|https\S+", "", text, flags=re.MULTILINE)
            text = re.sub(r"[■•&]", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            
            sentences = re.split(
                r"(?<!\w\.\w.)(?<![A-ZА-Я][a-zа-я]\.)(?<=[.!?])\s+(?=[А-ЯA-Z])", text
            )
            return [s.strip() for s in sentences if 20 < len(s.strip()) < 500 and not s.isdigit()]

        def _calculate_interest_score(self, text: str) -> float:
            text = re.sub(r"\s+", " ", text)
            keyword_count = sum(
                1 for word in self.keywords if re.search(rf"\b{word}\b", text.lower())
            )
            number_count = len(re.findall(r"\b\d+[\.,]\d+\b", text))
            length_score = min(len(text) / 400, 1.0)
            entity_score = len(
                re.findall(
                    r"\b(USD|EUR|RUB|нефть|газ|акции|дивиденды|прибыль|кредит)\b",
                    text,
                    flags=re.IGNORECASE,
                )
            )
            return (
                keyword_count * 0.5
                + number_count * 0.3
                + entity_score * 0.2
                + length_score * 0.1
            )

        def _group_similar(self, items: list, top_n: int) -> list:
            return [group for group in items if any(len(s) > 10 for s in group)][:top_n]

    class MistralAPI:
        def __init__(self, api_key: str):
            self.base_url = "https://api.mistral.ai/v1"
            self.headers = {"Authorization": f"Bearer {api_key}"}

        async def generate(self, session: aiohttp.ClientSession, prompt: str) -> str:
            data = {
                "model": "mistral-medium",
                "messages": [
                    {
                        "role": "system",
                        "content": "Вы senior финансовый аналитик. Выдели 3 главных финансовых факта на русском. Только цифры, показатели, рыночные изменения.",
                    },
                    {"role": "user", "content": f"Материал:\n{prompt}\n\nВыдели только финансовые аспекты:"},
                ],
                "temperature": 0.2,
                "max_tokens": 600,
            }

            try:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=data,
                    headers=self.headers,
                    timeout=20,
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    return result["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"Ошибка API: {e}")
                return "Анализ недоступен. Рекомендуем проверить подключение."

    class ReportGenerator:
        def __init__(self, api_key: str):
            self.mistral = MistralAPI(api_key)

        def _format_prompt(self, grouped_posts: list) -> str:
            return "\n\n".join(
                f"Новость {i+1}: " + ". ".join(g[:200] for g in group if len(g) > 20)
                for i, group in enumerate(grouped_posts)
            )[:3500]

        async def generate_report(self, grouped_posts: list) -> str:
            async with aiohttp.ClientSession() as session:
                valid_posts = [group for group in grouped_posts if any(len(s) > 20 for s in group)]
                
                report = [
                    "═" * 60,
                    "ФИНАНСОВЫЙ БЮЛЛЕТЕНЬ".center(60),
                    "═" * 60,
                    "",
                ]

                for idx, group in enumerate(valid_posts, 1):
                    if not group:
                        continue

                    report.append(f"▌ Блок {idx} ▌".center(60, "─"))
                    for item in group:
                        if len(item) < 20:
                            continue

                        clean_text = re.sub(r"\s+", " ", item.split(".", 1)[-1].strip())
                        wrapped = textwrap.fill(
                            f"→ {clean_text[:300]}",
                            width=58,
                            initial_indent="  ",
                            subsequent_indent="    ",
                        )
                        report.append(wrapped)
                    report.append("")

                if valid_posts:
                    analysis = await self.mistral.generate(session, self._format_prompt(valid_posts))
                    report.extend(
                        [
                            "═" * 60,
                            "КЛЮЧЕВЫЕ ВЫВОДЫ:".ljust(60),
                            analysis,
                        ]
                    )
                else:
                    report.extend(
                        [
                            "═" * 60,
                            "⚠ Нет данных для анализа".center(60),
                        ]
                    )

                report.extend(
                    [
                        "",
                        "Отчет сгенерирован автоматически".center(60),
                        "═" * 60,
                    ]
                )

                return "\n".join(report)

    # Telegram bot handlers
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = "Привет! Я бот для финансового анализа.\nИспользуйте кнопки ниже для управления:"
        await update.message.reply_text(welcome_text, reply_markup=settings_keyboard)

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        if text and "t.me/" in text:
            context.chat_data["channel_link"] = text.strip()
            await update.message.reply_text(
                f"Ссылка сохранена: {text.strip()}\nИспользуй /parse для сбора постов."
            )
        else:
            await update.message.reply_text("Отправьте ссылку на публичный канал.")

    async def parse_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        link = (
            context.args[0]
            if context.args
            else context.chat_data.get("channel_link")
        )

        if not link or "t.me/" not in link:
            await update.message.reply_text("Сначала отправьте ссылку на публичный канал.")
            return

        try:
            channel_username = link.split("t.me/")[1].split()[0]
            entity = await client.get_entity(channel_username)
            messages = await client.get_messages(entity, limit=3)

            if not messages:
                await update.message.reply_text("Посты не найдены.")
                return

            context.chat_data.setdefault("posts", [])
            for msg in messages:
                if msg.text and msg.text not in context.chat_data["posts"]:
                    context.chat_data["posts"].append(msg.text)

            await update.message.reply_text(
                f"Добавлено {len(messages)} новых постов. Всего собрано: {len(context.chat_data['posts'])}"
            )

        except Exception as e:
            await update.message.reply_text(f"Ошибка: {str(e)}")

    async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if "posts" not in context.chat_data or not context.chat_data["posts"]:
            await update.message.reply_text("Сначала соберите посты с помощью /parse")
            return

        valid_posts = [p for p in context.chat_data["posts"] if p and len(p) > 50]
        if not valid_posts:
            await update.message.reply_text("❌ Все посты пустые или слишком короткие")
            return

        processor = EnhancedNewsProcessor()
        grouped_posts = processor.process_news(valid_posts, top_n=3, sentences_in_summary=2)

        report = await ReportGenerator(mistral_api_key).generate_report(grouped_posts)
        for part in [report[i:i+4096] for i in range(0, len(report), 4096)]:
            await update.message.reply_text(part)
    async def setinterval_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Введите интервал в минутах (1-1440):", 
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data["waiting_for"] = "interval"
        return State.SET_INTERVAL
    async def process_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            interval = int(update.message.text)
            if 1 <= interval <= 1440:
                context.user_data["interval"] = interval
                await update.message.reply_text(
                    f"✅ Интервал установлен: {interval} минут", 
                    reply_markup=settings_keyboard
                )
                await restart_scheduler(
                    update.effective_user.id,
                    update.effective_chat.id,
                    context
                )
            else:
                await update.message.reply_text("❌ Введите число от 1 до 1440")
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите целое число")
        
        context.user_data.pop("waiting_for", None)
        return ConversationHandler.END
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("setinterval", setinterval_command)],
        states={
            State.SET_INTERVAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_interval)
            ]
        },
        fallbacks=[]
    )
    async def periodic_report(context: ContextTypes.DEFAULT_TYPE):
        user_id = context.job.user_id
        chat_id = context.job.chat_id
        
        if "posts" not in context.chat_data or not context.chat_data["posts"]:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏰ Нет данных для отчета. Используйте /parse для сбора постов."
            )
            return

        valid_posts = [p for p in context.chat_data["posts"] if p and len(p) > 50]
        if not valid_posts:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏰ Все посты пустые. Используйте /parse для сбора новых данных."
            )
            return

        processor = EnhancedNewsProcessor()
        grouped_posts = processor.process_news(valid_posts, top_n=3, sentences_in_summary=2)
        
        report = await ReportGenerator(mistral_api_key).generate_report(grouped_posts)
        for part in [report[i:i+4096] for i in range(0, len(report), 4096)]:
            await context.bot.send_message(chat_id=chat_id, text=part)

    async def setinterval_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Введите интервал в минутах (1-1440):", 
            reply_markup=ReplyKeyboardRemove()
        )
        return State.SET_INTERVAL

    async def process_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            interval = int(update.message.text)
            if 1 <= interval <= 1440:
                context.user_data["interval"] = interval
                await update.message.reply_text(
                    f"✅ Интервал установлен: {interval} минут", 
                    reply_markup=settings_keyboard
                )
                
                # Убедимся, что JobQueue существует
                if not context.application.job_queue:
                    context.application.job_queue = JobQueue()
                    context.application.job_queue.set_application(context.application)
                
                await restart_scheduler(
                    update.effective_user.id,
                    update.effective_chat.id,
                    context
                )
            else:
                await update.message.reply_text("❌ Введите число от 1 до 1440")
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите целое число")
        
        return ConversationHandler.END

    async def restart_scheduler(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
        try:
            interval = context.user_data.get("interval", 60)
            
            # Удаление старой задачи
            current_jobs = context.job_queue.get_jobs_by_name(f"periodic_report_{user_id}")
            for job in current_jobs:
                job.schedule_removal()
            
            # Создание новой задачи
            context.job_queue.run_repeating(
                periodic_report,
                interval=interval * 60,
                first=10,
                chat_id=chat_id,
                user_id=user_id,
                name=f"periodic_report_{user_id}"
            )
            
        except Exception as e:
            print(f"Ошибка в restart_scheduler: {str(e)}")
            raise

    async def main():
        await client.start()
        app = Application.builder().token(bot_token).build()
        
        # Инициализация JobQueue
        app.job_queue = JobQueue()
        app.job_queue.set_application(app)
        
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("setinterval", setinterval_command)],
            states={
                State.SET_INTERVAL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, process_interval)
                ]
            },
            fallbacks=[],
        )

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("parse", parse_command))
        app.add_handler(CommandHandler("report", report_command))
        app.add_handler(CommandHandler("stop", stop_command))
        app.add_handler(conv_handler)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()

    if __name__ == "__main__":
        asyncio.run(main())