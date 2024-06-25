import general_txt
from datetime import datetime
import paho.mqtt.client as mqtt
import json
import time
from xmlrpc.server import SimpleXMLRPCServer
from threading import Thread
import uuid

DIRECTION_STOP = "stop"

DIRECTION_FORWARDS = "forwards"

DIRECTION_BACKWARDS = "backwards"


def _calculate_color(value):
    color_red_lower = 1200
    color_blue_lower = 1500
    if value <= color_red_lower:
        return 'white'
    elif color_red_lower < value < color_blue_lower:
        return 'red'
    else:
        return 'blue'

class SortingMachineTXT(general_txt.GeneralTXT):
    def __init__(self, txt_number: int):
        super(SortingMachineTXT, self).__init__(txt_number)
        self.c2 = self.txt.colorsensor(2)

        # Motor speed
        self.m1_speed = 512

        # Start Threads
        threads = [
            Thread(target=self.execution_rpc_server),
            Thread(target=self.getter_setter_rpc_server),
            Thread(target=self.rpc_server_pwm),
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
        print(f"Started the MQTT Publisher for TXT{self.txt_number} - Topic-Name: {self.mqtt_topic_name}")
        while True:
            payload = {
                "id": str(uuid.uuid4()),
                "station": self.mqtt_topic_name.replace("FTFactory/", ""),
                "timestamp": str(datetime.now())[:-4],
                'i1_light_barrier': self.i1.state(),
                'i2_color_sensor': self.c2.value(),
                'i3_light_barrier': self.i3.state(),
                'i6_light_barrier': self.i6.state(),
                'i7_light_barrier': self.i7.state(),
                'i8_light_barrier': self.i8.state(),
                'm1_speed': self.txt.getPwm(0) - self.txt.getPwm(1),  # self.get_motor_speed(1),
                'o5_valve': self.txt.getPwm(4),
                'o6_valve': self.txt.getPwm(5),
                'o7_valve': self.txt.getPwm(6),
                'o8_compressor': self.txt.getPwm(7),
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
        server.register_function(self.is_connected, "is_connected")
        server.register_function(self.sort, "sort")
        # server.register_function(self.detect_color, "detect_color")
        # server.register_function(self.move_workpiece_from_lb_3_towards_sink, "move_workpiece_from_lb_3_towards_sink")
        # server.register_function(self.eject_workpiece_into_sink, "eject_workpiece_into_sink")
        # server.register_function(self.move_forwards_to_light_barrier, "move_forwards_to_light_barrier")
        # server.register_function(self.move_backwards_to_light_barrier, "move_backwards_to_light_barrier")
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
        server.register_function(self.status_of_light_barrier, "status_of_light_barrier")
        server.register_function(self.get_motor_speed, "get_motor_speed")
        server.register_function(self.set_motor_speed, "set_motor_speed")
        server.register_function(self.reset_all_motor_speeds, "reset_all_motor_speeds")
        server.register_function(self.detect_color, "detect_color")
        print(f"Started the getter_setter_rpc_server for TXT{self.txt_number}")
        server.serve_forever()

    def rpc_server_pwm(self) -> None:
        """
        RPC-Server-Thread for PWM
        # TODO Implement
        :return: None
        """
        SimpleXMLRPCServer.allow_reuse_address = True
        server = SimpleXMLRPCServer(("localhost", self.rpc_port + 1000), logRequests=False, allow_none=True)
        print(f"Started the RPC Server for TXT{self.txt_number} PWM")
        server.serve_forever()

    def set_motor_speed(self, motor: int, new_speed: int) -> None:
        """
        Sets the speed of the motor to the value specified
        :param motor: Motor to set speed for
        :param new_speed: Speed to set
        :raises ValueError when trying to access a hardware which doesn't exist
        :return: None
        """
        if new_speed > 512:
            new_speed = 512
        if new_speed < -512:
            new_speed = -512
        if motor == 1:
            self.m1_speed = new_speed
            return
        else:
            raise ValueError(f"Trying to access non-existing motor {motor}")

    def reset_all_motor_speeds(self) -> None:
        """
        Resets all motor speeds to the maximum
        :return: None
        """
        self.m1_speed = 512
        return

    def get_motor_speed(self, motor: int) -> int:
        """
        Gets the speed of the specified motor
        :raises ValueError when trying to access a hardware which doesn't exist
        :return: Motor speed
        """
        if motor == 1:
            return self.m1_speed
        else:
            raise ValueError(f"Trying to access non-existing motor {motor}")

    def _move_motor_forwards(self, distance: int = 1000) -> None:
        """
        Starts m1
        :param distance: Distance to drive, default: infinite
        :return: None
        """
        #self.logger.debug(f"distance: {distance}")
        self.m1.setSpeed(-1 * self.m1_speed)
        self.m1.setDistance(distance)
        if distance != 1000:
            while not self.m1.finished():
                pass
            self.m1.stop()
            # self.m1.setDistance(0)

    def _move_motor_backwards(self, distance: int = 1000) -> None:
        """
        Stops m1
        :param distance: Distance to drive, default: infinite
        :return: None
        """
        #self.logger.debug(f"distance: {distance}")
        self.m1.setSpeed(self.m1_speed)
        self.m1.setDistance(distance)
        if distance != 1000:
            while not self.m1.finished():
                pass
            self.m1.stop()

    def is_workpiece_in_sink(self, sink: int) -> bool:
        """
        Returns TRUE if the light barrier in the sink is interrupted --> workpiece ready for pick up
        if the light barrier is not interrupted this method returns False  --> no workpiece in sink
        :raises ValueError when trying to access a hardware which doesn't exist
        :param sink: Number of sink
        :return: Light barrier interruption status interrupted <-> True , uninterrupted <-> False
        """
        if sink == 1:
            result = self.i6.state() == 0
            # self.logger.debug(f"State of workpiece in {sink} is {result}")
            return result
        elif sink == 2:
            result = self.i7.state() == 0
            # self.logger.debug(f"State of workpiece in {sink} is {result}")
            return result
        elif sink == 3:
            result = self.i8.state() == 0
            # self.logger.debug(f"State of workpiece in {sink} is {result}")
            return result
        else:
            #self.logger.error(f"Trying to access non-existing sink {sink}")
            raise ValueError(f"Sink {sink} does not exist")

    def status_of_light_barrier(self, lb: int) -> bool:
        """
        Returns TRUE if the light barrier is interrupted else False
        :raises ValueError when trying to access a hardware which doesn't exist
        :param lb: Number of light barrier to check
        :return: Light barrier interruption status interrupted <-> True , uninterrupted <-> False
        """
        if lb == 1:
            result = self.i1.state() == 0
            # self.logger.debug(f"State of workpiece in {lb} is {result}")
            return result
        elif lb == 3:
            result = self.i3.state() == 0
            # self.logger.debug(f"State of workpiece in {lb} is {result}")
            return result
        elif lb == 6:
            result = self.i6.state() == 0
            # self.logger.debug(f"State of workpiece in {lb} is {result}")
            return result
        elif lb == 7:
            result = self.i7.state() == 0
            # self.logger.debug(f"State of workpiece in {lb} is {result}")
            return result
        elif lb == 8:
            result = self.i8.state() == 0
            # self.logger.debug(f"State of workpiece in {lb} is {result}")
            return result
        else:
            #self.logger.error(f"Trying to access non-existing light barrier {lb}")
            raise ValueError(f"Light Barrier {lb} does not exist")

    def move_conveyor_belt(self, direction: str) -> None:
        """
        Starts or stops the conveyor belt
        :raises ValueError when trying to access an unsupported direction
        :param direction: Forwards, backwards or stop
        :return: None
        """
        if direction == DIRECTION_BACKWARDS:
            #self.logger.debug(f"Setting the direction of the conveyor belt to {direction}")
            self._move_motor_backwards()
        elif direction == DIRECTION_FORWARDS:
            #self.logger.debug(f"Setting the direction of the conveyor belt to {direction}")
            self._move_motor_forwards()
        elif direction == DIRECTION_STOP:
            #self.logger.debug(f"Stopping the conveyor belt")
            self.m1.stop()
        else:
            #self.logger.error(f"Trying to access non-existing direction {direction}")
            raise ValueError(f"Direction {direction} not known")

    def detect_color(self) -> str:
        """
        Detects the color of the workpiece
        :return: Workpiece color
        """
        self.set_current_sub_task_to_detecting_color(1)
        lowest_detected_brightness = 3_000
        white_brightness_limit = 1_200
        red_brightness_limit = 1_500
        self._move_motor_forwards()
        #self.logger.debug(lowest_detected_brightness)
        while self.i3.state() != 0:
            current_brightness = self.c2.value()
            # self.logger.debug(f"cb: {current_brightness}, ldb: {lowest_detected_brightness}")
            if current_brightness != 0 and current_brightness <= lowest_detected_brightness:
                lowest_detected_brightness = current_brightness
                #self.logger.debug(lowest_detected_brightness)
        self.m1.stop()
        #self.logger.debug(f"Detected brightness value is {lowest_detected_brightness}")
        if lowest_detected_brightness < 1200:
            color = "white"
            #self.logger.debug(f"Detected color is {color}")
            return "white"
        elif 1200 <= lowest_detected_brightness <= 1500:
            color = "red"
            #self.logger.debug(f"Detected color is {color}")
            return color
        elif 1500 < lowest_detected_brightness <= 1620:
            color = "blue"
            return color
        else:
            color = "none"
            #self.logger.debug(f"Detected color is {color}")
            return color

    def eject_workpiece_into_sink(self, sink: int) -> None:
        """
        Pushes a workpiece into the sink specified
        :raises ValueError when trying to access a hardware which doesn't exist
        :param sink: Sink to push into
        :return: None
        """
        #self.logger.debug(f"Ejecting workpiece into sink {sink}")
        if 1 <= sink <= 3:
            self.o8.setLevel(512)  # Compressor on
            self.set_current_sub_task_to_eject(f"sink {sink}", 1)
            time.sleep(0.5)
            if sink == 1:
                self.o5.setLevel(512)  # First ejector piston valve
                time.sleep(0.5)
                self.o8.setLevel(0)
                time.sleep(0.5)
                self.o5.setLevel(0)
            elif sink == 2:
                self.o6.setLevel(512)  # Second ejector piston valve
                time.sleep(0.5)
                self.o8.setLevel(0)
                time.sleep(0.5)
                self.o6.setLevel(0)
            elif sink == 3:
                self.o7.setLevel(512)  # Third ejector piston valve
                time.sleep(0.5)
                self.o8.setLevel(0)
                time.sleep(0.5)
                self.o7.setLevel(0)
        else:
            #self.logger.error(f"Trying to access non-existing sink {sink}")
            raise ValueError(f"Sink {sink} does not exist")
        return

    def move_workpiece_from_lb_3_towards_sink(self, sink: int) -> None:
        """
        Moves the workpiece from light barrier i3 towards sink
        :raises ValueError when trying to access a hardware which doesn't exist
        :param sink: Sink to move to
        :return: None
        """
        #self.logger.debug(f"Moving the workpiece from light barrier 3 towards sink {sink}")
        if sink == 1:
            self.set_current_sub_task_to_transport("workpiece", f"sink {sink}", 1)
            distance = 3
        elif sink == 2:
            self.set_current_sub_task_to_transport("workpiece", f"sink {sink}", 1)
            distance = 8
        elif sink == 3:
            self.set_current_sub_task_to_transport("workpiece", f"sink {sink}", 1)
            distance = 14
        else:
            #self.logger.error(f"Trying to access non-existing sink {sink}")
            raise ValueError(f"Sink {sink} does not exist")
        self._move_motor_forwards(distance)
        return

    def move_workpiece_towards_drill_or_punch(self) -> None:
        """
        Moves the workpiece from light barrier i3 towards the punching machine
        :return: None
        """
        #self.logger.debug(f"Moving the workpiece from light barrier towards the interchange sink")
        self.set_current_sub_task_to_transport("workpiece", "interchange sink", 1)
        distance = 35
        self._move_motor_forwards(distance)
        return

    def move_backwards_to_light_barrier(self, lb: int) -> None:
        """
        Moves the workpiece from the end of the conveyor belt towards the light barrier
        :raises ValueError when trying to access a hardware which doesn't exist
        :param lb: Light barrier to move to
        :return: None
        """
        #self.logger.debug(f"Moving the workpiece from the end of the conveyor towards light barrier {lb}")
        self._move_motor_backwards()
        if lb == 1:
            self.set_current_sub_task_to_transport("workpiece", f"light barrier {lb}", 1)
            while self.i1.state() != 0:
                pass
            self.m1.stop()
        elif lb == 3:
            self.set_current_sub_task_to_transport("workpiece", f"light barrier {lb}", 1)
            while self.i3.state() != 0:
                pass
            self._move_motor_backwards(6)

            self._move_motor_forwards()
            while self.i3.state() != 0:
                pass
            self.m1.stop()
        else:
            #self.logger.error(f"Trying to access non-existing light barrier {lb}")
            raise ValueError(f"Light Barrier {lb} does not exist")

        return

    def move_forwards_to_light_barrier(self, lb: int) -> None:
        """
        Moves the workpiece from the start of the conveyor belt towards the light barrier
        :raises ValueError when trying to access a hardware which doesn't exist
        :param lb: Light barrier to move to
        :return: None
        """
        #self.logger.debug(f"Moving the workpiece from the start of the conveyor towards light barrier {lb}")
        self._move_motor_forwards()
        if lb == 1:
            self.set_current_sub_task_to_transport("workpiece", f"light barrier {lb}", 1)
            while not self.i1.state() == 0:
                pass
            self.m1.stop()
            self._move_motor_forwards(2)
        elif lb == 3:
            self.set_current_sub_task_to_transport("workpiece", f"light barrier {lb}", 1)
            while not self.i3.state() == 0:
                pass
            self.m1.stop()
        else:
            #self.logger.error(f"Trying to access non-existing light barrier {lb}")
            raise ValueError(f"Light Barrier {lb} does not exist")
        self.m1.stop()
        return

    def sort(self, start: str, use_nfc: bool = False, predefined_ejection_location: str = "none") -> int:
        """
        Starts the sorting process. Default is ejection into the sink determined by the color_detection process
        :param start: position where the workpiece starts the sorting process
        :param use_nfc: Whether to stop to read/ write the NFC tag of the chip
        :param predefined_ejection_location: When using the default "none" the workpiece gets ejected at the sink
        determined by the color detection. When using sink_1, _2 or _3, the workpiece gets ejected into the specified
        sink. When using "corner", the workpiece gets transported to the end of the SM (to the DM/PM corner)
        :raises ValueError: When trying to give illegal arguments
        :return: None
        """
        if (predefined_ejection_location != "sink_1" and
                predefined_ejection_location != "sink_2" and
                predefined_ejection_location != "sink_3" and
                predefined_ejection_location != "corner" and
                predefined_ejection_location != "none"):
            raise ValueError(f"Sink {predefined_ejection_location} is not a valid ejection position")
        if not (start == "initial" or start == "sm_cb"):
            raise ValueError(f"Start {start} is not a valid start position")
        #self.logger.debug("Starting sorting process")
        self.set_current_task_to_sorting(start, use_nfc, predefined_ejection_location, 1)
        if start == "sm_cb":
            self.move_backwards_to_light_barrier(1)
        color = self.detect_color()  # After this method the workpiece is at lb 3 under the nfc reader

        if use_nfc:
            time.sleep(1)  # Placeholder for NFC reader function
            self.set_current_sub_task_to_read_nfc("sorting machine conveyor belt nfc reader", 1)
            self.set_current_sub_task_to_read_nfc("sorting machine conveyor belt nfc reader", 1)

        if predefined_ejection_location == "none":  # Color detection + sink determined by color_detection
            sink_colors = ["white", "red", "blue"]
            eject_pos = sink_colors.index(color) + 1
            self.move_workpiece_from_lb_3_towards_sink(eject_pos)
            self.eject_workpiece_into_sink(eject_pos)
            self.set_current_task("", 1)
            return eject_pos
        else:
            if predefined_ejection_location == "corner":  # Towards pm or dm slider platform
                self.move_workpiece_towards_drill_or_punch()
                self.set_current_task("", 1)
            else:  # Into specified sink
                self.move_workpiece_from_lb_3_towards_sink(int(predefined_ejection_location.split("_")[1]))
                self.eject_workpiece_into_sink(int(predefined_ejection_location.split("_")[1]))
                self.set_current_task("", 1)
