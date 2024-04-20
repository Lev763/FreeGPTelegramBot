from concurrent.futures import Executor
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
import aiogram.utils.markdown as md
from g4f.client import Client
from pathlib import Path
from sys import argv
import functools

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Включение логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
# Чтение значения API_TOKEN из файла
API_TOKEN_path = (Path(argv[0]).resolve().parent) / "TOKEN_API_BOT"
with open(API_TOKEN_path, "r") as file:
    API_TOKEN = file.read().strip()

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Словарь для хранения истории разговоров
conversation_history = {}


async def generate_prompt(prompt) -> str:
    try:
        loop = asyncio.get_event_loop()
        func = functools.partial(
            Client().chat.completions.create, model="gpt-3.5-turbo", messages=prompt
        )
        finish = False
        while not finish:
            response = await loop.run_in_executor(None, func)
            content = response.choices[0].message.content
            if content == "流量异常,请尝试更换网络环境":
                print('Processing the message "流量异常,请尝试更换网络环境", try again.')
                continue
            break
        return content
    except Exception as e:
        print(f"There was an error: {e}")
        return f"There was an error!"


# Функция для обрезки истории разговора
def trim_history(history, max_length=4096):
    current_length = sum(len(message["content"]) for message in history)
    while history and current_length > max_length:
        removed_message = history.pop(0)
        current_length -= len(removed_message["content"])
    return history


# Словарь с командами и описаниями
commands = {
    "/start": "Start a conversation",
    "/clear": "Clear conversation history",
    "/help": "Show command list",
}

# Создание клавиатуры с выпадающим списком команд
commands_keyboard = ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
commands_keyboard.add(KeyboardButton("Select the command ⬇"))

for command, description in commands.items():
    commands_keyboard.insert(KeyboardButton(command))


# Обработчик для команды /start
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    conversation_history[user_id] = []
    await message.reply(
        "Hi! I'm ready to chat with you.", reply_markup=commands_keyboard
    )


# Обработчик для команды /clear
@dp.message_handler(commands=["clear"])
async def cmd_clear(message: types.Message):
    user_id = message.from_user.id
    conversation_history[user_id] = []
    await message.reply("History cleared.", reply_markup=commands_keyboard)


# Обработчик для команды /help
@dp.message_handler(commands=["help"])
async def cmd_help(message: types.Message):
    commands_list = "\n".join(
        [f"{command}: {description}" for command, description in commands.items()]
    )
    await message.reply(commands_list, reply_markup=commands_keyboard)


# Обработчик для всех остальных сообщений
@dp.message_handler()
async def echo_message(message: types.Message):
    user_id = message.from_user.id
    user_input = message.text

    # Проверяем, если сообщение состоит целиком из команды
    if user_input.strip() in commands.keys():
        # Игнорируем сообщение
        return

    if user_id not in conversation_history:
        conversation_history[user_id] = []

    # Если история пустая, добавляем приветственное сообщение от ассистента
    if not conversation_history[user_id]:
        conversation_history[user_id].append(
            {
                "role": "assistant gpt-3.5-turbo",
                "content": "I'm gpt-3.5-turbo as a telegram bot, ready to help with your questions!",
            }
        )

    conversation_history[user_id].append({"role": "user", "content": user_input})
    conversation_history[user_id] = trim_history(conversation_history[user_id])

    chat_history = conversation_history[user_id]

    try:
        response = await generate_prompt(chat_history)
        chat_gpt_response = response
    except Exception as e:
        chat_gpt_response = f"Sorry, there's been an error."

    conversation_history[user_id].append(
        {"role": "assistant gpt-3.5-turbo", "content": chat_gpt_response}
    )

    if chat_gpt_response:  # Проверяем, не пустой ли chat_gpt_response
        await message.reply(
            chat_gpt_response, reply_markup=commands_keyboard, parse_mode="Markdown"
        )


# Функция для проверки обновлений
async def check_updates(dp: Dispatcher):
    while True:
        try:
            await dp.bot.get_updates()
            await asyncio.sleep(5)  # Проверка обновлений каждые 5 секунд
        except Exception as e:
            logging.error(f"An error occurred while checking updates: {e}")


# Функция при запуске бота
async def on_startup(dp: Dispatcher):
    logging.info("Started bot!")
    # Запускаем функцию проверки обновлений в фоновом режиме
    asyncio.create_task(check_updates(dp))


# Функция при остановке бота
async def on_shutdown(dp: Dispatcher):
    logging.info("Shutting down bot!")
    await bot.close()


# Основная функция для запуска бота
def main():
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)


if __name__ == "__main__":
    main()
