import datetime
from math import floor

class vodloader_chapters(object):

    def __init__(self, title):
        self.start_time = datetime.datetime.now()
        self.timestamps = [('00:00:00', title)]
    

    def __len__(self):
        return self.timestamps.__len__()


    def append(self, title):
        delta = datetime.datetime.now() - self.start_time
        hours = floor(delta.seconds/3600)
        mins = floor(delta.seconds%3600/60)
        secs = floor(delta.seconds%60)
        timestamp = f'{hours}:{mins}:{secs}'
        self.timestamps.append((timestamp, title))


    def get_games(self):
        games = list(map(lambda x :x[1], self.timestamps))
        out = []
        [out.append(x) for x in games if x not in out]
        return out


    def get_string(self):
        out = ""
        for ts in self.timestamps:
            out += f'{ts[0]} {ts[1]}\n'
        return out