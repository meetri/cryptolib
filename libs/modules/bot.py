import os,sys,logging,time,json,datetime,random,numpy
from trader import Trader
from marketanalyzer import Analyzer
from botdata import BotDataProvider
from tcpsock import TcpSock
from bittrex import Bittrex
from scraper import Scraper
from mongowrapper import MongoWrapper
from threading import Thread


class Bot(object):

    def __init__(self, name, config):

        self.log = logging.getLogger('crypto')

        self.config = config
        self.name = name
        # self.budget = config.get("budget",0)
        # self.initial_budget = self.budget
        # self.tradelimit = config.get("tradelimit",0)

        self.market  = config.get("market",None)
        self.candlesize = config.get("candlesize","5m")
        self.timeframe  = config.get("timeframe","3d")
        self.basesize  = config.get("basesize","1m")
        self.stopped = False

        if not self.market:
            raise Exception("missing required fields market: {}, budget: {}, tradelimit: {}".format(self.market,self.budget,self.tradelimit))

        if "usdt" in self.market.lower():
            self.scale  = config.get("scale","2")
        else:
            self.scale  = config.get("scale","8")

        #candlestick data
        self.csdata = None
        self.market_summary = None
        self.last = None
        self.scrapeDate = None
        self.startDate = None

        #dataprovider for candlestick data
        self.trader = Trader(market=self.market)

        #manage indicators
        self.analyzer = None

        #tcp socket
        self.tcpsock = None

        #threadHandler
        self.thread = None
        self.botSleep = 15
        self.ticks = 0
        self.eticks = 0
        self.rticks = 0


    def processRunner(self):
        while not self.stopped:
            try:
                self.process()
                self.ticks += 1
            except Exception as ex:
                print("Error: {}".format(ex))
                self.eticks += 1
                raise ex

            # print(".",end=" ")
            time.sleep(self.botSleep)


    def start(self):
        self.startDate = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        self.thread = Thread(target=self.processRunner)
        self.thread.start()


    def stop(self):
        self.thread.join()


    def isStopped(self):
        return self.stopped


    def process(self, options = {}):
        return None


    def refresh(self, scrape=False):
        csdata = None
        if scrape:
            try:
                csdata = Scraper({'market':self.market}).cc_scrapeCandle("1m")
                self.scrapeDate = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
                self.rticks += 1
            except Exception as ex:
                print(ex)

            if self.candlesize not in ("1m"):
                csdata = None

        self.loadCandlesticks(csdata)

        self.market_summary = Bittrex().public_get_market_summary(self.market).data["result"][0]
        self.last = self.market_summary['Last']
        self.csdata['closed'][-1] = self.last


        self.calculate_ta()


    def lastidx(self):
        return len(self.csdata['closed']) - 1

    def calculate_ta(self):
        self.tadata = {}


    def createSocket( self, ip="127.0.0.1", port=9500 ):
        self.tcpsock = TcpSock(ip,port, self)
        self.tcpsock.start()


    def closeSocket(self):
        self.tcpsock.close()


    def candleColor(self, idx ):
        if self.csdata['closed'][idx] >= self.csdata['open'][idx]:
            return 'green'
        else:
            return 'red'


    def candle(self, idx, ta = None ):
        candle = {
                "date": self.csdata["time"][idx],
                "open": self.csdata["open"][idx],
                "high": self.csdata["high"][idx],
                "low": self.csdata["low"][idx],
                "close": self.csdata["closed"][idx],
                "volume": self.csdata["volume"][idx],
                "basevolume": self.csdata["basevolume"][idx]
                }

        if ta is not None:
            for name in self.tadata:
                if not numpy.isnan(self.tadata[name][idx]):
                    candle.update({name : self.tadata[name][idx]})

        return candle


    def getAnalyzer():
        return self.analyzer


    def getMarket(self):
        return self.market


    def getName(self):
        return self.name


    def getInfo(self,query=None):
        return {}


    def getIndicators(self):
        return self.indicators


    def loadCandlesticks(self,csdata=None):
        if csdata == None:
            self.csdata = self.trader.get_candlesticks(self.timeframe,size=self.candlesize,base_size=self.basesize)
        else:
            self.csdata = csdata

        self.analyzer = Analyzer( self.csdata )

