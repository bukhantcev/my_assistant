import asyncio
import logging
import os
import time
from datetime import datetime
import aiohttp
import aiofiles
import ssl
from openai import AsyncOpenAI, OpenAI
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile
from aiogram.utils.markdown import hbold
from aiogram.client.default import DefaultBotProperties


import ssl
import aiohttp

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


# Настройки
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("AITOKEN")
client = OpenAI(api_key=OPENAI_API_KEY)

# Инициализация бота и диспетчера
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

# Логирование
logging.basicConfig(level=logging.INFO)


try:
   thread_id_file = open('thread.txt', 'r')
   thread_id = thread_id_file.read()
   thread_id_file.close()
except:
    pass


def create_message(thread_id, message):
    thread_message = client.beta.threads.messages.create(
        thread_id,
        role="user",
        content=message,
    )


def message_list(thread_id):
    messages = client.beta.threads.messages.list(thread_id=thread_id)

    for msg in messages.data:
        if msg.role == "assistant":
            return "\n".join(block.text.value for block in msg.content if hasattr(block, "text"))

    return None  # Если сообщений ассистента нет


def create_run(thread_id, assistant_id):
    current_date = datetime.now().strftime("%d %B %Y")
    old_instructions = client.beta.assistants.retrieve(assistant_id).instructions
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        instructions=f'{old_instructions}\nсегодня {current_date}'
    )

    # Ожидание завершения выполнения
    while run.status in ["queued", "in_progress"]:
        time.sleep(1)
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)


def edit_instructions(assistant, new_instructions: str, old_instructions: str):
    instructions = old_instructions + '\n' + new_instructions
    my_updated_assistant = client.beta.assistants.update(
        assistant_id=assistant,
        instructions=instructions,
    )


# Обработчик команды /start
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        f"Привет, {hbold(message.from_user.first_name)}!\nЯ бот с функциями GPT-4o, DALL·E-3 и Whisper."
    )


# GPT-4o: Обработка текстовых сообщений
@dp.message(F.text)
async def chat_handler(message: types.Message):
    print(message.from_user.id)
    if message.from_user.id == 404354012 or message.from_user.id == 422964820:

        if message.from_user.id == 404354012:
            assistant_id = 'asst_kCFa7ZkhnCCtRY8roDO3vpfh'
        elif message.from_user.id == 422964820:
            assistant_id = 'asst_85Boy7BUjKTcIRzb1Ejvl6ch'
        if 'запомни' in message.text.lower():
            old_instructions = client.beta.assistants.retrieve(assistant_id).instructions
            edit_instructions(assistant_id, message.text[len('запомни'):], old_instructions)
            await message.reply('Запомнил')
            return None
        if 'нарисуй' in message.text.lower():
            text = message.text[7:].strip()
            if not text:
                await message.reply("Пожалуйста, напишите, что нарисовать после слова 'нарисуй'.")
                return
            try:
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=text,
                    n=1,
                    size="1024x1024"
                )
                image_url = response.data[0].url
                await message.answer_photo(photo=image_url, caption=f"Ваше изображение по запросу: {text}")
            except Exception as e:
                logging.error(f"Ошибка генерации изображения: {e}")
                await message.reply("Ошибка генерации изображения. Попробуйте позже.")
            return None

        create_message(thread_id, message.text)
        create_run(thread_id, assistant_id)
        await message.reply(message_list(thread_id))


# 🔹 Хендлер для обработки фото через GPT-4o (gpt-4-turbo)
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    if message.from_user.id == 404354012 or message.from_user.id == 422964820:
        photo = message.photo[-1]  # Берем самое большое фото
        file_info = await bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
        caption = "Что изображено на фото?"
        if message.caption:
            caption = message.caption

        try:
            # 🎯 Отправляем фото в GPT-4o (gpt-4-turbo)
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "Ты помощник, который анализирует изображения."},
                    {"role": "user", "content": [
                        {"type": "text", "text": caption},
                        {"type": "image_url", "image_url": {"url": file_url}}
                    ]}
                ],
                max_tokens=500
            )

            # 📤 Отправляем ответ пользователю
            answer = response.choices[0].message.content
            await message.answer(answer)

        except Exception as e:
            logging.error(f"Ошибка обработки фото: {e}")
            await message.answer("Ошибка обработки изображения. Попробуйте позже.")


