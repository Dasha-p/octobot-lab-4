import telebot
import gspread
import json
import pandas as pd
import re
from datetime import datetime, timedelta

bot = telebot.TeleBot('5344730448:AAFni6sFsRq0wXqm94LqsaakNE2Jfd4-VGc')
check = False
korobochka = []

def convert_date(date: str = "01/01/00"):
    """ Конвертируем дату из строки в datetime """
    return datetime.strptime(date, "%d.%m.%Y")


def connect_table(message):
    """ Подключаемся к Google-таблице """
    url = message.text
    sheet_id = "1-SY-svuozmRkCR2EUxmzME6-jmIa5PeJIlamx4zqDUI"  # Нужно извлечь id страницы из ссылки на Google-таблицу
    try:
        with open("tables.json") as json_file:
            tables = json.load(json_file)
        title = len(tables) + 1
        tables[title] = {"url": url, "id": sheet_id}
    except FileNotFoundError:
        tables = {0: {"url": url, "id": sheet_id}}
    with open('tables.json', 'w') as json_file:
        json.dump(tables, json_file)
    bot.send_message(message.chat.id, "Табличка подключена!")
    global check
    check = True
    start(message)


def access_current_sheet():
    """ Обращаемся к Google-таблице """
    with open("tables.json") as json_file:
        tables = json.load(json_file)

    sheet_id = tables[max(tables)]["id"]
    gc = gspread.service_account(filename="credentials.json")
    sh = gc.open_by_key(sheet_id)
    worksheet = sh.sheet1
    # Преобразуем Google-таблицу в таблицу pandas
    df = pd.DataFrame(worksheet.get_values(""), columns=worksheet.row_values(1))
    df = df.drop(0)
    df.index -= 1
    return worksheet, tables[max(tables)]["url"], df


def choose_action(message):
    """ Обрабатываем действия верхнего уровня """

    if message.text == "Подключить Google-табличку":
        connect_table(message)
    elif message.text == "Редактировать предметы и ссылки":
        start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        start_markup.row("+ предмет")
        start_markup.row("Редактировать")
        start_markup.row("- предмет")
        start_markup.row("Удалить все предметы")
        info = bot.send_message(message.chat.id, "Что сделать с предметом?", reply_markup=start_markup)
        bot.register_next_step_handler(info, choose_subject_action)
    elif message.text == "Изменить дедлайны":
        start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        start_markup.row("Добавить дедлайн")
        start_markup.row("Изменить дедлайн")
        info = bot.send_message(message.chat.id, "Что хотите сделать?", reply_markup=start_markup)
        bot.register_next_step_handler(info, choose_deadline_action)
    elif message.text == "Посмотреть дедлайны на этой неделе":
        today = datetime.today()
        week = today + timedelta(days=7)
        a, b, df = access_current_sheet()
        mes = f""
        for i in range(2, len(a.col_values(1)) + 1):
            for ddl in a.row_values(i)[2:]:
                if convert_date(ddl) <= week and convert_date(ddl) >= today:
                    mes += f"{a.cell(i, 1).value}: {ddl}\n"
        bot.send_message(message.chat.id, mes)
        start(message)


def choose_subject_action(message):
    """ Выбираем действие в разделе Редактировать предметы """
    if message.text == "+ предмет":
        message = bot.send_message(message.chat.id, "Напишите название и ссылку через пробел")
        bot.register_next_step_handler(message, add_new_subject)
    elif message.text == "Редактировать":
        a, b, c = access_current_sheet()
        mrkp = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for el in c.subject:
            mrkp.row(f"{el}")
        inf = bot.send_message(message.chat.id, "Какой предмет редактируем?", reply_markup=mrkp)
        bot.register_next_step_handler(inf, update_subject)
    elif message.text == "- предмет":
        a, b, c = access_current_sheet()
        mrkp = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for el in c.subject:
            mrkp.row(f"{el}")
        inf = bot.send_message(message.chat.id, "Какой именно предмет удаляем?", reply_markup=mrkp)
        bot.register_next_step_handler(inf, delete_subject)
    elif message.text == "Удалить все предметы":
        start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        start_markup.row("Да")
        start_markup.row("Нет")
        info = bot.send_message(message.chat.id, "Вы точно хотите удалить все предметы?", reply_markup=start_markup)
        bot.register_next_step_handler(info, choose_removal_option)


def choose_deadline_action(message):
    """ Выбираем действие в разделе Редактировать дедлайн """
    if message.text == "Добавить дедлайн":
        a, b, c = access_current_sheet()
        mrkp = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for el in c.subject:
            mrkp.row(f"{el}")
        inf = bot.send_message(message.chat.id, "Какому предмету добавляем?", reply_markup=mrkp)
        bot.register_next_step_handler(inf, add_subject_deadline)
    elif message.text == "Изменить дедлайн":
        a, b, c = access_current_sheet()
        mrkp = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for el in c.subject:
            mrkp.row(f"{el}")
        inf = bot.send_message(message.chat.id, "Для какого предмета изменяем?", reply_markup=mrkp)
        bot.register_next_step_handler(inf, update_subject_deadline)


def choose_removal_option(message):
    """ Уточняем, точно ли надо удалить все """
    if message.text == "Да, зачем они нужны!":
        clear_subject_list(message)
    elif message.text == "Пока нет":
        start(message)


def add_subject_deadline(message):
    """ Выбираем предмет, у которого надо отредактировать дедлайн """
    global korobochka
    korobochka = []
    korobochka.append(message.text)
    inf = bot.send_message(message.chat.id, "Введите дату в формате 'dd.mm.yyyy'")
    bot.register_next_step_handler(inf, add_subject_deadline2)


