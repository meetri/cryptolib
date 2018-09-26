import os,sys,json,time
curdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append( os.getenv("CRYPTO_LIB","/projects/apps/shared/crypto") )

import cryptolib
from bittrex import Bittrex
from mongowrapper import MongoWrapper

class CoinWatch(object):

    def __init__(self, config={}):
        self.bittrex = Bittrex()
        self.mongo = MongoWrapper.getInstance().getClient()
        self.history = None
        self.pendingorders = None
        self.bal = None

    def setupWatch(self):
        res = self.mongo.crypto.drop_collection("watch")
        #res = self.mongo.crypto.create_collection("watch")
        #res = self.mongo.crypto.watch.create_index([("name",pymongo.ASCENDING)],unique=True)

    def updateWatch(self, market, exchange="bittrex"):
        if market is not None:
            doc = {"name": market, "exchange": exchange}
            return self.mongo.crypto.watchlist.replace_one({'name':market},doc,upsert=True)

    def update(self, watch):
        if "name" in watch:
            return self.mongo.crypto.watchlist.replace_one({'name':watch['name']},watch,upsert=True)

    def removeWatch(self, market):
        if market is not None:
            return self.mongo.crypto.watchlist.delete_one({'name':market})


    def loadWatchList(self):
        res = self.mongo.crypto.watchlist.find({})
        return res


    def refresh(self):
        self.history  = self.bittrex.account_get_orderhistory().data["result"]
        self.bal = self.bittrex.account_get_balances().data["result"]
        self.pendingorders = self.bittrex.market_get_open_orders().data["result"]

    def tableize(self, rows):
        mincol = []
        if len(rows) == 0:
            return

        for head in rows[0]:
            mincol.append(len(head))

        for row in rows:
            for idx,head in enumerate(row):
                col = str(row[head])
                l = mincol[idx]
                mincol[idx] = max(len(col),l)

        for idx,head in enumerate(rows[0]):
            print("{}".format(head.ljust(mincol[idx]+2)),end="")
        print("")

        for row in rows:
            for idx,head in enumerate(row):
                col = str(row[head])
                print("{}".format(col.ljust(mincol[idx]+2)),end="")
            print("")


    def getPricePercentDif(self, price1, price2):
        return ((price1 - price2) * 100) / price1

    def order_summary(self, currency):
        orders = []
        for idx,order in enumerate(reversed(self.history)):
            if order["Exchange"].endswith("-{}".format(currency)):
                orders.append(order)

        qty = 0
        olist  = []
        for order in orders:
            if order["OrderType"] == "LIMIT_BUY":
                olist.append({'market':order["Exchange"],'qty':order["Quantity"],"price":order["PricePerUnit"]})
            elif order["OrderType"] == "LIMIT_SELL":
                qty = order["Quantity"]
                for buy in olist:
                    rem = buy['qty']-qty
                    if rem <= 0:
                        olist.remove(buy)
                    else:
                        buy['qty'] -= qty

        markets = {}

        for order in olist:
            market = order["market"]
            if market not in markets:
                markets[market] = self.buildWatcher(order={
                    "market": market,
                    "price": order["price"],
                    "qty": order["qty"],
                    "orders": 1
                    })
            else:
                markets[market]["price"] += order["price"]
                markets[market]["qty"] += order["qty"]
                markets[market]["orders"] += 1


        for market in markets:
            tick = self.bittrex.public_get_ticker(market).data["result"]
            markets[market]['price'] /= markets[market]['orders']
            markets[market]['last'] = tick['Last']
            markets[market]['bid'] = tick['Bid']
            markets[market]['ask'] = tick['Ask']
            markets[market]['dif'] = self.getPricePercentDif( tick["Last"], markets[market]['price'])
            markets[market]['total'] = markets[market]['qty'] * tick["Last"]
            # markets[market][''] = markets[market]['qty'] * markets[market]['price']

        return markets

    def buildWatcher(self, order):
        obj = {
            "market": "",
            "price": 0,
            "qty": 0,
            "orders": 0,
            "last": 0,
            "bid": 0,
            "ask": 0,
            "dif": 0,
            "total": 0,
        }
        obj.update(order)
        return obj

    def cancelOrder(self,orderId):
        mc = self.bittrex.market_cancel(orderId)
        return mc.data["success"]

    def parsePending(self):
        if self.pendingorders is None:
            self.refresh()

        out = []
        for order in self.pendingorders:
            out.append({
               "oid": order["OrderUuid"],
               "exchange": order["Exchange"],
               "type": order["OrderType"],
               "qty": order["Quantity"],
               "remaining": order["QuantityRemaining"],
               "Limit": "{:.08f}".format(order["Limit"]),
               "Openend": order["Opened"],
               "Closed": order["Closed"],
               #"Cancelled": order["ImmediateOrCancelled"]
               })

        return out



    def parse(self):
        if self.bal is None:
            self.refresh()

        acc = []
        rows = []
        for account in self.bal:
            if account['Balance'] > 0:
                if account["Currency"] not in ["USDT","BTC"]:
                    summary = self.order_summary(account["Currency"])
                    rows.append(summary)
                    acc.append(account)

        out = []
        for row in rows:
            for market in row:
                m = row[market]
                out.append(m)

        return out
