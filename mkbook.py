#! /usr/bin/env python3.9
"""
Utility for creating opening books in Polyglot format.
"""
import argparse
import chess, chess.pgn, chess.polyglot
import csv
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


def make_entry(key, move, weight):
    entry = ENTRY_STRUCT.pack(key, encode_move(move), weight % 65535, 0)
    assert len(entry)==16
    return entry


moves_table = defaultdict(list)


def add(board, new_move, stats):
    moves_list = moves_table[chess.polyglot.zobrist_hash(board)]

    for move in moves_list:
        if move.uci() == new_move.uci():
            move.stats.win += stats.win
            move.stats.loss += stats.loss
            return

    new_move.stats = stats
    moves_list.append(new_move)


def make_opening_book(args):
    chess.pgn.LOGGER.setLevel(50) # silence off PGN warnings
    try:
        crawler = ZipCrawler(args.input)
        crawler.set_action('.pgn', partial(read_pgn_file, args, [0]))
        crawler.crawl()
        print()
        output_book(args)
    except KeyboardInterrupt:
        print()


def output_book(args):
    count = 0
    with open(args.out, 'wb') as f:
        # The search algorithm expects entries to be sorted by key.
        for key in sorted(moves_table.keys()):
            moves = moves_table[key]
            moves.sort(key=lambda move: move.stats.win - move.stats.loss, reverse=True)

            moves = moves[:5] # cap variations to keep file size reasonable
            lowest = moves[-1].stats.win - moves[-1].stats.loss

            for move in moves:
                weight = move.stats.win - move.stats.loss - lowest + 1
                f.write(make_entry(key, move, weight))
                count += 1

    print (f'{args.out}: {count} moves')


def read_ranked(fname):
    names = []
    with open(fname, 'r') as f:
        for row in csv.reader(f):
            # match strings containing player's last name; good enough?
            names.append(f'.*{row[0].lower()}.*')
    return names


_flog = open('log.txt', 'w+')


def read_pgn_file(args, count, fname):
    # Filter by filename rather than by PGN headers -- for speed
    if args.ranked and not any((re.match(f, fname.lower()) for f in args.ranked)):
        _flog.write(f'- {path.splitext(path.basename(fname))[0]}\n')
        return
    _flog.write(f'+ {path.splitext(path.basename(fname))[0]}\n')
    for game in read_games(fname):
        try:
            info = game_metadata(game)
        except KeyError:
            continue

        board = game.board()
        for move in list(game.mainline_moves())[:args.depth]:
            color = chess.COLOR_NAMES[board.turn]
            result = info[color]['result']
            if result == WIN:
                add(board, move, MoveStats(2, 0))
            elif result == LOSS:
                add(board, move, MoveStats(0, 2))
            else:
                add(board, move, MoveStats(1, 0))

            board.push(move)
            assert board.is_valid(), board.status()

        count[0] += 1
        white = info['white']['name']
        black = info['black']['name']
        print (f'\033[K [{count[0]}] [{fname}] {white} / {black}]', end='\r')


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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('input', nargs='*')
    parser.add_argument('-d', '--depth', type=int, default=20)
    parser.add_argument('-o', '--out')
    parser.add_argument('-r', '--ranked')
    parser.add_argument('--test', action='store_true')

    args = parser.parse_args()

    if args.ranked:
        args.ranked = read_ranked(args.ranked)

    if args.test:
        # run tests
        test_encode_move()
        test_large_weight()
        #
        # todo: write more tests
        #
    else:
        if not args.input or not args.out:
            parser.error('input and output are required')

        make_opening_book(args)
