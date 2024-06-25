import high_bay_warehouse_txts
from collections import namedtuple
import json
import os

Coordinate = namedtuple("Coordinate", ["x", "y"])


class HighBayWarehouse1(high_bay_warehouse_txts.HighBayWarehouseTXT):
    def __init__(self):
        c = os.path.join("calib", "Calib.HBW.json")
        with open(c) as json_file:
            data = json.load(json_file)
        conv_x = data['HBW']['conv']['x']
        conv_y = data['HBW']['conv']['y']

        hbx_1 = data['HBW']['hbx']['1']
        hbx_2 = data['HBW']['hbx']['2']
        hbx_3 = data['HBW']['hbx']['3']

        hby_1 = data['HBW']['hby']['1']
        hby_2 = data['HBW']['hby']['2']
        hby_3 = data['HBW']['hby']['3']

        # Coordinates
        self.conveyor_belt_pos = Coordinate(conv_x, conv_y)  # Pos facing towards the crane jib
        #self.conveyor_belt_pos = Coordinate(32, 660)
        self.target_pos = Coordinate(0, 0)

        # Bucket positions in the HBW
        self.bucket_pos_tuple = (
            Coordinate(hbx_3, hby_1),
            Coordinate(hbx_2, hby_1),
            Coordinate(hbx_1, hby_1),
            Coordinate(hbx_3, hby_2),
            Coordinate(hbx_2, hby_2),
            Coordinate(hbx_1, hby_2),
            Coordinate(hbx_3, hby_3),
            Coordinate(hbx_2, hby_3),
            Coordinate(hbx_1, hby_3),
        )

        self.bucket_pos_tuple_old = (
            Coordinate(1980, 65),
            Coordinate(1380, 75),
            Coordinate(780, 75),
            Coordinate(1980, 430),
            Coordinate(1380, 430),
            Coordinate(780, 430),
            Coordinate(1985, 830),
            Coordinate(1385, 830),
            Coordinate(785, 830),
        )
        super(HighBayWarehouse1, self).__init__(12)
