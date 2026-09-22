import telebot
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import psycopg2
import re
import os
import json
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME", "postgres"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "postgres"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432")
)

cur = conn.cursor()

# Создаем бота с вашим токеном
bot = telebot.TeleBot(os.getenv("TOKEN"))

admin = [int(os.getenv("ADMIN_ID"))]

SAVE_DIR = 'data'
os.makedirs(SAVE_DIR, exist_ok=True)
user_info = {}
current_bouqet_id = 0
orders_list = []

back_to_start_button = InlineKeyboardButton("Назад", callback_data="back_to_start")
delete_bouqet_button = InlineKeyboardButton("Удалить букет", callback_data='delete_bouqet')
back_to_order_list_button = InlineKeyboardButton('Назад', callback_data="back_to_order_list")
p_keyboard = []
profile_button_texts = ['Изменить имя', 'Изменить номер телефона', 'Изменить электронную почту',
                        'Изменить адрес доставки']
sql_request = ['first_name', 'user_phone_number', 'email', 'delivery_address']
answer = ['Ваше имя успешно изменено', 'Ваш номер телефона успешно изменен', 'Ваша электронная почта успешно изменена',
          'Адрес доставки успешно изменен']
request_text = ['Ваше имя', 'Ваш номер телефона', 'Вашу электронную почту', 'адрес доставки']

b_keyboard = []
add_bouqet_button_text = ['Изменить название букета', 'Изменить фото букета', 'Изменить описание букета',
                          'Изменить цену букета', 'Сохранить']
sql_request_b = ['bouqet_name', 'bouqet_photo', 'bouqet_description', 'bouqet_price']
answer_b = ['Название букета успешно изменено', 'Фото букета успешно изменено', 'Описание букета успешно изменено',
            'Цена букета успешно изменена']
request_b = ['название букета', 'фото букета', 'описание букета', 'цену букета']
order_button = InlineKeyboardButton("Заказать", callback_data="send_order")
message_types = [
    "text",
    "document",
    "photo",
    "audio",
    "video",
    "voice",
    "video_note",
    "sticker",
    "location",
    "contact",
    "animation",
    "invoice",
    "chat_invite_link",
    "shipping_query",
    "pre_checkout_query"
]

greetings_text = '''"Наши Цветы" - Ваш надежный партнер в мире флористики!\n\n
📌 Оптовая и розничная продажа срезанных цветов сопутствующих товаров
📌 Упаковка подарков
📌 Воздушные шары
📌 Ландшафтный дизайн\n\n
Наши контакты: тел. 55-45-45\n\nНаш телеграм канал: @NASHI_CVETY
'''

# СОЗДАНИЕ КЛАВИАТУР
for i in profile_button_texts:
    button = InlineKeyboardButton(i, callback_data=i)
    p_keyboard.append([button])
p_keyboard.append([back_to_start_button])
profile_keyboard = InlineKeyboardMarkup(p_keyboard)

for i in add_bouqet_button_text:
    button = InlineKeyboardButton(i, callback_data=i)
    b_keyboard.append([button])
b_keyboard.append([back_to_start_button])
bouqets_keyboard = InlineKeyboardMarkup(b_keyboard)

forward = InlineKeyboardButton("->", callback_data='forward')
back = InlineKeyboardButton("<-", callback_data='back')
choose = InlineKeyboardButton("В корзину", callback_data="choose")

# Открываем файл и загружаем его содержимое
with open('users.json', 'r') as file:
    data = json.load(file)
    json_users = list(data.keys())


# ПРОВЕРКА ВАЛИДНОСТИ
def is_valid_email(email):
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email) is not None


def is_valid_name(name):
    if re.match("^[а-яА-ЯёЁa-zA-Z]+$", name) and 1 <= len(name) <= 50:
        return True
    return False


def is_valid_phone_number(phone_number):
    pattern = r'^(?:\+7|8)[0-9]{10}$'
    return bool(re.match(pattern, phone_number))


