# coding: utf-8
import flask
from functools import wraps

import sqlite3

import config

#datetime
from datetime import datetime as dt
from datetime import date, timedelta
#crypt for user's password
from flask_bcrypt import Bcrypt
#os for file processing
import os
#image processings
from PIL import Image, ImageFont, ImageFilter, ImageDraw
from resize_and_crop import resize_and_crop
from random import randrange
#https connection
#from OpenSSL import SSL

app = flask.Flask(__name__)
bcrypt = Bcrypt(app)
app.secret_key = config.secret_key

#tool functions

def connection(): #connection to sqlite3 database
	try:
		conn = sqlite3.connect(config.db_file)
		return conn
	except sqlite3.Error as e:
		print(e)
	return None

#decorator to check if user logged in
def is_logged(func):
	@wraps(func)
	def wrapper(*args, **kwargs):
		if 'logged' in flask.session:
			return func(*args, **kwargs)
		else:
			flask.flash("Необходимо войти или зарегистрироваться, чтобы просматривать данный раздел")
			return flask.redirect(flask.url_for("index"))
	return wrapper

def allowed_file(files): #check if file extension is allowed
	for file in files:
		if file.filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS:
			allowed = True
		else:
			allowed = False
	return allowed

def getLastDate():
	#this function finds date of the most recent post
	conn=connection()
	with conn:
		cur = conn.cursor()
		#get dates of all images by username
		dates = cur.execute("SELECT Date FROM Images WHERE Creator = ?", (flask.session['username'],)).fetchall()
	datetime_list = []
	try:
		for date in dates:
			#put all dates in list
			datetime_list.append(dt.strptime(str(date[0]), "%Y-%m-%d %H:%M"))
		date = (max(datetime_list)) #and find the most recent one
	except ValueError: #except if there's no any works in db (in case of new user)
		date = dt.now() - timedelta(days=1) #and if so return date {today - 1 day} so new user will have two days to upload first post
	return date

