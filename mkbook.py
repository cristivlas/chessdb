#! /usr/bin/env python3.9
"""
Utility for creating opening books in Polyglot format.
"""
import argparse
import chess, chess.pgn, chess.polyglot
import csv
import math
import re
import struct
from chessutils.pgn import *
from dataclasses import dataclass
from collections import defaultdict
from fileutils.zipcrawl import ZipCrawler
from functools import partial
from os import path

"""
A Polyglot book is a series of entries of 16 bytes
key    uint64
move   uint16
weight uint16
learn  uint32

Integers are stored big endian.
"""
ENTRY_STRUCT = struct.Struct('>QHHI')


def encode_move(move: chess.Move) -> int:
    promotion = ((move.promotion - 1) & 0x7) << 12 if move.promotion else 0
    return move.to_square | (move.from_square<<6) | promotion


@dataclass
class MoveStats:
    win: int = 0
    loss: int = 0
    depth: int = 0

    @property
    def win_ratio(self):
        return 1.0 if self.loss==0 else self.win / self.loss


def make_entry(key, move, weight, learn=0):
    assert weight > 0, weight
    assert learn >= 0, learn
    entry = ENTRY_STRUCT.pack(key, encode_move(move), weight % 65535, learn % 65535)
    assert len(entry)==16
    return entry


def add_move(moves_list, new_move):
    for move in moves_list:
        if move.uci() == new_move.uci():
            move.stats.win += new_move.stats.win
            move.stats.loss += new_move.stats.loss
            move.stats.depth = min(move.stats.depth, new_move.stats.depth)
            return
    moves_list.append(new_move)


def add(table, board, new_move):
    add_move(table[chess.polyglot.zobrist_hash(board)], new_move)


__moves_table = defaultdict(list)


def merge(table):
    for k, moves_list in table.items():
        for move in moves_list:
            add_move(__moves_table[k], move)
    table.clear()


def make_opening_book(args):
    chess.pgn.LOGGER.setLevel(50) # silence off PGN warnings
    try:
        count = [0]
        crawler = ZipCrawler(args.input)
        crawler.set_action('.pgn', partial(read_pgn_file, args, count))
        crawler.crawl()
        print()
        print(f'Read {count[0]} games. Generating opening book...')
        output_book(args)
    except KeyboardInterrupt:
        print()


def log2(n):
    return int(math.log(n, 2)) if n else 0


def output_book(args):
    count = 0
    with open(args.out, 'wb') as f:
        # The Polyglot search algorithm expects entries to be sorted by Zobrist key.
        for key in sorted(__moves_table.keys()):

            # discard moves with win ratio < 1
            moves = [move for move in __moves_table[key] if move.stats.win > move.stats.loss]
            if not moves:
                continue

            moves.sort(key=lambda move: (move.stats.win, move.stats.win_ratio), reverse=True)

            # cap alternate moves to keep file size reasonable
            moves = moves[:args.alt_moves]

            for move in moves:
                f.write(make_entry(key, move, weight=max(1, log2(move.stats.win)), learn=log2(move.stats.loss)))
                count += 1

    print (f'{args.out}: {count} moves')


def read_ranked(fname):
    names = []
    with open(fname, 'r') as f:
        for row in csv.reader(f):
            last = row[0].strip().lower()
            first = row[1].strip().lower()
            names.append(f'{last}$|{last}(,{first[0]})+')
    return names


_ranked = {}
_flog = open('mkbook.log', 'w')
_stat = ['-', '+']


def is_ranked(args, name):
    # no ranked players list given? treat all as ranked
    if not args.ranked:
        return True

    def format_name(name):
        return ','.join(name).lower()

    r = _ranked.get(name, None)
    if r is None:
        n = format_name(name)
        r = any((re.match(pattern, n) for pattern in args.ranked))
        _ranked[name] = r
        _flog.write(f'{_stat[r]} {name}\n')
    return r


def read_pgn_file(args, count, fname):
    def on_meta(game, meta):
        table.clear()
        game.white = meta['white']['name']
        game.black = meta['black']['name']
        return is_ranked(args, game.white) or is_ranked(args, game.black)

    def on_move(meta, board, move):
        depth = len(board.move_stack)
        if depth < args.depth:
            color = chess.COLOR_NAMES[board.turn]
            if is_ranked(args, meta[color]['name']):
                result = meta[color]['result']
                if result == WIN:
                    move.stats = MoveStats(2, 0, depth)
                elif result == LOSS:
                    move.stats = MoveStats(0, 2, depth)
                else:
                    move.stats = MoveStats(1, 0, depth)
                add(table, board, move)

    table=defaultdict(list)

    for game in GameFileReader(fname, on_meta, on_move):
        count[0] += 1
        print (f'\033[K [{count[0]}] [{fname}] {game.white} / {game.black}]', end='\r')
        merge(table)


def test_encode_move():
    test_moves = [ 'e2e4', 'e7e8q' ]
    for uci_move in test_moves:
        test_move = chess.Move.from_uci(uci_move)
        raw_move = encode_move(test_move)

        # Encode source and target square.
        to_square = raw_move & 0x3f
        from_square = (raw_move >> 6) & 0x3f

        # Encode the promotion type.
        promotion_part = (raw_move >> 12) & 0x7
        promotion = promotion_part + 1 if promotion_part else None

        move = chess.Move(from_square, to_square, promotion)
        assert test_move == move, (test_move, move)


def test_large_weight():
    move = chess.Move.from_uci('e2e4')
    make_entry(0, move, 65536)


def test_ranked(args):
    assert args.ranked, 'This test expects a list of ranked players'
    expected = [
        (('Kasparov', ), True),
        (('Kasparov', 'G'), True),
        (('Kasparov', 'G.'), True),
        (('Kasparov', 'Gary'), True),
        (('Kasparov', 'Garry'), True),
        (('Kasparov', 'S'), False),
        (('Kasparov', 'Sergey'), False),
        (('Polgar', ), True),
        (('Polgar', 'Judith'), True),
        (('Polgar', 'Ju'), True),
        (('Polgar', 'S'), False),
        (('Polgar', 'S.'), False),
        (('polgar', 'j.'), True),
    ]
    for name, ranked in expected:
        assert is_ranked(args, name)==ranked, (name, ranked)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('input', nargs='*')
    parser.add_argument('-a', '--alt-moves', type=int, default=5)
    parser.add_argument('-d', '--depth', type=int, default=40)
    parser.add_argument('-o', '--out')
    parser.add_argument('-r', '--ranked')
    parser.add_argument('--test', action='store_true')

    args = parser.parse_args()

    args.alt_moves = min(args.alt_moves, 5)
    if args.ranked:
        args.ranked = read_ranked(args.ranked)

    if args.test:
        test_encode_move()
        test_large_weight()
        test_ranked(args)
    else:
        if not args.input or not args.out:
            parser.error('input and output are required')

        make_opening_book(args)
