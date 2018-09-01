import random,uuid,os
from datetime import datetime
from mongowrapper import MongoWrapper
from twiliosms import TwilioSms


class TradeWallet(object):

    def __init__( self, config = {}):
        self.buys = []
        self.rejected = []
        self.sells = []
        self.reports = []
        # self.sell_queue = []
        self.mode = config.get("mode","simulation")
        self.name = config.get("name","sim1")
        self.market = config.get("market","")
        self.sync = config.get("sync",True)
        self.scale = config.get("scale",8)
        self.maxtrades = config.get("trades",5)

        if self.scale == 2:
            self.budget = config.get("budget",500)
        else:
            self.budget = config.get("budget",0.5)
            #self.qtyVal = config.get("qtyVal",0.02) # in bitcoin

        self.qtyVal = self.budget / self.maxtrades

        self.sellGoalPercent= config.get("sellGoalPercent",0.05)

        self.sms = TwilioSms()
        self.notifyList = os.getenv("TRADEBOT_NOTIFY","")

        #mongodb
        self.mongo = MongoWrapper.getInstance().getClient()


    def notify(self,msg):
        if self.sync:
            if len(msg) > 0:
                nl = self.notifyList.split(",")
                for number in nl:
                    self.sms.send(msg,number)


    def getResults(self, lastprice = None ):

        totalShorts = 0
        for trade in self.sells:
            if trade["type"] in ["short"]:
                totalShorts+=1

        openTrades = 0
        totalprofit = 0
        for trade in self.buys:
            if trade["status"] not in ["sold","forsale"]:
                openTrades+=1
                if lastprice is not None:
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
            doc = { 'name': self.name, 'mode': self.mode, 'buys': self.buys, 'sells': self.sells, 'rejected': self.rejected }
            return self.mongo.crypto.wallet.replace_one({'name':self.name},doc,upsert=True)


    def load(self):
        if self.sync:
            res = self.mongo.crypto.wallet.find_one({'name':self.name})
            if res is not None and 'name' in res:
                self.mode = res['mode']
                self.buys = res['buys']
                self.sells = res['sells']
                if "rejected" in res:
                    self.rejected = res['rejected']
            return res


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


    def short(self, candle, goalPercent=None, goalPrice=None, priceOverride = None, signals = None, timeIndex = None):
        '''used as an indicator predicting the market will be taking a down turn'''

        if self.mode == "simulation":
            utcnow = candle['date']
        else:
            utcnow = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        if priceOverride is not None:
            price = priceOverride
        else:
            price = candle['high']

        if goalPrice is None:
            if goalPercent is None:
                goalPercent = self.sellGoalPercent
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

    def buyCheck(self, buyobj ):

        res = self.getResults()
        if res['openTrades'] >= self.maxtrades:
            return False

        return True


    def buy(self, goalPercent=None, goalPrice=None, price= None, signals = None, timeIndex = None, candle=None, qty = None):
        '''create new buy order'''

        if self.mode == "simulation":
            utcnow = candle['date']
        else:
            utcnow = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        if goalPrice is None:
            if goalPercent is None:
                goalPercent = self.sellGoalPercent
            goalPrice = self.getPriceFromPercent(price,goalPercent)

        if qty is None:
            qty = self.qtyVal / price

        buyid = str(uuid.uuid4())
        buyObj = {
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
            }

        if self.buyCheck(buyObj):
            self.buys.append( buyObj )
        else:
            self.rejected.append ( buyObj )

        self.notify("Market {} buy {} units  @ {}".format(self.market,buyObj["qty"],buyObj["price"]))

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

        self.notify("Market {} sold {} units  @ {}".format(self.market,buydata["qty"],buydata["price"]))

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

