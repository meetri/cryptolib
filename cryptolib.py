import os,sys,logging

curdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(curdir + "/libs/modules")
sys.path.append(curdir + "/libs/datasources")
sys.path.append(curdir + "/libs/exchangeapis")
sys.path.append(curdir + "/libs/apis")
sys.path.append(curdir + "/libs/indicators")
sys.path.append(curdir + "/libs/orders")
sys.path.append(curdir + "/libs/exchanges")

logger = logging.getLogger('crypto')
hdlr = logging.FileHandler('/tmp/crypto.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)