def return_bouqet_text(spisok):
    return f"""Новый букет\nНазвание: {spisok['bouqet_name']}\nФото: {len(spisok['bouqet_photo']) if spisok['bouqet_photo'][0][-3:] == 'jpg' else 0}/1\nОписание: {spisok['bouqet_description']}\nЦена: {spisok['bouqet_price']} {'' if spisok['bouqet_price'] == 'Не указана' else 'р.'}"""


def create_new_bouqet():
    return {'bouqet_name': 'Не указано', 'bouqet_photo': ['Не добавлено'], 'bouqet_description': 'Не указано',
            'bouqet_price': 'Не указана', 'ready': True}


def return_text_about_bouqet(sp):
    text = f'''Название букета: {sp[1]}\n\nОписание букета: {sp[3]}\n\nСтоимость букета: {sp[4]} р.'''
    photo = 'data/' + sp[2]
    return [text, photo]


def return_first(a):
    return a[0]


def bouqet_id(a):
    return a[1]


# ФУНКЦИЯ СОЗДАНИЯ ТЕКСТА ДЛЯ КОРЗИНЫ ПОЛЬЗВАТЕЛЯ
def basket_text(sp):
    text_for_basket = '🛒Корзина\n\n🌷Букеты:\n\n'
    bouqets_ids = list(map(bouqet_id, sp))
    cur.execute(f"""SELECT * FROM bouqets WHERE id IN %s""", (tuple(bouqets_ids),))
    bouqets_ids = cur.fetchall()
    counter = 1
    summa = 0
    for el in bouqets_ids:
        summa += int(el[4])
        pr = len(str(counter)) + 3
        el_txt = list(el[1:2] + el[3:])
        text_for_basket += f'''{counter}. Название букета: {el_txt[0]}\n{' ' * pr}Описание букета: {el_txt[1]}\n{' ' * pr}Стоимость букета: {el_txt[2]} р. \n\n'''
        counter += 1
    text_for_basket += f'Итого: {summa}'
    return text_for_basket


# ФУНКЦИЯ СОЗДАНИЯ ТЕКСТА ЗАКАЗА ДЛЯ ОТОБРАЖЕНИЯ
def order_text(sp, username):
    text = f'''Пользователь: @{username}\n\nЗаказ:\n\n'''
    cur.execute(f"""SELECT * FROM bouqets WHERE id IN %s""", (tuple(sp),))
    bouqets_ids = cur.fetchall()
    summa = 0
    counter = 1
    for el in bouqets_ids:
        summa += int(el[4])
        pr = len(str(counter)) + 3
        el_txt = list(el[1:2] + el[3:])
        text += f'''{counter}. Название букета: {el_txt[0]}\n{' ' * pr}Описание букета: {el_txt[1]}\n{' ' * pr}Стоимость букета: {el_txt[2]} р. \n\n'''
        counter += 1
    text += f'Итого: {summa}'
    return text


# СОЗДАНИЕ СЛОВАРЯ ПОЛЬЗОВАТЕЛЕЙ, ДЛЯ ХРАНЕНИЯ ВРЕМЕННЫХ ПЕРЕМЕННЫХ
def make_json_user(us_id):
    data[str(us_id)] = {}
    data[str(us_id)]['wait_message_profile'] = False
    data[str(us_id)]['wait_message_add_bouqet'] = False
    data[str(us_id)]['download_photo'] = False
    data[str(us_id)]['profile_message_data'] = []
    data[str(us_id)]['add_bouqets_message_data'] = []
    data[str(us_id)]['current_order'] = ''
    data[str(us_id)]['click_count'] = 0
    data[str(us_id)]['page_count'] = 1
    data[str(us_id)]['access'] = False
    file = open('users.json', 'w')
    json.dump(data, file, indent=4)


def save_to_json():
    file = open('users.json', 'w')
    json.dump(data, file, indent=4)


# СОЗДАНИЕ СПИСКА ЗАКАЗОВ В ВИДЕ КЛАВИАТУРЫ
def make_orders_list(idu, lst):
    sp = []
    start = (data[str(idu)]['page_count'] - 1) * 10
    finish = data[str(idu)]['page_count'] * 10
    for i in range(len(lst[start: finish + 1])):
        button = InlineKeyboardButton(f"Заказ {i + 1}", callback_data=lst[i])
        sp.append([button])
    print(sp)
    return sp


