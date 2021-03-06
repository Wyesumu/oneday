# coding: utf-8
import flask
from functools import wraps
#sqlalchemy
from flask_sqlalchemy import SQLAlchemy
#custom config
import config
#datetime
from datetime import datetime as dt
from datetime import date, timedelta
#crypt for user's password
from flask_bcrypt import Bcrypt
#os for file processing
import os
#image processings
from PIL import Image as ProcessImage
from PIL import ImageFont, ImageFilter, ImageDraw
from resize_and_crop import resize_and_crop
from random import randrange
#https connection
from OpenSSL import SSL
#flask_admin
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView

app = flask.Flask(__name__)

bcrypt = Bcrypt(app)
app.secret_key = config.secret_key

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + config.db_file
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['THUMBNAIL_FOLDER'] = config.THUMBNAIL_FOLDER
app.config['RESIZE_FOLDER'] = config.RESIZE_FOLDER
#app.config['SQLALCHEMY_ECHO'] = True
db = SQLAlchemy(app)

#------------------------<databases classes>------------------------------

class emptyUser():

	id = 0
	username = None
	password = None
	privileges = 3
	last_post = None

class User(db.Model):

	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	username = db.Column(db.String())
	Email = db.Column(db.String())
	about = db.Column('FullName', db.String())
	password = db.Column(db.String())
	privileges = db.Column(db.Integer, db.ForeignKey("privilege.id"), nullable=False, default = 3)
	images = db.relationship('Image', backref='users', lazy=True, order_by="Image.id")
	last_post = db.Column(db.DateTime)
	winner_of = db.relationship('Stage', backref='user_won', lazy=True)
	profile_pic = db.Column(db.String(), default="default_pic.png")

	def __repr__(self):
		return self.username

class Image(db.Model):

	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	addr = db.Column(db.String())
	user = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
	username = db.relationship("User", back_populates="images")
	name = db.Column(db.String())
	note = db.Column(db.String())
	date = db.Column(db.DateTime, nullable=False)
	extras = db.relationship('Extra', backref='images', lazy=True)
	stage = db.Column(db.Integer, db.ForeignKey("stage.id"), nullable=False)

class Extra(db.Model):

	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	image = db.Column(db.Integer, db.ForeignKey("image.id"), nullable=False)
	addr = db.Column(db.String())

class Stage(db.Model):

	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	start_date = db.Column(db.DateTime, nullable=False)
	end_date = db.Column(db.DateTime)
	user_win = db.Column(db.Integer, db.ForeignKey("user.id"))
	user = db.relationship("User", backref="stage_user")
	images = db.relationship('Image', backref='stages', lazy=True)

	def __repr__(self):
		return "Этап № {}".format(self.id)

class Privilege(db.Model):

	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	name = db.Column(db.String())
	users = db.relationship("User", backref="tags")

	def __repr__(self):
		return self.name

db.create_all()

#------------------/database classes/---------------------------

#-------------------<tool functions>---------------------------

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

def getLastDate(user_id = None, stage_id = Stage.query.all()[-1].id):
	#this function finds date of the most recent post
	#get dates of all images by username
	if not user_id:
		user_id = flask.session['user_id']

	images = Image.query.filter(Image.user == user_id, Image.stage == stage_id).all()
	datetime_list = []
	try:
		for image in images:
			#put all dates in list
			datetime_list.append(image.date)
		date = (max(datetime_list)) #and find the most recent one
	except ValueError: #except if there's no any works in db (in case of new user)
		date = Stage.query.all()[-1].start_date #and if so return date {today - 1 day} so new user will have two days to upload first post
		#dt.now() - timedelta(days=1) 
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

def getUser():
	if 'logged' in flask.session:
		return User.query.get(flask.session['user_id'])
	else:
		return emptyUser()

#is user allowed to access this page
def user_allowed(level):
	if getUser().privileges <= level:
		return True
	else:
		return False

