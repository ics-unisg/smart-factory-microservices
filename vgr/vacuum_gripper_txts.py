from collections import namedtuple
import general_txt
from datetime import datetime
import paho.mqtt.client as mqtt
import json
import time
from xmlrpc.server import SimpleXMLRPCServer
from threading import Thread
from typing import Union
from time import sleep
import uuid
import TicsInD



NAME_WAITING_PLATFORM = "waiting_platform"
NAME_HIGH_BAY_WAREHOUSE = "high_bay_warehouse"
NAME_SINK_3 = "sink_3"
NAME_SINK_2 = "sink_2"
NAME_SINK_1 = "sink_1"
NAME_OVEN = "oven"
NAME_SORTING_MACHINE_CONVEYOR_BELT = "sm_cb"
NAME_DELIVERY_AND_PICK_UP_STATION = "delivery_pick_up_station"
NAME_COLOR_DETECTION_DELIVERY_AND_PICK_UP_STATION = "color_detection_delivery_pick_up_station"
NAME_NFC_READER_DELIVERY_AND_PICK_UP_STATION = "nfc_reader_delivery_pick_up_station"
NAME_HIGH_BAY_WAREHOUSE_HOLDING_POSITION = "high_bay_warehouse_holding_position"
NAME_HIGH_BAY_WAREHOUSE_DELIVERY_STATION = "high_bay_warehouse_delivery_station"

Coordinate = namedtuple("Coordinate", ["x", "y", "z"])


def convert_string_into_tuple(string: str) -> Union[tuple, None]:
    """
    Converts a position string (X, Y, Z) into a tuple
    :param string: tuple in string format
    :return: tuple if string is valid else None
    """
    if string.count(",") == 2 and string.count("(") == 1 and string.count(")") == 1:
        return tuple(string.replace("(", "").replace(")", "").split(","))
    return None


def _calculate_color(value):
    color_red_lower = 1200
    color_blue_lower = 1500
    if value <= color_red_lower:
        return 'white'
    elif color_red_lower < value < color_blue_lower:
        return 'red'
    else:
        return 'blue'


