import os
import re
import tempfile
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import yt_dlp

# Настройка логгирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения из файла .env
load_dotenv()

# Получение токена из переменных окружения
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Пользователь {update.effective_user.id} запустил бота")
    await update.message.reply_text('Привет! Я бот, который может скачивать контент с YouTube, YouTube Music и TikTok. Просто отправь мне ссылку.')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = message.text
    logger.info(f"Получено сообщение от пользователя {update.effective_user.id}: {text}")

    # Обновлённый паттерн для извлечения ссылок, включая YouTube Music
    url_pattern = r'(https?://(?:www\.)?(?:youtube\.com|youtu\.be|music\.youtube\.com|tiktok\.com|vm\.tiktok\.com|open\.spotify\.com)\S+)'
    urls = re.findall(url_pattern, text)

    if urls:
        for url in urls:
            logger.info(f"Обнаружена ссылка: {url}")
            await download_and_send_media(update, context, url)
    else:
        logger.info("Ссылка не обнаружена")

async def download_and_send_media(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    message = update.message
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    text = message.text.replace(url, '').strip()  # Убираем ссылку из текста

    # Формируем сообщение в зависимости от наличия текста
    if text:
        caption = f"{username} отправил сообщение с текстом \"{text}\""
    else:
        caption = f"{username} поделился файлом"

    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Создана временная директория: {temp_dir}")
        try:
            is_youtube_music = 'music.youtube.com' in url

            if is_youtube_music:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                }
            else:
                ydl_opts = {
                    'format': 'best',
                    'outtmpl': os.path.join(temp_dir, f"{int(message.date.timestamp())}.%(ext)s"),
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info("Начало загрузки с yt-dlp")
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                logger.info(f"Файл загружен: {filename}")

            # Если файл был сконвертирован в mp3 для YouTube Music, обновляем имя файла
            if is_youtube_music and filename.endswith(('.webm', '.m4a')):
                new_filename = os.path.splitext(filename)[0] + '.mp3'
                if os.path.exists(new_filename):
                    filename = new_filename

            with open(filename, 'rb') as file:
                if filename.endswith(('.mp4', '.webm')):
                    await context.bot.send_video(chat_id=message.chat_id, video=file, caption=caption)
                elif filename.endswith('.mp3'):
                    await context.bot.send_audio(chat_id=message.chat_id, audio=file, caption=caption)
                else:
                    await context.bot.send_document(chat_id=message.chat_id, document=file, caption=caption)

        except Exception as e:
            logger.error(f"Произошла ошибка: {str(e)}", exc_info=True)
            await context.bot.send_message(chat_id=message.chat_id, text=f'Произошла ошибка при скачивании: {str(e)}')

    # Удаление оригинального сообщения с ссылкой
    await message.delete()

def main():
    logger.info("Запуск бота")
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот начинает прослушивание обновлений")
    application.run_polling()

if __name__ == '__main__':
    main()
