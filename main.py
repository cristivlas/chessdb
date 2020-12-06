"""
Extract chess games from PGN-format (.pgn, .zip) into Sqlite3 database

Example of database use:
What are the openings played by Kasparov as black?

sqlite> SELECT DISTINCT o.name FROM openings o
   ...> LEFT JOIN games g ON g.opening = o.id
   ...> LEFT JOIN players p ON g.black = p.id
   ...> WHERE p.name IS 'Kasparov' AND p.first_middle is 'Gary';

To see the actual move sequence change the first line to:

    SELECT DISTINCT o.name, o.moves FROM openings o

"""

from chessutils.eco import *
from chessutils.pgn import *
from collections import defaultdict
from dbutils.sqlite import SQLConn
from fileutils.zipcrawl import ZipCrawler
from functools import partial

import argparse
import os

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
    """ Create three tables: openings, players and games. Index games by FEN (Forsyth-Edwards Notation) """
    with SQLConn(fname) as conn:
        conn.exec(_create_openings_table)
        conn.exec(_create_players_table)
        conn.exec(_create_games_table)
        conn.exec('CREATE UNIQUE INDEX idx_fen ON openings (fen)')
        sql = 'INSERT INTO openings(eco, name, variation, fen, moves) VALUES(?,?,?,?,?)'
        for _, entry in EcoAPI().db.items():
            row=(entry['eco'], entry['name'], entry.get('variation', None), entry['fen'], entry['moves'])
            conn.exec(sql, row)


# Dictionary of players for: 1) faster ID lookup 2) name cleanup
# Keyed by last name. Each entry is itself a dictionary, keyed by first_middle name.
__players = defaultdict(dict)


# Add name tuple to database and to the __players dictionary
def _add_player_to_db(sql_conn, name):
    sql_conn.exec('INSERT INTO players(name, first_middle) VALUES(?,?)', name)
    id = sql_conn.commit()
    __players[name[0]][name[1]] = id
    return id


def add_player(sql_conn, name):
    bad = '"/\\:;?!*#@$'
    # ignore names that contain blacklisted characters
    if any([c in n for n in name for c in bad]):
        return None

    first_middle_dict = __players.get(name[0], None)
    if first_middle_dict is None:
        return _add_player_to_db(sql_conn, name)

    id = first_middle_dict.get(name[1], None)
    # exact match for last and first-middle names? great!
    if id != None:
        return id

    for key, id in first_middle_dict.items():
        # is the first name just one initial?
        is_initial = len(name[1])==1

        # matches one of the already added names? cool
        if is_initial and name[1][0]==key[0]:
            return id

        # is the one already in the dictionary (and DB)
        # just an initial and it matches the name we are adding?
        if len(key)==1 and name[1][0]==key[0]:

            # are we adding a full name? then update the records
            if not is_initial:
                # add name to dictionary
                first_middle_dict[name[1]]=id
                # delete the entry with only the initial
                del first_middle_dict[key]
                # update the DB
                sql_conn.exec('UPDATE players SET first_middle=? WHERE id=?', (name[1], id))

            return id
    return _add_player_to_db(sql_conn, name)


# Add game and player names to the database
def add_to_db(sql_conn, count, fname):
    for game in read_games(fname):
        try:
            info = game_metadata(game)
        except KeyError:
            continue
        white = add_player(sql_conn, info['white']['name'])
        black = add_player(sql_conn, info['black']['name'])
        if white is None or black is None or white == black:
            return

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
    parser.add_argument('-c', '--clean', action='store_true')
    args = parser.parse_args()

    if args.clean:
        os.unlink(args.db)

    init_db(args.db)

    try:
        with SQLConn(args.db) as sql_conn:
            crawler = ZipCrawler(args.input)
            crawler.set_action('.pgn', partial(add_to_db, sql_conn, [0]))
            crawler.crawl()
    except KeyboardInterrupt:
        pass

    print()
