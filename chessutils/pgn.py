import chess, chess.pgn
import os
import re
from .eco import EcoAPI

ecoAPI = EcoAPI()

RESULT = [WIN, LOSS, DRAW] = [1, 0, 1/2]

__result = {
    '1/2': [ DRAW, DRAW  ],
'1/2-1/2': [ DRAW, DRAW  ],
'1/2 1/2': [ DRAW, DRAW  ],
    '1-0': [ LOSS, WIN  ],
    '0-1': [ WIN,  LOSS ],
    '1-O': [ LOSS, WIN  ],
    'O-1': [ WIN,  LOSS ],
    '+/-': [ LOSS, WIN  ],
    '-/+': [ WIN,  LOSS ],
    '(+)-(-)': [ LOSS, WIN  ],
    '(-)-(+)': [ WIN,  LOSS ],
    '1-0 ff': [ LOSS, WIN  ],
    '0-1 ff': [ WIN, LOSS  ],
}


def read_games(fname):
    with open(fname, encoding='utf-8') as f:
        while True:
            try:
                game = chess.pgn.read_game(f)                
            except:
                break
            if not game or game.errors:
                break
            if __is_valid(game):
                yield game


def __is_valid(game):
    board = game.board()
    for move in game.mainline_moves():
        if not board.is_legal(move):
            return False
        board.push(move)
        if board.is_checkmate():
            if __result[game.headers['Result']][board.turn] != LOSS:
                return False
            assert __result[game.headers['Result']][not board.turn] == WIN
    return bool(board.move_stack)


def __cleanup(info):
    event = info['event']['name']
    match = re.match('(.*)Round: (.*)', event)
    if match:
        info['event']['name'] = match.group(1).strip()
        info['event']['round'] = match.group(2).strip()


def __normalize_name(name):
    tok = name.split(',')
    FIRST, LAST = -1, 0
    if len(tok)==1:
        tok = name.split()
        FIRST, LAST = LAST, FIRST
    first = tok[FIRST].strip()
    last = tok[LAST].strip()
    middle = tok[1:-1] if len(tok)>2 else []
    return (last, ' '.join([first] + middle).strip())


def game_metadata(game):
    headers = game.headers
    info = { 'white': {}, 'black': {}, 'event': {}}
    result = __result[headers['Result']]
    info['white']['name'] = __normalize_name(headers.get('White', None))
    info['black']['name'] = __normalize_name(headers.get('Black', None))
    info['white']['result'] = result[chess.WHITE]
    info['black']['result'] = result[chess.BLACK]
    info['event']['name'] = headers.get('Event', None)
    info['event']['round'] = headers.get('Round', None)
    __cleanup(info)
    return info


def game_moves(game):
    return ' '.join([move.uci() for move in game.mainline_moves()]).strip()


def game_opening(game):
    opening = None
    board = game.board()
    for move in game.mainline_moves():
        board.push(move)
        entry = ecoAPI.lookup(board)
        if entry:
            opening = entry
    return opening
