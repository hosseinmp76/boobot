import os
import logging
import json
import re
import subprocess
from functools import wraps

from telegram.ext import Updater, CommandHandler, MessageHandler
from telegram.ext.filters import Filters
from telegram import InlineKeyboardButton, ReplyKeyboardMarkup

from src.db import DB, BooUser


class Boobot:

    def __init__(self, bot_token, admin_id, engine_uri, oc_host,
            mtproto_proxy, base_dir, log_level='INFO'):
        self.updater = Updater(bot_token, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.input_dispatcher = \
            {
                #user_id: callback_function
        }

        self.db = DB(engine_uri)
        
        self.admin_id = admin_id
        self.oc_host = oc_host
        self.mtproto_proxy = mtproto_proxy
        self.base_dir = base_dir

        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level={
                'INFO': logging.INFO,
                'DEBUG': logging.DEBUG,
                'ERROR': logging.ERROR,
                }[log_level]
        )


    def build_callback(self, data):
        return_value = json.dumps(data)
        if len(return_value) > 64:
            raise Exception("Callback data is larger than 64 bytes")
        return return_value


    def send_keyboard(self, update, keyboard, text):
        reply_keyboard = ReplyKeyboardMarkup(keyboard)
        update.message.reply_text(
            text=text,
            reply_markup=reply_keyboard
            )

    
    def check_user(func):
        def wrapper(self, *args, **kwargs):
            update, context = args[0], args[1]
            user = update.message.chat
            if self.db.get_user(user) == None:
                keyboard = [
                    [InlineKeyboardButton(f'ADD {user.id}')],
                    [InlineKeyboardButton('main menu')]
                ]
                admin_msg = (
                    'HEY ADMIN!\n'
                    f'following user wants to join {user.id} @{user.username} \n'
                )
                reply_keyboard = ReplyKeyboardMarkup(keyboard)
                context.bot.send_message(self.admin_id, admin_msg,
                    reply_markup=reply_keyboard)
                msg = (
                    'admin has been informed about your request.\n'
                    'they may contact you soon!\n'
                )
                update.message.reply_text(text=msg)
                return
            return func(self, *args, **kwargs)
        return wrapper


    def check_admin(func):
        def wrapper(self, *args, **kwargs):
            update, context = args[0], args[1]
            user_id = update.message.chat.id
            if str(user_id) != str(self.admin_id):
                msg = \
                    'BITCH YOU THOUGHT YOU CAN SEND ADMIN COMMANDS?'
                update.message.reply_text(text=msg)
                return
            return func(self, *args, **kwargs)
        return wrapper

    
    @check_admin
    def admin_add_user(self, update, context):
        text = update.message.text
        user_id = text.split()[1]
        chat = context.bot.get_chat(user_id)
        self.db.create_user(chat)
        keyboard = [
            [
                InlineKeyboardButton('openconnect'),
                InlineKeyboardButton('mtproto')
            ]
        ]
        admin_keyboard = [
            [InlineKeyboardButton('main menu')]
        ]
        self.send_keyboard(update, admin_keyboard, 'user registered')
        msg = 'Horray! now you\'re registered!'
        reply_keyboard = ReplyKeyboardMarkup(keyboard)
        context.bot.send_message(user_id, msg, reply_markup=reply_keyboard)


    @check_admin
    def admin_list_users(self, update, context):
        users = self.db.all_users()

        users_full = [context.bot.get_chat(user.id) for user in users]

        keyboard = [
            [
                InlineKeyboardButton('main menu'),
            ]
        ] + [
            [
                InlineKeyboardButton(
                    f'{user.first_name} {user.last_name} | @{user.username}'),
                InlineKeyboardButton(f'DEL {user.id}')

            ] for user in users_full
        ]
        self.send_keyboard(update, keyboard, f'all {len(users)} users:')


    @check_admin
    def admin_delete_user(self, update, context):
        text = update.message.text
        user_id = text.split()[1]
        oc_username = self.db.delete(user_id)

        if oc_username is not None:
            subprocess.run(
                [
                    self.base_dir + '/src/delete_user.sh',
                    f'{oc_username}',
                ]
            )

        keyboard = [
            [
                InlineKeyboardButton('openconnect'),
                InlineKeyboardButton('mtproto')
            ]
        ]
        admin_keyboard = [
            [InlineKeyboardButton('main menu')]
        ]
        self.send_keyboard(update, admin_keyboard, 'deleted')
        msg = 'How sad :( Hope to see you soon again!'
        reply_keyboard = ReplyKeyboardMarkup(keyboard)
        context.bot.send_message(user_id, msg, reply_markup=reply_keyboard)


    @check_admin
    def admin_sendtoall(self, update, context):
        user_id = update.message.chat.id
        self.input_dispatcher[user_id] = self.admin_sendtoall_message
        msg = 'Ok. now send me the message or cancel'
        keyboard = [
            [
                InlineKeyboardButton('cancel')
            ],
            [
                InlineKeyboardButton('openconnect'),
                InlineKeyboardButton('mtproto')
            ]
        ]
        self.send_keyboard(update, keyboard, msg)


    @check_admin
    def admin_sendtoall_message(self, update, context):
        user_id = update.message.chat.id
        self.input_dispatcher[user_id] = None
        text = update.message.text
        users = self.db.all_users()
        keyboard = [
            [
                InlineKeyboardButton('openconnect'),
                InlineKeyboardButton('mtproto')
            ]
        ]
        reply_keyboard = ReplyKeyboardMarkup(keyboard)
        for user in users:
            try:
                context.bot.send_message(user.id, text, reply_markup=reply_keyboard)
            except:
                print('bot blocked')


    @check_user
    def start(self, update, context):
        user = self.db.get_user(update.message.chat)
        keyboard = [
            [
                InlineKeyboardButton('openconnect'),
                InlineKeyboardButton('mtproto')
            ]
        ]
        self.send_keyboard(update, keyboard, 'main menu')


    @check_user
    def mtproto(self, update, context):
        keyboard = [
            [InlineKeyboardButton('main menu')]
        ]
        msg = self.mtproto_proxy
        self.send_keyboard(update, keyboard, msg)

    
    @check_user
    def openconnect(self, update, context):
        keyboard = [
            [InlineKeyboardButton('show openconnect data'),
            InlineKeyboardButton('add openconnect data')],
            [InlineKeyboardButton('main menu')]
        ]
        self.send_keyboard(update, keyboard, 'openconnect')


    @check_user
    def openconnect_show_data(self, update, context):
        user = self.db.get_user(update.message.chat)

        if not user.oc_username or not user.oc_password:
            keyboard = [
                [InlineKeyboardButton('add openconnect data'),
                InlineKeyboardButton('main menu')]
            ]
            self.send_keyboard(update, keyboard,
                'you have no openconnect data. first add one')
        else:
            keyboard = [
                [InlineKeyboardButton('main menu')]
            ]
            self.send_keyboard(update, keyboard,
                (
                    f'host: {self.oc_host}\n'
                    f'user: {user.oc_username}\n'
                    f'pass: {user.oc_password}\n'
                )
            )


    @check_user
    def openconnect_add_data(self, update, context):
        user = self.db.get_user(update.message.chat)
        keyboard = []
        if user.oc_username and user.oc_password:
            msg = 'you already have an openconnect account'
            keyboard.append([InlineKeyboardButton('show openconnect data')])
        else:
            msg = 'enter a username for openconnect:'
            self.input_dispatcher[user.id] = self.openconnect_add_data_username
        keyboard.append([InlineKeyboardButton('main menu')])
        self.send_keyboard(update, keyboard, msg)


    @check_user
    def openconnect_add_data_username(self, update, context):
        user = self.db.get_user(update.message.chat)
        text = update.message.text
        keyboard = [
            [InlineKeyboardButton('openconnect'),
            InlineKeyboardButton('main menu')]
        ]
        if re.match('\w{3,}', text):
            users = self.db.query(BooUser, BooUser.oc_username == text)
            if users.count() == 1 and users.first().id != user.id:
                msg = 'a user has already choosen this username!'
            else:
                s = self.db.session()
                user = s.query(BooUser).filter(BooUser.id == user.id).first()
                user.oc_username = text
                s.commit()
                msg = 'now choose a strong password:'
                self.input_dispatcher[user.id] = \
                        self.openconnect_add_data_password
        else:
            msg = (
                    'username must start with a-zA-Z\n'
                    'contain only a-zA-Z0-9\n'
                    'and be atleast 3 characters\n'
            )
        self.send_keyboard(update, keyboard, msg)


    @check_user
    def openconnect_add_data_password(self, update, context):
        user = self.db.get_user(update.message.chat)
        text = update.message.text
        keyboard = [
            [InlineKeyboardButton('main menu')]
        ]
        if 8 <= len(text) <= 128:
            s = self.db.session()
            user = s.query(BooUser).filter(BooUser.id == user.id).first()
            user.oc_password = text
            s.commit()
            
            subprocess.run(
                [
                    self.base_dir + '/src/add_user.sh',
                    f'{user.oc_username}',
                    f'{user.oc_password}',
                ]
            )

            msg = (
                'nice! your openconnect account is ready.\n'
                'press "show openconnect data" to get your account information'
            )
            keyboard.append([InlineKeyboardButton('show openconnect data')])
            self.send_keyboard(update, keyboard, msg)
            self.input_dispatcher[user.id] = None
        else:
            msg = 'password must be between 8 and 128 characters'
            self.send_keyboard(update, keyboard, msg)


    @check_user
    def user_input(self, update, context):
        user_id = update.message.chat.id
        if user_id in self.input_dispatcher:
            return self.input_dispatcher[user_id](update, context)
        else:
            keyboard = [
                [InlineKeyboardButton('main menu')]
            ]
            msg = 'can\'t understand what to do'
            self.send_keyboard(update, keyboard, msg)


    def add_handlers(self):
        start_handler = CommandHandler('start', self.start)
        self.dispatcher.add_handler(start_handler)

        admin_list_users_handler = MessageHandler(Filters.regex('^LIST$'),
                self.admin_list_users)
        self.dispatcher.add_handler(admin_list_users_handler)

        admin_add_user_handler = MessageHandler(Filters.regex('^ADD \d+$'),
                self.admin_add_user)
        self.dispatcher.add_handler(admin_add_user_handler)

        admin_delete_user_handler = MessageHandler(Filters.regex('^DEL \d+$'),
                self.admin_delete_user)
        self.dispatcher.add_handler(admin_delete_user_handler)

        admin_sendtoall_handler = MessageHandler(Filters.regex('^SENDTOALL'),
                self.admin_sendtoall)
        self.dispatcher.add_handler(admin_sendtoall_handler)

        mainmenu_handler = MessageHandler(Filters.regex('^main menu$'),
                self.start)
        self.dispatcher.add_handler(mainmenu_handler)

        openconnect_handler = MessageHandler(Filters.regex('^openconnect$'),
                self.openconnect)
        self.dispatcher.add_handler(openconnect_handler)

        mtproto_handler = MessageHandler(Filters.regex('^mtproto$'),
                self.mtproto)
        self.dispatcher.add_handler(mtproto_handler)

        openconnect_show_data_handler = \
            MessageHandler(Filters.regex('^show openconnect data$'),
                    self.openconnect_show_data)
        self.dispatcher.add_handler(openconnect_show_data_handler)

        openconnect_add_data_handler = \
            MessageHandler(Filters.regex('^add openconnect data$'),
                    self.openconnect_add_data)
        self.dispatcher.add_handler(openconnect_add_data_handler)

        user_input_handler = MessageHandler(Filters.regex('.*'),
                self.user_input)
        self.dispatcher.add_handler(user_input_handler)


    def run(self):
        self.add_handlers()
        self.updater.start_polling()
