import vacuum_gripper_txts
from vacuum_gripper_txts import Coordinate
import json
import os


class VacuumGripperRobot1(vacuum_gripper_txts.VacuumGripperTXT):
    def __init__(self):


        # Coordinates
        # X = Moves the gripper to the left/right
        # Y = Moves the gripper up/down
        # Z = Extracts/Retracts the gripper head

        c = os.path.join("calib", "Calib.VGR.json")
        with open(c) as json_file:
            data = json.load(json_file)

        # Position after the color detection box from the Sorting Machine
        self.color_detection_belt_pos = Coordinate(467, 630, 910)

        # Delivery & Pickup Station
        dps_init = data['VGR']['pos3list'][1]['DIN']
        dps_init['x'] += 10
        dps_init['z'] += 10
        self.delivery_pick_up_pos = Coordinate(dps_init['x'], dps_init['y'], dps_init['z'])
        #self.delivery_pick_up_pos = Coordinate(10, 740, 30)
        dps_color = data['VGR']['pos3list'][5]['DCS']
        # new
        dps_color['x'] += 20
        dps_color['y'] -= 15
        dps_color['z'] += 50
        # new end
        self.color_detection_delivery_pick_up_pos = Coordinate(dps_color['x'], dps_color['y'], dps_color['z'])
        #self.color_detection_delivery_pick_up_pos = Coordinate(120,630,80)
        dps_nfc = data['VGR']['pos3list'][7]['DNFC']
        self.nfc_reader_delivery_pick_up_pos = Coordinate(dps_nfc['x'], dps_nfc['y'], dps_nfc['z'])
        #self.nfc_reader_delivery_pick_up_pos = Coordinate(210,630,250)
        dps_p = data['VGR']['pos3list'][9]['DOUT']
        self.hbw_delivery_station_pos = Coordinate(dps_p['x'], dps_p['y'], dps_p['z'])
        #self.hbw_delivery_station_pos = Coordinate(270,330,530)

        # Positions for the three sinks in the Sorting Machine

        sink1_pu = data['VGR']['pos3list'][16]['SSD1']
        self.sink_1_pick_up_pos = Coordinate(sink1_pu['x'], sink1_pu['y'], sink1_pu['z'])
        #self.sink_1_pick_up_pos = Coordinate(470, 830, 363)
        sink2_pu = data['VGR']['pos3list'][18]['SSD2']
        self.sink_2_pick_up_pos = Coordinate(sink2_pu['x'], sink2_pu['y'], sink2_pu['z'])
        #self.sink_2_pick_up_pos = Coordinate(390, 830, 415)
        sink3_pu = data['VGR']['pos3list'][20]['SSD3']
        self.sink_3_pick_up_pos = Coordinate(sink3_pu['x'], sink3_pu['y'], sink3_pu['z'])
        #self.sink_3_pick_up_pos = Coordinate(323, 830, 572)

        self.sink_1_drop_off_pos = Coordinate(464, 630, 690)
        self.sink_2_drop_off_pos = Coordinate(405, 630, 800)
        self.sink_3_drop_off_pos = Coordinate(345, 630, 900)

        # Positions for the High Bay Warehouse
        self.hbw_waiting_platform_pos = Coordinate(1485, 140, 20)

        hbw_loading = data['VGR']['pos3list'][12]['HBW1']
        self.hbw_loading_pos = Coordinate(hbw_loading['x'], hbw_loading['y'], hbw_loading['z'])
        #self.hbw_loading_pos = Coordinate(1400, 165, 170)

        hbw_holding = data['VGR']['pos3list'][11]['HBW']
        self.hbw_holding_pos = Coordinate(hbw_holding['x'], hbw_holding['y'], hbw_holding['z'])
        #self.hbw_holding_pos = Coordinate(1400, 20, 200)

        # Position for the oven
        oven = data['VGR']['pos3list'][14]['MPO']
        oven['x'] += 6
        self.oven_pos = Coordinate(oven['x'], oven['y'], oven['z'])
        #self.oven_pos = Coordinate(926, 460, 910)

        super(VacuumGripperRobot1, self).__init__(13)
