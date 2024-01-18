import json
from flask import Flask, abort, get_template_attribute, jsonify, render_template, request, session, stream_with_context
from database import dbWrapper
import secret
from utils import Utils
import constants
import sys
import os
if sys.platform == 'win32':
	sys.path.append(os.path.join(os.path.expanduser('~'), 'Documents/Python'))
from AnimeManager import Manager, AnimeList

routes = []
def route(*args, **kwargs):
	def wrapper(func):
		routes.append((func, args, kwargs))
		return func
	return wrapper

class App(Flask, Utils):
	def __init__(self, name=None):
		super().__init__(name or __name__)
		self.secret_key = secret.SECRET_KEY

		self.userDb = dbWrapper()
		self.main = Manager(remote=True)
		
		self.db = self.main.getDatabase()

		for sub in dir(Utils):
			if sub[:1] != '__':
				func = eval(f'self.{sub}')
				if callable(func):
					self.jinja_env.filters[sub] = func
     
		for func, args, kwargs in routes:
			f = eval(f'self.{func.__name__}')
			self.route(*args, **kwargs)(f)

		self.context_processor(self.handle_context)

	# @app.context_processor
	def handle_context(self):
		data = {k: eval(f'constants.{k}') for k in dir(constants) if k not in constants.__builtins__.keys() and k[:2] != '__'}
		return data

	@route('/')
	def index(self):
		page = request.values.get('page', None)
		tag = request.values.get('tag', None)

		if page is None:
			page = 0
		else:
			page = int(page)-1

		if 'user_id' in session:
			# Logged in
			pass

		if tag is None:
			animelist, nextList = self.main.getAnimelist("DEFAULT", listrange=(0, 50))
		else:
			animelist, nextList = self.main.getAnimelist(tag, listrange=(0, 50))

		animelist = list(animelist)

		count = len(animelist)
		return render_template('index.jinja', animes=animelist, count=count, page=page)

	@route('/anime_info/<id>') # add a parameter 'id'
	def anime_info(self, id):
		tags = ("SEEN", "WATCHING", "WATCHLIST", "NONE")
		
		anime = self.db.get(id, 'anime')
		return render_template('anime_info.jinja', anime=anime, tags=tags)

	@route('/anime_info/updateTag', methods=["POST"])
	def updateTag(self):
		id = request.values.get('id', None)
		tag = request.form.get('tag', None)
		if not id or not tag:
			abort(400)
		
		id = int(id)
		
		# TODO
		ok = True
		
		if ok:
			return '', 200
		else:
			return '', 500

	@route('/auth/login', methods=["POST"])
	def login(self):
		email = request.form.get('email', None)
		password = request.form.get('password', None)
		if not email or not password:
			abort(400)
		
		target = request.form.get('target', None)
		if target is None: 
			target = request.referrer
		
		id = self.userDb.LoginUser(email, password)
			
		if id:
			user = self.userDb.GetUser(id)
			session['user_id'] = user['id']
			return jsonify(user), 200
		else:
			if id is None:
				# Not found
				return 'BAD - No account found'
			else:
				return 'BAD - Wrong password'
		
	@route('/auth/register', methods=["POST"])
	def register(self):
		email = request.form.get('email', None)
		password = request.form.get('password', None)
		username = request.form.get('username', None)
		if not email or not password or not username:
			abort(400)

		if len(password) < 8: # TODO - Stronger password and email regex
			return 'Password is too short!', 400
		
		out = self.userDb.RegisterUser(username, email, password)
		if out is True:
			return 'OK', 200
		else:
			return 'Account already exists!', 400

	@route('/search', methods=["POST"])
	def search(self):
		terms = request.values.get('terms', None)
		force_api = request.values.get('force_api', None)
		
		if force_api is None:
			force_api = False
		
		if not terms or len(terms) < 2:
			animelist, nextList = self.main.getAnimelist("DEFAULT", listrange=(0, 50))
		else:
			try:
				if not force_api:
					animelist = self.main.searchDb(terms)

				if force_api or animelist is False:
					self.main.stopSearch = False
					animelist = self.main.api.searchAnime(terms, limit=self.main.animePerPage)
			except Exception as e:
				print('ERROOOOOR', e)
				pass
		
		render = get_template_attribute('anime_list.jinja', 'render_animelist')

		return render(animelist=animelist, count=1, page=1)

	def stream_template(template_name, **context):
		app.update_template_context(context)
		t = app.jinja_env.get_template(template_name)
		rv = t.stream(context)
		# rv.enable_buffering(5)
		return rv

	def stream_itemlist(data):
		def generator():
			yield '['
			start = True
			for i in data:
				if not start:
					yield ', '
				else:
					start = False

				yield json.dumps(i)
			yield ']'
		return app.response_class(generator(), mimetype='application/json')

app = App()
if __name__ == '__main__':
    app.run(debug=True)
	# while True:
	# 	try:
	# 		app.run(debug=True)
	# 	except SystemExit:
	# 		print('SystemExit')