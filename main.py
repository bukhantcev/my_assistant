import asyncio
import logging
import os
import time
from datetime import datetime

from openai import AsyncOpenAI, OpenAI
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile
from aiogram.utils.markdown import hbold
from aiogram.client.default import DefaultBotProperties


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

thread_id = ''

try:
   thread_id_file =  open('thread.txt', 'r')
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
    run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id, instructions=f'{old_instructions}\nсегодня {current_date}')

# Ожидание завершения выполнения
    while run.status in ["queued", "in_progress"]:
        time.sleep(1)
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

def edit_instructions(assistant, new_instructions:str, old_instructions:str):
    instructions = old_instructions + '\n' + new_instructions
    my_updated_assistant = client.beta.assistants.update(
        assistant_id=assistant,
        instructions=instructions,
    )



# Обработчик команды /start
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        f"Привет, {hbold(message.from_user.first_name)}!\nЯ бот с функциями GPT-4o, DALL·E-3 и Whisper.")


# GPT-4o: Обработка текстовых сообщений
@dp.message()
async def chat_handler(message: types.Message):
    print(message.from_user.id)
    if message.from_user.id == 404354012 or message.from_user.id == 7394393302:

        if message.from_user.id == 404354012:
            assistant_id = 'asst_kCFa7ZkhnCCtRY8roDO3vpfh'
        elif message.from_user.id == 7394393302:
            assistant_id = 'asst_85Boy7BUjKTcIRzb1Ejvl6ch'
        if 'запомни' in message.text.lower():
            old_instructions = client.beta.assistants.retrieve(assistant_id).instructions
            edit_instructions(assistant_id, message.text[len('запомни'):],old_instructions)
            await message.reply('Запомнил')
            return None
        create_message(thread_id, message.text)
        create_run(thread_id, assistant_id)
        await message.reply(message_list(thread_id))


# Запуск бота
async def main():
    logging.info("Бот запущен")
    thread = client.beta.threads.create()
    with open('thread.txt', 'w') as file:
        file.write(thread.id)
    await dp.start_polling(bot)



if __name__ == "__main__":
    asyncio.run(main())

