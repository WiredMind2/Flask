#! /usr/bin/python3

import sys
import os
sys.path.append(os.path.dirname(__file__))
sys.path.insert(0, '/var/www/anime.tetrazero.com/')
from app import app as application
# application.secret_key = constants.SECRET_KEY
