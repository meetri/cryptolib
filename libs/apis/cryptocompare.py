import os
import requests
import json

class CryptoCompare(object):

    def __init__(self,appname="cryptodata"):
        self.name = "cryptocompare"
        self.timeout = 4
        self.api_root = "https://min-api.cryptocompare.com/"

        self.app_name = appname

        self.response = None
        self.data = None

        self.headers = {
            "Content-Type": "application/json",
        }

    def process(self, api_path, payload = {}, api_root = None):

        appendchar = "?"
        if appendchar in api_path:
            appendchar = "&"

        if api_root is None:
            api_root = self.api_root

        uri = "{}{}{}extraParams={}".format(api_root,api_path,appendchar,self.app_name)

        self.response = requests.post( uri , data = json.dumps(payload) , headers = self.headers, timeout=self.timeout )
        self.response.raise_for_status()
        self.data = self.response.json()

        return self


    def data_coinlist(self):
        return self.process("data/all/coinlist")


    def data_socialstats(self,cc_id):
        return self.process("api/data/socialstats?id={}".format(cc_id),api_root="https://www.cryptocompare.com/")

