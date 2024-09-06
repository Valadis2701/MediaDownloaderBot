import os
import re
import tempfile
import logging
from urllib.parse import urlparse, parse_qs, urlencode
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

def clean_youtube_url(url):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)

    # Убираем параметры, не относящиеся к видео (плейлисты и т.д.)
    ignore_params = ['list', 'start', 'index', 't', 'start_radio']

    if 'youtube.com' in parsed_url.netloc or 'youtu.be' in parsed_url.netloc:
        if 'v' in query_params:
            clean_params = {'v': query_params['v'][0]}
        elif parsed_url.path.startswith('/watch'):
            clean_params = {}
        else:
            video_id = parsed_url.path.lstrip('/')
            return f"https://youtube.com/watch?v={video_id}"

        # Удаляем игнорируемые параметры
        clean_query = urlencode(clean_params)
        return f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{clean_query}"

    return url

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
            clean_url = clean_youtube_url(url)
            logger.info(f"Обнаружена ссылка: {clean_url}")
            await download_and_send_media(update, context, clean_url)
    else:
        logger.info("Ссылка не обнаружена")

async def download_and_send_media(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    message = update.message
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    # Убираем ссылку и её параметры из сообщения, чтобы параметры не считались текстом пользователя
    cleaned_text = re.sub(r'&[^ ]*', '', message.text.replace(url, '').strip())

    # Формируем сообщение в зависимости от наличия текста
    if cleaned_text:
        caption = f"{username} отправил сообщение с текстом \"{cleaned_text}\""
    else:
        caption = f"{username} поделился файлом"

    max_attempts = 3
    attempts = 0

    while attempts < max_attempts:
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                logger.info(f"Создана временная директория: {temp_dir}")
                
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

            # Если успешно загружено и отправлено, удаляем исходное сообщение
            await message.delete()
            return  # Выходим из функции после успешной загрузки

        except Exception as e:
            logger.error(f"Произошла ошибка: {str(e)}", exc_info=True)
            attempts += 1
            if attempts < max_attempts:
                logger.info(f"Попытка {attempts} из {max_attempts}")
            else:
                error_message = "К сожалению, тип контента не поддерживается или же произошла ошибка. Попробуйте ещё раз или проигнорируйте это сообщение"
                await context.bot.send_message(chat_id=message.chat_id, text=error_message, reply_to_message_id=message.message_id)

def main():
    logger.info("Запуск бота")
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот начинает прослушивание обновлений")
    application.run_polling()

if __name__ == '__main__':
    main()
