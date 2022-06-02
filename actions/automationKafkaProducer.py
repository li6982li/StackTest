from kafka import KafkaProducer

from st2common.runners.base_action import Action
import json
import logging
class LMACProducer(Action):
    def run(self,tickets):
        print(tickets)

        tickets = eval(tickets)
        print(tickets)
        tickets = tickets["payload"]["message"]
        ips = tickets["ips"].split(",")
        try:
            producer = KafkaProducer(bootstrap_servers=ips)
        except Exception as e:
            print("connect error:%s" % e)
            return "Failed:%s" % e
        try:
            msg = json.dumps(tickets).encode()
            producer.send(tickets["topic"], msg).get()
            producer.close()
            return "Success"
        except Exception as e:
            print("send error:%s" % e)
            return "Failed：%s" % e

        finally:
            producer.close()
