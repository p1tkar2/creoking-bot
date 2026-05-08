import os
import logging
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic
import random

# ===== НАСТРОЙКИ =====
TELEGRAM_TOKEN = "8697092851:AAH0InQyfggRyGQBLw7DpkFRTDZBZhEQRXg"
CLAUDE_API_KEY = "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"
SPREADSHEET_ID = "1UW8EstvgOspU2wMyfbJWU5zTZy3ZGATWDn6lL6EYc9E"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)


def get_tz_examples(count=3):
    """Получить примеры ТЗ из Google Sheets через публичный доступ"""
    import urllib.request
    import csv
    import io

    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid=0"
    
    try:
        with urllib.request.urlopen(url) as response:
            content = response.read().decode('utf-8')
        
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        
        # Пропускаем заголовок (строка 0), берём строки с данными
        data_rows = [row for row in rows[1:] if len(row) >= 5 and row[4].strip()]
        
        if not data_rows:
            return []
        
        # Берём случайные примеры
        selected = random.sample(data_rows, min(count, len(data_rows)))
        return [row[4] for row in selected]  # Колонка E - Текст ТЗ
    
    except Exception as e:
        logger.error(f"Ошибка при чтении таблицы: {e}")
        return []


def generate_tz(user_request: str, examples: list) -> str:
    """Генерировать ТЗ через Claude API"""
    
    examples_text = "\n\n---\n\n".join(examples) if examples else "Примеры не найдены"
    
    prompt = f"""Ты помощник для составления ТЗ на арбитражные креативы.

СТРОГИЕ ПРАВИЛА:
1. Используй ТОЛЬКО структуру и стиль из примеров ниже
2. Не придумывай ничего от себя — только адаптируй под новые параметры  
3. Сохраняй те же форматы сцен, те же типы текста, ту же длину и детальность
4. Меняй только: имя персонажа, суммы, локальные детали под ГЕО, язык текста
5. Текст внутри ТЗ (речь персонажа, субтитры) пиши на языке указанного ГЕО

ЗАПРОС КЛИЕНТА:
{user_request}

ПРИМЕРЫ ТЗ ИЗ БАЗЫ (строго следуй этому стилю и структуре):

{examples_text}

Составь новое ТЗ строго по образцу выше. Не добавляй лишних пояснений — только само ТЗ."""

    message = claude_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return message.content[0].text


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я генератор ТЗ для арбитражных креативов CREO KING.\n\n"
        "Просто напиши мне что нужно, например:\n\n"
        "ГЕО: VEN, категория: инвест, формат: видео, персонаж: Эмилия\n\n"
        "или\n\n"
        "ГЕО: UZ, инвест, рилс, персонаж: Зайнаб\n\n"
        "И я сгенерирую ТЗ по образцу твоих лучших крео! 🎯"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    # Отправляем сообщение что генерируем
    thinking_msg = await update.message.reply_text("⏳ Генерирую ТЗ на основе твоей базы...")
    
    try:
        # Получаем примеры из таблицы
        examples = get_tz_examples(count=3)
        
        if not examples:
            await thinking_msg.edit_text(
                "❌ Не удалось загрузить примеры из таблицы.\n"
                "Убедись что таблица открыта для просмотра по ссылке."
            )
            return
        
        # Генерируем ТЗ
        tz = generate_tz(user_text, examples)
        
        # Удаляем сообщение "генерирую"
        await thinking_msg.delete()
        
        # Отправляем результат (разбиваем если длинное)
        if len(tz) > 4000:
            # Разбиваем на части
            parts = [tz[i:i+4000] for i in range(0, len(tz), 4000)]
            for i, part in enumerate(parts):
                if i == 0:
                    await update.message.reply_text(f"📋 *ТЗ готово:*\n\n{part}", parse_mode='Markdown')
                else:
                    await update.message.reply_text(part)
        else:
            await update.message.reply_text(f"📋 *ТЗ готово:*\n\n{tz}", parse_mode='Markdown')
            
        # Кнопка для нового запроса
        await update.message.reply_text(
            "✅ Готово! Хочешь ещё одно ТЗ? Просто напиши новый запрос.\n"
            "Или /start чтобы увидеть инструкцию."
        )
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await thinking_msg.edit_text(
            f"❌ Ошибка при генерации. Попробуй ещё раз.\n\nДетали: {str(e)[:200]}"
        )


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
