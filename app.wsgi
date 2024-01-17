#! /usr/bin/python3

import logging
import sys
import constants
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, '/home/user/www/flask/')
from my_flask_app import app as application
application.secret_key = constants.SECRET_KEY