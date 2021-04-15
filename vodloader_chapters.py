import datetime
from math import floor

class vodloader_chapters(object):

    def __init__(self, game, title):
        self.start_time = datetime.datetime.now()
        self.timestamps = [('00:00:00', game, title)]
    

    def __len__(self):
        return self.timestamps.__len__()

    def append(self, game, title):
        delta = datetime.datetime.now() - self.start_time
        hours = floor(delta.seconds/3600)
        mins = floor(delta.seconds%3600/60)
        secs = floor(delta.seconds%60)
        timestamp = f'{hours}:{mins}:{secs}'
        self.timestamps.append((timestamp, game, title))

    def get_games(self):
        games = list(map(lambda x :x[1], self.timestamps))
        out = []
        [out.append(x) for x in games if x not in out]
        return out

    def get_current_game(self):
        return self.timestamps[-1][1]
    
    def get_current_title(self):
        return self.timestamps[-1][2]

    def get_game_chapters(self):
        out = f'{self.timestamps[0][0]} {self.timestamps[0][1]}\n'
        count = 1
        for i in range(1, len(self.timestamps)):
            if self.timestamps[i][1] != self.timestamps[i-1][1]:
                out += f'{self.timestamps[i][0]} {self.timestamps[i][1]}\n'
                count += 1
        if count > 2:
            return out
        else:
            return None

    def get_title_chapters(self):
        out = f'{self.timestamps[0][0]} {self.timestamps[0][2]}\n'
        count = 1
        for i in range(1, len(self.timestamps)):
            if self.timestamps[i][2] != self.timestamps[i-1][2]:
                out += f'{self.timestamps[i][0]} {self.timestamps[i][2]}\n'
                count += 1
        if count > 2:
            return out
        else:
            return None