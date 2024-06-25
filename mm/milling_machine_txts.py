import multi_processing_station_txts
from datetime import datetime
import paho.mqtt.client as mqtt
import json
import time
from xmlrpc.server import SimpleXMLRPCServer
from threading import Thread
import uuid

NAME_EJECTION = "ejection"
NAME_INITIAL = "initial"
NAME_MILL = "mill"


class MillingMachineTXT(multi_processing_station_txts.MultiProcessingStationTXT):
    def __init__(self, txt_number):
        super(MillingMachineTXT, self).__init__(txt_number)

        self.m1_speed = 512
        self.m2_speed = 512
        self.m3_speed = 512

        # Start Threads
        self.set_current_task_to_full_calibration(1)
        threads = [
            Thread(target=self.execution_rpc_server),
            Thread(target=self.getter_setter_rpc_server),
            Thread(target=self.pwm_rpc_server),
            Thread(target=self.stream_data_via_mqtt),
            Thread(target=self.calibrate),
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
                'i1_pos_switch': self.i1.state(),
                'i2_pos_switch': self.i2.state(),
                'i3_pos_switch': self.i3.state(),
                'i4_light_barrier': self.i4.state(),
                'm1_speed': self.txt.getPwm(0) - self.txt.getPwm(1),
                'm2_speed': self.txt.getPwm(2) - self.txt.getPwm(3),
                'm3_speed': self.txt.getPwm(4) - self.txt.getPwm(5),
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
        print(f"Started the RPC Server for TXT{self.txt_number}")
        server.register_function(self.is_connected, "is_connected")
        server.register_function(self.calibrate, "calibrate")
        server.register_function(self.mill, "mill")
        server.register_function(self.move_from_to, "move_from_to")
        server.register_function(self.transport_from_to, "transport_from_to")
        server.register_function(self.activate_compressor, "activate_compressor")
        server.register_function(self.deactivate_compressor, "deactivate_compressor")
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
        server.register_function(self.check_position, "check_position")
        server.register_function(self.is_active,"is_active")
        print(f"Started the getter_setter_rpc_server for TXT{self.txt_number}")
        server.serve_forever()

    def is_active(self) -> bool:
        return self.i5.state()

    def pwm_rpc_server(self) -> None:
        """
        RPC-Server-Thread for PWM
        # TODO Implement
        :return: None
        """
        SimpleXMLRPCServer.allow_reuse_address = True
        server = SimpleXMLRPCServer(("localhost", self.rpc_port + 1000), logRequests=False, allow_none=True)
        print(f"Started the pwm_rpc_server for TXT{self.txt_number} PWM")
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
        elif motor == 2:
            self.m2_speed = new_speed
            return
        elif motor == 3:
            self.m3_speed = new_speed
            return
        else:
            raise ValueError(f"Trying to access non-existing motor {motor}")

    def reset_all_motor_speeds(self) -> None:
        """
        Resets all motor speeds to the maximum
        :return: None
        """
        self.m1_speed = 512
        self.m2_speed = 512
        self.m3_speed = 512
        return

    def get_motor_speed(self, motor: int) -> int:
        """
        Gets the speed of the specified motor
        :raises ValueError when trying to access a hardware which doesn't exist
        :return: Motor speed
        """
        if motor == 1:
            return self.m1_speed
        elif motor == 2:
            return self.m2_speed
        elif motor == 3:
            return self.m3_speed
        else:
            raise ValueError(f"Trying to access non-existing motor {motor}")

    def activate_compressor(self) -> None:
        self.o8.setLevel(512)

    def deactivate_compressor(self) -> None:
        self.o8.setLevel(0)

    def calibrate(self) -> None:
        """
        Calibrates M1
        :return: None
        """
        self.set_current_task_to_full_calibration(1)
        self.set_current_sub_task_to_individual_motor_calibration("motor 1", 1)
        self._move_to_initial_position_without_updating_the_current_sub_task()
        self.set_current_task("", 1)
        return

    def _move_to_initial_position_without_updating_the_current_sub_task(self):
        """
        Calibrates M1
        :return: None
        """
        self.m1.setSpeed(self.m1_speed)
        while self.i1.state() == 0:
            pass
        self.m1.stop()
        return

    def status_of_light_barrier(self, lb: int) -> bool:
        """
        Returns TRUE if the light barrier is interrupted else False
        :raises ValueError when trying to access a hardware which doesn't exist
        :param lb: Number of light barrier to check
        :return: Light barrier interruption status interrupted <-> True , uninterrupted <-> False
        """
        if lb == 4:
            result = self.i4.state() == 0
            #self.logger.debug(f"State of workpiece in {lb} is {result}")
            return result
        else:
            #self.logger.error(f"Trying to access non-existing light barrier {lb}")
            raise ValueError(f"Light Barrier {lb} does not exist")

    def _move_forwards(self):
        """
        Starts Motor m1 and which actuates the turntable clockwise.

        :return: None
        """
        # self.m1.setDistance(6000)
        self.m1.setSpeed(-1 * self.m1_speed)

    def _move_backwards(self):
        """
        Starts Motor m1 which actuates the turntable counterclockwise.

        :return: None
        """
        # self.m1.setDistance(6000)
        self.m1.setSpeed(self.m1_speed)

    def _move_to_initial_position_updating_the_current_sub_task(self):
        """
        Moves the turntable to its initial position where it can receive a workpiece from the blast furnace crane.

        :return: None
        """
        self.set_current_sub_task_to_move(f"{NAME_INITIAL} position", 1)
        self._move_to_initial_position_without_updating_the_current_sub_task()

    def _move_from_initial_to_milling_machine(self) -> None:
        """
        Moves from the initial position to the Milling Machine
        :return: None
        """
        # self.m1.setSpeed(-1 * self.m1_speed)
        self._move_forwards()
        while not self.i2.state() == 1:
            pass
        self.m1.stop()
        return

    def _move_from_ejection_to_milling_machine(self) -> None:
        """
        Moves from the ejection position to the Milling Machine
        :return: None
        """
        # self.m1.setSpeed(self.m1_speed)
        self._move_to_ejection_position()
        self._move_backwards()
        while self.i2.state() == 0:
            pass
        self.m1.stop()
        return

    def _move_to_ejection_position(self) -> None:
        """
        Moves to the ejection position
        :return: None
        """
        # self.m1.setDistance(1000)
        self._move_forwards()
        # self.m1.setSpeed(-1 * self.m1_speed)
        while not self.i3.state() == 1:
            pass
        self.m1.stop()
        return

    def check_position(self, position_which_is_queried) -> bool:
        if position_which_is_queried == NAME_INITIAL:
            return self.i1.state() == 1
        elif position_which_is_queried == NAME_MILL:
            return self.i2.state() == 1
        elif position_which_is_queried == NAME_EJECTION:
            return self.i3.state() == 1
        else:
            return False

    def mill(self, start: str, end: str, time_in_seconds: int = 2) -> None:
        """
        Mills for the specified seconds
        :param start: start position of turntable
        :param end: end position of turntable
        :param time_in_seconds: time to mill, has to be positive
        :raises ValueError when giving a negative time
        :return: None
        """
        if time_in_seconds <= 0:
            raise ValueError("Time must be more than 0")
        self.set_current_task_to_mill(start, end, time_in_seconds, 1)
        if start == NAME_INITIAL and end == NAME_EJECTION:
            self.transport_from_to(NAME_INITIAL, NAME_MILL)
            self.set_current_sub_task_to_mill(time_in_seconds, 1)
            self.m2.setSpeed(self.m2_speed)
            time.sleep(time_in_seconds)
            self.m2.stop()
            self.transport_from_to(NAME_MILL, NAME_EJECTION)
            self._move_to_initial_position_updating_the_current_sub_task()

        elif start == NAME_INITIAL and end == NAME_INITIAL:
            self.transport_from_to(NAME_INITIAL, NAME_MILL)
            self.set_current_sub_task_to_mill(time_in_seconds, 1)
            self.m2.setSpeed(self.m2_speed)
            time.sleep(time_in_seconds)
            self.m2.stop()
            self.transport_from_to(NAME_MILL, NAME_INITIAL)
        else:
            pass
            #self.logger.error(f"Wrong start or end parameter")
        self.set_current_task("", 1)

    def _eject_into_conveyor_belt(self) -> None:
        """
        Ejects the workpiece into the conveyor belt and starts the conveyor belt
        :return: None
        """
        self.set_current_sub_task_to_eject("conveyor belt", 1)
        self.o7.setLevel(512)  # Open valve
        self.o8.setLevel(512)  # Turn compressor on
        time.sleep(1)
        self.o7.setLevel(0)  # Close valve
        self.o8.setLevel(0)  # Turn compressor off
        self.set_current_sub_task_to_transport("workpiece", "sorting machine", 1)
        self.m3.setSpeed(-1 * self.m3_speed)  # conveyor belt forwards
        while not self.i4.state() == 1:
            pass
        time.sleep(4)
        self.m3.stop()
        return

    def move_from_to(self, start: str, end: str) -> None:
        """
        Moves from the given position to the specified position
        :param start: Position to move from
        :param end: Position to move to
        :raises ValueError when trying to get to a non-existing position
        :return: None
        """
        self.set_current_task_to_move(end, 1)
        if start == NAME_INITIAL and end == NAME_MILL:
            self.set_current_sub_task_to_move(NAME_MILL, 1)
            self._move_to_initial_position_without_updating_the_current_sub_task()
            self._move_from_initial_to_milling_machine()
        elif start == NAME_MILL and end == NAME_EJECTION:
            self.set_current_sub_task_to_move(NAME_EJECTION, 1)
            self._move_to_ejection_position()
        elif start == NAME_INITIAL and end == NAME_EJECTION:
            self.set_current_sub_task_to_move(NAME_EJECTION, 1)
            self._move_to_initial_position_without_updating_the_current_sub_task()
            self._move_to_ejection_position()
        elif start == NAME_MILL and end == NAME_INITIAL:
            self.set_current_sub_task_to_move(NAME_INITIAL, 1)
            self._move_to_initial_position_without_updating_the_current_sub_task()
        elif start == NAME_EJECTION and end == NAME_INITIAL:
            self.set_current_sub_task_to_move(NAME_INITIAL, 1)
            self._move_to_ejection_position()
            self._move_to_initial_position_without_updating_the_current_sub_task()
        elif start == NAME_EJECTION and end == NAME_MILL:
            self.set_current_sub_task_to_move(NAME_MILL, 1)
            self._move_from_ejection_to_milling_machine()
        else:
            raise ValueError("Wrong start or end parameter")
        self.set_current_task("", 1)
        return

    def transport_from_to(self, start: str, end: str) -> None:
        """
        Transports a workpiece from the given position to the specified position
        :param start: Position to move from
        :param end: Position to move to
        :raises ValueError when trying to get to a non-existing position
        :return: None
        """
        if self.current_task == "":
            this_method_was_started_by_rpc = True
            self.set_current_task_to_transport("workpiece", end, 1)
        else:
            this_method_was_started_by_rpc = False
        if start == NAME_INITIAL and end == NAME_MILL:
            self.set_current_sub_task_to_transport("workpiece", NAME_MILL, 1)
            self._move_to_initial_position_without_updating_the_current_sub_task()
            self._move_from_initial_to_milling_machine()
        elif start == NAME_MILL and end == NAME_EJECTION:
            self.set_current_sub_task_to_transport("workpiece", f"{NAME_EJECTION} position", 1)
            self._move_to_ejection_position()
            self._eject_into_conveyor_belt()
        elif start == NAME_INITIAL and end == NAME_EJECTION:
            self.set_current_sub_task_to_transport("workpiece", f"{NAME_EJECTION} position", 1)
            self._move_to_initial_position_without_updating_the_current_sub_task()
            self._move_to_ejection_position()
            self._eject_into_conveyor_belt()
        elif start == NAME_MILL and end == NAME_INITIAL:
            self.set_current_sub_task_to_transport("workpiece", f"{NAME_INITIAL} position", 1)
            self._move_to_initial_position_without_updating_the_current_sub_task()
        elif start == NAME_EJECTION and end == NAME_INITIAL:
            self.set_current_sub_task_to_transport("workpiece", f"{NAME_INITIAL} position", 1)
            self._move_to_ejection_position()
            self._move_to_initial_position_without_updating_the_current_sub_task()
        elif start == NAME_EJECTION and end == NAME_MILL:
            self.set_current_sub_task_to_transport("workpiece", NAME_MILL, 1)
            self._move_from_ejection_to_milling_machine()
        else:
            raise ValueError("Wrong start or end parameter")
        if this_method_was_started_by_rpc:
            self.set_current_task("", 1)
        return
