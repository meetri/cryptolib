import os,sys,talib,numpy,math,logging,time,datetime,numbers
from collections import OrderedDict

from baseindicator import BaseIndicator

class VolumeBases(BaseIndicator):

    def __init__(self,csdata, vsma, config = {}):
        BaseIndicator.__init__(self,csdata,config)

        self.vmx = config.get("vmx",10)
        self.md = config.get("md",0.004)
        self.vsma = vsma

        self.data = self.getBases()


    def getBases(self):
        bases = []
        for idx,t in enumerate( self.csdata["time"]):
            if not numpy.isnan(self.csdata["volume"][idx]) and not numpy.isnan(self.vsma[idx]):
                mx = self.csdata["volume"][idx] / self.vsma[idx]
                if mx > self.vmx:
                    self.addBase(bases,idx,"low")
                    self.addBase(bases,idx,"high")

        return bases


    def addBase(self, bases, idx, item ):
        price = self.csdata[item][idx]
        found = False
        for base in bases:
            df = max(price,base['price']) / min(price,base['price'])
            df -= 1
            if df <= self.md:
                found = True

        if not found:
            bases.append({
                "price": price,
                "item": item,
                "candle": self.csdata["time"][idx]
            })
