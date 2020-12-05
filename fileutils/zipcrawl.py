
from .filecrawl import FileCrawler, walk_directory
from functools import partial
from zipfile import ZipFile
import shutil
import tempfile


def extract_from_zip(callbacks, default_callback, fname):
    with ZipFile(fname, 'r') as archive:
        try:
            print (f'Expanding {fname}\033[K')
            dirpath = tempfile.mkdtemp()
            archive.extractall(dirpath)
            if walk_directory(dirpath, callbacks, default_callback):
                return True
        finally:
            shutil.rmtree(dirpath)


class ZipCrawler(FileCrawler):
    """ A FileCrawler that also digs into zip files """
    def __init__(self, paths, default_callback=lambda _: None):
        super().__init__(paths, default_callback)
        self._callbacks['.zip'] = partial(extract_from_zip, self._callbacks, self._default_callback)

