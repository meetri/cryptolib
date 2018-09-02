import os,urllib.parse
from twilio.rest import Client

class TwilioSms(object):

    def __init__(self,sms_from=None,sid=None,token=None):
        self.sms_from = os.getenv("TWILIO_FROM",sms_from)
        sid = urllib.parse.quote_plus(os.getenv("TWILIO_SID",sid))
        token = urllib.parse.quote_plus(os.getenv("TWILIO_TOKEN",token))
        self.client = Client(sid, token)


    def send( self,msg, number):
        numlist = number.split(",")
        for num in numlist:
            num = num.strip()
            message = self.client.messages.create(to=num, from_= self.sms_from , body=msg)

