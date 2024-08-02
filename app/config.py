import yaml

class Config(dict):
    
    def __init__(self, path):
        self.path = path
        self.load()

    def load(self):
        with open(self.path, 'r') as file:
            self.update(**yaml.safe_load(file))

    def save(self):
        with open(self.path, 'w') as file:
            yaml.safe_dump(self, file)
