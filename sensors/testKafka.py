import sys
import json
from st2reactor.sensor.base import Sensor
from kafka import KafkaConsumer


class KafkaMessageSensor(Sensor):
    """
    Read multiple topics from Apache Kafka cluster and auto-commit offset (mark tasks as finished).
    If responded topic message is JSON - try to convert it to object for reuse inside st2.
    """
    TRIGGER = 'kafka.lyn_test'

    def __init__(self, sensor_service, config=None):
        """
        Parse config variables, set defaults.
        """
        super(KafkaMessageSensor, self).__init__(sensor_service=sensor_service, config=config)
        self._logger = self._sensor_service.get_logger(__name__)

        message_sensor = self._config.get('message_sensor')
        if not message_sensor:
            raise ValueError('[KafkaMessageSensor]: "message_sensor" config value is required!')

        self._hosts = message_sensor.get('hosts')
        if not self._hosts:
            raise ValueError(
                '[KafkaMessageSensor]: "message_sensor.hosts" config value is required!')

        self._topics = set(message_sensor.get('topics', []))
        if not self._topics:
            raise ValueError(
                '[KafkaMessageSensor]: "message_sensor.topics" should list at least one topic!')

        # set defaults for empty values
        self._group_id = message_sensor.get('group_id')
        self._client_id = message_sensor.get('client_id')
        self._consumer = None

    def setup(self):
        """
        Create connection and initialize Kafka Consumer.
        """
        self._logger.debug('[KafkaMessageSensor]: Initializing consumer ...')
        self._consumer = KafkaConsumer(*self._topics,
                                       client_id=self._client_id,
                                       group_id=self._group_id,
                                       bootstrap_servers=self._hosts,
                                      )
        # self._ensure_topics_existence()

    def _ensure_topics_existence(self):
        """
        Ensure that topics we're listening to exist.
        Fetching metadata for a non-existent topic will automatically try to create it
        with the default replication factor and number of partitions (default server config).
        Otherwise Kafka server is not configured to auto-create topics and partitions.
        """
        map(self._consumer._client.ensure_topic_exists, self._topics)
        self._consumer.set_topic_partitions(*self._topics)

    def run(self,):
        """
        Run infinite loop, continuously reading for Kafka message bus,
        dispatch trigger with payload data if message received.
        """
        self._logger.debug('[KafkaMessageSensor]: Entering into listen mode ...')

        while True:
            consumer_records_dict = self._consumer.poll(timeout_ms=100)
            for key, record_list in consumer_records_dict.items():
                for message in record_list:
                    self._logger.debug(
                        "[KafkaMessageSensor]: Received %s:%d:%d: key=%s message=%s" %
                        (message.topic, message.partition,
                         message.offset, message.key, message.value)
                    )
                    topic = message.topic
                    # if sys.version_info.major >= 3:
                    #     topic = topic.decode('utf-8')
                    payload = {
                        'topic': topic,
                        'partition': message.partition,
                        'offset': message.offset,
                        'key': message.key,
                        'message': message.value,
                    }
                    print(payload)
                    self._sensor_service.dispatch(trigger=self.TRIGGER, payload=payload)
                    # Mark this message as fully consumed
                    self._consumer.task_done(message)
                    self._consumer.commit()

    def cleanup(self):
        """
        Close connection, just to be sure.
        """
        # self._consumer._client.close()
        pass

    def add_trigger(self, trigger):
        pass

    def update_trigger(self, trigger):
        pass

    def remove_trigger(self, trigger):
        pass

