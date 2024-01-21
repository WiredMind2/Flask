import json
import random
import string
import subprocess
import time
from flask import Flask, Response, abort, get_template_attribute, jsonify, render_template, request, session, stream_with_context
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
	def wrapper(self, *args, **kwargs):
		if 'x-access-token' in request.headers:
			token = request.headers['x-access-token']
		if not token:
			return jsonify({'message': 'Token is missing!'}), 401
		try:
			data = jwt.decode(token, app.config['SECRET_KEY'])

			current_user = data['public_id']

		except:

			return jsonify({'message': 'Token is invalid!'}), 401

		return func(current_user, *args, **kwargs)

	return wrapper

class App(Flask, Utils):
	def __init__(self, name=None):
		super().__init__(name or __name__)
		self.secret_key = secret.SECRET_KEY

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
  
		self.search_threads = {}

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
  
		source = self.main.getFolder(id)
		episodes = self.main.getEpisodes(source)

		return render_template('anime_info.jinja', anime=anime, tags=tags, episodes=episodes)

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

	@route('/video/<id>/<episode>')
	def video(self, id, episode):
		root = f'static/data/cache/{id}'
		if not os.path.exists(root):
			os.makedirs(root)

		source = self.main.getFolder(id) + f'/{episode}.mkv'

		if not os.path.exists(source):
			abort(404)

		stream_url = f'data/cache/{id}/stream_{episode}.m3u8'
		stream = os.path.abspath('static/' + stream_url)
		if not os.path.exists(stream):
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
			print(command)
			process = subprocess.Popen(command, shell=False) #, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

			while not os.path.exists(stream):
				time.sleep(0.1)

		# return Response(open(stream, 'rb').read(), mimetype='application/vnd.apple.mpegurl')
		# return Response(stream_with_context(generate()), mimetype='video/mp4')
  
		return render_template('video.jinja', stream_url = stream_url)

	@route('/watch/<id>/<episode>')
	def watch(self, id, episode):
		# TODO - An actual player UI
		return self.video(id, episode)

	@route('/torrents/<id>')
	def torrents(self, id):

		timestamp = str(int(time.time()))
		random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
		search_id = f'{timestamp}-{random_chars}'
  
		data = self.main.database(id=id, table="anime")
		titles = data.title_synonyms

		fetcher = search_engines.search(titles)

		# Start search
		torrents = TorrentList(fetcher)
		self.search_threads[search_id] = torrents

		return render_template('torrents.jinja', id=id, search_id=search_id)

	@route('/torrents_search')
	def torrents_search(self):
		search_id = request.values.get('search_id', None)
		thread = None
		if search_id is not None:
			thread = self.search_threads.get(search_id, None)
   
		if thread is None:
			abort(404)

		out = []
		loop = True
		while loop:
			val = thread.get()
			if val is not None:
				loop = False
	
			while val is not None:
				out.append(val)
				val = thread.get(timeout=None)

		empty = thread.empty()

		for i, torrent in enumerate(out):
			torrent['link'] = torrent['link'].__dict__
			
		return jsonify({'data': out, 'empty': empty}, )
			
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