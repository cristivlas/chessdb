#! /usr/bin/env python3
from itertools import count
import wget

base = 'https://www.newinchess.nl/Na/Downloads/Yearbook/'
urls = {
    'NIC_yb{}_pgn.zip': 62,
    'YB{}_pgn.zip': 80,
    'Yb{}_pgn.zip': 115,
    'yearbook{}.zip': 119,
}

for u in urls:
    for i in count(start=urls[u], step=1):
        url = u.format(i)
        try:
            print (' ', wget.download(base + url))
        except:
            if url.islower():
                break
            url = url.lower()
            try:
                print (' ', wget.download(base + url.lower()))
            except:
                break
