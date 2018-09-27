import os
import requests
import json


class GenericApi(object):

    def __init__(self, config):

        self.timeout = 4
        self.api_root = config.get("apiroot")

        self.response = None
        self.data = None

        self.headers = {
            "Content-Type": "application/json",
        }

    def process(self, api_path, payload=None):

        appendchar = "?"
        if appendchar in api_path:
            appendchar = "&"

        api_root = self.api_root

        uri = "{}{}{}".format(api_root,appendchar,api_path)

        print(uri)
        if payload is None:
            self.response = requests.get(uri, headers = self.headers, timeout=self.timeout)
        else:
            self.response = requests.post(uri, data=json.dumps(payload), headers=self.headers, timeout=self.timeout)

        self.response.raise_for_status()
        self.data = self.response.json()

        return self

    def top_markets(self,limit=10,basecurrency='BTC'):
        return self.process("data/top/volumes?tsym={}&limit={}".format(basecurrency,limit))


    def get_market_average(self,exchanges,market):
        marr = market.split("-")
        base = marr[0]
        token = marr[1]
        req = "data/generateAvg?fsym={}&tsym={}&e={}".format(token,base,exchanges)
        return self.process(req)


    def rate_limit(self,limit="minute"):
        return self.process("stats/rate/{}/limit".format(limit))


    def get_news(self,feeds="",categories="",sortOrder="latest"):
        req = "data/v2/news/?feed={},categories={},sortOrder={}".format(feeds,categories,sortOrder)
        return self.process(req)


    def get_candles(self,exchange,market,period):
        marr = market.split("-")
        base = marr[0]
        token = marr[1]

        if period == "1m":
            req = "data/histominute?fsym={}&tsym={}&aggregate=1&e={}".format(token,base,exchange)
            return self.process(req)
        elif period == "1h":
            req = "data/histohour?fsym={}&tsym={}&aggregate=1&e={}".format(token,base,exchange)
            return self.process(req)
        elif period == "1d":
            req = "data/histoday?fsym={}&tsym={}&aggregate=1&e={}".format(token,base,exchange)
            return self.process(req)


    def data_coinlist(self):
        return self.process("data/all/coinlist")


    def data_socialstats(self,cc_id):
        return self.process("api/data/socialstats?id={}".format(cc_id),api_root="https://www.cryptocompare.com/")

