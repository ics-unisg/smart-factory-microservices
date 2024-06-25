import json
from threading import Thread
import time
from datetime import datetime
from xmlrpc.server import SimpleXMLRPCServer

import paho.mqtt.client as mqtt
import general_txt
import uuid


class EnvironmentAndCameraTxt(general_txt.GeneralTXT):

    def __init__(self, txt_number: int):
        super(EnvironmentAndCameraTxt, self).__init__(txt_number)

        self.phototransistor = self.txt.resistor(3)

        # Motor speeds
        self.m1_speed = 512
        self.m2_speed = 512

        # Start Threads
        threads = [
            Thread(target=self.execution_rpc_server),
            Thread(target=self.getter_setter_rpc_server),
            Thread(target=self.stream_data_via_mqtt)
        ]
        [thread.start() for thread in threads]
        [thread.join() for thread in threads]

    def stream_data_via_mqtt(self) -> None:
        """
        Starts the MQTT streaming
        :return: None
        """

        client = mqtt.Client()
        client.connect(self.mqtt_host,1883,60)
        print(
            f"Started the MQTT Publisher for TXT{self.txt_number} - Topic-Name: {self.mqtt_topic_name}")


        while True:
            payload = {
                "id": str(uuid.uuid4()),
                "station": self.mqtt_topic_name.replace("FTFactory/", ""),
                "timestamp": str(datetime.now())[:-4],
                'i1_pos': self.i1.state(),
                'i2_pos': self.i2.state(),
                'i3_photoresistor': self.phototransistor.value(),
                'i5_joystick_x_f': self.i5.state(),
                'i6_joystick_y_f': self.i6.state(),
                'i7_joystick_x_b': self.i7.state(),
                'i8_joystick_y_b': self.i8.state(),

                'current_state': self.current_state,
                'current_task': self.current_task,
                'current_task_duration': self.calculate_elapsed_seconds_since_start(1),
                'current_sub_task': self.current_sub_task,
            }
            json_payload = json.dumps(payload)
            client.publish(topic=self.mqtt_topic_name, payload=json_payload, qos=0, retain=False)
            time.sleep(1 / self.mqtt_publish_frequency)

    def execution_rpc_server(self) -> None:
        """
        RPC-Server-Thread for execution methods which have to be handled one after the other
        :return: None
        """
        SimpleXMLRPCServer.allow_reuse_address = True
        server = SimpleXMLRPCServer(("localhost", self.rpc_port), logRequests=False, allow_none=True)
        print(f"Started the RPC Server for TXT{self.txt_number}")
        server.register_function(self.is_connected, "is_connected")
        server.register_function(self.calibrate, "calibrate")
        server.register_function(self.take_camera_pic, "take_camera_pic")
        server.register_function(self.rotate_camera_cw, "rotate_camera_cw")
        server.register_function(self.rotate_camera_ccw, "rotate_camera_cw")
        server.register_function(self.switch_on_led_camera, "switch_on_led_camera")
        server.register_function(self.switch_off_led_camera, "switch_off_led_camera")
        server.register_function(self.switch_on_led_red, "switch_on_led_red")
        server.register_function(self.switch_on_led_red, "switch_off_led_red")
        server.register_function(self.switch_on_led_yellow, "switch_on_led_yellow")
        server.register_function(self.switch_on_led_yellow, "switch_off_led_yellow")
        server.register_function(self.switch_on_led_green, "switch_on_led_green")
        server.register_function(self.switch_on_led_green, "switch_off_led_green")
        print(f"Started the execution_rpc_server for TXT{self.txt_number}")
        server.serve_forever()

    def getter_setter_rpc_server(self) -> None:
        """
        RPC-Server-Thread for getter and setter methods
        :return: None
        """
        SimpleXMLRPCServer.allow_reuse_address = True
        server = SimpleXMLRPCServer(("localhost", self.rpc_port - 1000), logRequests=False, allow_none=True)
        server.register_function(self.is_connected, "is_connected")
        server.register_function(self.state_of_machine, "state_of_machine")
        print(f"Started the getter_setter_rpc_server for TXT{self.txt_number}")
        server.serve_forever()

    def calibrate(self):
        self.rotate_camera_cw()
        self.tilt_camera_down()

    def take_camera_pic(self):
        self.txt.startCameraOnline()
        time.sleep(2.5)
        pic = self.txt.getCameraFrame()
        return bytearray(pic)

    def rotate_camera_cw(self):
        self.m1.setSpeed(512)
        while not self.i1.state() == 1:
            pass
        self.m1.stop()

    def rotate_camera_ccw(self):
        self.m1.setSpeed(-512)
        while not self.i1.state() == 1:
            pass
        self.m1.stop()

    def tilt_camera_down(self):
        self.m2.setSpeed(512)
        while not self.i2.state() == 1:
            pass
        self.m2.stop()

    def tilt_camera_up(self):
        self.m2.setSpeed(-512)
        while not self.i2.state() == 1:
            pass
        self.m2.stop()

    def switch_on_led_camera(self):
        self.i5.setLevel(512)

    def switch_off_led_camera(self):
        self.i5.setLevel(0)

    def switch_on_led_red(self):
        self.i6.setLevel(512)

    def switch_off_led_red(self):
        self.i6.setLevel(0)

    def switch_on_led_yellow(self):
        self.i7.setLevel(512)

    def switch_off_led_yellow(self):
        self.i7.setLevel(0)

    def switch_on_led_green(self):
        self.i6.setLevel(512)

    def switch_off_led_green(self):
        self.i6.setLevel(0)

    def read_nfc(self):
        #TODO: we need a newer version of ftRoboPy to access i2c (1.88 or higher), also on the controllers (currently 1.87)
        #NFC Reader PN532 V3
        #NFC Tags NTAG213
        #res = self.txt.i2c_read(0x76, 0x3f, data_len=6)
        #x, y, z = struct.unpack('<hhh', res)
        pass

    def write_nfc(self):
        #TODO
        pass