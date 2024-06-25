import ftrobopy
import datetime
from typing import Union

STATE_READY = "ready"
STATE_INACTIVE = "inactive"
STATE_NOT_READY = "not ready"


class GeneralTXT:
    def __init__(self, txt_number: int):
        """
        Initialize TXT
        :param txt_number: Number of the txt
        """
        self.txt = ftrobopy.ftrobopy(host=f"192.168.0.{txt_number}", port=65000, update_interval=0.01)
        self.txt_number = txt_number
        # Motors
        self.m1 = self.txt.motor(1)
        self.m2 = self.txt.motor(2)
        self.m3 = self.txt.motor(3)
        self.m4 = self.txt.motor(4)
        # Inputs e.g. light barriers or position switches
        self.i1 = self.txt.input(1)
        self.i2 = self.txt.input(2)
        self.i3 = self.txt.input(3)
        self.i4 = self.txt.input(4)
        self.i5 = self.txt.input(5)
        self.i6 = self.txt.input(6)
        self.i7 = self.txt.input(7)
        self.i8 = self.txt.input(8)
        # Outputs e.g. valves
        self.o1 = self.txt.output(1)
        self.o2 = self.txt.output(2)
        self.o3 = self.txt.output(3)
        self.o4 = self.txt.output(4)
        self.o5 = self.txt.output(5)
        self.o6 = self.txt.output(6)
        self.o7 = self.txt.output(7)
        self.o8 = self.txt.output(8)
        # RPC Port for the RPC Server on the TXT
        self.rpc_port = 8000 + self.txt_number
        # MQTT configs

        self.mqtt_topic_name = self.get_mqtt_topic_name(1)
        self.current_task = ""
        self.current_task_start_timestamp = None
        self.current_sub_task = ""
        self.current_state = STATE_READY
        self.failure_label = ""

        self.mqtt_topic_name_for_second_machine = self.get_mqtt_topic_name(2)
        self.current_task_for_second_machine = ""
        self.current_task_start_timestamp_for_second_machine = None
        self.current_sub_task_for_second_machine = ""
        self.current_state_for_second_machine = STATE_READY
        self.failure_label_for_second_machine = ""
        self.mqtt_publish_frequency = 2
        self.mqtt_host = "broker.hivemq.com"

    def is_connected(self) -> str:
        """
        returns a string if the txt is connected
        :return: "(number of TXT) is connected"
        """
        return f"TXT {self.txt_number} is connected"

    def state_of_machine(self, machine_number: int) -> str:
        """
        returns the current state of the machine
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: state of the machine
        """
        if machine_number == 1:
            return self.current_state
        elif machine_number == 2:
            return self.current_state_for_second_machine
        else:
            raise ValueError("There is no txt controller which controls 3 machines")

    def set_current_state(self, new_state: str, machine_number: int) -> None:
        """
        updates the current_state if the String within the argument is valid
        :param new_state: new state with which the old current_state will be updated
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        if machine_number == 1:
            if new_state == STATE_READY or new_state == STATE_NOT_READY or new_state == STATE_INACTIVE:
                self.current_state = new_state
            return
        elif machine_number == 2:
            if new_state == STATE_READY or new_state == STATE_NOT_READY or new_state == STATE_INACTIVE:
                self.current_state_for_second_machine = new_state
            return
        else:
            raise ValueError("There is no txt controller which controls 3 machines")

    def set_current_task(self, string_message: str, machine_number: int) -> None:
        """
        updates the current_task to the String of the only argument
        if the argument String is empty the current_state is set to "ready" and current_sub_task is reset to ""
        if the argument String is not empty the current_state gets updated to 'not ready"
        :param string_message: new message with which the old current_task will be updated
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        if machine_number == 1:
            if string_message == "":
                self.current_task_start_timestamp = None
                self.current_task = ""
                self.set_current_sub_task("", 1)
                self.set_current_state(STATE_READY, 1)
            else:
                self.set_current_state(STATE_NOT_READY, 1)
                self.current_task = f"{string_message}"
                self.current_task_start_timestamp = datetime.datetime.now()
            return
        elif machine_number == 2:
            if string_message == "":
                self.current_task_start_timestamp_for_second_machine = None
                self.current_task_for_second_machine = ""
                self.set_current_sub_task("", 2)
                self.set_current_state(STATE_READY, 2)
            else:
                self.set_current_state(STATE_NOT_READY, 2)
                self.current_task_for_second_machine = f"{string_message}"
                self.current_task_start_timestamp_for_second_machine = datetime.datetime.now()
            return
        else:
            raise ValueError("There is no txt controller which controls 3 machines")

    def set_current_task_to_pick_up_and_transport(self, transported_thing: str, pick_up_position: Union[str, tuple],
                                                  drop_off_position: Union[str, tuple], machine_number: int) -> None:
        """
        updates the current_task to a transport task with a start and an end
        :param transported_thing: what is transported - e.g. a workpiece or a bucket
        :param pick_up_position: where is the transported thing picked up from
        :param drop_off_position: where is the transported thing transported to and dropped of
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_task(
            f"picking up and transporting the {transported_thing} from "
            f"the {pick_up_position} to the {drop_off_position}", machine_number)
        return

    def set_current_task_to_pick_up(self, picked_up_thing: str, pick_up_position: Union[str, tuple],
                                    machine_number: int) -> None:
        """
        updates the current_task to a transport task with a start and an end
        :param picked_up_thing: what is picked up - e.g. a workpiece or a bucket
        :param pick_up_position: where is the picked up thing picked up from
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_task(f"picking up the {picked_up_thing} from the {pick_up_position}", machine_number)
        return

    def set_current_task_to_transport(self, transported_thing: str, drop_off_position: Union[str, tuple],
                                      machine_number: int) -> None:
        """
        updates the current_task to a transport task with a start and an end
        :param transported_thing: what is transported - e.g. a workpiece or a bucket
        :param drop_off_position: where is the transported thing transported to and dropped of
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_task(f"transporting the {transported_thing} to the {drop_off_position}", machine_number)
        return

    def set_current_task_to_move(self, target_position: str, machine_number: int) -> None:
        """
        updates the current_task to a movement task with an end
        :param target_position: where should the component of the machine move to
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_task(f"moving towards the {target_position}", machine_number)
        return

    def set_current_task_to_stop_holding(self, machine_number: int) -> None:
        self.set_current_task(f"dropping the workpiece ", machine_number)
        return

    def set_current_task_to_mill(self, start: str, end: str, time_in_seconds: int, machine_number: int) -> None:
        """
        updates the current_task to a milling task
        :param start: where does the workpiece start when the milling process is called
        :param end: where does the workpiece end when the milling process is completed
        :param time_in_seconds: how long should the mill be used
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_task(f"transporting the workpiece from the {start} to the mill, "
                              f"milling it for {time_in_seconds} seconds and "
                              f"transporting it to the {end} afterwards", machine_number)

    def set_current_task_to_burn(self, time_in_seconds: int, machine_number: int) -> None:
        """
        updates the current_task to a predefined burn text
        :param time_in_seconds: how long should the workpiece stay in the oven
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_task(f"burning the workpiece for {time_in_seconds} seconds", machine_number)
        return

    def set_current_task_to_store(self, transported_thing: str, slot_number: int, machine_number: int) -> None:
        """
        updates the current_task to a storage task
        :param transported_thing: what is stored -e.g. a bucket
        :param slot_number: in which slot is the bucket (with the workpiece) stored
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_task(f"storing a new {transported_thing} in slot {slot_number}", machine_number)
        return

    def set_current_task_to_unload(self, transported_thing: str, slot_number: int, machine_number: int) -> None:
        """
        updates the current_task to a unload task
        :param transported_thing: what is stored -e.g. a bucket
        :param slot_number: in which slot is the bucket (with the workpiece) stored which should be unloaded
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_task(f"unloading a {transported_thing} from slot {slot_number}", machine_number)
        return

    def set_current_task_to_change_buckets(self, slot_one: int, slot_two: int, machine_number: int) -> None:
        """
        updates the current_task to a bucket changing task
        :param slot_one: in which slot is the first bucket located which should switch it's slot
        :param slot_two: in which slot is the second bucket located which should switch it's slot
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_task(f"changing the position of the bucket in slot {slot_one} and bay {slot_two}",
                              machine_number)
        return

    def set_current_task_to_full_calibration(self, machine_number: int) -> None:
        """
        updates the current_task to a predefined calibration text which is identical across all machine controllers
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_task("calibrating all components", machine_number)
        return

    def set_current_task_to_sorting(self, start: str, read_nfc: bool, predefined_ejection_location: str,
                                    machine_number: int) -> None:
        """
        updates the current_task to a predefined sorting text
        :param start: specifies where the workpiece starts the sorting process
        :param read_nfc: specifies if the nfc_tag_reader should be used during the sorting process
        :param predefined_ejection_location: into which predefined sink should the workpiece go - 0 means that no
        predefined sink has been set
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        if read_nfc:
            nfc_string = "using the nfc reader"
        else:
            nfc_string = "without using the nfc reader"
        if predefined_ejection_location:
            sink_string = f"into the predefined ejection location {predefined_ejection_location}"
        else:
            sink_string = "into a sink based on the detected color"
        self.set_current_task(f"sorting the workpiece which is located at {start} {nfc_string} {sink_string}",
                              machine_number)
        return

    def set_current_sub_task(self, string_message: str, machine_number: int) -> None:
        """
        updates the current_sub_task to the String of the only argument
        :param string_message: message which will replace the old current_sub_task
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        if machine_number == 1:
            self.current_sub_task = f"{string_message}"
            return
        elif machine_number == 2:
            self.current_sub_task_for_second_machine = f"{string_message}"
            return
        else:
            raise ValueError("There is no txt controller which controls 3 machines")

    def set_current_sub_task_to_eject(self, target_destination: str, machine_number: int) -> None:
        """
        updates the current_sub_task to an ejecting task with a target_destination
        :param target_destination: to which destination should the workpiece be ejected
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_sub_task(f"ejecting the workpiece to the {target_destination}", machine_number)

    def set_current_sub_task_to_read_nfc(self, nfc_reader_name: str, machine_number: int) -> None:
        """
        updates the current_sub_task to an nfc reading task by a given nfc_reader
        :param nfc_reader_name: name of the nfc reader which should read the workpiece's nfc data
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_sub_task(f"reading workpiece nfc data with {nfc_reader_name}", machine_number)
        return

    def set_current_sub_task_to_write_nfc(self, nfc_reader_name: str, machine_number: int) -> None:
        """
        updates the current_sub_task to an nfc writing task by a given nfc_reader
        :param nfc_reader_name: name of the nfc reader which should write the workpiece's nfc data
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_sub_task(f"writing workpiece nfc data with {nfc_reader_name}", machine_number)
        return

    def set_current_sub_task_to_transport(self, transported_thing: str,
                                          target_destination: Union[int, str, tuple], machine_number: int) -> None:
        """
        updates the current_sub_task to a transport task with a target destination
        the difference between a transport task an a movement task is that
        a transport operation involves a workpiece and a movement task does not involve a workpiece
        :param transported_thing: what is transported - e.g. a workpiece or a bucket
        :param target_destination: tho where is the transported thing transported
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_sub_task(f"transporting the {transported_thing} to the {target_destination}", machine_number)
        return

    def set_current_sub_task_to_move(self, target_destination: Union[str, tuple], machine_number: int) -> None:
        """
        updates the current_sub_task to a movement task with a target destination
        the difference between a transport task an a movement task is that
        a transport operation involves a workpiece and a movement task does not involve a workpiece
        :param target_destination: where should the component of the machine move to
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_sub_task(f"moving towards the {target_destination}", machine_number)
        return

    def set_current_sub_task_to_individual_motor_calibration(self, motor_name: str, machine_number: int) -> None:
        """
        updates the current_sub_task to a calibration task for a given motor
        :param motor_name: which motor is currently calibrating itself
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_sub_task(f"calibrating {motor_name}", machine_number)
        return

    def set_current_sub_task_to_pick_up(self, picked_up_thing: str, pick_up_position: str, machine_number: int) -> None:
        """
        updates the current_sub_task to a pick_up_task task with a pick up position
        :param picked_up_thing: what is picked up - e.g. a workpiece or a bucket
        :param pick_up_position: where is the picked up thing picked up from
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_sub_task(f"picking up the {picked_up_thing} from the {pick_up_position}", machine_number)
        return

    def set_current_sub_task_to_drop_off(self, dropped_off_thing: str, drop_off_position: str,
                                         machine_number: int) -> None:
        """
        updates the current_sub_task to a drop_off_task task with a drop off position
        :param dropped_off_thing: what is dropped off - e.g. a workpiece or a bucket
        :param drop_off_position: where is the transported thing transported to and dropped of
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_sub_task(f"dropping off the {dropped_off_thing} at the {drop_off_position}", machine_number)
        return

    def set_current_sub_task_to_detecting_color(self, machine_number: int) -> None:
        """
        updates the current_sub_task to a color detection task
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_sub_task("detecting the workpiece color", machine_number)

    def set_current_sub_task_to_manipulating_oven_door(self, opening_or_closing: str, machine_number: int) -> None:
        """
        updates the current_sub_task to a door opening/ closing task
        :param opening_or_closing: is the door opened or closed
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_sub_task(f"{opening_or_closing} the oven door", machine_number)

    def set_current_sub_task_to_mill(self, time_in_seconds: int, machine_number: int) -> None:
        """
        updates the current_sub_task to a milling task
        :param time_in_seconds: how long should the mill be used
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_sub_task(f"milling the workpiece for {time_in_seconds} seconds", machine_number)

    def set_current_sub_task_to_burning(self, time_in_seconds: int, machine_number: int) -> None:
        """
        updates the current_sub_task to a waiting for burning to complete task
        :param time_in_seconds: how long should the workpiece stay in the oven
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_sub_task(f"burning the workpiece for {time_in_seconds} seconds", machine_number)

    def set_current_sub_task_to_waiting(self, string_for_what: str, machine_number: int) -> None:
        """
        updates the current_sub_task to a waiting task
        :param string_for_what: message which specifies what is being waited for
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: None
        """
        self.set_current_sub_task(f"waiting for {string_for_what}", machine_number)

    def get_mqtt_topic_name(self, machine_number: int) -> str:
        """
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: Mqtt topic name for the specific txt
        """
        if machine_number == 1:
            topics = {
                14: "SM_1",
                11: "MM_1",
                15: "OV_1",
                13: "VGR_1",
                10: "EC_1",
                12: "HBW_1"
            }
        elif machine_number == 2:
            topics = {
                14: "",
                11: "",
                15: "WT_1",
                13: "",
                10: "",
                12: ""
            }
        else:
            raise ValueError("There is no txt controller which controls 3 machines")
        topic_name = "FTFactory/" + str(topics.get(self.txt_number))
        return topic_name

    def calculate_elapsed_seconds_since_start(self, machine_number) -> float:
        """
        :param machine_number: since there are txt controllers which control multiple machines this parameter specifies
        which machine of the same txt controller is addressed
        :return: elapsed time in seconds since start
        """
        if machine_number == 1:
            if self.current_task_start_timestamp is None:
                return 0.0
            else:
                time_delta = datetime.datetime.now() - self.current_task_start_timestamp
                return float(f"{time_delta.seconds}.{time_delta.microseconds:06d}")
        elif machine_number == 2:
            if self.current_task_start_timestamp_for_second_machine is None:
                return 0.0
            else:
                time_delta = datetime.datetime.now() - self.current_task_start_timestamp_for_second_machine
                return float(f"{time_delta.seconds}.{time_delta.microseconds:06d}")
        else:
            raise ValueError("There is no txt controller which controls 3 machines")
