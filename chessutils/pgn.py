import chess, chess.pgn
import os
import re
from .eco import EcoAPI

ecoAPI = EcoAPI()

RESULT = [WIN, LOSS, DRAW] = [1, 0, 1/2]

# normalize result encodings
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

        # Make sure the winner was recorded correctly...
        reshdr = game.headers['Result']
        if board.is_checkmate():
            if __result[reshdr][board.turn] != LOSS:
                return False
            assert __result[reshdr][not board.turn] == WIN

        if board.is_stalemate():
            return __result[reshdr][board.turn]==DRAW and __result[reshdr][not board.turn]==DRAW
    return bool(board.move_stack)


def __cleanup(info):
    event = info['event']['name']
    match = re.match('(.*)Round: (.*)', event)
    if match:
        info['event']['name'] = match.group(1).strip()
        info['event']['round'] = match.group(2).strip()


def __normalize_name(name):
    def capitalize(n):
        return ' '.join([t.strip().capitalize() for t in n]).strip()

    tok = name.split(',')
    FIRST, LAST = -1, 0
    if len(tok)==1:
        tok = name.split()
        FIRST, LAST = LAST, FIRST
    first = tok[FIRST]
    last = tok[LAST]
    middle = tok[1:-1] if len(tok)>2 else []
    return capitalize(last.split()), capitalize(first.split() + middle)


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
    # go through the moves and apply them to the board
    for move in game.mainline_moves():
        board.push(move)
        # lookup the opening that matches the current board configuration
        entry = ecoAPI.lookup(board)
        if entry:
            opening = entry
    # return the last match, if any
    return opening
