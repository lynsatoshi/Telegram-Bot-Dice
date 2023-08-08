import matplotlib.pyplot as plt
import os
import sqlite3
import io

from aiogram import Bot, Dispatcher, types, executor
from aiogram.dispatcher.filters import Text
from asyncio import sleep

# Подключение к базе данных
conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Создание таблицы, если ее нет
cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (ID INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  throws_count INTEGER DEFAULT 0,
                  win INTEGER DEFAULT 0,
                  lose INTEGER DEFAULT 0,
                  draw INTEGER DEFAULT 0)''')
conn.commit()

bot = Bot(os.environ['TOKEN'])
dp = Dispatcher(bot)


@dp.message_handler(commands=['start'])
async def start_message(message: types.Message):
    user_id = message.from_user.id

    # Проверка наличия пользователя в базе данных
    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()

    if result is None:
        # Запись нового пользователя в базу данных
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()

    await bot.send_message(message.from_user.id, f"Привет, {message.from_user.first_name}!")
    kb = [
        [
            types.KeyboardButton(text="Кинуть кубик"),
            types.KeyboardButton(text="Статистика")
        ],
        [
            types.KeyboardButton(text="Общий график побед")
        ],
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Для начала игры нажмите на кнопку Кинуть кубик.", reply_markup=keyboard)


@dp.message_handler(Text("Кинуть кубик"))
async def game(message: types.Message):
    user_id = message.from_user.id

    # Увеличение количества бросков пользователя
    cursor.execute("UPDATE users SET throws_count = throws_count + 1 WHERE user_id=?", (user_id,))
    conn.commit()

    user_data = await bot.send_dice(user_id)
    user_data = user_data['dice']['value']

    await sleep(4)

    await bot.send_message(user_id, "\U0001F47E Кубик кидает бот:")

    bot_data = await bot.send_dice(user_id)
    bot_data = bot_data['dice']['value']

    await sleep(4)

    if bot_data > user_data:
        await bot.send_message(user_id, "Вы проиграли!")

        # Увеличение количества проигрышей пользователя
        cursor.execute("UPDATE users SET lose = lose + 1 WHERE user_id=?", (user_id,))
        conn.commit()
    elif bot_data < user_data:
        await bot.send_message(user_id, "Вы победили!")

        # Увеличение количества побед пользователя
        cursor.execute("UPDATE users SET win = win + 1 WHERE user_id=?", (user_id,))
        conn.commit()
    else:
        await bot.send_message(user_id, "Ничья!")

        # Увеличение количества ничьих пользователя
        cursor.execute("UPDATE users SET draw = draw + 1 WHERE user_id=?", (user_id,))
        conn.commit()


@dp.message_handler(Text("Статистика"))
async def show_stats(message: types.Message):
    user_id = message.from_user.id

    # Получение статистики пользователя из базы данных
    cursor.execute("SELECT throws_count, win, lose, draw FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()

    throws_count = result[0]
    win_count = result[1]
    lose_count = result[2]
    draw_count = result[3]

    # Вычисление процента побед
    total_games = win_count + lose_count + draw_count
    win_percentage = (win_count / total_games) * 100 if total_games > 0 else 0

    await bot.send_message(user_id, f"<b>Статистика:</b>\n"
                                    f"\U0001F64F Количество бросков: {throws_count}\n"
                                    f"\U0001F601 Количество побед: {win_count}\n"
                                    f"\U0001F614 Количество проигрышей: {lose_count}\n"
                                    f"\U0001F5FF Количество ничьих: {draw_count}\n"
                                    f"\U0001F64C Процент побед: <u>{win_percentage}%</u>",
                           parse_mode=types.ParseMode.HTML
                           )


@dp.message_handler(Text("Общий график побед"))
async def schedule(message: types.Message):
    user_id = message.from_user.id

    # Получение данных из базы
    cursor.execute("SELECT SUM(win) FROM users", ())
    total_wins_all_players = cursor.fetchone()[0]
    cursor.execute("SELECT win FROM users WHERE user_id=?", (user_id,))
    user_wins = cursor.fetchone()[0]

    # Создание графика
    labels = ['Ваши победы', 'Победы других\nигроков']
    sizes = [user_wins, total_wins_all_players - user_wins]
    colors = ['#ccff99', '#cc99ff']
    explode = (0.1, 0)

    plt.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%', shadow=True, startangle=140)
    plt.axis('equal')
    plt.title('Ваша доля из общего числа побед всех игроков')

    buffer = io.BytesIO()

    # Сохраняем график в буфер
    plt.savefig(buffer, format='png')
    plt.close()  # Close the figure to free up resources

    # Перед отправкой сбрасываем позицию буфера на начало
    buffer.seek(0)

    # Отправляем изображение пользователю

    if buffer.getbuffer().nbytes > 0:
        await bot.send_photo(user_id, photo=types.InputFile(buffer, filename='chart.png'))
    else:
        await message.answer("Произошла ошибка при создании графика. Попробуйте позже.")

    # Закрываем буфер
    buffer.close()


if __name__ == '__main__':
    executor.start_polling(dp)
