from datetime import datetime
import sys
import os
if sys.platform == 'win32':
	sys.path.append(os.path.join(os.path.expanduser('~'), 'Documents/Python'))
else:
    sys.path.append('/var/www/anime.tetrazero.com')
from AnimeManager import Anime

class Utils:
    def cropText(self, text, chars=None):
        if not text:
            return 'No synopsis'

        if not chars:
            chars = 50
        return text.strip()[:chars]

    def GetStatusText(self, anime):
        anime = Anime(anime)
        datefrom, dateto = anime.date_from, anime.date_to
        if isinstance(datefrom, str):
            datefrom = anime.date_from = int(datefrom)
        if isinstance(dateto, str):
            dateto = anime.dateto = int(dateto)
        if datefrom is not None:
            datefrom = datetime.utcfromtimestamp(datefrom)
        if dateto is not None:
            dateto = datetime.utcfromtimestamp(dateto)

        return '<br>'.join(self.main.getDateText(anime))