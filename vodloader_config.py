import yaml

class vodloader_config(dict):
    
    def __init__(self, filename):
        self.load(filename)
    
    def load(self, filename):
        self.filename = filename
        self.clear()
        with open(self.filename, 'r') as stream:
            try:
                self.update(yaml.safe_load(stream).copy())
            except yaml.YAMLError as e:
                print(e)
    
    def reload(self):
        self.load(self.filename)