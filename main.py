import telebot
import logging
import requests
import json
import re
import ast
import sqlite3
import random
from lxml import etree

config = etree.parse('config.xml').getroot()
tgkey = config[0].text
auddkey = config[1].text

bot = telebot.TeleBot(tgkey)
logger = logging.getLogger()


@bot.message_handler(func=lambda message: message.text == 'Моё избранное')
def handle_text(message):
	favorites = getFavorites(message.from_user.id)
	bot.send_message(message.chat.id, favorites)


def connectToDB():
	try:
		conn = sqlite3.connect("mydatabase.db")
		cursor = conn.cursor()
		return {'cursor': cursor, 'conn': conn}
	except Exception as e:
		return e


@bot.message_handler(commands=['start', 'help'])
def sendWelcome(message):
	markup = telebot.types.ReplyKeyboardMarkup(row_width=1)
	markup.add(telebot.types.InlineKeyboardButton("Моё избранное"))
	bot.send_message(message.chat.id, 'Привет!\nЯ бот, который слушает твои голосовухи и говорит что на них играет. \nЗапиши голосовуху и жди результат.', reply_markup=markup)


@bot.message_handler(content_types='text')
def sendDefaultInfo(message):
	try:
		markup = telebot.types.ReplyKeyboardMarkup(row_width=1)
		markup.add(telebot.types.InlineKeyboardButton("Моё избранное"))
		bot.send_message(message.chat.id, 'Отправь мне голосовое сообщение и я отправлю музыку которая играет рядом с тобой ' + u"\U0001F609", reply_markup=markup)
	except Exception as e:
		bot.send_message(message.chat.id, u"\u26A0" + 'Что-то пошло не так: ' + str(e))


def randomEmoji():
	emojis = [
		u"\U0001F60B",
		u"\U0001F60B",
		u"\U0001F61C",
		u"\U0001F638",
		u"\U0001F64B",
		u"\U0001F60E",
		u"\U0001F619",
		u"\U0001F44C",
		u"\U0001F44D",
		u"\U0001F44F",
		u"\U0001F3C6",
		u"\U0001F389",
		u"\u2728",
		u"\u270C",
		u"\u263A",
		u"\U0001F3B9",
		u"\U0001F3AF",
		u"\U0001F3A7",
		u"\U0001F46F",
		u"\U0001F4A5",
		u"\U0001F4E3",
		u"\U0001F4FB",
		u"\U0001F50A",
		u"\U0001F525"
	]
	num = random.randint(0, len(emojis))
	return emojis[num]


def shazamity(file):
	data = {
		'url': file,
		'return': 'apple_music,spotify',
		'api_token': auddkey
	}
	result = requests.post('https://api.audd.io/', data=data)
	parsed_string = json.loads(result.text)
	return parsed_string


def getTrackInfo(file):
	parsed_string = shazamity(file)
	result_dict = parsed_string["result"]
	result_string = result_dict["artist"], result_dict["title"]
	result_pic = result_dict.get("apple_music", {}).get("artwork", {}).get('url')
	if not result_pic:
		result_pic = result_dict.get("spotify", {}).get("artwork", {}).get('url')
	if not result_pic:
		result_pic = 'http://www.mayline.com/products/images/product/noimage.jpg'

	am_link = result_dict["apple_music"]["url"]
	sp_link = result_dict["spotify"]["external_urls"]["spotify"]

	return {
		'apple_link': am_link,
		'spotify_link': sp_link,
		'track': result_string,
		'pic': result_pic
	}


def sendInfo(track_info, message):
	track_link = '<a href ="{0}">{1}</a>'
	am_str = track_link.format(track_info['apple_link'], "Apple Music") if track_info['apple_link'] else None
	sp_str = track_link.format(track_info['spotify_link'], "Spotify") if track_info['spotify_link'] else None

	divider = " | " if am_str and sp_str else ''

	result_str = "Трек распознан! {0} \nЭто {1} \n{2}{3}{4}".format(randomEmoji(), ' - '.join(track_info['track']), am_str, divider, sp_str)
	bot.send_photo(message.chat.id, track_info['pic'].format(w='1000', h='1000'), result_str, parse_mode='HTML')


def getMusicLink(query):
	url = 'https://gdespaces.com/musicat/search/index/'
	r = requests.get(url, params={'sq': query})
	content = str(r.content)
	sound_link = re.findall(r'href="([^\'\"]+.mp3)', content)
	if len(sound_link) > 0:
		return sound_link[0]
	else:
		return None


