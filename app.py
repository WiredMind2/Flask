from functools import wraps
import json
import random
import string
import subprocess
import time
from urllib.parse import urlparse
from flask import Flask, Response, abort, g, get_template_attribute, jsonify, render_template, request, session, stream_with_context
import jwt
import secret
from utils import Utils
import constants
import sys
import os
if sys.platform == 'win32':
	sys.path.append(os.path.join(os.path.expanduser('~'), 'Documents/Python'))
from AnimeManager import Manager, AnimeList, TorrentList, search_engines

routes = []


def route(*args, **kwargs):
	def wrapper(func):
		routes.append((func, args, kwargs))
		return func
	return wrapper


def require_login(func):
	@wraps(func)
	def wrapper(self, *args, **kwargs):
		connected = True
		token = request.cookies.get('Token', None)
		if not token:
			connected = False
		else:
			try:
				data = jwt.decode(token, secret.JWT_SECRET_KEY,
								  algorithms=["HS256"])
			except jwt.InvalidSignatureError:
				# Someone tried to hack me
				connected = False

		# user = data['data']
		if connected:
			return func(self, *args, **kwargs)
		else:
			# return func(self, *args, **kwargs)
			return self.disconnected()

	return wrapper


class App(Flask, Utils):
	def __init__(self, name=None):
		super().__init__(name or __name__)
		self.secret_key = secret.SECRET_KEY

		if 'global_data' not in globals():
			self.main = Manager(remote=True)

			self.db = self.main.getDatabase()

			self.search_threads = {}
			globals()['global_data'] = {
				'main': self.main,
				'db': self.db,
				'search_threads': self.search_threads
			}
		else:
			for k, v in globals()['global_data']:
				eval(f'self.{k} = {v}')

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
		data = {k: eval(f'constants.{k}') for k in dir(
			constants) if k not in constants.__builtins__.keys() and k[:2] != '__'}
		data['user'] = self.get_user()
		g.user = data['user']
		return data

	@route('/')
	def index(self):
		page = request.values.get('page', None)
		tag = request.values.get('tag', None)

		if page is None:
			page = 0
		else:
			page = int(page)-1

		# if 'user_id' in session:
		# 	# Logged in
		# 	pass

		user = self.get_user()
		if user:
			user_id = user['id']
		else:
			user_id = False

		if tag is None:
			# animelist = []
			# while len(animelist) == 0:
			animelist, nextList = self.main.getAnimelist(
				"DEFAULT", listrange=(0, 50), user_id=user_id)
			animelist = list(animelist)
		else:
			if not user_id:
				return self.disconnected()
			animelist, nextList = self.main.getAnimelist(
				tag, listrange=(0, 50), user_id=user_id)
			animelist = list(animelist)

		count = len(animelist)
		return render_template('index.jinja', animes=animelist, count=count, page=page)

	@route('/anime_info/<id>')
	def anime_info(self, id):
		user = self.get_user()
		
		origin = request.referrer
		if origin:
			parsed = urlparse(origin)
			if parsed.path != '/':
				origin = None
		else:
			origin = None

		reload = request.values.get('reload', False)
		if reload:
			# Require login
			if user:
				self.main.api.anime(id)

		anime = self.db.get(id, 'anime')
		if user:
			data = self.main.getDatabase().sql('SELECT tag, liked FROM user_tags WHERE user_id=:user_id AND anime_id=:anime_id', {'user_id': user['id'], 'anime_id': id})
			if data:
				anime.tag, anime.like = data[0]

		source = self.main.getFolder(anime=anime)
		episodes = self.main.getEpisodes(source)

		progress = self.get_torrents_progress(id)
		torrents = [{'hash': k} | v for k, v in progress.items()]

		return render_template('anime_info.jinja', anime=anime, episodes=episodes, torrents=torrents, origin=origin)

	@route('/disconnected')
	def disconnected(self):
		user = self.get_user()
		if user is not None:
			# Don't tell that they're not connected if they actually are
			return self.index()

		return render_template('disconnected.jinja')

	@route('/torrent_progress/<id>')
	@require_login
	def torrent_progress(self, id):
		progress = self.get_torrents_progress(id)
		return jsonify({'data': progress})

	def get_torrents_progress(self, id):
		torrents = self.main.getTorrentsProgress(id)
		if len(torrents) == 0:
			return {}

		torrents = list(filter(lambda t: t.downloaded and t.size, torrents))

		progress = {}
		for t in torrents:
			progress[t.hash] = {'name': t.name, 'progress': (t.downloaded*100/t.size/len(torrents))}
		return progress

	@route('/anime_info/updateTag', methods=["POST"])
	@require_login
	def updateTag(self):
		id = request.values.get('id', None)
		tag = request.form.get('tag', None)
		if not id or not tag:
			abort(400)

		user = self.get_user()

		id = int(id)
		try:
			self.main.set_tag(id, tag.upper(), user['id'])
		except Exception as e:
			ok = False
		else:
			ok = True

		if ok:
			return '', 200
		else:
			return '', 500

	@route('/search', methods=["POST"])
	def search(self):
		terms = request.values.get('terms', None)
		force_api = request.values.get('force_api', None)

		if force_api is None:
			force_api = False

		if not terms or len(terms) < 2:
			animelist, nextList = self.main.getAnimelist(
				"DEFAULT", listrange=(0, 50))
		else:
			animelist = []
			try:
				if not force_api:
					animelist = self.main.searchDb(terms)
					if animelist is not False:
						animelist = list(animelist)
					else:
						animelist = []
	 
				if force_api or len(animelist) == 0:
					print(f'Search with APIs: {terms}')
					self.main.stopSearch = False
					animelist = self.main.api.searchAnime(
						terms, limit=self.main.animePerPage)
			except Exception as e:
				print('ERROOOOOR', e)
				pass

		if animelist is not False:
			animelist = list(animelist)
		else:
			animelist = []
		render = get_template_attribute('anime_list.jinja', 'render_animelist')

		return render(animelist=animelist, count=1, page=1)

	@route('/watch/<id>/<episode>', methods=["GET"])
	@require_login
	def watch(self, id, episode):
		web_root = '/var/www/anime.tetrazero.com/Flask/'
		root = web_root + f'static/data/cache/{id}'
		try:
			if not os.path.exists(root):
				os.makedirs(root)
		except PermissionError:
				abort(504, "Can't create the necessary folders!")

		source = self.main.getFolder(id) + f'/{episode}.mkv'

		if not os.path.exists(source):
			abort(404)

		filename = f'stream_{episode}'
		stream_file = f'{filename}.m3u8'
		
		stream_url = f'data/cache/{id}/{stream_file}'
		stream = f'{root}/{stream_file}'

		stream_data = f'{root}/{filename}.ts'

		if not os.path.exists(stream):
			print('Started stream')

			try:
				command = [
					'ffmpeg',
					'-loglevel', 'error',
					'-i', f'{source}',
					'-preset', 'ultrafast',
					'-tune', 'zerolatency',
					'-vf', f"subtitles='{source}'",
					# '-c:s', 'mov_text',
					'-c:v', 'libx264',
					'-c:a', 'aac',
					# '-map', '0',
					# '-flags', '+global_header',
					'-f', 'hls',
					'-hls_time', '5',
					'-hls_list_size', '0',
					'-hls_flags', 'single_file',
					'-movflags', '+faststart',
					'-map_metadata', '0',
					'-y',
					f'{stream}'
				]
				# command = ' '.join(command)
				# print(command)
				# , stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
				process = subprocess.Popen(command, shell=False)
			except Exception as e:
				abort(500)

			print('Waiting for stream')

			while not os.path.exists(stream) or not os.path.exists(stream_data):
				time.sleep(0.1)

		# return Response(open(stream, 'rb').read(), mimetype='application/vnd.apple.mpegurl')
		# return Response(stream_with_context(generate()), mimetype='video/mp4')

		return render_template('video.jinja', stream_url=stream_url, id=id, episode=episode)

	@route('/watch/<id>/<episode>', methods=["POST"])
	@require_login
	def watch_post(self, id, episode):
		pass

	@route('/torrents/<id>', methods=["GET", "POST"])
	@require_login
	def torrents(self, id):
		if request.method == "POST":
			custom_search = request.values.get('custom_search', None)
		else:
			custom_search = None

		timestamp = str(int(time.time()))
		random_chars = ''.join(random.choices(
			string.ascii_uppercase + string.digits, k=6))
		search_id = f'{timestamp}-{random_chars}'

		data = self.main.database.get(id=id, table="anime")
		if custom_search:
			titles = [custom_search]
		else:
			titles = data.title_synonyms

		testing = False
		if testing:
			def generator():
				for i in range(50):
					yield {'name': ''.join(random.choices(string.ascii_letters, k=5)), 'seeds': i, 'leech': random.randint(1, 100), 'link': {'url': f'url{i}'}, 'hash': i}
					time.sleep(1)

			fetcher = generator()
		else:
			fetcher = search_engines.search(titles)

		# Start search
		torrents = TorrentList(fetcher)

		self.search_threads[search_id] = torrents

		return render_template('torrents.jinja', id=id, search_id=search_id)

	@route('/torrents_search')
	@require_login
	def torrents_search(self):
		search_id = request.values.get('search_id', None)
		thread = None
		if search_id is not None:
			thread = self.search_threads.get(search_id, None)

		if thread is None:
			return jsonify({'error': f'search_id {search_id} is unknown'})

		out = []
		val = thread.get(timeout=1)

		while val is not None:
			out.append(val)
			val = thread.get(timeout=None)

		empty = thread.empty()
		return jsonify({'data': out, 'empty': empty}, )

	@route('/download/<id>')
	@require_login
	def download(self, id):
		magnet = request.values.get('magnet', None)

		if not magnet:
			abort(400)

		try:
			out = self.main.downloadFile(id, url=magnet, download=False)
		except Exception as e:
			val = False
		else:
			val = out.get()

		return jsonify({'success': val})

	def get_user(self):
		token = request.cookies.get('Token', None)
		# default = {'id': 1, 'username': 'Guest'}
		default = None
		if not token:
			return default

		try:
			data = jwt.decode(token, secret.JWT_SECRET_KEY,
							  algorithms=["HS256"])
		except jwt.InvalidSignatureError:
			# Someone tried to hack me
			return default
		except jwt.exceptions.ExpiredSignatureError:
			# Login has expired
			return default

		return data['data']

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
	app.run(debug=True, threaded=True)
	# while True:
	# 	try:
	# 		app.run(debug=True)
	# 	except SystemExit:
	# 		print('SystemExit')
