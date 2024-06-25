from multiprocessing import Process

import OV1


def init_ov1():
    OV1.OvenAndWTAndWT1()


if __name__ == '__main__':
    process_list = [
        Process(target=init_ov1),
    ]
    [process.start() for process in process_list]
    [process.join() for process in process_list]