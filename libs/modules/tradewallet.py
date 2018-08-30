import random
from datetime import datetime


class TradeWallet(object):

    def __init__( self, config = {}):
        self.buys = []
        self.sells = []
        self.reports = []
        self.completed = []
        # self.sell_queue = []
        self.mode = config.get("mode","simulation")

        # self.startBuyHandler()
        # self.startSellHandler()


    def report(self, candle, signals = None, timeIndex = None ):
        if self.mode == "simulation":
            utcnow = candle['date']
        else:
            utcnow = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        self.reports.append( {
            'type': 'report',
            'date': utcnow,
            'index': timeIndex,
            'candle': candle['date'],
            'price': candle['close'],
            'signals': signals
            })

    def short(self, candle, goalPercent=0.05, goalPrice=None, priceOverride = None, signals = None, timeIndex = None):
        '''create new buy order'''

        if self.mode == "simulation":
            utcnow = candle['date']
        else:
            utcnow = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        if priceOverride is not None:
            price = priceOverride
        else:
            price = candle['high']

        if goalPrice is None:
            goalPrice = self.getPriceFromPercent(price,goalPercent)

        sellid= random.randint(1000,99999)
        self.sells.append( {
            'id': sellid,
            'status': 'pending',
            'type': 'short',
            'index': timeIndex,
            'date': utcnow,
            'candle': candle['date'],
            'price': price,
            'signals': signals
            } )


    def getSignals(self):
        sigevent = []
        sigevent.extend(self.buys)
        sigevent.extend(self.sells)
        sigevent.extend(self.reports)
        return sigevent


    def buy(self, candle, goalPercent=0.05, goalPrice=None, priceOverride = None, signals = None, timeIndex = None):
        '''create new buy order'''

        if self.mode == "simulation":
            utcnow = candle['date']
        else:
            utcnow = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        if priceOverride is not None:
            price = priceOverride
        else:
            price = candle['close']

        if goalPrice is None:
            goalPrice = self.getPriceFromPercent(price,goalPercent)

        buyid= random.randint(1000,99999)
        self.buys.append( {
            'id': buyid,
            'sell_id': None,
            'status': 'pending',
            'type': 'buy',
            'date': utcnow,
            'candle': candle['date'],
            'index': timeIndex,
            'price': price,
            'goalPercent': goalPercent,
            'goalPrice': goalPrice,
            'signals': signals
            } )


    def sell(self, buydata, saledata, signals = None, timeIndex = None ):
        '''place buy order in sell queue'''

        sellid = random.randint(1000,99999)
        buydata['sell_id'] = sellid

        self.sells.append({
                'id': sellid,
                'status': 'pending',
                'type': 'sell',
                'date': saledata['date'],
                'index': timeIndex,
                'price': saledata['price'],
                'buy_price': buydata['price'],
                'buy_id': buydata['id'],
                'signals': signals
                })


    # TODO:
    def getPriceFromPercent(self, price, percent ):
        return (price * percent) + price


    def isForSale(self, candle, price, buydata):
        goalPrice = buydata['goalPrice']
        if goalPrice is None:
            goalPrice = self.getPriceFromPercent(buydata['price'],buydata['goalPercent'])

        if self.mode == "simulation":
            utcnow = candle['date']
        else:
            utcnow = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        forsale = price >= goalPrice

        return {
                "status": forsale,
                "price":price,
                "date": utcnow,
                "buy":buydata['price'],
                "goal":goalPrice,
                "goalPercent": buydata['goalPercent']
                }


    def checkSales(self,candle, price, timeIndex = None, shortScore = 0):
        for buydata in self.buys:
            if buydata['sell_id'] is None:
                sale = self.isForSale(candle,price,buydata)
                if sale['status']:
                    self.sell( buydata, sale, timeIndex=timeIndex )

