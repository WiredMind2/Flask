from datetime import datetime
import sys
sys.path.append('D:\willi\Documents\Python')
from AnimeManager import Manager, Anime

def cropText(text, chars=None):
    if not text:
        return 'No synopsis'

    if not chars:
        chars = 50
    return text.strip()[:chars]

def GetStatusText(anime):
    anime = Anime(anime)
    datefrom, dateto = anime.date_from, anime.date_to
    if datefrom is not None:
        datefrom = datetime.utcfromtimestamp(datefrom)
    if dateto is not None:
        dateto = datetime.utcfromtimestamp(dateto)

    return '<br>'.join(main.getDateText(anime))