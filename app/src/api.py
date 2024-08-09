from gunicorn.app.base import BaseApplication


class API(BaseApplication):

    def __init__(self, app, settings=None):
        self.app = app
        self.settings = settings or {}
        super().__init__()

    def load_config(self):
        for k, v in self.settings.items():
            self.cfg.set(k, v)

    def load(self):
        return self.app
