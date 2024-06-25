import general_txt
from datetime import datetime
import paho.mqtt.client as mqtt
import json
import time
from xmlrpc.server import SimpleXMLRPCServer
from threading import Thread
from collections import namedtuple
from typing import Union
import os
import uuid
import TicsInD


Coordinate = namedtuple("Coordinate", ["x", "y"])


class HighBayWarehouseTXT(general_txt.GeneralTXT):
    def __init__(self, txt_number):
        super(HighBayWarehouseTXT, self).__init__(txt_number)

        # Motor speeds
        self.m1_speed = 512
        self.m2_speed = 512
        self.m3_speed = 512
        self.m4_speed = 512

        # Coordinates
        self.current_pos = Coordinate(0, 0)

        self.is_bucket_empty_list = [True for _ in range(9)]
        self.current_stock = self._load_current_hbw_stock()

        i = 0
        for pos in self.current_stock:
            if not self.current_stock[pos]:
                pass
            else:
                self.is_bucket_empty_list[i] = False
            i += 1

        # Start Threads
        threads = [
            Thread(target=self.execution_rpc_server),
            Thread(target=self.getter_setter_rpc_server),
            Thread(target=self.stream_data_via_mqtt),
            Thread(target=self.calibrate)
        ]
        [thread.start() for thread in threads]
        [thread.join() for thread in threads]

    def stream_data_via_mqtt(self) -> None:
        client = mqtt.Client()
        client.connect(self.mqtt_host,1883,60)
        print(f"Started the MQTT Publisher for TXT{self.txt_number} - Topic-Name: {self.mqtt_topic_name}")
        while True:
            payload = {
                "id": str(uuid.uuid4()),
                "station": self.mqtt_topic_name.replace("FTFactory/", ""),
                "timestamp": str(datetime.now())[:-4],
                'i1_light_barrier': self.i1.state(),
                'i2_light_barrier': self.i2.state(),
                'i3_light_barrier': self.i3.state(),
                'i4_light_barrier': self.i4.state(),
                'i5_pos_switch': self.i5.state(),
                'i6_pos_switch': self.i6.state(),
                'i7_pos_switch': self.i7.state(),
                'i8_pos_switch': self.i8.state(),
                'm1_speed': self.txt.getPwm(0) - self.txt.getPwm(1),
                'm2_speed': self.txt.getPwm(2) - self.txt.getPwm(3),
                'm3_speed': self.txt.getPwm(4) - self.txt.getPwm(5),
                'm4_speed': self.txt.getPwm(6) - self.txt.getPwm(7),
                'current_state': self.current_state,
                'current_task': self.current_task,
                'current_task_duration': self.calculate_elapsed_seconds_since_start(1),
                'current_sub_task': self.current_sub_task,
                "current_pos_x": TicsInD.t_in_di(self.current_pos.x),
                "current_pos_y": TicsInD.t_in_di(self.current_pos.y),
                "target_pos_x": TicsInD.t_in_di(self.target_pos.x),
                "target_pos_y": TicsInD.t_in_di(self.target_pos.y),
                "amount_of_workpieces": self.get_amount_of_stored_workpieces(),
                "current_stock": self.current_stock
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
        server.register_function(self.store, "store")
        server.register_function(self.unload, "unload")
        server.register_function(self.change_buckets, "change_buckets")
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
        server.register_function(self.get_amount_of_stored_workpieces, "get_amount_of_stored_workpieces")
        server.register_function(self.get_slot_number_of_workpiece_by_color,"get_slot_number_of_workpiece_by_color")
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
        elif motor == 4:
            self.m4_speed = new_speed
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
        self.m4_speed = 512
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
        elif motor == 4:
            return self.m4_speed
        else:
            raise ValueError(f"Trying to access non-existing motor {motor}")

    def update_with_nfc(self) -> None:
        # TODO Implement
        pass

    def calibrate(self, motor: Union[int, None] = None) -> None:
        """
        Calibrates the given motor by powering as long as the calibration button (pressure button) is not pressed
        When not passing an argument or None, the whole HBW gets calibrated
        :param motor: Motor to calibrate
        :raises ValueError when trying to access a hardware which doesn't exist
        :return: None
        """
        if motor is None:
            self.set_current_task_to_full_calibration(1)
            self.set_current_sub_task_to_individual_motor_calibration(f"motor 3", 1)
            self.calibrate(3)
            self.set_current_sub_task_to_individual_motor_calibration(f"motor 2", 1)
            self.calibrate(2)
            self.set_current_sub_task_to_individual_motor_calibration(f"motor 4", 1)
            self.calibrate(4)
            self.set_current_task("", 1)
        elif 2 <= motor <= 4:
            txt_motor = None
            position_switch = None
            motor_speed = None
            if motor == 2:
                txt_motor = self.m2
                position_switch = self.i5
                motor_speed = self.m2_speed
            elif motor == 3:
                txt_motor = self.m3
                position_switch = self.i6
                motor_speed = self.m3_speed
            elif motor == 4:
                txt_motor = self.m4
                position_switch = self.i8
                motor_speed = self.m4_speed
            if not position_switch.state() == 1:
                if motor == 2:
                    self.target_pos = self.target_pos._replace(x=0)
                    current_pos_x_before_movement = self.current_pos.x
                elif motor == 4:
                    self.target_pos = self.target_pos._replace(y=0)
                    current_pos_y_before_movement = self.current_pos.y
                else:
                    pass
                txt_motor.setDistance(6000)
                txt_motor.setSpeed(motor_speed)
                while not position_switch.state() == 1:
                    if motor == 2:
                        self.current_pos = self.current_pos._replace(
                            x=current_pos_x_before_movement - self.txt.getCurrentCounterValue(1))
                    elif motor == 4:
                        self.current_pos = self.current_pos._replace(
                            y=current_pos_y_before_movement - self.txt.getCurrentCounterValue(3))
                    else:
                        pass
                    self.txt.updateWait()
                txt_motor.setDistance(0)
                txt_motor.stop()
                if motor == 2:
                    self.current_pos = self.current_pos._replace(x=0)
                elif motor == 4:
                    self.current_pos = self.current_pos._replace(y=0)
                else:
                    pass

        else:
            raise ValueError(f"Trying to access non-existing motor {motor}")
        return

    def _move_jib_forwards(self) -> None:
        """
        Moves the crane jib forwards
        :return: None
        """
        self.m3.setSpeed(-1 * self.m3_speed)
        self.m3.setDistance(1000)
        while self.i7.state() == 0:
            pass
        self.m3.stop()
        return

    def _move_jib_backwards(self) -> None:
        """
        Moves the crane jib backwards
        :return: None
        """
        self.m3.setSpeed(1 * self.m3_speed)
        self.m3.setDistance(1000)
        while self.i6.state() == 0:
            pass
        self.m3.stop()
        return

    def _move_crane_on_axis(self, distance: int, axis: str) -> None:
        """
        Moves the crane jib on the given axis (x or y). This method does not change the variable which contains the
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
        if axis == "x":
            current_pos_x_before_movement = self.current_pos.x
            self.m2.setDistance(abs(distance))
            self.m2.setSpeed(speed * self.m2_speed)
            while not self.m2.finished():
                if speed == 1:
                    self.current_pos = self.current_pos._replace(
                        x=current_pos_x_before_movement - self.txt.getCurrentCounterValue(1))
                else:
                    self.current_pos = self.current_pos._replace(
                        x=current_pos_x_before_movement + self.txt.getCurrentCounterValue(1))
                self.txt.updateWait()
            self.m2.stop()
        elif axis == "y":
            current_pos_y_before_movement = self.current_pos.y
            self.m4.setDistance(abs(distance))
            self.m4.setSpeed(speed * self.m4_speed)
            while not self.m4.finished():
                if speed == 1:
                    self.current_pos = self.current_pos._replace(
                        y=current_pos_y_before_movement - self.txt.getCurrentCounterValue(3))
                else:
                    self.current_pos = self.current_pos._replace(
                        y=current_pos_y_before_movement + self.txt.getCurrentCounterValue(3))
                self.txt.updateWait()
            self.m4.stop()

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
        if pos_to_move_to.x is not None:  # Crane jib should move x
            if pos_to_move_to.x != 0:
                if pos_to_move_to.x < 100:  # this prevents the crane from driving too far if the x coordinate is small
                    self.calibrate(2)
                distance_x = self.target_pos.x - pos_to_move_to.x
                self._move_crane_on_axis(distance_x, "x")
                self.target_pos = self.target_pos._replace(x=pos_to_move_to.x)  # Updates the jib Coordinate
            else:
                self.calibrate(2)
        while not self.m2.finished():
            pass
        if pos_to_move_to.y is not None:  # Crane jib should move y
            if pos_to_move_to.y != 0:
                distance_y = self.target_pos.y - pos_to_move_to.y
                self._move_crane_on_axis(distance_y, "y")
                self.target_pos = self.target_pos._replace(y=pos_to_move_to.y)  # Updates the jib Coordinate
            else:
                self.calibrate(4)
        while not self.m4.finished():
            pass
        return

    def status_of_light_barrier(self, lb: int) -> bool:
        """
        Returns TRUE if the light barrier is interrupted else False
        :raises ValueError when trying to access a hardware which doesn't exist
        :param lb: Number of light barrier to check
        :return: Light barrier interruption status interrupted <-> True , uninterrupted <-> False
        """
        if lb == 1:
            result = self.i1.state() == 0
            #self.logger.debug(f"State of workpiece in {lb} is {result}")
            return result
        elif lb == 2:
            result = self.i2.state() == 0
            #self.logger.debug(f"State of workpiece in {lb} is {result}")
            return result
        elif lb == 3:
            result = self.i3.state() == 0 # Waiting platform interrupted
            #self.logger.debug(f"State of workpiece in {lb} is {result}")
            return result
        elif lb == 4:
            result = self.i4.state() == 0
            #self.logger.debug(f"State of workpiece in {lb} is {result}")
            return result
        else:
            #self.logger.error(f"Trying to access non-existing light barrier {lb}")
            raise ValueError(f"Light Barrier {lb} does not exist")

    def _move_jib_up_to_pick_up_bucket(self) -> None:
        """
        Drives the jib up to lift a bucket out of the rack
        :return: None
        """
        pos_to_move_to = self.target_pos.y - 140
        self._move_to_target(Coordinate(None, pos_to_move_to))

    def _move_jib_down_to_set_bucket(self) -> None:
        """
        Drives the jib down to set a bucket into a rack
        :return: None
        """
        pos_to_move_to = self.target_pos.y + 100
        self._move_to_target(Coordinate(None, pos_to_move_to))

    def _move_conveyor_belt_to_waiting_platform(self) -> None:
        """
        Moves the conveyor belt forwards to the waiting platform
        :return: None
        """
        self.set_current_sub_task_to_transport(
            f"bucket", f"vacuum gripper robot crane jib", 1)
        self.m1.setSpeed(-1 * self.m1_speed)
        self.m1.setDistance(200)
        while self.i1.state() == 1:
            pass
        self.m1.stop()
        return

    def _move_conveyor_belt_to_crane_jib(self):
        """
        Moves the conveyor belt backwards to the crane jib
        :return: None
        """
        self.set_current_sub_task_to_transport(
            f"bucket", f"high bay warehouse crane jib", 1)
        self.m1.setSpeed(self.m1_speed)
        self.m1.setDistance(200)
        while self.i4.state() == 1:
            pass
        self.m1.stop()
        return

    def _pick_up_bucket_from_slot(self) -> None:
        """
        Moves the crane jib forwards, picks the bucket up and retracts the jib
        :return: None
        """
        self.set_current_sub_task_to_pick_up(f"bucket", f"slot", 1)
        self._move_jib_forwards()
        self._move_jib_up_to_pick_up_bucket()
        self._move_jib_backwards()

    def _pick_up_bucket_from_conveyor_belt(self) -> None:
        """
        Moves the crane jib forwards, picks the bucket up and retracts the jib
        :return: None
        """
        self.set_current_sub_task_to_transport(f"bucket", "high-bay warehouse crane jib", 1)
        self._move_jib_forwards()
        self._move_conveyor_belt_to_crane_jib()
        self.set_current_sub_task_to_pick_up(f"bucket", f"conveyor belt", 1)
        self._move_jib_up_to_pick_up_bucket()
        self._move_jib_backwards()
        # self._move_jib_down_to_set_bucket()

    def _drop_off_bucket_to_slot(self) -> None:
        """
        Moves the crane jib forwards, drops the bucket off and retracts the jib
        :return: None
        """
        self.set_current_sub_task_to_drop_off(f"bucket", f"slot", 1)
        self._move_jib_forwards()
        self._move_jib_down_to_set_bucket()
        self._move_jib_backwards()

    def _drop_off_bucket_to_conveyor_belt(self) -> None:
        """
        Moves the crane jib forwards, drops the bucket off and retracts the jib
        :return: None
        """
        self.set_current_sub_task_to_drop_off(f"bucket", f"conveyor belt", 1)
        self._move_jib_forwards()
        self._move_jib_down_to_set_bucket()
        self._move_jib_backwards()

    def store(self, slot_number: Union[int, str], color:str = None, nfc: bool = False) -> None:
        """
        Stores the workpiece in bucket at desired location by bringing the empty bucket to the conveyor belt,
        waiting for the vgr to interact with it and bringing the now full bucket back to the slot
        If nfc is True, it uses the nfc-tag-id from a workpiece as the bucket position
        Else it uses the bucket position (0-8) or searches the next one if "next" is passed
        :param slot_number: Number of bucket to store
        :param nfc: Whether to use nfc or not
        :raises ValueError: When the HBW is full or the slot_number is wrong
        :return: None
        """
        self.update_with_nfc()
        if nfc:
            pass  # TODO Implement
        else:
            if slot_number == "next":
                slot_number = self._find_empty_slot()
                if slot_number == -1:
                    raise ValueError("High Bay Warehouse is full")

            if 0 <= slot_number <= 8:
                self.set_current_task_to_store(f"workpiece", slot_number, 1)
                self._transport_bucket_to_conveyor_belt(slot_number)
                self._move_conveyor_belt_to_waiting_platform()
                self._wait_for_vgr_to_interact_with_bucket()
                self._transport_bucket_to_slot(slot_number)
                self.is_bucket_empty_list[slot_number] = False
                self.set_current_task("", 1)
                self._update_current_hbw_stock(slot_number, color)
            else:
                raise ValueError("Position does not exist")
        return

    def unload(self, slot_number: Union[int, str], nfc: bool = False) -> None:
        """
        Unloads the workpiece from bucket at desired location by bringing the full bucket to the conveyor belt,
        waiting for the vgr to interact with it and bringing the now empty bucket back to the slot
        If nfc is True, it uses the nfc-reader-id as the bucket position
        Else it uses the bucket position (0-8) or searches the next one if "next" is passed
        :param slot_number: Number of bucket to store
        :param nfc: Whether to use nfc or not
        :raises ValueError: When the HBW is empty or the slot_number is wrong
        :return: None
        """
        self.update_with_nfc()
        if nfc:
            pass  # TODO Implement
        else:
            if slot_number == "next":
                try:
                    slot_number = self.is_bucket_empty_list.index(False)
                except ValueError:
                    raise ValueError("High Bay Warehouse is empty")
            if 0 <= slot_number <= 8:
                self.set_current_task_to_unload(f"workpiece", slot_number, 1)
                self._transport_bucket_to_conveyor_belt(slot_number)
                self._move_conveyor_belt_to_waiting_platform()
                self._wait_for_vgr_to_interact_with_bucket()
                self._transport_bucket_to_slot(slot_number)
                self.is_bucket_empty_list[slot_number] = True
                self.set_current_task("", 1)
                self._update_current_hbw_stock(slot_number, "")
            else:
                raise ValueError("Position does not exist")
        return

    def _transport_bucket_to_slot(self, slot_number):
        temp_coordinate = self.conveyor_belt_pos
        self._move_to_target(temp_coordinate._replace(y=temp_coordinate[1] + 100))
        self._pick_up_bucket_from_conveyor_belt()
        self.calibrate(2)
        self.calibrate(4)
        self.set_current_sub_task_to_transport(f"bucket", f"slot {slot_number}", 1)
        temp2_coordinate = self.bucket_pos_tuple[slot_number]
        self._move_to_target(temp2_coordinate._replace(y=temp2_coordinate[1]-40))
        self._drop_off_bucket_to_slot()

    def _transport_bucket_to_conveyor_belt(self, slot_number: int):
        self.set_current_sub_task_to_move(f"slot {slot_number}", 1)
        temp_coordinate = self.bucket_pos_tuple[slot_number]
        self._move_to_target(temp_coordinate._replace(y=temp_coordinate[1] + 60))
        self._pick_up_bucket_from_slot()
        self.set_current_sub_task_to_transport(f"bucket", f"conveyor belt", 1)
        self._move_to_target(self.conveyor_belt_pos)
        self._drop_off_bucket_to_conveyor_belt()

    def _wait_for_vgr_to_interact_with_bucket(self):
        self.set_current_sub_task_to_waiting("the vacuum gripper robot to interact with the bucket", 1)
        while self.i2.state() == 1:
            time.sleep(0.5)
            # print("waiting")
        time.sleep(4)

    def change_buckets(self, slot_one: Union[int, str], slot_two: Union[int, str], nfc: bool = False):
        """
        Changes the two buckets
        If nfc is True, it uses the nfc-reader-id as the bucket position
        Else it uses the bucket position (0-8) or searches the next one if "next" is passed
        :param slot_one: Number of bucket to change
        :param slot_two: Number of bucket to change
        :param nfc: Whether to use nfc or not
        :raises ValueError: When trying to change two empty buckets or when slot_number is wrong
        :return: None
        """
        if slot_one == slot_two:
            return
        self.update_with_nfc()
        if nfc:
            pass  # TODO Implement
        else:
            if slot_one == "next" and slot_two == "next":  # or
                #  (self.is_bucket_empty_list[bucket_one] and self.is_bucket_empty_list[bucket_two])):
                raise ValueError("Both buckets are empty")
            else:
                self.set_current_task_to_change_buckets(slot_one, slot_two, 1)
                self.set_current_sub_task_to_move(f"slot {slot_one}", 1)
                temp_coordinate = self.bucket_pos_tuple[slot_one]
                self._move_to_target(temp_coordinate._replace(y=temp_coordinate[1] + 60))
                self._pick_up_bucket_from_slot()

                self.set_current_sub_task_to_transport("bucket", "conveyor belt", 1)
                self._move_to_target(self.conveyor_belt_pos)
                self._drop_off_bucket_to_conveyor_belt()
                self.calibrate(2)
                self.calibrate(4)

                self.set_current_sub_task_to_move(f"slot {slot_two}", 1)
                temp_coordinate = self.bucket_pos_tuple[slot_two]
                self._move_to_target(temp_coordinate._replace(y=temp_coordinate[1] + 60))

                self._pick_up_bucket_from_slot()
                self.set_current_sub_task_to_transport("bucket", f"slot {slot_one}", 1)
                self._move_to_target(self.bucket_pos_tuple[slot_one])
                self._drop_off_bucket_to_slot()

                self.set_current_sub_task_to_move("conveyor belt", 1)
                temp_coordinate = self.conveyor_belt_pos
                self._move_to_target(temp_coordinate._replace(y=temp_coordinate[1] + 100))
                self._pick_up_bucket_from_conveyor_belt()
                self.calibrate(2)
                self.calibrate(4)
                self.set_current_sub_task_to_transport("bucket", f"slot {slot_two}", 1)
                self._move_to_target(self.bucket_pos_tuple[slot_two])
                self._drop_off_bucket_to_slot()

                # Swap bucket states
                self.is_bucket_empty_list[slot_one], self.is_bucket_empty_list[slot_two] = \
                    self.is_bucket_empty_list[slot_two], self.is_bucket_empty_list[slot_one]
                self.set_current_task("", 1)

    def get_amount_of_stored_workpieces(self) -> int:
        """
        Returns the quantity of stored workpieces
        :return: Amount of stored workpieces
        """
        return self.is_bucket_empty_list.count(False)

    def get_slot_number_of_workpiece_by_color(self, color) -> int:
        for key, slot in self.current_stock.items():
            if slot == color:
                return int(key)
        return -1

    def _load_current_hbw_stock(self):
        file = os.path.join("stock", "hbw", "HBW.json")
        with open(file) as json_file:
            data = json.load(json_file)
        return data

    def _update_current_hbw_stock(self,slot_number, color):
        file = os.path.join(os.path.dirname(os.getcwd()), "stock", "hbw", "HBW.json")
        self.current_stock[str(slot_number)] = color
        with open(file, 'w') as json_file:
            json.dump(self.current_stock, json_file)

    def _find_empty_slot(self):
        for key, slot in self.current_stock.items():
            if slot == "":
                return int(key)
        return -1