def sendAudio(name, message):
	msg = bot.send_message(message.chat.id, 'Ищем трек...')
	bot.send_chat_action(message.chat.id, 'upload_audio')
	name = ' - '.join(name)
	audio_link = getMusicLink(name)
	track_id = addTrackToDatabase(message.from_user.id, name)
	if audio_link is not None:
		markup = telebot.types.InlineKeyboardMarkup(row_width=1)
		button = telebot.types.InlineKeyboardButton(text='Добавить в избранное', callback_data='["add","{0}","{1}"]'.format(message.from_user.id, track_id))
		markup.add(button)
		bot.send_audio(message.chat.id, audio_link, 'Можешь послушать этот трек', reply_markup=markup)
		bot.delete_message(message.chat.id, msg.message_id)
	else:
		bot.delete_message(message.chat.id, msg.message_id)
		bot.send_message(message.chat.id, 'Послушать этот трек не получится, мы не смогли его найти ' + u'\U0001F605')


@bot.message_handler(content_types='voice')
def sendMusicInfo(message):
	try:
		file_info = bot.get_file(message.voice.file_id)
		file = 'https://api.telegram.org/file/bot{0}/{1}'.format(bot.token, file_info.file_path)
		msg = bot.send_message(message.chat.id, 'Распознаю...')
		bot.send_chat_action(message.chat.id, 'upload_photo')
		parsed_string = shazamity(file)
		bot.delete_message(message.chat.id, msg.message_id)
		if parsed_string["status"] == "success" and parsed_string["result"] is not None:
			track_info = getTrackInfo(file)
			sendInfo(track_info, message)
			sendAudio(track_info['track'], message)
		else:
			bot.send_message(message.chat.id, "Трек не распознан {0} \nПопробуй поднести микрофон ближе к источнику музыки и убедись что рядом нет толпы орущих школьников".format(u'\U0001F616'))
	except Exception as e:
		bot.send_message(message.chat.id, u"\u26A0" + 'Что-то пошло не так: ' + str(e))


def addTrackToDatabase(userid, track_name):
	try:
		db = connectToDB()

		sql = db['cursor'].execute("""SELECT * FROM tracks WHERE user='{0}' AND name='{1}'""".format(userid, track_name))
		count = sql.fetchone()

		if not count:
			db['cursor'].execute("""INSERT INTO tracks (user, name) VALUES ('{0}', '{1}')""".format(userid, track_name))
			db['conn'].commit()
			return db['cursor'].lastrowid
		else:
			track_id = count[0]
			return track_id
	except Exception as e:
		print(e)
		return e


def addTrackToFavorites(userid, trackid):
	try:
		db = connectToDB()

		sql = db['cursor'].execute("""SELECT * FROM users WHERE user_id='{0}' AND track_id='{1}'""".format(userid, trackid))
		count = sql.fetchone()

		if count:
			return "Трек уже у тебя в избранном"
		else:
			db['cursor'].execute("""INSERT INTO users (user_id, track_id) VALUES ('{0}', '{1}')""".format(userid, trackid))
			db['conn'].commit()
			return "Трек добавлен в избранные!"
	except Exception as e:
		print(e)
		return e


def getFavorites(userid: int or None) -> str or Exception:
	try:
		db = connectToDB()

		getfavids = db['cursor'].execute("""SELECT track_id FROM users WHERE user_id='{0}'""".format(userid))
		resultids = getfavids.fetchall()

		if not resultids:
			return "У тебя нет треков в избранном\nСамое время это исправить " + u"\U0001F609"
		ids = []
		for res in resultids:
			ids.append(str(res[0]))
		favids = ', '.join(ids)

		getfavnames = db['cursor'].execute("""SELECT name FROM tracks WHERE id in ({0})""".format(favids))
		resultnames = getfavnames.fetchall()
		favnames = []
		for i in resultnames:
			favnames.append(i[0])

		resultstr = u"\U0001F4FB" + 'Твои избранные треки:\n'
		for i in favnames:
			resultstr = resultstr + i + '\n'

		return resultstr

	except Exception as e:
		return e


@bot.callback_query_handler(func=lambda call: True)
def query_handler(call):

	callback = ast.literal_eval(call.data)
	if callback[0] == "add":
		result = addTrackToFavorites(callback[1], callback[2])
		bot.answer_callback_query(callback_query_id=call.id, text=result)
		bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id)


bot.polling(none_stop=True)
