import logging  
import os.path

class create_logger():
    def __init__(self, logger_name, sub_path=""):
       
        self.name = logger_name
        self.sub_path = sub_path


    def crete(self):
        logger = logging.getLogger()
       
        logger.setLevel(logging.INFO)
       
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.join('log', self.sub_path))
        if not os.path.exists(log_path):
            os.makedirs(log_path)
        logfile = os.path.join(log_path, self.name)

        fh = logging.FileHandler(logfile, mode='a')
       
        formatter = logging.Formatter("[%(asctime)s][%(filename)s][line:%(lineno)d]-%(levelname)s: %(message)s")
        fh.setFormatter(formatter)
        
        logger.addHandler(fh)
        console = logging.StreamHandler()  
        formatter_console = logging.Formatter("[%(filename)s][line:%(lineno)d]: %(message)s")
        console.setFormatter(formatter_console)
        console.setLevel('INFO')
        logger.addHandler(console)
        return logger



