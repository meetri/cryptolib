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
        self.exchange = None


    def reset(self):
        self.buys = []
        self.rejected = []
        self.sells = []
        self.reports = []


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
                "last": lastprice,
                "totalTrades": totalTrades,
                "totalBuys": len(self.buys),
                "totalSells": totalSells,
                "totalShorts": totalShorts,
                "openTrades": openTrades,
                "sellprofit": "{:.8f}".format(total),
                "openprofit": "{:.8f}".format(totalprofit),
                "totalprofit": "{:.8f}".format(totalprofit+total)
                }


    def exchangeSync(self):
        if self.exchange is None:
            return

        for buy in self.buys:
            if buy['status'] == 'pending':
                status = self.exchange.getOrderStatus(buy['buy_id'])

        for sell in self.sells:
            if sell['status'] == 'pending':
                status = self.exchange.getOrderStatus(buy['buy_id'])



    def setup(self):
        res = self.mongo.crypto.drop_collection("wallet")
        res = self.mongo.crypto.wallet.create_index([("name",pymongo.ASCENDING)],unique=True)


    def update(self):
        if self.sync:
            doc = { 'name': self.name, 'buys': self.buys, 'sells': self.sells, 'rejected': self.rejected }
            return self.mongo.crypto.wallet.replace_one({'name':self.name},doc,upsert=True)


    def load(self):
        if self.sync:
            res = self.mongo.crypto.wallet.find_one({'name':self.name})
            if res is not None and 'name' in res:
                self.buys = res['buys']
                self.sells = res['sells']
                if "rejected" in res:
                    self.rejected = res['rejected']
            return res


    def report(self, candle, signals = None, timeIndex = None ):
        if self.exchange is None:
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


    def short(self, candle, price = None, signals = None, timeIndex = None):
        '''used as an indicator predicting the market will be taking a down turn'''

        self.checkSales(short=True,candle=candle,price=price,timeIndex=timeIndex,signals=signals)


    def getSignals(self):
        sigevent = []
        sigevent.extend(self.buys)
        sigevent.extend(self.sells)
        #sigevent.extend(self.reports)
        return sigevent


    def buyCheck(self, buyobj ):

        reject = False

        for buy in self.buys:
            if buy['status'] not in ['sold','forsale','error']:
                if buy['candle'] == buyobj['candle']:
                    reject = True

                if buyobj['price'] > buy['price'] - (buy['price'] * 0.03):
                    reject = True


        res = self.getResults()
        price = buyobj["price"]
        if res['openTrades'] >= self.maxtrades:
            reject = True

        return not reject


    def buy(self, goalPercent=None, goalPrice=None, price= None, signals = None, timeIndex = None, candle=None, qty = None):
        '''create new buy order'''

        if self.exchange is None:
            utcnow = candle['date']
        else:
            utcnow = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        if goalPrice is None:
            if goalPercent is None:
                goalPercent = self.sellGoalPercent
            goalPrice = self.getPriceFromPercent(price,goalPercent)

        if qty is None:
            qty = self.qtyVal / price

        buyid = "sim-{}".format(str(uuid.uuid4()))
        buyObj = {
            'id': buyid,
            'sell_id': None,
            'status': 'pending',
            'type': 'buy',
            'date': utcnow,
            'market': self.market,
            'candle': candle['date'],
            'index': timeIndex,
            'price': price,
            'qty': qty,
            'goalPercent': goalPercent,
            'goalPrice': goalPrice,
            'signals': signals
            }

        if self.buyCheck(buyObj):
            if self.exchange is not None:
                buyObj = self.exchange.buy( buyObj )

            self.buys.append( buyObj )
            self.update()
            self.notify("Market {} buy {} units  @ {}".format(self.market,buyObj["qty"],buyObj["price"]))
        else:
            buyObj["status"] = "rejected"
            self.rejected.append ( buyObj )
            self.update()


        return buyObj


    def sell(self, buydata, saledata, signals = None, timeIndex = None):
        '''place buy order in sell queue'''

        sellid = str(uuid.uuid4())
        sellObj = {
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
                }

        if self.exchange is not None:
            sellObj = self.exchange.sell(sellObj)

        buydata['sell_id'] = sellObj["id"]
        buydata["status"] = "sold"

        self.sells.append(sellObj)
        self.update()

        self.notify("Market {} sold {} units  @ {:.8f}".format(self.market,sellObj["qty"],sellObj["price"]))



    # TODO:
    def getPriceFromPercent(self, price, percent ):
        return (price * percent) + price


    def isForSale(self, candle, price, buydata,short=False):
        goalPrice = buydata['goalPrice']
        if goalPrice is None:
            goalPrice = self.getPriceFromPercent(buydata['price'],buydata['goalPercent'])

        if self.exchange is None:
            utcnow = candle['date']
        else:
            utcnow = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        forsale = short or price >= goalPrice

        return {
                "status": forsale,
                "price":price,
                "date": utcnow,
                "buy":buydata['price'],
                "goal":goalPrice,
                "goalPercent": buydata['goalPercent']
                }


    def checkSales(self,candle, price, timeIndex = None, shortScore = 0, short = False, signals = None):
        for buydata in self.buys:
            if buydata['sell_id'] is None:
                sale = self.isForSale(candle,price,buydata,short=short)
                if sale['status']:
                    self.sell( buydata, sale, timeIndex=timeIndex, signals=signals )