#------------------/tool functions/---------------------------

#------------------<flask_admin>--------------------------------

#restict access to /admin index
class MyAdminIndexView(AdminIndexView):

	def is_visible(self):
		return False

	def is_accessible(self):
		return user_allowed(1)

#list of users in admin
class UserView(ModelView):

	column_exclude_list = ['password','stage_user']
	form_excluded_columns = ['password','stage_user']

	#restict access to user list
	def is_accessible(self):
		return user_allowed(1)

class ImageView(ModelView):

	column_exclude_list = ['username',]
	form_excluded_columns = ['username',]

	column_display_pk = True

	#column_sortable_list = ('id')

	column_labels = {'addr':"Имя файла", 
					"name":"Название", 
					"note":"Примечание", 
					"date":"Дата",
					"extras":"Доп. изображения",
					"users":"Автор",
					"stages":"Этап"}

	def is_accessible(self):
		return user_allowed(1)

class StageView(ModelView):

	column_display_pk = True
	column_exclude_list = ['username','user']
	form_excluded_columns = ['username','user']

	#column_sortable_list = ('id')

	column_labels = {'id':"Номер", 
					"start_date":"Время начала", 
					"end_date":"Время завершения", 
					"images":"Изображения",
					"user_won":"Победитель"
					}

	def is_accessible(self):
		return user_allowed(1)

#initialize admin views
admin = Admin(app, name='1day1page', template_mode='bootstrap3', index_view=MyAdminIndexView(), url='/')
admin.add_view(UserView(User, db.session, 'Пользователи', url='/admin/user'))
admin.add_view(ImageView(Image, db.session, 'Изображения', url='/admin/image'))
admin.add_view(StageView(Stage, db.session, 'Этапы', url='/admin/stage'))

#---------------------/flask_admin/---------------------

#-----------------<paths for static files>-------------------

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

#------------------/paths for static files/------------------

#--------------------<session control>----------------------

@app.route("/login", methods=['GET', 'POST'])
def login():
	if flask.request.method == 'POST':
		#get data from form
		login = flask.request.form["login"] 
		password = flask.request.form["password"]
		user_data = User.query.filter_by(username = login).first()
		if user_data is not None:
			if bcrypt.check_password_hash(user_data.password, str(password)): #compare user input and password hash from db
				#set session info in crypted session cookie
				flask.session['logged'] = "yes"
				flask.session['user_id'] = user_data.id
				flask.session['last_post'] = getLastDate().strftime("%Y-%m-%d %H:%M")
				return flask.redirect(flask.url_for("index"))
			else:
				flask.flash("Wrong password. Try again")
		else:
			flask.flash("Wrong Login. Try again")
	return flask.render_template("login.html")

@app.route("/register", methods=['GET', 'POST'])
def register():
	if flask.request.method == 'POST':
		f = flask.request.form.to_dict(flat=False) #get data from form
	
		if [''] in f.values(): #if there's any empty field
			flask.flash("Не все поля заполнены")
			return flask.redirect(flask.url_for("register"))
		elif f['password'][0] != f['password_check'][0]: #if passwords doesn't match
			flask.flash("Пароли не совпадают")
			return flask.redirect(flask.url_for("register"))
		elif f['pass_phrase'][0] != config.pass_phrase: #if passphrase is wrong
			flask.flash('Неверно введена кодовая фраза')
			return flask.redirect(flask.url_for("register"))
		else:
			#check if username already in db
			if User.query.filter_by(username = f["login"][0]).first():
				flask.flash("Пользователь с таким именем уже существует")
				return flask.redirect(flask.url_for("register"))
			else:
				#create new user
				new_user = User(username = f["login"][0], last_post = dt.now(), password = bcrypt.generate_password_hash(str(f["password"][0])))
				db.session.add(new_user)
				db.session.commit()

		return flask.redirect(flask.url_for("login"))
	else:
		return flask.render_template("register.html")

