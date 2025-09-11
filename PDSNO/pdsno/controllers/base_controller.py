class BaseController:
    def __init__(self, name):
        self.name = name
    
    def receive_message(self, message):
        raise NotImplementedError
    
    def send_message(self, target, message):
        raise NotImplementedError