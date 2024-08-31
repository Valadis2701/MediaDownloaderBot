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
    await update.message.reply_text('Привет! Я бот, который может скачивать контент с YouTube, TikTok и YouTube Music. Просто отправь мне ссылку.')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = message.text

    url_pattern = r'(https?://(?:www\.)?(?:youtube\.com|youtu\.be|music\.youtube\.com|vm\.tiktok\.com|tiktok\.com)\S+)'
    urls = re.findall(url_pattern, text)

    if urls:
        for url in urls:
            logger.info(f"Обнаружена ссылка: {url}")
            await download_and_send_media(message, url)
    else:
        logger.info(f"Сообщение от пользователя {update.effective_user.id} не содержит ссылку и будет проигнорировано.")

async def download_and_send_media(message, url):
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Создана временная директория: {temp_dir}")
        try:
            ydl_opts = {
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'format': 'bestvideo+bestaudio/best',
                'postprocessors': [],
            }

            if 'music.youtube.com' in url:
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info("Начало загрузки с yt-dlp")
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

                if 'music.youtube.com' in url:
                    filename = filename.replace('.webm', '.mp3').replace('.m4a', '.mp3')
                    with open(filename, 'rb') as file:
                        logger.info("Отправка аудио")
                        await message.reply_audio(audio=file, reply_to_message_id=message.message_id)
                else:
                    with open(filename, 'rb') as file:
                        logger.info("Отправка видео")
                        await message.reply_video(video=file, reply_to_message_id=message.message_id)

        except Exception as e:
            logger.error(f"Произошла ошибка: {str(e)}", exc_info=True)
            await message.reply_text(f'Произошла ошибка при скачивании: {str(e)}', reply_to_message_id=message.message_id)

def main():
    logger.info("Запуск бота")
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот начинает прослушивание обновлений")
    application.run_polling()

if __name__ == '__main__':
    main()
