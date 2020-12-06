#! /usr/bin/env python3
"""
    Download PGNs from web page
    default='https://www.pgnmentor.com/files.html'
"""
import argparse
import re
import wget
import urllib.parse
import urllib.request


if __name__ == '__main__':
    """
    The PGN mentor site has games archived by Event, Opening and Player.
    The -e -o -p command line flag combination specifies which to download.

    Events are a small dataset, Openings is large (and has games by random players).
    """
    parser = parser = argparse.ArgumentParser()
    parser.add_argument('site', default='https://www.pgnmentor.com/files.html', nargs='?')
    parser.add_argument('-e', '--events', action='store_true')
    parser.add_argument('-o', '--openings', action='store_true')
    parser.add_argument('-p', '--players', action='store_true')

    args = parser.parse_args() # parse command line

    URL = urllib.parse.urlsplit(args.site)
    base = f'{URL.scheme}://{URL.netloc}/'

    with urllib.request.urlopen(args.site) as resp:
        page = resp.read().decode('utf-8')

        # use regular expressions to match URLs within the HTML we just downloaded
        for match in re.finditer('<a href="([\w.:/]+(\.zip|\.pgn))">', page, re.MULTILINE):

            url = base + match.group(1)
            include = args.openings and '/openings/' in url
            include = include or (args.players and '/players/' in url)
            include = include or (args.events and '/events/' in url)
            if include:
                try:
                    print(url)
                    wget.download(url)
                    print()
                except Exception as e:
                    print (f'\n{e}')