@app.route("/exit", methods=["GET"])
def exit():
	flask.session.clear() #clear session when user log out
	return flask.redirect(flask.url_for("login"))

#---------------------/session control/--------------------------

@app.route("/")
def index():
	#get posts from db for gallery
	stage_id = flask.request.args.get("stage")
	page = flask.request.args.get('page', type=int, default=1)
	stages = Stage.query.all()
	if stage_id:
		data = Image.query.filter_by(stage = stage_id).order_by(Image.id.desc()).paginate(page, 30, False)
		if stages[int(stage_id)-1].user_win:
			User.survived = getLastDate(user_id = stages[int(stage_id)-1].user_win, stage_id=stage_id) - stages[int(stage_id)-1].start_date
	else:
		data = Image.query.filter_by(stage = stages[-1].id).order_by(Image.id.desc()).paginate(page, 30, False)
		if stages[-1].user_win:
			User.survived = getLastDate(user_id = stages[-1].user_win) - stages[-1].start_date

	return flask.render_template("index.html", stages=stages, data=data, user=getUser(), time_left=time_left())


@app.route('/user/<username>', methods=["GET","POST"]) #one artist only gallery
def user_gallery(username):
	if flask.request.method == 'GET':
		#data = Image.query.order_by(Image.id.desc()).filter(Image.stage == Stage.query.all()[-1].id, Image.user == User.query.filter_by(username=username).first().id)
		data = User.query.filter_by(username=username).first()
		User.survived = getLastDate(user_id = data.id) - Stage.query.all()[-1].start_date
		return flask.render_template("profile.html", data=data, user=getUser())
	else:
		user = getUser()

		files = flask.request.files.getlist("file")
		if files[0] and allowed_file(files):
			filename = "profile_" + str(randrange(10000,100000)) + '.' + files[0].filename.rsplit('.', 1)[1].lower()
			try:
				image = resize_and_crop(files[0], (256,256), "middle")
				image.save(os.path.join(config.THUMBNAIL_FOLDER, filename))
			except Exception as e:
				flask.flash(e)

			if user.profile_pic != 'default_pic.png':
				try:
					os.remove(config.THUMBNAIL_FOLDER +'/'+ user.profile_pic)
				except Exception as e:
					flask.flash(e)

			user.profile_pic = filename
			flask.flash("Загружено")

			user.username = flask.request.form['name']
			user.about = flask.request.form['about']
			db.session.commit()
		else:
			flask.flash("Не удалось загрузить изображение: неподходящий тип")

		return flask.redirect(flask.url_for("stats"))


