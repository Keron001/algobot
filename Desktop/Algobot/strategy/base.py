class BaseStrategy:
    def __init__(self, data, lot_size=0.01):
        self.data = data
        self.lot_size = lot_size

    def run(self):
        raise NotImplementedError("run() must be implemented by subclasses.") 