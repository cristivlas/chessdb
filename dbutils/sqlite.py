import sqlite3

class SQLConn:
    """ Sqlite3 Connection Wrapper """
    def __init__(self, db_file):
        self._conn = sqlite3.connect(db_file)
        self._cursor = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self._conn:
            if self._cursor:
                self._conn.commit()
            self._conn.close()

    def commit(self):
        assert self._cursor
        self._conn.commit()
        rowid = self._cursor.lastrowid
        self._cursor = None
        return rowid

    def exec(self, *args):
        self._cursor = self._conn.cursor()
        self._cursor.execute(*args)
