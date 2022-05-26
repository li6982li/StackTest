from kafka import KafkaProducer

from st2common.runners.base_action import Action


class LMACProducer(Action):
    def run(self,tickets):
        print(tickets)
        return tickets
        # try:
        #     ip = cf2.get("kafka", hostList)
        #     ips = ip.split(",")
        #     topic = cf2.get("kafka", topic)
        #     producer = KafkaProducer(bootstrap_servers=ips)
        #
        #     # write into the kafka
        #     try:
        #         msg = json.dumps(data).encode()
        #         producer.send(topic, msg).get()
        #     # write into the kafka fail
        #     except Exception as e:
        #         logging.warning('[%s] product send data to the kafka topic [%s] error %s!' % (data['Incident ID'], topic, e))
        #         writeError(data['Incident ID'], datetime.datetime.now(), data['Summary'], data['Priority'],
        #                    "%s insert kafka topic %s error %s" % (data['Incident ID'], topic, e))
        #         producer.close()
        #         return -1
        #     # write into the kafka success
        #     else:
        #         producer.close()
        #         return 0
        # except Exception as e:
        #     logging.warning('[%s] send data to the kafka topic [%s] error %s!' % (data['Incident ID'], topic, e))
        #     writeError(data['Incident ID'], datetime.datetime.now(), data['Summary'], data['Priority'],
        #                "%s insert kafka topic %s error %s" % (data['Incident ID'], topic, e))
        #     return -1