import os,sys,json,time
curdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append( os.getenv("CRYPTO_LIB","/projects/apps/shared/crypto") )

import cryptolib
from bittrex import Bittrex

class CoinWatch(object):

    def __init__(self, config={}):
        self.bittrex = Bittrex()
        self.history = None
        self.bal = None

    def refresh(self):
        self.history  = self.bittrex.account_get_orderhistory().data["result"]
        self.bal = self.bittrex.account_get_balances().data["result"]

    def tableize(self, rows):
        mincol = []
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
                markets[market] = {
                        'market': market,
                        'price': order['price'],
                        'qty': order['qty'],
                        "orders": 1
                        }
            else:
                markets[market]["price"] += order["price"]
                markets[market]["qty"] += order["qty"]
                markets[market]["orders"] += 1


        for market in markets:
            tick = self.bittrex.public_get_ticker(market).data["result"]
            markets[market]['price'] /= markets[market]['orders']
            markets[market]['lastprice'] = tick['Last']
            markets[market]['bid'] = tick['Bid']
            markets[market]['ask'] = tick['Ask']
            markets[market]['dif'] = self.getPricePercentDif( markets[market]['lastprice'], markets[market]['price'])
            markets[market]['total'] = markets[market]['qty'] * markets[market]['lastprice']
            markets[market]['last'] = markets[market]['qty'] * markets[market]['price']

        return markets

    def parse(self):
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