# ФУНКЦИЯ ТРАНСФОРМАЦИИ КОРТЕЖА В СПИСОК ДЛЯ CALLBACK_DATA
def make_string(a):
    return '.'.join(list(map(str, a)))


# НАЧАЛЬНОЕ СООБЩЕНИЕ
@bot.message_handler(commands=['start'])
def start(message):
    cur.execute(
        f"""INSERT INTO users (user_id, username) VALUES ({message.chat.id}, '{message.chat.username}') ON CONFLICT (user_id) DO NOTHING;""")
    cur.execute('''SELECT role FROM users WHERE user_id = %s''', (message.chat.id,))
    role = cur.fetchone()[0]
    make_json_user(message.chat.id)
    button1 = InlineKeyboardButton("Готовые букеты", callback_data='bouquets')
    button2 = InlineKeyboardButton("Корзина", callback_data='basket')
    button3 = InlineKeyboardButton("Профиль", callback_data='profile')
    button4 = InlineKeyboardButton("Добавить букет", callback_data='add_bouqet')
    button5 = InlineKeyboardButton("Список заказов", callback_data='order_list')
    keyboard = [[button1], [button2], [button3], [button5]]
    if role in [2, 3]:
        keyboard.append([button4])
    keyboard = InlineKeyboardMarkup(keyboard)
    # bot.send_message(message.chat.id, greetings_text, reply_markup=keyboard)
    with open('data/logo.jpg', 'rb') as photo:
        bot.send_photo(message.chat.id, caption=greetings_text, photo=photo, reply_markup=keyboard)
    conn.commit()


# ОТКРЫТИЕ СПИСКА ЗАКАЗОВ АДМИН/ПОЛЬЗОВАТЕЛЬ
@bot.callback_query_handler(func=lambda call: call.data in ['order_list'])
def orders(call):
    global orders_list
    cur.execute('''SELECT role FROM users WHERE user_id = %s''', (call.message.chat.id,))
    user_role = cur.fetchone()[0]
    idu = call.message.chat.id
    keyboard = []
    if user_role in [2, 3]:
        cur.execute("""SELECT * FROM orders""")
        orders_list = list(map(make_string, cur.fetchall()))
        if orders_list:
            keyboard = make_orders_list(idu, orders_list)
    else:
        cur.execute(f"""SELECT * FROM orders WHERE user_id = '{call.message.chat.id}'""")
        orders_list = list(map(make_string, cur.fetchall()))
        if orders_list:
            keyboard = make_orders_list(idu, orders_list)
    forward_button = InlineKeyboardButton('->', callback_data='next_page')
    back_button = InlineKeyboardButton('<-', callback_data='back_page')
    keyboard.append([back_button, forward_button])
    keyboard.append([back_to_start_button])
    keyboard_1 = InlineKeyboardMarkup(keyboard)
    bot.delete_message(call.message.chat.id, message_id=call.message.message_id)
    bot.send_message(idu, 'Список заказов', reply_markup=keyboard_1)


# ОТКРЫТЬ ЗАКАЗ
@bot.callback_query_handler(func=lambda call: call.data in orders_list)
def open_order(call):
    bot.delete_message(call.message.chat.id, message_id=call.message.message_id)
    delete_order = InlineKeyboardButton("Удалить заказ", callback_data="delete_order")
    inf = call.data.split('.')
    data[str(call.message.chat.id)]['current_order'] = int(inf[0])
    save_to_json()
    print(inf)
    cur.execute("""SELECT bouqets_id FROM orders WHERE id = %s AND user_id = %s""", (inf[0], inf[1]))
    bouqets_id = cur.fetchone()[0]
    cur.execute("""SELECT username FROM users WHERE user_id = %s""", (inf[1],))
    username = cur.fetchone()[0]
    keyboard = InlineKeyboardMarkup([[delete_order], [back_to_order_list_button]])
    text = order_text(bouqets_id.split(';'), username)
    bot.send_message(call.message.chat.id, text, reply_markup=keyboard)