def time_left(): #calculate how many time left until block
	try:
		delta = dt.now() - dt.strptime(str(flask.session["last_post"]), "%Y-%m-%d %H:%M")
		left = 80 - ((delta.days * 24) + (delta.seconds // 3600))
		if left > 0:
			return ("Hours left: " + str(left))
		else:
			return "Time is over"
	except Exception as e:
		print(e)

def getUsername():
	if 'username' in flask.session:
		return flask.session['username']
	else:
		return None

#/tool functions/

#paths for static files

@app.route('/fonts/<path:path>')
def send_fonts(path):
	return flask.send_from_directory('fonts', path)

@app.route('/resize/<path:path>')
def send_resize(path):
	return flask.send_from_directory('resize', path)

@app.route('/images/<path:path>')
def send_images(path):
	return flask.send_from_directory('images', path)

@app.route('/thumbnails/<path:path>')
def send_thumbain(path):
	return flask.send_from_directory('thumbnails', path)

#/paths for static files/

#session control

@app.route("/login", methods=['GET', 'POST'])
def login():
	if flask.request.method == 'POST':
		#get data from form
		login = flask.request.form["login"]
		password = flask.request.form["password"]
		conn = connection()
		with conn:
			cur = conn.cursor()
			try:
				#check if user in db
				user_data = cur.execute("SELECT Password, Priveleges, FullName, LastPostDate FROM Users WHERE Username = ?", (login,)).fetchone()
				if bcrypt.check_password_hash(user_data[0], str(password)): #compare user input and password hash from db
					#set session info in crypted session cookie
					flask.session['logged'] = "yes"
					flask.session['username'] = login
					flask.session['priveleges'] = user_data[1]
					flask.session['full_name'] = user_data[2]
					flask.session['last_post'] = user_data[3]
					return flask.redirect(flask.url_for("index"))
				else:
					flask.flash("Wrong password. Try again")
			except TypeError as e:
				flask.flash("Wrong Login. Try again")
	return flask.render_template("login.html")

@app.route("/register", methods=['GET', 'POST'])
def register():
	if flask.request.method == 'POST':
		f = flask.request.form.to_dict(flat=False) #get data from form
	
		if [''] in f.values(): #if there's any empty field
			flask.flash("Не все поля заполнены")
		elif f['password'][0] != f['password_check'][0]: #if passwords doesn't match
			flask.flash("Пароли не совпадают")
		elif f['pass_phrase'][0] != config.pass_phrase: #if passphrase is wrong
			flask.flash('Неверно введена кодовая фраза')
		else:
			conn = connection()
			with conn:
				cur = conn.cursor()
				#check if username already in db
				if cur.execute("SELECT Username FROM Users WHERE Username = ?", (f["login"][0],)).fetchone():
					flask.flash("Пользователь с таким именем уже существует")
					return flask.redirect(flask.url_for("login"))
				else:
					#create new user
					cur.execute("INSERT INTO Users(Username, Password, LastPostDate) VALUES(?,?,?)", (f["login"][0],bcrypt.generate_password_hash(str(f["password"][0])), dt.now().strftime("%Y-%m-%d %H:%M"),))
					conn.commit()
					return flask.redirect(flask.url_for("login"))
		return flask.redirect(flask.url_for("register"))
	else:
		return flask.render_template("register.html")

@app.route("/exit", methods=["POST"])
def exit():
	exit = flask.request.form['exit']
	if exit:
		flask.session.clear() #clear session when user log out
		return flask.redirect(flask.url_for("login"))

#/session control/

@app.route("/")
def index():
	conn = connection()
	with conn:
		cur = conn.cursor()
		#get last 60 posts from db for gallery
		images = cur.execute("SELECT ID, Addr, Creator, Name, Date FROM Images ORDER BY ID DESC LIMIT 60").fetchall()
	return flask.render_template("index.html", images=images, username=getUsername(), time_left = time_left())

@app.route("/upload", methods=["GET","POST"])
@is_logged
def upload():
#
# Thus function is just a mess. I'm so sorry :-:
#
	conn=connection()
	with conn:
		cur = conn.cursor() #get date of user's last post
		d1 = cur.execute("SELECT LastPostDate, Priveleges FROM Users WHERE Username = ?",(flask.session['username'],)).fetchone()

	delta = dt.now() - dt.strptime(str(d1[0]), "%Y-%m-%d %H:%M") # and calculate how many time left since this date
	if (delta.days * 24) + (delta.seconds // 3600) < 80 and d1[1] < 4: # if amout of hours less than 80 and level of privileges < 6 (new user get 5. 6 means admin blocked access for user manually)
		if flask.request.method == 'POST':
			# check if the post request has the file part
			if 'file' not in flask.request.files:
				flask.flash('Ошибка, файл не найден. Обратитесь к администратору')
				return flask.redirect(flask.request.url)
			files = flask.request.files.getlist("file") #get names of uploaded files

			if files[0].filename == '': # if filename is empty
				flask.flash('Необходимо выбрать файл')
				return flask.redirect(flask.request.url)

			if allowed_file(files): # if file extension is allowed
				filename = []
				for file in files: #save every file in Image folder (which contains original of uploaded images)
					#create random file name from numbers in range of 10 000 and 100 000 and add original file extension to it
					filename.append(str(randrange(10000,100000)) +'.'+ file.filename.rsplit('.', 1)[1].lower()) #file.filename
					file.save(os.path.join(config.UPLOAD_FOLDER, filename[-1])) #save this file

					#load saved file and resize it to 700x500 (it will be used inside post)
					with Image.open(os.path.join(config.UPLOAD_FOLDER, filename[-1])) as image:
						image.thumbnail((700, 560), Image.ANTIALIAS)
						image.save(os.path.join(config.RESIZE_FOLDER, filename[-1])) #and save it

				#again open original file and resize_and_crop middle of it so we can create a thumbnail
				image = resize_and_crop(os.path.join(config.UPLOAD_FOLDER, filename[0]), (256,256), "middle")
				if 'censor' in flask.request.form.to_dict(): #if NSFW box was checked
					image = image.filter(ImageFilter.BoxBlur(6)) #blur the image
					# and add censored tag on it in 100x and 128y coordinates
					textX = 100
					textY = 128
					text = 'Censored'
					font = ImageFont.truetype("./fonts/sans-serif.ttf", 16) #load font
					# draw this word four times to create white (0,0,0) border on the black text
					ImageDraw.Draw(image).text((textX-0.5, textY-0.5), text,(0,0,0),font=font)
					ImageDraw.Draw(image).text((textX+0.5, textY-0.5), text,(0,0,0),font=font)
					ImageDraw.Draw(image).text((textX+0.5, textY+0.5), text,(0,0,0),font=font)
					ImageDraw.Draw(image).text((textX-0.5, textY+0.5), text,(0,0,0),font=font)
					ImageDraw.Draw(image).text((textX, textY), text, fill=(255, 255, 255), font=font) #draw black text

				if filename[0].rsplit('.', 1)[1].lower() == 'gif': # do same but if file is give
					textX = 5
					textY = 5
					text = 'Animated'
					font = ImageFont.truetype("./fonts/sans-serif.ttf", 16)
					ImageDraw.Draw(image).text((textX-0.5, textY-0.5), text,(0,0,0),font=font)
					ImageDraw.Draw(image).text((textX+0.5, textY-0.5), text,(0,0,0),font=font)
					ImageDraw.Draw(image).text((textX+0.5, textY+0.5), text,(0,0,0),font=font)
					ImageDraw.Draw(image).text((textX-0.5, textY+0.5), text,(0,0,0),font=font)
					ImageDraw.Draw(image).text((textX, textY), text, fill=(255, 255, 255), font=font)

				image.save(os.path.join(config.THUMBNAIL_FOLDER, filename[0])) #save thumbnail
				flask.flash('Изображение ' + filename[0] + ' успешно загружено')

				if flask.request.form['name'] == "": #if user haven't specified the name of the post use "Untitled"
					name = 'Untitled'
				else:
					name = flask.request.form['name']

				last_date = getLastDate() #get the most recent date
				day_more = last_date + timedelta(days=1) #add 1 day to this date
				if flask.request.form['time_input'] == '': #if user didn't specified the date set recent date + 1 day
					time_input = day_more.strftime("%Y-%m-%d %H:%M")
					LastPostDate = day_more.strftime("%Y-%m-%d %H:%M")
				else: #and if specified
					if dt.strptime(flask.request.form['time_input'], "%Y-%m-%d %H:%M") > day_more: #check if there's no day gap between recent post from db and current post
						#this check was made to give user opportunity to post in dates before his first post or in dates that already have uploaded arts
						time_input = day_more.strftime("%Y-%m-%d %H:%M")
						LastPostDate = day_more.strftime("%Y-%m-%d %H:%M")
						flask.flash("Пропуск более одного дня, загружено с датой " + time_input) # if so use recent date + 1 day
					else:
						time_input = flask.request.form['time_input']
						LastPostDate = flask.request.form['time_input']

				conn=connection()
				with conn:
					cur = conn.cursor() #put new image in db
					cur.execute("INSERT INTO Images(Addr, Creator, Name, Note, Date) VALUES(?,?,?,?,?)",(filename[0], flask.session['username'], name, flask.request.form['note'], time_input,))
					image_id = cur.lastrowid
					for i in range(1,len(files)): #if there was more than one image, put other images in the different table
						cur.execute("INSERT INTO ExtraImages(Image_ID, Addr) VALUES(?,?)",(image_id, filename[i],))
					cur.execute("UPDATE Users SET LastPostDate = ? WHERE Username = ?",(LastPostDate, flask.session['username'],)) #update date of user's last post
					conn.commit()
				flask.session['last_post'] = LastPostDate #and also update cookies

				return flask.redirect(flask.url_for("index")) #redirect user to index
			else:
				flask.flash("Invalid file type")
				return flask.redirect(flask.url_for("index"))
		else:
			return flask.render_template("upload.html", username=flask.session['username'])
	else:
		flask.flash("Вы не создавали записи более 3 дней. Доступ закрыт")
		return flask.redirect(flask.url_for("index"))
		

@app.route('/refresh_time') #refresh time in times on index
def get_left_time():
	last_date = getLastDate().strftime("%Y-%m-%d %H:%M")
	conn = connection()
	with conn:
		cur = conn.cursor()
		cur.execute("SELECT LastPostDate FROM Users WHERE Username = ?",(flask.session['username'],))
		conn.commit()
	flask.session["last_post"] = last_date
	return flask.redirect(flask.url_for("index"))

@app.route('/stats', methods=["GET", "POST"])
@is_logged
def stats():
	if flask.request.method == "POST":
		r = flask.request.form.to_dict() #get all fields in dict
		if "reset" in r: #if admin pushed reset button to give access to user back
			username = flask.request.form["reset"]
			conn=connection()
			with conn:
				cur = conn.cursor() #date of of user's last post will set to today
				cur.execute("UPDATE Users SET LastPostDate = ?, Priveleges = 3 WHERE Username = ?", (dt.now().strftime("%Y-%m-%d %H:%M"),username,))
				conn.commit()
			flask.flash("Доступ пользователю " + username + " восстановлен")
			return flask.redirect(flask.url_for("stats"))
		if "block" in r: #if admin want to block access
			username = flask.request.form["block"]
			conn = connection()
			with conn:
				cur = conn.cursor() #then we set date of last post to january and set privileges to 6, so even if user will
							#log out and log in again access won't back
				cur.execute("UPDATE Users SET LastPostDate = '2019-01-01 01:01', Priveleges = 4 WHERE Username = ?", (username,))
				conn.commit()
			flask.flash("Доступ пользователю заблокирован")
			return flask.redirect(flask.url_for("stats"))
	else: #GET request
		conn=connection()
		with conn:
			cur = conn.cursor() #return list of users on GET request
			users_stats = cur.execute('''SELECT Users.Username, Users.LastPostDate,
							(SELECT COUNT(*) FROM Images WHERE Users.Username = Images.Creator) AS Counter
							FROM Users
								WHERE Users.Priveleges > 1;''').fetchall()
		return flask.render_template("stats.html", username=flask.session['username'], stats = users_stats, priveleges=flask.session['priveleges'])

@app.route('/user/<username>') #one artist only gallery
def user_gallery(username):
	conn = connection()
	with conn:
		cur = conn.cursor() #get all works by artist's name
		images = cur.execute("SELECT ID, Addr, Creator, Name, Date FROM Images WHERE Creator = ? ORDER BY ID DESC", (username,)).fetchall()
	#using index template here, just return different data
	return flask.render_template("index.html", images=images, username=getUsername())

@app.route('/image/<int:image_id>', methods=["GET","POST"]) #this is what inside the post
def full_image(image_id):
	if flask.request.method == 'POST': #delete image
		conn=connection()
		with conn:
			cur = conn.cursor() #get image filename
			addr = cur.execute("SELECT Addr FROM Images WHERE ID = ?", (image_id,)).fetchone()
			#if there are more than one images in the post, then get their filenames
			extra_addr = cur.execute("SELECT Addr FROM ExtraImages WHERE Image_ID = ?", (image_id,)).fetchall()
			cur.execute("DELETE FROM Images WHERE ID = ?", (image_id,)) #delete all images from db
			cur.execute("DELETE FROM ExtraImages WHERE Image_ID = ?", (image_id,))
			conn.commit()
		
			last_date = getLastDate().strftime("%Y-%m-%d %H:%M") #calculate new recent post date and insert into db
			cur.execute("UPDATE Users SET LastPostDate = ? WHERE Username = ?",(last_date, flask.session['username'],))
			conn.commit()
		flask.session["last_post"] = last_date #update date in cookies too
		
		try:
			os.remove(config.UPLOAD_FOLDER +'/'+ addr[0]) #delete all forms of image
			os.remove(config.RESIZE_FOLDER +'/'+ addr[0])
			os.remove(config.THUMBNAIL_FOLDER +'/'+ addr[0])
			for el in extra_addr: #and delete extra images
				os.remove(config.UPLOAD_FOLDER +'/'+ el[0])
				os.remove(config.RESIZE_FOLDER +'/'+ el[0])
		except FileNotFoundError:
			flask.flash("Ошибка: Файл не найден")
		finally:
			flask.flash("Файл " + addr[0] + " успешно удален")
		return flask.redirect(flask.url_for("index"))

	#if we just want to show bigger image
	else: #if GET request return images
		conn=connection()
		with conn:
			cur = conn.cursor()
			image = cur.execute("SELECT * FROM Images WHERE ID = ?", (image_id,)).fetchone()
			extra_image = cur.execute("SELECT Addr FROM ExtraImages WHERE Image_ID = ?", (image_id,)).fetchall()

		if 'username' in flask.session:
			username = flask.session['username']
			priveleges = flask.session['priveleges']
		else:
			username = None
			priveleges = 3
		return flask.render_template("image.html", username=username, image=image, priveleges=priveleges, extra_image=extra_image)


@app.route('/cal') #page with calendar
def calendar():
	return flask.render_template("cal.html", username = getUsername())

@app.route('/data') #send JSON events to calendar
def return_data():
	#start_date = flask.request.args.get('start', '')
	#end_date = flask.request.args.get('end', '')
	json = []
	conn=connection()
	with conn:
		cur = conn.cursor()
		images = cur.execute("SELECT ID, Creator, Name, Date FROM Images").fetchall()
	for data in images:
		json.append({"id":str(data[0]),"title":str(data[1]) + ", " + str(data[2]),"url":"/image/"+str(data[0]),"start":str(data[3]).replace(" ","T")})
	return flask.jsonify(json)


#run only if started standalone, not imported
if __name__ == "__main__":
	app.run(host=config.host, port=config.port) #, ssl_context='adhoc'