def add_subject_deadline2(message):
    global korobochka
    if not re.match(r"\d\d.\d\d.\d\d\d\d", message.text):
        inf = bot.send_message(message.chat.id, "Неправильный формат!\nВведите дату в формате 'dd.mm.yyyy'")
        bot.register_next_step_handler(inf, add_subject_deadline2)
    else:
        if convert_date(message.text) < datetime.today():
            bot.send_message(message.chat.id, "Ты профукал этот дедлайн давай новый!")
        else:
            a, b, c = access_current_sheet()
            row = a.find(f"{korobochka[0]}").row
            n = len(a.row_values(row))
            a.update_cell(row, n+1, message.text)
            if not a.cell(1, n+1).value:
                num = int(a.cell(1, n).value)
                a.update_cell(1, n + 1, num+1)
            bot.send_message(message.chat.id, "Изменено!")
            start(message)


def update_subject_deadline(message):
    """ Обновляем дедлайн """
    global korobochka
    korobochka = []
    korobochka.append(message.text)
    a, b, c = access_current_sheet()
    mrkp = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for el in c.columns[2:]:
        mrkp.row(f"{el}")
    inf = bot.send_message(message.chat.id, "Для какой лабы изменяем?", reply_markup=mrkp)
    bot.register_next_step_handler(inf, update_subject_deadline2)


def update_subject_deadline2(message):
    global korobochka
    korobochka.append(message.text)
    inf = bot.send_message(message.chat.id, "Введите дату в формате 'dd.mm.yyyy'")
    bot.register_next_step_handler(inf, update_subject_deadline3)


def update_subject_deadline3(message):
    global korobochka
    if not re.match(r"\d\d.\d\d.\d\d\d\d", message.text):
        inf = bot.send_message(message.chat.id, "Неправильный формат!\nВведите время в формате 'dd.mm.yyyy'")
        bot.register_next_step_handler(inf, update_subject_deadline2)
    else:
        if convert_date(message.text) < datetime.today():
            bot.send_message(message.chat.id, "Ты профукал этот дедлайн давай новый!")
        else:
            a, b, c = access_current_sheet()
            row = a.find(f"{korobochka[0]}").row
            col = a.find(f"{korobochka[1]}").col
            a.update_cell(row, col, message.text)
            bot.send_message(message.chat.id, "Готово!")
            start(message)


def add_new_subject(message):
    """ Вносим новое название предмета в Google-таблицу """
    try:
        name = message.text.split()[0]
        url = message.text.split()[1]
        worksheet, b, c = access_current_sheet()
        worksheet.append_row([name, url])
        bot.send_message(message.chat.id, "Готово!")
        start(message)
    except IndexError:
        inf = bot.send_message(message.chat.id,
                               "Название и ссылка должны быть в одном сообщении и разделены пробелом!!")
        bot.register_next_step_handler(inf, add_new_subject)


def update_subject(message):
    """ Обновляем информацию о предмете в Google-таблице """
    global korobochka
    korobochka = []
    korobochka.append(message.text)
    inf = bot.send_message(message.chat.id,
                           "Введите название и ссылку через пробел. Если не хотите менять что-то из этого, то просто повторите старый вариант")
    bot.register_next_step_handler(inf, update_subject2)


def update_subject2(message):
    global korobochka
    try:
        name = message.text.split()[0]
        url = message.text.split()[1]
        worksheet, b, df = access_current_sheet()
        ind = df.loc[df.isin(korobochka).any(axis=1)].index[0] + 2
        cell_list = worksheet.range(f'A{ind}:B{ind}')
        cell_list[0].value = name
        cell_list[1].value = url
        worksheet.update_cells(cell_list)
        bot.send_message(message.chat.id, "Готово!")
        start(message)
    except IndexError:
        inf = bot.send_message(message.chat.id,
                               "Название и ссылка должны быть в одном сообщении и разделены пробелом!!")
        bot.register_next_step_handler(inf, update_subject2)



def delete_subject(message):
    """ Удаляем предмет в Google-таблице """
    worksheet, b, df = access_current_sheet()
    ind = df.loc[df.isin([message.text]).any(axis=1)].index[0] + 2
    worksheet.delete_rows(int(ind), int(ind))
    bot.send_message(message.chat.id, "Готово!")
    start(message)


def clear_subject_list(message):
    """ Удаляем все из Google-таблицы """
    with open("tables.json") as json_file:
        tables = json.load(json_file)
    sheet_id = tables[max(tables)]["id"]
    gc = gspread.service_account(filename="credentials.json")
    sh = gc.open_by_key(sheet_id)
    worksheet = sh.sheet1
    sh.del_worksheet(worksheet)
    bot.send_message(message.chat.id, "Хе-хе, я все удалил!")
    start(message)


def check_table():
    global check
    try:
        f = open("tables.json")
        check = True
    except FileNotFoundError:
        check = False


@bot.message_handler(commands=["start"])
def start(message):
    global check
    check_table()
    start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    if not check:
        start_markup.row("Подключить Google-табличку")
    else:
        a, b, c = access_current_sheet()
        otvet = f""
        for i in c.index:
            otvet += f"[{c.loc[i, 'subject']}]({c.loc[i, 'link']})\n"
        bot.send_message(message.chat.id, otvet, parse_mode="MarkdownV2")
        start_markup.row("Посмотреть дедлайны на этой неделе")
        start_markup.row("Изменить дедлайны")
        start_markup.row("Редактировать предметы и ссылки")
    info = bot.send_message(message.chat.id, "Что хотите сделать?", reply_markup=start_markup)
    bot.register_next_step_handler(info, choose_action)


if __name__=="__main__":
    bot.infinity_polling()