# ВОЗВРАТ К СПИСКУ ЗАКАЗОВ
@bot.callback_query_handler(func=lambda call: call.data in ['back_to_order_list'])
def close_order(call):
    orders(call)
    bot.delete_message(call.message.chat.id, message_id=call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data in ['delete_order'])
def delete_order_fn(call):
    order_id = data[str(call.message.chat.id)]['current_order']
    cur.execute(f"""DELETE FROM orders WHERE id = {order_id}""")
    close_order(call)


# ОТКРЫТИЕ ВИТРИНЫ С БУКЕТАМИ
@bot.callback_query_handler(func=lambda call: call.data in ['bouquets'])
def handle_first_buttons(call):
    global bouqets, role, current_bouqet_id
    cur.execute('''SELECT role FROM users WHERE user_id = %s''', (call.message.chat.id,))
    role = cur.fetchone()[0]
    cur.execute('''SELECT * FROM bouqets WHERE bouqet_busy = 0''')
    bouqets = cur.fetchall()
    bot.delete_message(call.message.chat.id, call.message.message_id)
    data[str(call.message.chat.id)]['click_count'] = 0
    save_to_json()
    if bouqets:
        info = return_text_about_bouqet(bouqets[data[str(call.message.chat.id)]['click_count']])
        current_bouqet_id = bouqets[data[str(call.message.chat.id)]['click_count']][0]
        showcase_keyboard = [[back, choose, forward], [back_to_start_button]]
        if role in [2, 3]:
            showcase_keyboard.append([delete_bouqet_button])
        new_keyboard = InlineKeyboardMarkup(showcase_keyboard)
        with open(info[1], 'rb') as photo:
            bot.send_photo(call.message.chat.id, caption=info[0], photo=photo, reply_markup=new_keyboard)
    else:
        keyboard = InlineKeyboardMarkup([[back_to_start_button]])
        bot.send_message(chat_id=call.message.chat.id, text='Витрина пока что пуста, приходите позже :)',
                         reply_markup=keyboard)


# УДАЛЕНИЕ БУКЕТА С ВИТРИНЫ

