from twitchAPI.types import VideoType
import os
import _thread
import datetime
import pickle

class vodloader_status(dict):

    def __init__(self, vodloader):
        self.vodloader = vodloader
        self.load()


    def get_file(self):
        pickle_dir = os.path.join(os.path.dirname(__file__), 'backlog_status')
        if not os.path.isdir(pickle_dir): os.mkdir(pickle_dir)
        return(os.path.join(pickle_dir, f'status_{self.vodloader.channel}.pickle'))


    def load(self):
        pickle_file = self.get_file()
        if os.path.exists(pickle_file):
            with open(pickle_file, 'rb') as status_file:
                self.update(pickle.load(status_file).copy())
        else:
            self.status = {}
            self.save()


    def save(self):
        pickle_file = self.get_file()
        with open(pickle_file, 'wb') as status_file:
            pickle.dump(self.copy(), status_file)


    def __del__(self):
        self.save()