class VacuumGripperTXT(general_txt.GeneralTXT):
    def __init__(self, txt_number):
        super(VacuumGripperTXT, self).__init__(txt_number)

        self.target_pos = Coordinate(0, 0, 0)
        self.current_pos = Coordinate(0, 0, 0)

        # Motor speeds
        self.m1_speed = 512
        self.m2_speed = 512
        self.m3_speed = 512

        self.colorsensor = self.txt.colorsensor(8)

        # Start Threads
        threads = [
            Thread(target=self.execution_rpc_server),
            Thread(target=self.getter_setter_rpc_server),
            Thread(target=self.stream_data_via_mqtt),
            Thread(target=self.calibrate),
        ]
        [thread.start() for thread in threads]
        [thread.join() for thread in threads]

        '''
        Wenn kein Werkstück drauf ist dann = 1  wenn werkstück drauf ist dann 0 - 
        self.i7.state() stellt den Sensor in der Pickup Station dar. 
        '''

    def stream_data_via_mqtt(self) -> None:
        """
        Starts the MQTT streaming
        :return: None
        """
        client = mqtt.Client()
        client.connect(self.mqtt_host,1883,60)

        print(f"Started the MQTT Publisher for TXT{self.txt_number} - Topic-Name: {self.mqtt_topic_name} ")
        while True:
            payload = {
                "id": str(uuid.uuid4()),
                "station": self.mqtt_topic_name.replace("FTFactory/", ""),
                "timestamp": str(datetime.now())[:-4],
                'i1_pos_switch': self.i1.state(),
                'i2_pos_switch': self.i2.state(),
                'i3_pos_switch': self.i3.state(),
                'i7_light_barrier': self.i7.state(),
                'i4_light_barrier': self.txt.getCurrentCounterInput(3),
                'i8_color_sensor': self.colorsensor.value(),
                'o7_compressor_level': self.txt.getPwm(6),
                'o8_valve_open': self.txt.getPwm(7),
                'm1_speed': self.txt.getPwm(0) - self.txt.getPwm(1),
                'm2_speed': self.txt.getPwm(2) - self.txt.getPwm(3),
                'm3_speed': self.txt.getPwm(4) - self.txt.getPwm(5),
                'current_state': self.current_state,
                'current_task': self.current_task,
                'current_task_duration': self.calculate_elapsed_seconds_since_start(1),
                'current_sub_task': self.current_sub_task,
                "current_pos_x": TicsInD.t_in_di(self.current_pos.x),
                "current_pos_y": TicsInD.t_in_di(self.current_pos.y),
                "current_pos_z": TicsInD.t_in_di(self.current_pos.z),
                "target_pos_x": TicsInD.t_in_di(self.target_pos.x),
                "target_pos_y": TicsInD.t_in_di(self.target_pos.y),
                "target_pos_z": TicsInD.t_in_di(self.target_pos.z)
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
        server.register_function(self.calibrate, "calibrate")
        server.register_function(self.pick_up_and_transport, "pick_up_and_transport")
        server.register_function(self.move_to, "move_to")
        server.register_function(self.stop_vacuum_suction, "stop_vacuum_suction")
        server.register_function(self.read_color, "read_color")
        # server.register_function(self.pick_up, "pick_up")
        # server.register_function(self.transport, "transport")
        #     Not needed since each pick up HAS TO BE followed by transport which implies that the
        #     webservice '/vgr/pick_up_and_transport' is fully sufficient
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

        print(f"Started the getter_setter_rpc_server for TXT{self.txt_number}")
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

    def check_position(self, position_which_is_queried) -> bool:
        if position_which_is_queried == NAME_WAITING_PLATFORM:
            #return self.target_pos.x == self.hbw_waiting_platform_pos.x & self.target_pos.z > 0
            return self.target_pos.x == self.hbw_waiting_platform_pos.x
        elif position_which_is_queried == NAME_SINK_1:
            #return self.target_pos.x == self.sink_1_pick_up_pos.x & self.target_pos.z > 0
            return self.target_pos.x == self.sink_1_pick_up_pos.x
        elif position_which_is_queried == NAME_SINK_2:
            #return self.target_pos.x == self.sink_2_pick_up_pos.x & self.target_pos.z > 0
            return self.target_pos.x == self.sink_2_pick_up_pos.x
        elif position_which_is_queried == NAME_SINK_3:
            #return self.target_pos.x == self.sink_3_pick_up_pos.x & self.target_pos.z > 0
            return self.target_pos.x == self.sink_3_pick_up_pos.x
        elif position_which_is_queried == NAME_OVEN:
            #return self.target_pos.x == self.oven_pos.x & self.target_pos.z > 0
            return self.target_pos.x == self.oven_pos.x
        elif position_which_is_queried == NAME_SORTING_MACHINE_CONVEYOR_BELT:
            #return self.target_pos.x == self.color_detection_belt_pos.x & self.target_pos.z > 0
            return self.target_pos.x == self.color_detection_belt_pos.x
        elif position_which_is_queried == NAME_DELIVERY_AND_PICK_UP_STATION:
            return self.target_pos.x == self.delivery_pick_up_pos.x
            #return self.target_pos.x == self.delivery_pick_up_pos.x & self.target_pos.z > 0
        elif position_which_is_queried == NAME_COLOR_DETECTION_DELIVERY_AND_PICK_UP_STATION:
            #return self.target_pos.x == self.color_detection_delivery_pick_up_pos.x & self.target_pos.z > 0
            return self.target_pos.x == self.color_detection_delivery_pick_up_pos.x
        elif position_which_is_queried == NAME_NFC_READER_DELIVERY_AND_PICK_UP_STATION:
            #return self.target_pos.x == self.nfc_reader_delivery_pick_up_pos.x & self.target_pos.z > 0
            return self.target_pos.x == self.nfc_reader_delivery_pick_up_pos.x
        elif position_which_is_queried == NAME_HIGH_BAY_WAREHOUSE_HOLDING_POSITION:
            #return self.target_pos.x == self.hbw_holding_pos.x & self.target_pos.z > 0
            return self.target_pos.x == self.hbw_holding_pos.x
        else:
            return False

    def calibrate(self, motor: Union[int, None] = None) -> None:
        """
        Calibrates the given motor by powering as long as the calibration button (pressure button) is not pressed
        When not passing an argument or None, the whole VGR gets calibrated
        :param motor: Motor to calibrate
        :raises ValueError when trying to access a hardware which doesn't exist
        :return: None
        """
        if motor is None:
            self.set_current_task_to_full_calibration(1)
            self._move_into_reset_pos()
            self.calibrate(1)
            self.set_current_task("", 1)
        elif 1 <= motor <= 3:
            txt_motor = None
            position_switch = None
            motor_speed = None
            if motor == 1:
                self.set_current_sub_task_to_individual_motor_calibration(f"motor {motor}", 1)
                txt_motor = self.m1
                position_switch = self.i1
                motor_speed = self.m1_speed
            elif motor == 2:
                self.set_current_sub_task_to_individual_motor_calibration(f"motor {motor}", 1)
                txt_motor = self.m2
                position_switch = self.i2
                motor_speed = self.m2_speed
            elif motor == 3:
                self.set_current_sub_task_to_individual_motor_calibration(f"motor {motor}", 1)
                txt_motor = self.m3
                position_switch = self.i3
                motor_speed = self.m3_speed

            if not position_switch.state() == 1:
                if motor == 1:
                    self.target_pos = self.target_pos._replace(x=0)
                    current_pos_x_before_movement = self.current_pos.x
                elif motor == 2:
                    self.target_pos = self.target_pos._replace(y=0)
                    current_pos_y_before_movement = self.current_pos.y
                elif motor == 3:
                    self.target_pos = self.target_pos._replace(z=0)
                    current_pos_z_before_movement = self.current_pos.z
                txt_motor.setDistance(6000)
                txt_motor.setSpeed(motor_speed)
                while not position_switch.state() == 1:
                    if motor == 1:
                        self.current_pos = self.current_pos._replace(
                            x=current_pos_x_before_movement - self.txt.getCurrentCounterValue(0))
                    if motor == 2:
                        self.current_pos = self.current_pos._replace(
                            y=current_pos_y_before_movement - self.txt.getCurrentCounterValue(1))
                    if motor == 3:
                        self.current_pos = self.current_pos._replace(
                            z=current_pos_z_before_movement - self.txt.getCurrentCounterValue(2))
                txt_motor.setDistance(0)
                txt_motor.stop()
                if motor == 1:
                    self.current_pos = self.current_pos._replace(x=0)
                elif motor == 2:
                    self.current_pos = self.current_pos._replace(y=0)
                elif motor == 3:
                    self.current_pos = self.current_pos._replace(z=0)
        else:
            raise ValueError(f"Trying to access non-existing motor {motor}")
        return

    def status_of_light_barrier(self, lb: int) -> bool:
        """
        Returns TRUE if the light barrier is interrupted else False
        :raises ValueError when trying to access a hardware which doesn't exist
        :param lb: Number of light barrier to check
        :return: Light barrier interruption status interrupted <-> True , uninterrupted <-> False
        """
        if lb == 7:
            result = self.i7.state() == 0
            #self.logger.debug(f"State of workpiece in {lb} is {result}")
            return result
        if lb == 4:
            result = self.txt.getCurrentCounterInput(3) == 0
            #self.logger.debug(f"State of workpiece in {lb} is {result}")
            return result
        else:
            #self.logger.error(f"Trying to access non-existing light barrier {lb}")
            raise ValueError(f"Light Barrier {lb} does not exist")


    def _move_crane_on_axis(self, distance: int, axis: str) -> None:
        """
        Moves the crane on the given axis (x,y or z). This method does not change the variable which contains the
        Coordinate of the crane.
        :param distance: Distance to move
        :param axis: Axis to move
        :raises ValueError when trying to access a hardware which doesn't exist
        :return: None
        """
        if distance > 0:
            speed = 1
        elif distance < 0:
            speed = -1
        else:
            speed = 0
        # if axis == "x":
        #     self.m1.setDistance(abs(distance))
        #     self.m1.setSpeed(speed * self.m1_speed)
        #     while not self.m1.finished():
        #         pass
        #     self.m1.stop()
        # elif axis == "y":
        #     self.m2.setDistance(abs(distance))
        #     self.m2.setSpeed(speed * self.m2_speed)
        #     while not self.m2.finished():
        #         pass
        #     self.m2.stop()
        # elif axis == "z":
        #     self.m3.setDistance(abs(distance))
        #     self.m3.setSpeed(speed * self.m3_speed)
        #     while not self.m3.finished():
        #         pass
        #     self.m3.stop()
        if axis == "x":
            current_pos_x_before_movement = self.current_pos.x
            self.m1.setDistance(abs(distance))
            self.m1.setSpeed(speed * self.m1_speed)
            while not self.m1.finished():
                if speed == 1:
                    self.current_pos = self.current_pos._replace(
                        x=current_pos_x_before_movement - self.txt.getCurrentCounterValue(0))
                else:
                    self.current_pos = self.current_pos._replace(
                        x=current_pos_x_before_movement + self.txt.getCurrentCounterValue(0))
                self.txt.updateWait()
            self.m1.setSpeed(0)
        elif axis == "y":
            current_pos_y_before_movement = self.current_pos.y
            self.m2.setDistance(abs(distance))
            self.m2.setSpeed(speed * self.m2_speed)
            while not self.m2.finished():
                if speed == 1:
                    self.current_pos = self.current_pos._replace(
                        y=current_pos_y_before_movement - self.txt.getCurrentCounterValue(1))
                else:
                    self.current_pos = self.current_pos._replace(
                        y=current_pos_y_before_movement + self.txt.getCurrentCounterValue(1))
                self.txt.updateWait()
            self.m2.setSpeed(0)
        elif axis == "z":
            current_pos_z_before_movement = self.current_pos.z
            self.m3.setDistance(abs(distance))
            self.m3.setSpeed(speed * self.m3_speed)
            while not self.m3.finished():
                if speed == 1:
                    self.current_pos = self.current_pos._replace(
                        z=current_pos_z_before_movement - self.txt.getCurrentCounterValue(2))
                else:
                    self.current_pos = self.current_pos._replace(
                        z=current_pos_z_before_movement + self.txt.getCurrentCounterValue(2))
                self.txt.updateWait()
            self.m3.setSpeed(0)
        else:
            raise ValueError(f"Axis {axis} does not exist")
        return

    def _move_to_target(self, pos_to_move_to) -> None:
        """
        Moves the crane to the desired location and modifies the Coordinate target_pos of the crane
        Moves the x-axis first, followed by the z-axis and ultimately the y-axis. One axis can only extract after the
        previous is finished to avoid collisions
        :param pos_to_move_to: Coordinate to move to
        :return: None
        """
        if pos_to_move_to.x is not None:  # VGR should move x
            if pos_to_move_to.x != 0:
                distance_x = self.target_pos.x - pos_to_move_to.x
                self._move_crane_on_axis(distance_x, "x")
                self.target_pos = self.target_pos._replace(x=pos_to_move_to.x)  # Updates the crane Coordinate
            else:
                self.calibrate(1)
        while not self.m1.finished():
            pass
        if pos_to_move_to.z is not None:  # VGR should move z
            if pos_to_move_to.z != 0:
                distance_z = self.target_pos.z - pos_to_move_to.z
                self._move_crane_on_axis(distance_z, "z")
                self.target_pos = self.target_pos._replace(z=pos_to_move_to.z)  # Updates the crane Coordinate
            else:
                self.calibrate(3)
        while not self.m3.finished():
            pass
        if pos_to_move_to.y is not None:  # VGR should move y
            if pos_to_move_to.y != 0:
                distance_y = self.target_pos.y - pos_to_move_to.y
                self._move_crane_on_axis(distance_y, "y")
                self.target_pos = self.target_pos._replace(y=pos_to_move_to.y)  # Updates the crane Coordinate
            else:
                self.calibrate(2)
        while not self.m2.finished():
            pass
        return

    def _move_into_reset_pos(self) -> None:
        """
        Retracts the y-axis followed by the z-axis to avoid collisions
        :return: None
        """
        self._move_to_target(Coordinate(None, 0, None))
        self._move_to_target(Coordinate(None, None, 0))
        return

    def _start_vacuum_suction(self) -> None:
        """
        Starts the vacuum suction of a workpiece
        :return: None
        """
        self.o8.setLevel(512)  # Generate vacuum for the vacuum suction head
        self.o7.setLevel(512)  # Turn compressor on
        sleep(1)
        return

    def _stop_vacuum_suction(self) -> None:
        """
        Stops the vacuum suction of a workpiece
        :return: None
        """
        self.o7.setLevel(0)  # Turn compressor off
        time.sleep(0.2)
        self.o8.setLevel(0)  # Close valve which regulates the vacuum piston
        time.sleep(0.1)
        self.o8.setLevel(512)
        time.sleep(0.1)
        self.o8.setLevel(0)
        time.sleep(0.1)
        self.o8.setLevel(512)
        return

    def _pick_up_from_hbw_waiting_platform(self) -> None:
        """
        Picks up workpiece from the High Bay Warehouse Waiting Platform
        :return: None
        """
        pick_up_position_for_current_task = "high bay warehouse waiting platform"
        self.set_current_sub_task_to_move(pick_up_position_for_current_task, 1)
        self._move_into_reset_pos()
        self._move_to_target(self.hbw_waiting_platform_pos)
        self.set_current_sub_task_to_pick_up("workpiece", pick_up_position_for_current_task, 1)
        self._start_vacuum_suction()
        return

    # PD
    def _pick_up_from_delivery_and_pickup_station(self) -> None:
        pick_up_position_for_current_task = "delivery_pick_up_station"
        self.set_current_sub_task_to_move(pick_up_position_for_current_task, 1)
        self._move_into_reset_pos()
        self._move_to_target(self.delivery_pick_up_pos)
        self.set_current_sub_task_to_pick_up("workpiece", pick_up_position_for_current_task, 1)
        self._start_vacuum_suction()
        return

    def _pick_up_from_color_detection_delivery_and_pickup_station(self) -> None:
        pick_up_position_for_current_task = "color_detection_delivery_pick_up_station"
        self.set_current_sub_task_to_move(pick_up_position_for_current_task, 1)
        self._move_into_reset_pos()
        self._move_to_target(self.color_detection_delivery_pick_up_pos)
        self.set_current_sub_task_to_pick_up("workpiece", pick_up_position_for_current_task, 1)
        self._start_vacuum_suction()
        return

    def _pick_up_from_nfc_reader_delivery_and_pickup_station(self) -> None:
        pick_up_position_for_current_task = "nfc_reader_delivery_pick_up_station"
        self.set_current_sub_task_to_move(pick_up_position_for_current_task, 1)
        self._move_into_reset_pos()
        self._move_to_target(self.nfc_reader_delivery_pick_up_pos)
        self.set_current_sub_task_to_pick_up("workpiece", pick_up_position_for_current_task, 1)
        self._start_vacuum_suction()
        return

    def _pick_up_from_sink(self, sink: int) -> None:
        """
        Picks up workpiece from the desired sink
        :raises ValueError when trying to access a hardware which doesn't exist
        :param sink: Sink to move to
        :return: None
        """
        pick_up_position_for_current_task = f"sink {sink}"
        if sink == 1:
            self.set_current_sub_task_to_move(pick_up_position_for_current_task, 1)
            self._move_to_target(self.sink_1_pick_up_pos)
        elif sink == 2:
            self.set_current_sub_task_to_move(pick_up_position_for_current_task, 1)
            self._move_to_target(self.sink_2_pick_up_pos)
        elif sink == 3:
            self.set_current_sub_task_to_move(pick_up_position_for_current_task, 1)
            self._move_to_target(self.sink_3_pick_up_pos)
        else:
            raise ValueError(f"Sink {sink} does not exist")
        self.set_current_sub_task_to_pick_up("workpiece", pick_up_position_for_current_task, 1)
        self._start_vacuum_suction()
        return

    def _pick_up_from_oven(self) -> None:
        """
        Picks up workpiece from the Oven
        :return: None
        """
        pick_up_position_for_current_task = "oven"
        self.set_current_sub_task_to_move(pick_up_position_for_current_task, 1)
        self._move_into_reset_pos()
        self._move_to_target(self.oven_pos)
        self.set_current_sub_task_to_pick_up("workpiece", pick_up_position_for_current_task, 1)
        self._start_vacuum_suction()
        return

    def _pick_up_from_high_bay_warehouse(self) -> None:
        """
        Picks up workpiece from the High Bay Warehouse
        :return: None
        """
        pick_up_position_for_current_task = "high bay warehouse"
        self.set_current_sub_task_to_move(pick_up_position_for_current_task, 1)
        self._move_into_reset_pos()
        self._move_to_target(self.hbw_loading_pos)
        self.set_current_sub_task_to_pick_up("workpiece", pick_up_position_for_current_task, 1)
        self._start_vacuum_suction()
        return

    def _pick_up_from_color_detection_belt(self) -> None:
        """
        Picks up workpiece from the conveyor belt after the color detection box in the Sorting Machine
        :return: None
        """
        pick_up_position_for_current_task = "sorting machine conveyor belt"
        self.set_current_sub_task_to_move(pick_up_position_for_current_task, 1)
        self._move_into_reset_pos()
        self._move_to_target(self.color_detection_belt_pos)
        self.set_current_sub_task_to_pick_up("workpiece", pick_up_position_for_current_task, 1)
        self._start_vacuum_suction()
        return

    def _transport_and_drop_into_sink(self, sink: int) -> None:
        """
        Drives to the desired sink and drops the workpiece
        :raises ValueError when trying to access a hardware which doesn't exist
        :param sink: Sink to move to
        :return: None
        """
        drop_off_position_for_current_task = f"sink {sink}"
        self._move_into_reset_pos()
        if sink == 1:
            self.set_current_sub_task_to_transport("workpiece", drop_off_position_for_current_task, 1)
            self._move_to_target(self.sink_1_drop_off_pos)
        elif sink == 2:
            self.set_current_sub_task_to_transport("workpiece", drop_off_position_for_current_task, 1)
            self._move_to_target(self.sink_2_drop_off_pos)
        elif sink == 3:
            self.set_current_sub_task_to_transport("workpiece", drop_off_position_for_current_task, 1)
            self._move_to_target(self.sink_3_drop_off_pos)
        else:
            raise ValueError(f"Sink {sink} does not exist")
        self.set_current_sub_task_to_drop_off("workpiece", drop_off_position_for_current_task, 1)
        self._stop_vacuum_suction()
        self._move_into_reset_pos()
        return

    def _transport_and_drop_into_waiting_platform(self) -> None:
        """
        Drives to the High Bay Warehouse Waiting Platform and drops the workpiece
        :return: None
        """
        drop_off_position_for_current_task = "high bay warehouse waiting platform"
        self._move_into_reset_pos()
        self.set_current_sub_task_to_transport("workpiece", drop_off_position_for_current_task, 1)
        self._move_to_target(self.hbw_waiting_platform_pos)
        self.set_current_sub_task_to_drop_off("workpiece", drop_off_position_for_current_task, 1)
        self._stop_vacuum_suction()
        self._move_into_reset_pos()
        return

    def _transport_and_drop_into_oven(self) -> None:
        """
        Drives to the Oven and drops the workpiece
        :return: None
        """
        drop_off_position_for_current_task = "oven"
        self._move_into_reset_pos()
        self.set_current_sub_task_to_transport("workpiece", drop_off_position_for_current_task, 1)
        self._move_to_target(self.oven_pos)
        self.set_current_sub_task_to_drop_off("workpiece", drop_off_position_for_current_task, 1)
        self._stop_vacuum_suction()
        self._move_into_reset_pos()
        return

    def _transport_and_drop_into_high_bay_warehouse(self) -> None:
        """
        Drives to the High Bay Warehouse and drops the workpiece
        :return: None
        """
        drop_off_position_for_current_task = "high bay warehouse"
        self._move_into_reset_pos()
        self.set_current_sub_task_to_transport("workpiece", drop_off_position_for_current_task, 1)
        self._move_to_target(self.hbw_loading_pos)
        self.set_current_sub_task_to_drop_off("workpiece", drop_off_position_for_current_task, 1)
        self._stop_vacuum_suction()
        self._move_into_reset_pos()
        return
    #PD
    def _transport_and_hold_into_high_bay_warehouse(self) -> None:

        drop_off_position_for_current_task = "high bay warehouse"
        self._move_into_reset_pos()
        self.set_current_sub_task_to_transport("workpiece", drop_off_position_for_current_task, 1)
        self._move_to_target(self.hbw_holding_pos)
        #self.set_current_sub_task_to_drop_off("workpiece", drop_off_position_for_current_task, 1)
        #self._stop_vacuum_suction()
        #self._move_into_reset_pos()
        return

    def _transport_and_drop_into_delivery_station(self) -> None:
        drop_off_position_for_current_task = "high bay warehouse"
        self._move_into_reset_pos()
        self.set_current_sub_task_to_transport("workpiece", drop_off_position_for_current_task, 1)
        self._move_to_target(self.hbw_delivery_station_pos)
        self._stop_vacuum_suction()
        self._move_into_reset_pos()
        return

    def _transport_and_drop_into_color_detection_belt(self) -> None:
        """
        Drives to the conveyor belt after the color detection box in the Sorting Machine and drops the workpiece
        """
        drop_off_position_for_current_task = "sorting machine conveyor belt"
        self._move_into_reset_pos()
        self.set_current_sub_task_to_transport("workpiece", drop_off_position_for_current_task, 1)
        self._move_to_target(self.color_detection_belt_pos)
        self.set_current_sub_task_to_drop_off("workpiece", drop_off_position_for_current_task, 1)
        self._stop_vacuum_suction()
        self._move_into_reset_pos()
        return

    def _transport_and_drop_into_color_detection_delivery_and_pick_up_station(self) -> None:
        drop_off_position_for_current_task = "color_detection_delivery_pick_up_station"
        self._move_into_reset_pos()
        self.set_current_sub_task_to_transport("workpiece", drop_off_position_for_current_task, 1)
        self._move_to_target(self.color_detection_delivery_pick_up_pos)
        self.set_current_sub_task_to_drop_off("workpiece", drop_off_position_for_current_task, 1)
        self._stop_vacuum_suction()
        self._move_into_reset_pos()
        color = self.read_color()
        print(f'THE COLOR IS {color}')

    def _transport_and_drop_into_nfc_reader_delivery_and_pick_up_station(self) -> None:
        drop_off_position_for_current_task = "nfc_reader_delivery_pick_up_station"
        self._move_into_reset_pos()
        self.set_current_sub_task_to_transport("workpiece", drop_off_position_for_current_task, 1)
        self._move_to_target(self.nfc_reader_delivery_pick_up_pos)
        self.set_current_sub_task_to_drop_off("workpiece", drop_off_position_for_current_task, 1)
        self._stop_vacuum_suction()
        self._move_into_reset_pos()

    def move_to(self, position: str) -> None:
        """
        Moves to the x coordinate of the specified predefined position
        :raises ValueError when trying to access a position which doesn't exist or giving wrong types
        :param position: position to move to or Coordinates as a tuple
        :return: None
        """
        if position == NAME_SORTING_MACHINE_CONVEYOR_BELT:
            self.set_current_task_to_move("sorting machine conveyor belt", 1)
            self.set_current_sub_task_to_move("sorting machine conveyor belt", 1)
            self._move_to_target(Coordinate(self.color_detection_belt_pos.x, 0, 0))
        elif position == NAME_OVEN:
            self.set_current_task_to_move(NAME_OVEN, 1)
            self.set_current_sub_task_to_move(NAME_OVEN, 1)
            self._move_to_target(Coordinate(self.oven_pos.x, 0, 0))
        elif position == NAME_SINK_1:
            self.set_current_task_to_move(NAME_SINK_1, 1)
            self.set_current_sub_task_to_move(NAME_SINK_1, 1)
            self._move_to_target(Coordinate(self.sink_1_pick_up_pos.x, 0, 0))
        elif position == NAME_SINK_2:
            self.set_current_task_to_move(NAME_SINK_2, 1)
            self.set_current_sub_task_to_move(NAME_SINK_2, 1)
            self._move_to_target(Coordinate(self.sink_2_pick_up_pos.x, 0, 0))
        elif position == NAME_SINK_3:
            self.set_current_task_to_move(NAME_SINK_3, 1)
            self.set_current_sub_task_to_move(NAME_SINK_3, 1)
            self._move_to_target(Coordinate(self.sink_3_pick_up_pos.x, 0, 0))
        elif position == NAME_HIGH_BAY_WAREHOUSE:
            self.set_current_task_to_move(NAME_HIGH_BAY_WAREHOUSE, 1)
            self.set_current_sub_task_to_move(NAME_HIGH_BAY_WAREHOUSE, 1)
            self._move_to_target(Coordinate(self.hbw_loading_pos.x, 0, 0))
        elif position == NAME_WAITING_PLATFORM:
            self.set_current_task_to_move(NAME_WAITING_PLATFORM, 1)
            self.set_current_sub_task_to_move(NAME_WAITING_PLATFORM, 1)
            self._move_to_target(Coordinate(self.hbw_waiting_platform_pos.x, 0, 0))
        elif position == NAME_DELIVERY_AND_PICK_UP_STATION:
            self.set_current_task_to_move(NAME_DELIVERY_AND_PICK_UP_STATION, 1)
            self.set_current_sub_task_to_move(NAME_DELIVERY_AND_PICK_UP_STATION, 1)
            self._move_to_target(Coordinate(self.delivery_pick_up_pos.x, 728, 30))
        elif position == NAME_COLOR_DETECTION_DELIVERY_AND_PICK_UP_STATION:
            self.set_current_task_to_move(NAME_COLOR_DETECTION_DELIVERY_AND_PICK_UP_STATION, 1)
            self.set_current_sub_task_to_move(NAME_COLOR_DETECTION_DELIVERY_AND_PICK_UP_STATION, 1)
            self._move_to_target(Coordinate(self.color_detection_delivery_pick_up_pos.x, 600, 80))
        elif position == NAME_NFC_READER_DELIVERY_AND_PICK_UP_STATION:
            self.set_current_task_to_move(NAME_NFC_READER_DELIVERY_AND_PICK_UP_STATION, 1)
            self.set_current_sub_task_to_move(NAME_NFC_READER_DELIVERY_AND_PICK_UP_STATION, 1)
            self._move_to_target(Coordinate(self.nfc_reader_delivery_pick_up_pos.x, 600, 250))
        elif position == NAME_HIGH_BAY_WAREHOUSE_HOLDING_POSITION:
            self.set_current_task_to_move(NAME_HIGH_BAY_WAREHOUSE_HOLDING_POSITION,1)
            self.set_current_sub_task_to_move(NAME_HIGH_BAY_WAREHOUSE_HOLDING_POSITION,1)
            self._move_to_target(Coordinate(self.hbw_holding_pos.x,20,200))
        else:
            self._move_to_target(Coordinate(int(position), 0, 0))
        self.set_current_task("", 1)

    def pick_up_and_transport(self, start: Union[str, tuple], end: Union[str, tuple]) -> None:
        """
        Picks up workpiece from start and transports it to the end
        :raises ValueError when trying to access a position which doesn't exist or giving wrong types
        :param start: position to move to or Coordinates as a tuple
        :param end: position to move to or Coordinates as a tuple
        :return: None
        """
        if start == end:
            raise ValueError(f"Position {start} and {end} have to be different and also can't be None.")
        if start is None or end is None:
            raise ValueError("None is not allowed")
        self.set_current_task_to_pick_up_and_transport("workpiece", start, end, 1)
        start_tuple = convert_string_into_tuple(start)
        end_tuple = convert_string_into_tuple(end)
        if start_tuple is not None:
            start = start_tuple
        if end_tuple is not None:
            end = end_tuple
        if type(start) == str:
            if start == NAME_SORTING_MACHINE_CONVEYOR_BELT:
                self._pick_up_from_color_detection_belt()
            elif start == NAME_OVEN:
                self._pick_up_from_oven()
            elif start == NAME_SINK_1:
                self._pick_up_from_sink(1)
            elif start == NAME_SINK_2:
                self._pick_up_from_sink(2)
            elif start == NAME_SINK_3:
                self._pick_up_from_sink(3)
            elif start == NAME_HIGH_BAY_WAREHOUSE:
                self._pick_up_from_high_bay_warehouse()
            elif start == NAME_WAITING_PLATFORM:
                self._pick_up_from_hbw_waiting_platform()
            elif start == NAME_DELIVERY_AND_PICK_UP_STATION:
                self._pick_up_from_delivery_and_pickup_station()
            elif start == NAME_COLOR_DETECTION_DELIVERY_AND_PICK_UP_STATION:
                self._pick_up_from_color_detection_delivery_and_pickup_station()
            elif start == NAME_NFC_READER_DELIVERY_AND_PICK_UP_STATION:
                self._pick_up_from_nfc_reader_delivery_and_pickup_station()
            else:
                raise ValueError(f"Position {start} does not exist")
        elif type(start) == tuple:
            if len(start) == 3:
                pick_up_position_for_current_task = f"position x:{start[0]}, y:{start[1]}, z:{start[2]}"
                self.set_current_sub_task_to_move(pick_up_position_for_current_task, 1)
                self._move_into_reset_pos()
                start_coordinate = Coordinate(int(start[0]), int(start[1]), int(start[2]))
                self._move_to_target(start_coordinate)
                self.set_current_sub_task_to_pick_up("workpiece", pick_up_position_for_current_task, 1)
                self._start_vacuum_suction()
            else:
                raise ValueError("Too many coordinates as start position")
        else:
            raise ValueError("Wrong format of start position")

        if type(end) == str:
            if end == NAME_SORTING_MACHINE_CONVEYOR_BELT:
                self._transport_and_drop_into_color_detection_belt()
            elif end == NAME_OVEN:
                self._transport_and_drop_into_oven()
            elif end == NAME_SINK_1:
                self._transport_and_drop_into_sink(1)
            elif end == NAME_SINK_2:
                self._transport_and_drop_into_sink(2)
            elif end == NAME_SINK_3:
                self._transport_and_drop_into_sink(3)
            elif end == NAME_HIGH_BAY_WAREHOUSE:
                self._transport_and_drop_into_high_bay_warehouse()
            elif end == NAME_WAITING_PLATFORM:
                self._transport_and_drop_into_waiting_platform()
            elif end == NAME_COLOR_DETECTION_DELIVERY_AND_PICK_UP_STATION:
                self._transport_and_drop_into_color_detection_delivery_and_pick_up_station()
            elif end == NAME_NFC_READER_DELIVERY_AND_PICK_UP_STATION:
                self._transport_and_drop_into_nfc_reader_delivery_and_pick_up_station()
            elif end == NAME_HIGH_BAY_WAREHOUSE_HOLDING_POSITION:
                self._transport_and_hold_into_high_bay_warehouse()
            elif end == NAME_HIGH_BAY_WAREHOUSE_DELIVERY_STATION:
                self._transport_and_drop_into_delivery_station()
            else:
                raise ValueError(f"Position {end} does not exist")
        elif type(end) == tuple:
            if len(end) == 3:
                drop_off_position_for_current_task = f"position x:{end[0]}, y:{end[1]}, z:{end[2]}"
                self._move_into_reset_pos()
                self.set_current_sub_task_to_transport("workpiece", drop_off_position_for_current_task, 1)
                end_coordinate = Coordinate(int(end[0]), int(end[1]), int(end[2]))
                self._move_to_target(end_coordinate)
                self.set_current_sub_task_to_drop_off("workpiece", drop_off_position_for_current_task, 1)
                self._stop_vacuum_suction()
            else:
                raise ValueError("Too many coordinates as end position")
        else:
            raise ValueError("Wrong format of end position")

        self.set_current_task("", 1)
        return

    def stop_vacuum_suction(self):
        self._stop_vacuum_suction()

    #TODO set task and subtask
    def read_color(self):
        return _calculate_color(self.colorsensor.value())