@bot.callback_query_handler(func=lambda call: call.data in ['delete_bouqet'])
def delete_bouqet_fn(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    start(call.message)
    cur.execute(f"""SELECT bouqet_photo FROM bouqets WHERE id = {current_bouqet_id}""")
    file_name = str(map(return_first, cur.fetchone()))
    file_path = os.path.join('data', file_name + '.jpg')
    if os.path.isfile(file_path):
        os.remove(file_path)
    cur.execute(f"""DELETE FROM bouqets WHERE id = {current_bouqet_id}""")
    conn.commit()


# ОТКРЫТИЕ ПРОФИЛЯ ПОЛЬЗОВАТЕЛЯ

@bot.callback_query_handler(func=lambda call: call.data in ['profile'])
def profile_open(call):
    global profile_keyboard
    bot.delete_message(call.message.chat.id, call.message.message_id)
    cur.execute("""SELECT email, first_name, user_phone_number, delivery_address FROM users WHERE user_id = %s;""",
                (call.message.chat.id,))
    user_info = cur.fetchone()
    profile_text = f"""Профиль\n\nИмя: {user_info[1]}\n\nНомер телефона: {user_info[2]}\n\nЭлектронная почта: {user_info[0]}\n\nАдрес доставки: {user_info[3]}"""
    msg = bot.send_message(call.message.chat.id, profile_text, reply_markup=profile_keyboard)
    data[str(call.message.chat.id)]['profile_message_data'] = []
    data[str(call.message.chat.id)]['profile_message_data'].append(msg.message_id)
    save_to_json()


# ДОБАВЛЕНИЕ БУКЕТА В КОРЗИНУ
@bot.callback_query_handler(func=lambda call: call.data in ['choose'])
def add_to_basket(call):
    bouqet_id = bouqets[data[str(call.message.chat.id)]['click_count']][0]
    user_id = call.message.chat.id
    cur.execute(f"""SELECT bouqet_id FROM basket WHERE user_id = '{user_id}'""")
    bouqets_id = list(map(return_first, cur.fetchall()))
    if bouqet_id not in bouqets_id:
        cur.execute(f"""INSERT INTO basket (bouqet_id, user_id) VALUES ({bouqet_id}, '{user_id}')""")
        conn.commit()
        msg = bot.send_message(call.message.chat.id, text='Букет успешно добавлен в корзину!')
        time.sleep(2)
        bot.delete_message(call.message.chat.id, message_id=msg.message_id)
    else:
        msg = bot.send_message(call.message.chat.id, 'Этот букет уже у Вас в корзине')
        time.sleep(2)
        bot.delete_message(call.message.chat.id, message_id=msg.message_id)


# ФУНКЦИОНАЛ СМЕНЫ ЛИЧНЫХ ДАННЫХ

@bot.callback_query_handler(func=lambda call: call.data in profile_button_texts)
def change(call):
    global profile_button_texts, type_message
    data[str(call.message.chat.id)]['wait_message_profile'] = True
    bot.answer_callback_query(call.id)
    for el in range(1, len(data[str(call.message.chat.id)]['profile_message_data'])):
        bot.delete_message(chat_id=call.message.chat.id,
                           message_id=data[str(call.message.chat.id)]['profile_message_data'][el])
    data[str(call.message.chat.id)]['profile_message_data'] = [
        data[str(call.message.chat.id)]['profile_message_data'][0]]
    bck_to_profile = InlineKeyboardButton("Назад", callback_data="back_to_profile")
    keyboard = [[bck_to_profile]]
    new_keyboard = InlineKeyboardMarkup(keyboard)
    msg_1 = bot.send_message(call.message.chat.id,
                             f"Теперь вы можете отправить {' '.join(call.json['data'].split()[1:])}",
                             reply_markup=new_keyboard)
    data[str(call.message.chat.id)]['profile_message_data'].append(msg_1.message_id)
    save_to_json()
    bot.register_next_step_handler(call.message, chn)
    type_message = profile_button_texts.index(call.json['data'])


def chn(message):
    global profile_keyboard, type_message, answer, sql_request
    if str(message.chat.id) in json_users:
        data[str(message.chat.id)]['wait_message_profile'] = False
        save_to_json()
        if type_message == 0:
            if is_valid_name(message.text):
                data[str(message.chat.id)]['access'] = True
        elif type_message == 1:
            if is_valid_phone_number(message.text):
                data[str(message.chat.id)]['access'] = True
        elif type_message == 2:
            if is_valid_email(message.text):
                data[str(message.chat.id)]['access'] = True
        elif type_message == 3:
            data[str(message.chat.id)]['access'] = True
        if data[str(message.chat.id)]['access']:
            ans = bot.send_message(message.chat.id, answer[type_message])
            cur.execute(f"""UPDATE users SET {sql_request[type_message]} = %s WHERE user_id = %s""",
                        (message.text, message.chat.id))
            conn.commit()
            cur.execute(
                """SELECT username, user_phone_number, email, delivery_address FROM users WHERE user_id = %s;""",
                (message.chat.id,))
            user_info = cur.fetchone()
            profile_text = f"""Профиль\n\nИмя: {user_info[0]}\n\nНомер телефона: {user_info[1]}\n\nЭлектронная почта: {user_info[2]}\n\nАдрес доставки: {user_info[3]}"""
            bot.edit_message_text(text=profile_text, chat_id=message.chat.id,
                                  message_id=data[str(message.chat.id)]['profile_message_data'][0],
                                  reply_markup=profile_keyboard)
            data[str(message.chat.id)]['wait_message_profile'] = False
            data[str(message.chat.id)]['access'] = False
        else:
            ans = bot.send_message(message.chat.id, "Неверный формат ввода.\nПопробуйте еще раз.")
            data[str(message.chat.id)]['wait_message_profile'] = False
        time.sleep(2)
        bot.delete_message(chat_id=message.chat.id, message_id=data[str(message.chat.id)]['profile_message_data'][1])
        bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        bot.delete_message(chat_id=message.chat.id, message_id=ans.message_id)
        data[str(message.chat.id)]['profile_message_data'] = [data[str(message.chat.id)]['profile_message_data'][0]]
        save_to_json()


# ОСНОВНЫЕ ДЕЙСТВИЯ С КНОПКАМИ


# ВОЗВРАТ К ПЕРВОМУ СООБЩЕНИЮ
@bot.callback_query_handler(func=lambda call: call.data == 'back_to_start')
def handle_second_buttons(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    start(call.message)


# ВОЗВРАТ К ПРОФИЛЮ
@bot.callback_query_handler(func=lambda call: call.data == 'back_to_profile')
def back_profile(call):
    for el in data[str(call.message.chat.id)]['profile_message_data'][1:]:
        bot.delete_message(call.message.chat.id, message_id=el)
    data[str(call.message.chat.id)]['profile_message_data'] = [
        data[str(call.message.chat.id)]['profile_message_data'][0]]
    save_to_json()
    bot.delete_message(call.message.chat.id, call.message.message_id)
    profile_open(call)


# ВОЗВРАТ К СОЗДАНИЮ БУКЕТА
@bot.callback_query_handler(func=lambda call: call.data == 'back_to_change_list')
def back_change(call):
    global temporary_data
    if temporary_data:
        save_photo(*temporary_data)
    data[str(call.message.chat.id)]['wait_message_add_bouqet'] = False
    data[str(call.message.chat.id)]['download_photo'] = False
    for message in data[str(call.message.chat.id)]['add_bouqets_message_data'][1:]:
        bot.delete_message(call.message.chat.id, message)
    data[str(call.message.chat.id)]['add_bouqets_message_data'] = [
        data[str(call.message.chat.id)]['add_bouqets_message_data'][0]]
    save_to_json()


# СОХРАНЕНИЕ БУКЕТА
@bot.callback_query_handler(func=lambda call: call.data == 'Сохранить')
def save_bouqet(call):
    global new_bouqet, temporary_data
    cur.execute(
        f'''INSERT INTO bouqets (bouqet_name, bouqet_photo, bouqet_description, bouqet_price) 
        VALUES ('{new_bouqet['bouqet_name']}', '{str(new_bouqet['bouqet_photo'][0])}', '{new_bouqet['bouqet_description']}', 
        '{new_bouqet['bouqet_price']}')''')
    conn.commit()
    new_bouqet = create_new_bouqet()
    ans = bot.send_message(call.message.chat.id, 'Данные успешно сохранены')
    time.sleep(2)
    bot.delete_message(call.message.chat.id, ans.message_id)
    temporary_data = []
    text_bouqets = return_bouqet_text(new_bouqet)
    bot.edit_message_text(text_bouqets, chat_id=call.message.chat.id,
                          message_id=data[str(call.message.chat.id)]['add_bouqets_message_data'][0],
                          reply_markup=bouqets_keyboard)


# ПЕРЕЛИСТЫВАНИЕ ВИТРИНЫ (ВПЕРЕД/НАЗАД)
@bot.callback_query_handler(func=lambda call: call.data in ['forward', 'back'])
def forward_back_buttons(call):
    global bouqets, role, current_bouqet_id
    edit = False
    if call.data == 'forward' and data[str(call.message.chat.id)]['click_count'] < len(bouqets) - 1:
        data[str(call.message.chat.id)]['click_count'] += 1
        edit = True
    elif call.data == 'back' and data[str(call.message.chat.id)]['click_count'] > 0:
        data[str(call.message.chat.id)]['click_count'] -= 1
        edit = True
    save_to_json()
    if edit:
        showcase_keyboard = [[back, choose, forward], [back_to_start_button]]
        if role in [2, 3]:
            showcase_keyboard.append([delete_bouqet_button])
        new_keyboard = InlineKeyboardMarkup(showcase_keyboard)
        info = return_text_about_bouqet(bouqets[data[str(call.message.chat.id)]['click_count']])
        current_bouqet_id = bouqets[data[str(call.message.chat.id)]['click_count']][0]
        with open(info[1], 'rb') as new_photo:
            bot.edit_message_media(media=InputMediaPhoto(new_photo, caption=info[0]), chat_id=call.message.chat.id,
                                   message_id=call.message.message_id, reply_markup=new_keyboard)


# ОТКРЫТИЕ КОРЗИНЫ
@bot.callback_query_handler(func=lambda call: call.data in ['basket'])
def open_basket(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    keyboard = [[back_to_start_button]]
    cur.execute(f"""SELECT * FROM basket WHERE user_id = '{call.message.chat.id}'""")
    bouqs = cur.fetchall()
    profile_text = "Корзина пока что пуста.\nДобавьте в неё товары."
    if bouqs:
        keyboard.insert(0, [order_button])
        profile_text = basket_text(bouqs)
    new_keyboard_1 = InlineKeyboardMarkup(keyboard)
    bot.send_message(call.message.chat.id, profile_text, reply_markup=new_keyboard_1)


@bot.callback_query_handler(func=lambda call: call.data in ['send_order'])
def send_order_function(call):
    cur.execute(f"""SELECT * FROM basket WHERE user_id = '{call.message.chat.id}'""")
    user_id = call.message.chat.id
    bouqs = cur.fetchall()
    if bouqs:
        bouqs_id = ';'.join([str(el[1]) for el in bouqs])
        msg = bot.send_message(admin[0], 'У Вас новый заказ!')
        cur.execute(f"""UPDATE bouqets SET bouqet_busy = 1 WHERE id IN ({', '.join(bouqs_id.split(';'))})""")
        cur.execute(f"""INSERT INTO orders (user_id, bouqets_id) VALUES ('{user_id}', '{bouqs_id}')""")
        conn.commit()
        time.sleep(10)
        bot.delete_message(admin[0], message_id=msg.message_id)


# ДОБАВЛЕНИЕ НОВОГО БУКЕТА
@bot.callback_query_handler(func=lambda call: call.data in ['add_bouqet'])
def add_bouq(call):
    global bouqets_keyboard, new_bouqet, temporary_data
    temporary_data = []
    new_bouqet = create_new_bouqet()
    bot.delete_message(call.message.chat.id, call.message.message_id)
    text_bouqets = return_bouqet_text(new_bouqet)
    msg = bot.send_message(call.message.chat.id, text_bouqets, reply_markup=bouqets_keyboard)
    data[str(call.message.chat.id)]['add_bouqets_message_data'] = []
    data[str(call.message.chat.id)]['add_bouqets_message_data'].append(msg.message_id)
    save_to_json()


# ВЫБОР ПАРАМЕТРА ИЗМЕНЕНИЯ У БУКЕТА
@bot.callback_query_handler(func=lambda call: call.data in add_bouqet_button_text)
def change_1(call):
    global add_bouqet_button_text, type_message_2
    bck_to_changes = InlineKeyboardButton("Назад", callback_data="back_to_change_list")
    new_keyboard_b = InlineKeyboardMarkup([[bck_to_changes]])
    msg_2 = bot.send_message(call.message.chat.id,
                             f"Теперь вы можете отправить {' '.join(call.json['data'].split()[1:])}",
                             reply_markup=new_keyboard_b)
    data[str(call.message.chat.id)]['add_bouqets_message_data'].append(msg_2.message_id)
    type_message_2 = add_bouqet_button_text.index(call.json['data'])
    if type_message_2 in [0, 2, 3]:
        data[str(call.message.chat.id)]['wait_message_add_bouqet'] = True
        bot.register_next_step_handler(call.message, text_changes)
    else:
        if new_bouqet['ready'] is True:
            new_bouqet[sql_request_b[1]].clear()
            new_bouqet['ready'] = False
        data[str(call.message.chat.id)]['download_photo'] = True
        bot.register_next_step_handler(call.message, handle_photo)
    save_to_json()


# ОБРАБОТКА ТЕКСТОВЫХ ПАРАМЕТРОВ У БУКЕТА
@bot.message_handler(content_types=['message'])
def text_changes(message: telebot.types.Message):
    global bouqets_keyboard, answer_b, sql_request_b, type_message_2, new_bouqet
    if data[str(message.chat.id)]['wait_message_add_bouqet']:
        data[str(message.chat.id)]['wait_message_add_bouqet'] = False
        data[str(message.chat.id)]['add_bouqets_message_data'].append(message.message_id)
        new_bouqet[sql_request_b[type_message_2]] = message.text
        text_bouqets = return_bouqet_text(new_bouqet)
        ans_b = bot.send_message(message.chat.id, answer_b[type_message_2])
        data[str(message.chat.id)]['add_bouqets_message_data'].append(ans_b.message_id)
        bot.edit_message_text(text_bouqets, chat_id=message.chat.id,
                              message_id=data[str(message.chat.id)]['add_bouqets_message_data'][0],
                              reply_markup=bouqets_keyboard)
        time.sleep(2)
        for el in data[str(message.chat.id)]['add_bouqets_message_data'][1:]:
            bot.delete_message(message.chat.id, el)
        data[str(message.chat.id)]['add_bouqets_message_data'] = [
            data[str(message.chat.id)]['add_bouqets_message_data'][0]]
    save_to_json()


# ОБРАБОТКА ФОТОГРАФИЙ ДЛЯ БУКЕТА
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    global new_bouqet, temporary_data
    if data[str(message.chat.id)]['download_photo']:
        if len(temporary_data) < 1:
            temporary_data.append(message.photo[-1])
            data[str(message.chat.id)]['add_bouqets_message_data'].append(message.message_id)
        if len(temporary_data) == 1:
            data[str(message.chat.id)]['download_photo'] = False
            save_photo(*temporary_data[len(new_bouqet[sql_request_b[1]]):])
            temporary_data = []
            ans_b = bot.send_message(message.chat.id, answer_b[1])
            data[str(message.chat.id)]['add_bouqets_message_data'].append(ans_b.message_id)
            for el in data[str(message.chat.id)]['add_bouqets_message_data'][1:]:
                bot.delete_message(message.chat.id, el)
            data[str(message.chat.id)]['add_bouqets_message_data'] = [
                data[str(message.chat.id)]['add_bouqets_message_data'][0]]
        text_bouqets = return_bouqet_text(new_bouqet)
        bot.edit_message_text(text_bouqets, chat_id=message.chat.id,
                              message_id=data[str(message.chat.id)]['add_bouqets_message_data'][0],
                              reply_markup=bouqets_keyboard)
        save_to_json()
    else:
        bot.delete_message(message.chat.id, message.message_id)


# СОХРАНЕНИЕ ФОТОГРАФИЙ В ПАПКУ data
def save_photo(*file_info):
    for files in file_info:
        file_count = len([f for f in os.listdir('data') if os.path.isfile(os.path.join('data', f))])
        file_id = files.file_id
        file = bot.get_file(file_id)
        file_path = os.path.join('data', f"photo_{file_count + 1}.jpg")
        downloaded_file = bot.download_file(file.file_path)
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
            new_bouqet[sql_request_b[1]].append(file_path.split('\\')[1])


# УДАЛЕНИЕ ЛЮБЫХ СООБЩЕНИЙ, КОТОРЫЕ НЕ ЖДАЛ БОТ
@bot.message_handler(content_types=message_types)
def echo_message(message):
    if not data[str(message.chat.id)]['wait_message_profile'] and not data[str(message.chat.id)]['download_photo']:
        bot.delete_message(chat_id=message.chat.id, message_id=message.id)


# ОТПРАВКА СООБЩЕНИЙ АДМИНИСТРАТОРУ
@bot.message_handler(content_types=['document'])
def doc(message):
    if message.document:
        bot.send_document(admin[0], message.document.file_id, caption=f'Сдал отчет @{message.from_user.username}')


# Запускаем бота
if __name__ == '__main__':
    bot.polling(none_stop=True)
