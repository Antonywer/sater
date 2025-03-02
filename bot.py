import re
import asyncio
import sqlite3
import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Токен бота (замени на свой)
TOKEN = "7658744424:AAH3kuLvTLfF2oqpEhjA1xejDx20Ti0-5SE"
async def auto_ping():
    while True:
        await asyncio.sleep(2880)  # Ждём 48 мин
        try:
            chat_id = 841651683  # Укажи свой ID
            print(f"Отправляю пинг в {chat_id}")
            await bot.send_message(chat_id, "/ping")
        except Exception as e:
            print(f"Ошибка при пинге: {e}")



# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Подключение к базе данных
conn = sqlite3.connect("attendance.db")
cursor = conn.cursor()

# Обновлённая схема таблицы: добавлено поле pair_number
cursor.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    pair_number INTEGER,
    name TEXT,
    total_hours INTEGER,
    unexcused_hours INTEGER
)
""")
conn.commit()


# Клавиатура с кнопкам
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Всего за неделю")],
        [KeyboardButton(text="Всего за месяц")]
    ],
    resize_keyboard=True
)

# Функция парсинга сообщения с отсутствиями.
# Формат:
# 25 января 2025
# 1) Иванов, Петров*
# 2) Сидоров, Петров
# 3) Сергеев*, Иванов
def parse_message(text):
    lines = text.strip().split("\n")
    # Извлекаем дату из первой строки
    date_match = re.search(r"(\d{1,2}) (\w+) (\d{4})", lines[0])
    if not date_match:
        return None
    
    day, month_name, year = date_match.groups()
    month_map = {
        "января": "01", "февраля": "02", "марта": "03", "апреля": "04",
        "мая": "05", "июня": "06", "июля": "07", "августа": "08",
        "сентября": "09", "октября": "10", "ноября": "11", "декабря": "12"
    }
    month = month_map.get(month_name.lower())
    if not month:
        return None

    date = f"{year}-{month}-{day.zfill(2)}"  # Формат YYYY-MM-DD

    records = []
    # Обрабатываем каждую строку с данными об отсутствии
    for line in lines[1:]:
        # Извлекаем номер пары в начале строки, например "1)" или "2)"
        pair_match = re.match(r"^\s*(\d+)\)", line)
        if not pair_match:
            continue  # Если строка не соответствует формату, пропускаем
        pair_number = int(pair_match.group(1))
        # Удаляем номер пары из строки
        remaining_line = line[pair_match.end():]
        # Находим фамилии с опциональной звёздочкой
        names = re.findall(r"\b[А-ЯЁ][а-яё]+\*?", remaining_line)
        for name in names:
            has_star = name.endswith("*")
            name_clean = name.rstrip("*")
            record = {
                "date": date,
                "pair_number": pair_number,
                "name": name_clean,
                "total_hours": 2,
                "unexcused_hours": 2 if not has_star else 0,
            }
            records.append(record)
    return records


# Функция записи данных в БД
def save_attendance(records):
    for record in records:
        cursor.execute(
            "INSERT INTO attendance (date, pair_number, name, total_hours, unexcused_hours) VALUES (?, ?, ?, ?, ?)",
            (record["date"], record["pair_number"], record["name"], record["total_hours"], record["unexcused_hours"])
        )
    conn.commit()


# Функция подсчета часов за период (незатронута)
def get_summary(days):
    start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT name, SUM(total_hours), SUM(unexcused_hours)
        FROM attendance
        WHERE date >= ?
        GROUP BY name
    """, (start_date,))
    rows = cursor.fetchall()
    if not rows:
        return "Нет данных"
    return "\n".join([f"{name} - {total} часов ({unexcused} по неуважительной)" for name, total, unexcused in rows])

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Отправь список отсутствующих в формате:\n\n"
                         "25 января 2025\n"
                         "1) Иванов, Петров*\n"
                         "2) Сидоров, Петров\n"
                         "3) Сергеев*, Иванов\n\n"
                         "Кнопки для просмотра отчетов доступны ниже.", reply_markup=keyboard)
    print(message.chat.id)

# Обработчики для кнопок отчетов
@dp.message(F.text == "Всего за неделю")
async def report_week(message: types.Message):
    await message.answer(f"Отчет за неделю:\n{get_summary(7)}")

@dp.message(F.text == "Всего за месяц")
async def report_month(message: types.Message):
    await message.answer(f"Отчет за месяц:\n{get_summary(30)}")

# Новый обработчик для команды /set, который выводит подробный список отсутствующих за указанную дату
@dp.message(Command("set"))
async def set_report(message: types.Message):
    # Ожидается формат: /set 25 января 2025
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите дату в формате: /set 25 января 2025")
        return

    date_input = parts[1].strip()
    date_match = re.search(r"(\d{1,2})\s+([а-яёА-ЯЁ]+)\s+(\d{4})", date_input)
    if not date_match:
        await message.answer("Неверный формат даты. Используйте: /set 25 января 2025")
        return
    day, month_name, year = date_match.groups()
    month_map = {
        "января": "01", "февраля": "02", "марта": "03", "апреля": "04",
        "мая": "05", "июня": "06", "июля": "07", "августа": "08",
        "сентября": "09", "октября": "10", "ноября": "11", "декабря": "12"
    }
    month = month_map.get(month_name.lower())
    if not month:
        await message.answer("Неверное название месяца.")
        return
    parsed_date = f"{year}-{month}-{day.zfill(2)}"  # Формат YYYY-MM-DD

    # Запрос к базе: получаем записи за указанную дату
    cursor.execute(
        "SELECT pair_number, name, total_hours, unexcused_hours FROM attendance WHERE date = ?",
        (parsed_date,)
    )
    rows = cursor.fetchall()
    if not rows:
        await message.answer(f"За {date_input} нет данных.")
        return

    # Группируем записи по номеру пары
    pairs = {}
    for pair_number, name, total_hours, unexcused_hours in rows:
        if pair_number not in pairs:
            pairs[pair_number] = []
        # Если total_hours != unexcused_hours, значит, была уважительная причина
        status = " (уваж)" if total_hours != unexcused_hours else ""
        pairs[pair_number].append(name + status)

    # Формируем ответ: первая строка – введённая дата, далее по парам
    response_lines = [date_input]
    for pair_number in sorted(pairs.keys()):
        names_str = ", ".join(pairs[pair_number])
        response_lines.append(f"{pair_number}) {names_str}")
    response_text = "\n".join(response_lines)
    await message.answer(response_text)

# Обработчик обычных текстовых сообщений для записи данных
@dp.message()
async def handle_message(message: types.Message):
    records = parse_message(message.text)
    if records:
        save_attendance(records)
        await message.answer("Данные записаны!", reply_markup=keyboard)
    else:
        await message.answer("Неверный формат данных. Попробуйте снова.")


# Функция запуска бота
async def main():
    asyncio.create_task(auto_ping())
    await dp.start_polling(bot)
    

# Запуск бота
if __name__ == "__main__":
    asyncio.run(main())
