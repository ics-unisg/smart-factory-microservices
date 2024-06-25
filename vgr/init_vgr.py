from multiprocessing import Process

import VGR1


def init_vgr1():
    VGR1.VacuumGripperRobot1()



if __name__ == '__main__':
    process_list = [
        Process(target=init_vgr1),
    ]
    [process.start() for process in process_list]
    [process.join() for process in process_list]