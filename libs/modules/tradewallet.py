import random,uuid
from datetime import datetime
from mongowrapper import MongoWrapper


class TradeWallet(object):

    def __init__( self, config = {}):
        self.buys = []
        self.sells = []
        self.reports = []
        self.completed = []
        # self.sell_queue = []
        self.mode = config.get("mode","simulation")
        self.name = config.get("name","sim1")
        self.sync = config.get("sync",True)

        #mongodb
        self.mongo = MongoWrapper.getInstance().getClient()


    def getResults(self, lastprice ):

        totalShorts = 0
        for trade in self.sells:
            if trade["type"] in ["short"]:
                totalShorts+=1

        openTrades = 0
        totalprofit = 0
        for trade in self.buys:
            if trade["status"] not in ["sold","forsale"]:
                openTrades+=1
                totalprofit += (lastprice - trade["price"])*trade["qty"]

        total = 0
        totalSells = 0
        for trade in self.sells:
            if trade["type"] == "sell":
                totalSells += 1
                profit = (trade["price"] - trade["buy_price"]) * trade["qty"]
                # print("{:.8f}-{:.8f}={:.8f}".format(trade['price'],trade['buy_price'],profit))
                total += profit

        totalTrades = totalSells  + len(self.buys)

        return {
                "totalTrades": totalTrades,
                "totalBuys": len(self.buys),
                "totalSells": totalSells,
                "totalShorts": totalShorts,
                "openTrades": openTrades,
                "sellprofit": "{:.8f}".format(total),
                "openprofit": "{:.8f}".format(totalprofit),
                "totalprofit": "{:.8f}".format(totalprofit+total)
                }



    def setup(self):
        res = self.mongo.crypto.drop_collection("wallet")
        res = self.mongo.crypto.wallet.create_index([("name",pymongo.ASCENDING)],unique=True)


    def update(self):
        if self.sync:
            doc = { 'name': self.name, 'mode': self.mode, 'buys': self.buys, 'sells': self.sells, 'completed': self.completed }
            return self.mongo.crypto.wallet.replace_one({'name':self.name},doc,upsert=True)


    def load(self):
        if self.sync:
            res = self.mongo.crypto.wallet.find_one({'name':self.name})
            if res is not None and 'name' in res:
                self.mode = res['mode']
                self.buys = res['buys']
                self.sells = res['sells']
                self.completed = res['completed']
            return res

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

        # sellid= random.randint(1000,99999)
        sellid = str(uuid.uuid4())
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

        self.update()


    def getSignals(self):
        sigevent = []
        sigevent.extend(self.buys)
        sigevent.extend(self.sells)
        sigevent.extend(self.reports)
        return sigevent


    def buy(self, goalPercent=0.05, goalPrice=None, price= None, signals = None, timeIndex = None, candle=None):
        '''create new buy order'''

        if self.mode == "simulation":
            utcnow = candle['date']
        else:
            utcnow = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        if goalPrice is None:
            goalPrice = self.getPriceFromPercent(price,goalPercent)

        qty = 0.01 / price
        # buyid= random.randint(1000,99999)
        buyid = str(uuid.uuid4())
        self.buys.append( {
            'id': buyid,
            'sell_id': None,
            'status': 'pending',
            'type': 'buy',
            'date': utcnow,
            'candle': candle['date'],
            'index': timeIndex,
            'price': price,
            'qty': qty,
            'goalPercent': goalPercent,
            'goalPrice': goalPrice,
            'signals': signals
            } )

        self.update()


    def sell(self, buydata, saledata, signals = None, timeIndex = None ):
        '''place buy order in sell queue'''

        # sellid = random.randint(1000,99999)
        sellid = str(uuid.uuid4())
        buydata['sell_id'] = sellid
        buydata["status"] = "sold"

        self.sells.append({
                'id': sellid,
                'status': 'pending',
                'type': 'sell',
                'date': saledata['date'],
                'index': timeIndex,
                'price': saledata['price'],
                'qty': buydata['qty'],
                'buy_price': buydata['price'],
                'buy_id': buydata['id'],
                'signals': signals
                })

        self.update()


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

