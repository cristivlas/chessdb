#! /usr/bin/env python3.9
"""
Utility for creating opening books in Polyglot format.
"""
import argparse
import chess, chess.pgn, chess.polyglot
import struct
from chessutils.pgn import *
from collections import defaultdict
from fileutils.zipcrawl import ZipCrawler
from functools import partial

ENTRY_STRUCT = struct.Struct('>QHHI')


def encode_move(move: chess.Move) -> int:
    promotion = ((move.promotion - 1) & 0x7) << 12 if move.promotion else 0
    return move.to_square | (move.from_square<<6) | promotion


def make_entry(board: chess.Board, move: chess.Move, weight: int):
    return ENTRY_STRUCT.pack(chess.polyglot.zobrist_hash(board), encode_move(move), weight, 0)


moves_table = defaultdict(list)


def add_move(board, new_move, weight):
    assert weight
    moves_list = moves_table[chess.polyglot.zobrist_hash(board)]
    for move in moves_list:
        if move.uci()==new_move.uci():
            move.weight += weight
            return
    new_move.weight = weight
    moves_list.append(new_move)


def make_opening_book(args):
    chess.pgn.LOGGER.setLevel(50) # silence off PGN warnings
    try:
        crawler = ZipCrawler([args.input])
        crawler.set_action('.pgn', partial(read_pgn_file, args, [0]))
        crawler.crawl()
    except KeyboardInterrupt:
        pass    
    print()
    output_book(args)


def output_book(args):
    count = 0
    with open(args.out, 'wb') as f:
        for key in sorted(moves_table.keys()):
            for move in moves_table[key]:
                entry = ENTRY_STRUCT.pack(key, encode_move(move), int(move.weight), 0)
                assert len(entry)==16
                f.write(entry)
                count += 1
    print (f'{args.out}: {count} moves')
    
    # read_book(args.out)


def read_book(fname):
    with chess.polyglot.MemoryMappedReader(fname) as reader:
        for entry in reader:
            print (entry.move.uci(), entry.weight, entry.learn)


def read_pgn_file(args, count, fname):    
    for game in read_games(fname):
        try:
            info = game_metadata(game)
        except KeyError:
            continue

        board = game.board()
        for move in list(game.mainline_moves())[:args.depth]:
            color = chess.COLOR_NAMES[board.turn]            
            result = info[color]['result']
            if result != LOSS:
                add_move(board, move, 2*result)            
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

        # Extract source and target square.
        to_square = raw_move & 0x3f
        from_square = (raw_move >> 6) & 0x3f

        # Extract the promotion type.
        promotion_part = (raw_move >> 12) & 0x7
        promotion = promotion_part + 1 if promotion_part else None

        move = chess.Move(from_square, to_square, promotion)
        assert test_move == move, (test_move, move)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('input', nargs='?')
    parser.add_argument('-d', '--depth', type=int, default=20)
    parser.add_argument('-o', '--out')
    parser.add_argument('--test', action='store_true')

    args = parser.parse_args()

    if args.test:
        test_encode_move()
        #
        # todo: write more tests
        #
    else:
        if not args.input or not args.out:
            parser.error('input and output are required')

        make_opening_book(args)
