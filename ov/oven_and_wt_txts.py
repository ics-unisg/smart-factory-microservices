import multi_processing_station_txts
from datetime import datetime
import paho.mqtt.client as mqtt
import json
import time
from xmlrpc.server import SimpleXMLRPCServer
from threading import Thread
import xmlrpc.client
import uuid

NAME_OVEN = "oven"
NAME_MILLING_MACHINE = "milling_machine"


class OvenAndWTTXT(multi_processing_station_txts.MultiProcessingStationTXT):
    def __init__(self, txt_number):
        super(OvenAndWTTXT, self).__init__(txt_number)
        self.m1_speed = 512
        self.m2_speed = 512

        self.is_compressor_used_by_oven = False
        self.is_compressor_used_by_wt = False

        # Start Threads
        threads = [
            Thread(target=self.ov_execution_rpc_server),
            Thread(target=self.wt_execution_rpc_server),
            Thread(target=self.ov_getter_setter_rpc_server),
            Thread(target=self.wt_getter_setter_rpc_server),
            Thread(target=self.stream_data_via_mqtt),
            Thread(target=self.wt_stream_data_via_mqtt),
            Thread(target=self.calibrate()),
            Thread(target=self.wt_calibrate()),
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
                'i5_light_barrier': self.i5.state(),
                'm1_speed': self.txt.getPwm(0) - self.txt.getPwm(1),
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

    def wt_stream_data_via_mqtt(self) -> None:
        """
        Starts the MQTT streaming
        :return: None
        """
        client = mqtt.Client()
        client.connect(self.mqtt_host, 1883, 60)
        print(f"Started the MQTT Publisher for TXT{self.txt_number} WT - "
                             f"Topic-Name: {self.mqtt_topic_name_for_second_machine}")
        while True:
            payload = {
                "id": str(uuid.uuid4()),
                "station": self.mqtt_topic_name_for_second_machine.replace("FTFactory/",""),
                "timestamp": str(datetime.now())[:-4],
                'i3_pos_switch': self.i3.state(),
                'i4_pos_switch': self.i4.state(),
                'm2_speed': self.txt.getPwm(2)-self.txt.getPwm(3),
                'o5_valve': self.txt.getPwm(4),
                'o6_valve': self.txt.getPwm(5),
                'o8_compressor': self.txt.getPwm(7),
                'current_state': self.current_state_for_second_machine,
                'current_task': self.current_task_for_second_machine,
                'current_task_duration': self.calculate_elapsed_seconds_since_start(2),
                'current_sub_task': self.current_sub_task_for_second_machine,
            }
            json_payload = json.dumps(payload)
            client.publish(topic=self.mqtt_topic_name_for_second_machine, payload=json_payload, qos=0, retain=False )
            time.sleep(1/self.mqtt_publish_frequency)

    def ov_execution_rpc_server(self) -> None:
        """
        RPC-Server-Thread for oven execution methods which have to be handled one after the other
        :return: None
        """
        SimpleXMLRPCServer.allow_reuse_address = True
        server = SimpleXMLRPCServer(("localhost", self.rpc_port), logRequests=False, allow_none=True)
        server.register_function(self.is_connected, "is_connected")
        server.register_function(self.calibrate, "calibrate")
        server.register_function(self.burn, "burn")
        print(f"Started the ov_execution_rpc_server for TXT{self.txt_number}")
        server.serve_forever()

    def ov_getter_setter_rpc_server(self) -> None:
        """
         RPC-Server-Thread for oven getter and setter methods
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
        print(f"Started the ov_getter_setter_rpc_server for TXT{self.txt_number}")
        server.serve_forever()

    def wt_execution_rpc_server(self) -> None:
        """
        RPC-Server-Thread for workstation transport execution methods which have to be handled one after the other
        Sets the Port + 500 to let two RPC Server run on the same TXT
        :return: None
        """
        SimpleXMLRPCServer.allow_reuse_address = True
        server = SimpleXMLRPCServer(("localhost", self.rpc_port + 400), logRequests=False, allow_none=True)
        server.register_function(self.wt_is_connected, "wt_is_connected")
        server.register_function(self.wt_calibrate, "wt_calibrate")
        server.register_function(self.wt_move_to, "wt_move_to")
        server.register_function(self.wt_pick_up_and_transport, "wt_pick_up_and_transport")
        print(f"Started the RPC Server for TXT{self.txt_number} WT")
        server.serve_forever()

    def wt_getter_setter_rpc_server(self) -> None:
        """
         RPC-Server-Thread for workstation transport getter and setter methods
        :return: None
        """
        SimpleXMLRPCServer.allow_reuse_address = True
        server = SimpleXMLRPCServer(("localhost", self.rpc_port - 400), logRequests=False, allow_none=True)
        server.register_function(self.wt_is_connected, "wt_is_connected")
        server.register_function(self.state_of_machine, "wt_state_of_machine")
        server.register_function(self.wt_get_motor_speed, "wt_get_motor_speed")
        server.register_function(self.wt_set_motor_speed, "wt_set_motor_speed")
        server.register_function(self.wt_reset_all_motor_speeds, "wt_reset_all_motor_speeds")
        server.register_function(self.wt_check_position, "wt_check_position")
        print(f"Started the wt_getter_setter_rpc_server for TXT{self.txt_number}")
        server.serve_forever()

    def wt_is_connected(self) -> str:
        """
        returns a string if the txt is connected
        :return: "(number of TXT) is connected"
        """
        return f"TXT {self.txt_number} is connected"

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

    def calibrate(self) -> None:
        """
        Calibrates M1
        :return: None
        """
        self.set_current_task_to_full_calibration(1)
        self._open_oven_door()
        self.set_current_sub_task_to_individual_motor_calibration(f"motor 1", 1)
        self.m1.setDistance(1000)
        self.m1.setSpeed(self.m1_speed)
        while self.i2.state() == 0:
            pass
        self.m1.stop()
        self._close_oven_door()
        self._adjust_platform_for_workstation_transport()
        self.set_current_task("", 1)


    def status_of_light_barrier(self, lb: int) -> bool:
        """
        Returns TRUE if the light barrier is interrupted else False
        :raises ValueError when trying to access a hardware which doesn't exist
        :param lb: Number of light barrier to check
        :return: Light barrier interruption status interrupted <-> True , uninterrupted <-> False
        """
        if lb == 5:
            result = self.i5.state() == 0
            #self.ov_logger.debug(f"State of workpiece in {lb} is {result}")
            return result
        else:
            #self.ov_logger.error(f"Trying to access non-existing light barrier {lb}")
            raise ValueError(f"Light Barrier {lb} does not exist")

    def _drive_into_oven(self) -> None:
        """
        Drives the transport platform into the Oven and opens the Ovens door
        :return: None
        """
        if self.i1.state() != 0:
            # Platform already in oven
            return
        self._open_oven_door()
        self.set_current_sub_task_to_transport("workpiece", "inside of the oven", 1)
        self.m1.setDistance(1000)
        self.m1.setSpeed(-1 * self.m1_speed)
        while self.i1.state() == 0: #This works now
            pass
        self.m1.stop()
        self._close_oven_door()
        return

    def _drive_out_of_oven(self) -> None:
        """
        Drives the transport platform out of the Oven and closes the Ovens door
        :return: None
        """
        if self.i2.state() != 0:
            # Platform already out of oven
            return
        self._open_oven_door()
        self.set_current_sub_task_to_transport("workpiece", "outside of the oven", 1)
        self.m1.setSpeed(1 * self.m1_speed)
        while self.i2.state() == 0:
            pass
        self.m1.stop()
        self._close_oven_door()
        return

    def _adjust_platform_for_workstation_transport(self) -> None:
        """
        Drives the transport platform towards the oven so the suction head of the Workstation Transport aligns better
        """
        self.m1.setDistance(100)
        self.m1.setSpeed(-1 * self.m1_speed)
        time.sleep(0.3)
        self.m1.stop()
        return

    def _open_oven_door(self) -> None:
        """
        Opens the door of the Oven
        :return: None
        """
        while self.is_compressor_used_by_wt:  # WT uses Compressor
            pass
        self.set_current_sub_task_to_manipulating_oven_door("opening", 1)
        self.is_compressor_used_by_oven = True
        time.sleep(1)
        mm1 = xmlrpc.client.ServerProxy("http://mm:8011")
        mm1.activate_compressor()
        time.sleep(2)
        self.o7.setLevel(512)

    def _close_oven_door(self) -> None:
        """
        Closes the door of the Oven
        :return: None
        """
        self.set_current_sub_task_to_manipulating_oven_door("closing", 1)
        time.sleep(1)
        mm1 = xmlrpc.client.ServerProxy("http://mm:8011")
        mm1.deactivate_compressor()
        self.o7.setLevel(0)  # Close valve
        self.is_compressor_used_by_oven = False

    def burn(self, time_in_seconds: int = 2) -> None:
        """
        Drives into the oven, "burns" for the specified time and drives out of the oven
        """
        self.set_current_task_to_burn(time_in_seconds, 1)
        self._drive_into_oven()
        self.set_current_sub_task_to_burning(time_in_seconds, 1)
        self.txt.play_sound(15)
        for i in range(time_in_seconds*8):
            if i%2==0:
                self.o8.setLevel(512)
            else: self.o8.setLevel(0)
            time.sleep(0.3)
        self.o8.setLevel(0)
        self._drive_out_of_oven()
        self._adjust_platform_for_workstation_transport()
        self.set_current_task("", 1)
        return

    # - WORKSTATION TRANSPORT - #

    def wt_set_motor_speed(self, motor: int, new_speed: int) -> None:
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
        if motor == 2:
            self.m2_speed = new_speed
            return
        else:
            raise ValueError(f"Trying to access non-existing motor {motor}")

    def wt_reset_all_motor_speeds(self) -> None:
        """
        Resets all motor speeds to the maximum
        :return: None
        """
        self.m2_speed = 512
        return

    def wt_get_motor_speed(self, motor: int) -> int:
        """
        Gets the speed of the specified motor
        :raises ValueError when trying to access a hardware which doesn't exist
        :return: Motor speed
        """
        if motor == 2:
            return self.m2_speed
        else:
            raise ValueError(f"Trying to access non-existing motor {motor}")

    def wt_calibrate(self) -> None:
        """
        Calibrates M2
        :return: None
        """
        self.set_current_task_to_full_calibration(1)
        self.set_current_sub_task_to_individual_motor_calibration(f"motor 1", 1)
        self._wt_move_to_milling_machine()
        self.set_current_task("", 1)
        return

    def wt_move_to(self, position: str):
        if position == NAME_OVEN:
            self.set_current_task_to_move(NAME_OVEN, 1)
            self.set_current_sub_task_to_move(NAME_OVEN, 1)
            self._wt_move_to_oven()
            self.set_current_task("", 1)
        elif position == NAME_MILLING_MACHINE:
            self.set_current_task_to_move(NAME_MILLING_MACHINE, 1)
            self.set_current_sub_task_to_move(NAME_MILLING_MACHINE, 1)
            self._wt_move_to_milling_machine()
            self.set_current_task("", 1)
        else:
            raise ValueError("Wrong position parameter")

    def wt_check_position(self, position_which_is_queried) -> bool:
        if position_which_is_queried == NAME_OVEN:
            return self.current_position == NAME_OVEN
        elif position_which_is_queried == NAME_MILLING_MACHINE:
            return self.current_position == NAME_MILLING_MACHINE
        else:
            return False

    def wt_pick_up_and_transport(self, start: str, end: str) -> None:
        """
        Moves to the desired start position, picks the workpiece up, then moves to the desired end position to drop
        the workpiece off
        :param start: either "oven" or "milling machine"
        :param end: either "oven" or "milling machine"
        :raises ValueError when start == end or one of them != oven / milling_machine
        """
        if (start == end) or (start != NAME_OVEN and start != NAME_MILLING_MACHINE) \
                or (end != NAME_OVEN and end != NAME_MILLING_MACHINE):
            raise ValueError("Wrong start or end parameter")
        if start == NAME_OVEN:
            self.set_current_task_to_pick_up_and_transport("workpiece", NAME_OVEN, NAME_MILLING_MACHINE, 1)
            self._wt_pick_up_from_oven()
        else:
            self.set_current_task_to_pick_up_and_transport("workpiece", NAME_MILLING_MACHINE, NAME_OVEN, 1)
            self._wt_pick_up_from_milling_machine()
        if end == NAME_OVEN:
            self._wt_transport_to_oven()
        else:
            self._wt_transport_to_milling_machine()
        self.set_current_task("", 1)
        return

    def _wt_move_to_milling_machine(self) -> None:
        """
        Moves the crane to the Milling Machine
        :return: None
        """
        self.current_position = NAME_MILLING_MACHINE
        self.m2.setDistance(1000)
        self.m2.setSpeed(self.m2_speed)
        mm1 = xmlrpc.client.ServerProxy("http://mm:7011")
        while mm1.is_active() == 0:
            pass
        self.m2.stop()
        # self.m2.setDistance(1000)
        # self.m2.setSpeed(-1 * self.m2_speed)
        # time.sleep(0.3)
        # self.m2.stop()
        return

    def _wt_move_to_oven(self) -> None:
        """
        Moves the crane to the Oven
        :return: None
        """
        self.current_position = NAME_OVEN
        self.m2.setDistance(1000)
        self.m2.setSpeed(-1 * self.m2_speed)
        while self.i3.state() == 0:
            pass
        self.m2.stop()
        return

    def _wt_pick_workpiece_up(self) -> None:
        """
        Moves the crane down, starts the vacuum suction to pick the workpiece up and moves the crane up
        :return: None
        """
        while self.is_compressor_used_by_oven:  # Compressor is used by oven
            pass
        self.is_compressor_used_by_wt = True
        time.sleep(1)
        mm1 = xmlrpc.client.ServerProxy("http://mm:8011")
        mm1.activate_compressor()
        time.sleep(0.5)
        self.o6.setLevel(512)  # Open valve to drive crane down
        time.sleep(0.3)
        self.o5.setLevel(512)  # Open valve to start vacuum suction
        time.sleep(0.6)
        self.o6.setLevel(0)  # Close valve to drive crane up
        return

    def _wt_drop_workpiece_off(self) -> None:
        """
        Moves the crane down, stops the vacuum suction to drop the workpiece off and moves the crane up
        :return: None
        """
        self.o6.setLevel(512)  # Open valve to drive crane down
        time.sleep(0.2)
        self.o5.setLevel(0)  # Close valve to stop vacuum suction
        time.sleep(0.5)
        self.o6.setLevel(0)  # Close valve to drive crane up
        time.sleep(0.5)
        time.sleep(1)
        mm1 = xmlrpc.client.ServerProxy("http://mm:8011")
        mm1.deactivate_compressor()
        self.is_compressor_used_by_wt = False
        return

    def _wt_pick_up_from_oven(self) -> None:
        """
        Moves to the Oven and picks the workpiece up
        :return: None
        """
        self.set_current_sub_task_to_move(NAME_OVEN, 1)
        self._wt_move_to_oven()
        self.set_current_sub_task_to_pick_up("workpiece", NAME_OVEN, 1)
        self._wt_pick_workpiece_up()

    def _wt_pick_up_from_milling_machine(self) -> None:
        """
        Moves to the Milling Machine and picks the workpiece up
        :return: None
        """
        self.set_current_sub_task_to_move(NAME_MILLING_MACHINE, 1)
        self._wt_move_to_milling_machine()
        self.set_current_sub_task_to_pick_up("workpiece", NAME_MILLING_MACHINE, 1)
        self._wt_pick_workpiece_up()

    def _wt_transport_to_oven(self) -> None:
        """
        Moves to the Oven and drops the workpiece off
        :return: None
        """
        self.set_current_sub_task_to_transport("workpiece", NAME_OVEN, 1)
        self._wt_move_to_oven()
        self.set_current_sub_task_to_drop_off("workpiece", NAME_OVEN, 1)
        self._wt_drop_workpiece_off()

    def _wt_transport_to_milling_machine(self) -> None:
        """
        Moves to the Milling Machine and drops the workpiece off
        :return: None
        """
        self.set_current_sub_task_to_transport("workpiece", NAME_MILLING_MACHINE, 1)
        self._wt_move_to_milling_machine()
        # self.m2.setDistance(1000)
        # self.m2.setSpeed(-1 * self.m2_speed)
        # time.sleep(0.3)
        # self.m2.stop()
        self.set_current_sub_task_to_drop_off("workpiece", NAME_MILLING_MACHINE, 1)
        self._wt_drop_workpiece_off()
