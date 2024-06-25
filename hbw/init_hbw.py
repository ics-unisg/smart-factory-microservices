from multiprocessing import Process

import HBW1


def init_hbw1():
    HBW1.HighBayWarehouse1()

if __name__ == '__main__':
    process_list = [
        Process(target=init_hbw1),
    ]
    [process.start() for process in process_list]
    [process.join() for process in process_list]