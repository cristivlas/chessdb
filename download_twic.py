from itertools import count
import wget

url = 'https://www.theweekinchess.com/zips/twic{}g.zip'
for i in count(start=1383, step=1):
    try:
        wget.download(url.format(i))
    except:
        break

print(i)