# 🔹 Хендлер для обработки голосовых сообщений и аудиофайлов
@dp.message(F.voice | F.audio | F.document)
async def handle_audio(message: types.Message):
    if message.from_user.id not in [404354012, 422964820]:
        return

    # Определяем тип файла
    if message.voice:
        file_id = message.voice.file_id
        file_format = "ogg"
    elif message.audio:
        file_id = message.audio.file_id
        file_format = message.audio.file_name.split(".")[-1]
    elif message.document:
        file_id = message.document.file_id
        file_format = message.document.file_name.split(".")[-1]
    else:
        await message.reply("Неподдерживаемый формат аудио.")
        return

    file_info = await bot.get_file(file_id)
    file_path = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
    local_filename = f"audio.{file_format}"

    # Скачивание файла
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.get(file_path) as resp:
                if resp.status == 200:
                    async with aiofiles.open(local_filename, "wb") as f:
                        await f.write(await resp.read())
                else:
                    await message.reply("Ошибка загрузки аудиофайла.")
                    return
    except Exception as e:
        logging.error(f"Ошибка скачивания файла: {e}")
        await message.reply("Ошибка скачивания аудиофайла.")
        return

    # Отправка в OpenAI Whisper
    try:
        with open(local_filename, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ru"  # Распознавание русского языка
            )
        if message.from_user.id == 404354012 or message.from_user.id == 422964820:

            if message.from_user.id == 404354012:
                assistant_id = 'asst_kCFa7ZkhnCCtRY8roDO3vpfh'
            elif message.from_user.id == 422964820:
                assistant_id = 'asst_85Boy7BUjKTcIRzb1Ejvl6ch'
            if 'запомни' in transcription.text.lower():
                old_instructions = client.beta.assistants.retrieve(assistant_id).instructions
                edit_instructions(assistant_id, message.text[len('запомни'):], old_instructions)
                await message.reply('Запомнил')
                return None
            if 'нарисуй' in transcription.text.lower():
                text = transcription.text[7:].strip()
                if not text:
                    await message.reply("Пожалуйста, напишите, что нарисовать после слова 'нарисуй'.")
                    return
                try:
                    response = client.images.generate(
                        model="dall-e-3",
                        prompt=text,
                        n=1,
                        size="1024x1024"
                    )
                    image_url = response.data[0].url
                    await message.answer_photo(photo=image_url, caption=f"Ваше изображение по запросу: {text}")
                except Exception as e:
                    logging.error(f"Ошибка генерации изображения: {e}")
                    await message.reply("Ошибка генерации изображения. Попробуйте позже.")
                return None

            create_message(thread_id, transcription.text)
            create_run(thread_id, assistant_id)
            await message.reply(message_list(thread_id))
    except Exception as e:
        logging.error(f"Ошибка обработки аудио: {e}")
        await message.reply("Ошибка обработки аудиофайла.")


# Запуск бота
async def main():
    logging.info("Бот запущен")

    # Проверяем, существует ли файл
    file_path = os.path.join(os.getcwd(), 'thread.txt')

    if not os.path.exists(file_path):
        # Создаём новый поток, если файла нет
        thread = client.beta.threads.create()
        with open(file_path, 'w') as file:
            file.write(thread.id)
    else:
        # Читаем существующий thread_id
        with open(file_path, 'r') as file:
            thread_id = file.read().strip()

        logging.info(f"Используется существующий thread_id: {thread_id}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())