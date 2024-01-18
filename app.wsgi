#! /usr/bin/python3

import logging
import sys
import os
print(__file__)
sys.path.append(os.path.dirname(__file__))
import constants
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, '/var/www/anime.tetrazero.com/')
from app import app as application
# application.secret_key = constants.SECRET_KEY