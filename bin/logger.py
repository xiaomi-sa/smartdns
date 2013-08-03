# -*- coding: utf-8 -*-
import logging
import logging.handlers

def create_logger(filename):
	handle = logging.handlers.TimedRotatingFileHandler(     filename = filename,
								when='h',
								interval=1,
								backupCount=72 )
	#handle.setLevel(logging.INFO)
	fmt = logging.Formatter(fmt='%(asctime)s  %(filename)s [line:%(lineno)d] [%(levelname)s]  %(message)s',
				datefmt='%Y-%m-%d %H:%M:%S' )
	handle.setFormatter(fmt)
	logger = logging.getLogger()
	logger.addHandler(handle)
	logger.setLevel(logging.DEBUG)
	#logger.setLevel(logging.INFO)
	#logger.propagate = False
	return logger

logger = None

class SLogger():
	def __init__(self):
		pass
	
	@classmethod
	def init_logger(cls, filename):
		global logger
		if not logger:
			logger = create_logger(filename)
		return logger

if __name__ == "__main__":
	logger = SLogger.init_logger("../log/test_log.log")
	logger.info('start to init IP pool ......')
	#test mem leak
	while True:
		logger.info('xxxxxxxxxxxxxxxxx')
