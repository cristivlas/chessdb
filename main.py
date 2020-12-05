"""
Extract chess games from PGN-format (.pgn, .zip) into Sqlite3 database
"""
from chessutils.eco import *
from chessutils.pgn import *
from dbutils.sqlite import SQLConn
from fileutils.zipcrawl import ZipCrawler
from functools import partial

import argparse

"""
Build table of ECO-classified openings
https://en.wikipedia.org/wiki/Encyclopaedia_of_Chess_Openings
"""
_create_openings_table = """CREATE TABLE openings(
    id integer PRIMARY KEY,
    eco text NOT NULL,
    name text NOT NULL,
    variation text,
    fen text NOT NULL,
    moves text NOT NULL,
    UNIQUE(fen)
)"""
_create_players_table = """CREATE TABLE players(
    id integer PRIMARY KEY,
    name text NOT NULL,
    first_middle text
)"""
_create_games_table = """CREATE TABLE games(
    id integer PRIMARY KEY,
    white integer NOT NULL,
    black integer NOT NULL,
    event text,
    round text,
    winner text,
    opening integer,
    moves text,
    FOREIGN KEY (white) REFERENCES players (id),
    FOREIGN KEY (black) REFERENCES players (id),
    FOREIGN KEY (opening) REFERENCES openings (id)
)"""


def init_db(fname):
    with SQLConn(fname) as conn:
        conn.exec(_create_openings_table)
        conn.exec(_create_players_table)
        conn.exec(_create_games_table)
        conn.exec('CREATE UNIQUE INDEX idx_fen ON openings (fen)')
        sql = 'INSERT INTO openings(eco, name, variation, fen, moves) VALUES(?,?,?,?,?)'
        for _, entry in EcoAPI().db.items():
            row=(entry['eco'], entry['name'], entry.get('variation', None), entry['fen'], entry['moves'])
            conn.exec(sql, row)


__players = {}


def add_player(sql_conn, name):
    id = __players.get(name, None)
    if id is None:
        sql_conn.exec('INSERT INTO players(name, first_middle) VALUES(?,?)', name)
        id = sql_conn.commit()
        __players[name] = id
    return id


def add_to_db(sql_conn, count, fname):
    for game in read_games(fname):
        try:
            info = game_metadata(game)
        except KeyError:
            continue
        white = add_player(sql_conn, info['white']['name'])
        black = add_player(sql_conn, info['black']['name'])
        if white == black:
            continue
        winner = None
        for player in ['black', 'white']:
            if info[player]['result']==1:
                assert winner is None
                winner = player
        opening = game_opening(game)
        if opening:
            sql_conn.exec('SELECT id from openings WHERE fen=?', (opening['fen'],))
            opening = sql_conn._cursor.fetchall()
            assert len(opening)==1
            opening = opening[0][0]

        event = (info['event']['name'], info['event'].get('round', None))            
        sql_conn.exec('INSERT INTO games(white, black, event, round, winner, opening, moves) VALUES(?,?,?,?,?,?,?)',        
            (white, black, *event, winner, opening, game_moves(game))
        )
        white = info['white']['name']
        black = info['black']['name']
        print (f'\033[K [{count[0]}] [{fname}] {white} / {black}]', end='\r')
        count[0] += 1        


if __name__ == '__main__':
    """ Specify a list of files and directories containing PGN files and/or ZIP files """
    parser = argparse.ArgumentParser()
    parser.add_argument('input', nargs='+')
    parser.add_argument('-db', required=True)
    args = parser.parse_args()

    init_db(args.db)

    with SQLConn(args.db) as sql_conn:
        crawler = ZipCrawler(args.input)
        crawler.set_action('.pgn', partial(add_to_db, sql_conn, [0]))
        crawler.crawl()
    
    print()
