import binascii
import hashlib
import os
import sqlite3


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

class dbWrapper:
    def __init__(self) -> None:                        
        # appdata = os.path.join(os.getenv('APPDATA'), "Anime Manager")
        self.dbPath = os.path.join(os.path.dirname(__file__), "animeData.db")
        
        self.con = sqlite3.connect(self.dbPath, check_same_thread=False)
        self.con.row_factory = dict_factory
        self.cur = self.con.cursor()
        
    def GetUser(self, id):
        self.cur.execute('SELECT id, username, email, avatar_url FROM user WHERE id=?', (id, ))
        data = self.cur.fetchone()
        return data
    
    def RegisterUser(self, username, email, password, avatar=None):
        # Create a new salt
        salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')

        # Create a password hash
        pwdhash = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), salt, 100000)
        pwdhash = binascii.hexlify(pwdhash)

        # Return a salt|hash combination
        out = (salt + pwdhash).decode('ascii')
    
        try:
            self.cur.execute('INSERT INTO user(username, email, password, avatar_url) VALUES (?,?,?,?)', (username, email, out, avatar))
        except sqlite3.IntegrityError as e:
            return False
        else:
            self.con.commit()
            return True
        
    def LoginUser(self, email, password):
        self.cur.execute('SELECT id, password FROM user WHERE email=?', (email,))
        data = self.cur.fetchone()
        if data is None:
            # Doesn't exist
            return None

        id, stored_password = data
        
        salt = stored_password[:64].encode('ascii')
        stored_password = stored_password[64:]

        pwdhash = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), salt, 100000)
        pwdhash = binascii.hexlify(pwdhash).decode('ascii')

        if pwdhash == stored_password:
            # Correct password
            return id
        else:
            # Incorrect
            return False