@app.route("/upload", methods=["GET","POST"])
@is_logged
def upload():
#
# This function is just a mess. I'm so sorry :-:
#
	data = getUser() #get last post date

	delta = dt.now() - data.last_post # and calculate how many time left since this date
	delta_last_post = (delta.days * 24) + (delta.seconds // 3600)
	delta = dt.now() - Stage.query.all()[-1].start_date
	delta_stage_start = (delta.days * 24) + (delta.seconds // 3600)

	if delta_last_post < 80 or delta_stage_start < 80:
		not_allowed = False
	else:
		not_allowed = True

	if data.privileges <= 2:
		not_allowed = False

	# if amout of hours less than 80 and level of privileges < 4 (new user get 3. 4 means admin blocked access for user manually)
	if not_allowed or data.privileges == 4: 
		flask.flash("Вы не создавали записи более 3 дней. Доступ закрыт")
		return flask.redirect(flask.url_for("index"))
	else:
		if flask.request.method == 'GET':
			return flask.render_template("upload.html", user=data)
		else:
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
					with ProcessImage.open(os.path.join(config.UPLOAD_FOLDER, filename[-1])) as image:
						image.thumbnail((700, 560), ProcessImage.ANTIALIAS)
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

				new_image = Image(addr=filename[0], user=flask.session['user_id'], name=name, note=flask.request.form['note'],date=dt.strptime(str(time_input), "%Y-%m-%d %H:%M"), stage=Stage.query.all()[-1].id)
				db.session.add(new_image)
				db.session.flush()
				for i in range(1,len(files)):
					new_extra = Extra(image=new_image.id, addr=filename[i])
					db.session.add(new_extra)
				update_user = User.query.get(flask.session['user_id'])
				update_user.last_post = dt.strptime(str(LastPostDate), "%Y-%m-%d %H:%M")
				db.session.commit()
				flask.session['last_post'] = LastPostDate #and also update cookies

				return flask.redirect(flask.url_for("index")) #redirect user to index
			else:
				flask.flash("Invalid file type")
				return flask.redirect(flask.url_for("index"))
			

@app.route('/refresh_time') #refresh time in times on index
def get_left_time():
	last_date = getLastDate().strftime("%Y-%m-%d %H:%M")
	flask.session["last_post"] = last_date
	return flask.redirect(flask.url_for("index"))

@app.route('/stats', methods=["GET", "POST"])
def stats():
	if flask.request.method == "POST":
		r = flask.request.form.to_dict() #get all fields in dict
		if "reset" in r: #if admin pushed reset button to give access to user back
			user = User.query.get(r["reset"])
			user.last_post = dt.now()
			if user.privileges == 4:
				user.privileges = 3
			flask.flash("Доступ пользователю " + user.username + " восстановлен")
			db.session.commit()
			return flask.redirect(flask.url_for("stats"))
		if "block" in r: #if admin want to block access
			user = User.query.get(r["block"])
			user.privileges = 4
			flask.flash("Доступ пользователю " + user.username + " заблокирован")
			db.session.commit()
			return flask.redirect(flask.url_for("stats"))
	else: #GET request
		users = User.query.all()
		return flask.render_template("stats.html", user=getUser(), users = users)

@app.route('/image/<int:image_id>', methods=["GET","POST"]) #this is what inside the post
def full_image(image_id):
	if flask.request.method == 'POST': #delete image
		try:

			extra = Extra.query.filter_by(image=image_id).all()
			for el in extra: #and delete extra images
				db.session.delete(el)
				os.remove(config.UPLOAD_FOLDER +'/'+ el.addr)
				os.remove(config.RESIZE_FOLDER +'/'+ el.addr)

			image = Image.query.get(image_id)
			db.session.delete(image)

			os.remove(config.UPLOAD_FOLDER +'/'+ image.addr) #delete all forms of image
			os.remove(config.RESIZE_FOLDER +'/'+ image.addr)
			os.remove(config.THUMBNAIL_FOLDER +'/'+ image.addr)
		except FileNotFoundError:
			flask.flash("Ошибка: Файл не найден")
		finally:
			last_date = getLastDate()

			user = User.query.get(image.user)
			user.last_post = last_date
			db.session.commit()

			flask.session["last_post"] = last_date.strftime("%Y-%m-%d %H:%M") #update date in cookies too

			flask.flash("Файл " + image.addr + " успешно удален")
		return flask.redirect(flask.url_for("index"))

	#if we just want to show bigger image
	else: #if GET request return images
		image = Image.query.get(image_id)
		return flask.render_template("image.html", user=getUser(), image=image)


@app.route('/cal') #page with calendar
def calendar():
	return flask.render_template("cal.html", user = getUser())

@app.route('/data') #send JSON events to calendar
def return_data():
	#start_date = flask.request.args.get('start', '')
	#end_date = flask.request.args.get('end', '')
	json = []
	images = Image.query.all()
	for data in images:
		json.append({"id":str(data.id),"title":str(data.name) + ", " + str(data.username),"url":"/image/"+str(data.id),"start":str(data.date).replace(" ","T")})
	return flask.jsonify(json)


#run only if started standalone, not imported
if __name__ == "__main__":
	app.run(host=config.host, port=config.port, ssl_context='adhoc')
