from multiprocessing import Process

import EC1


def init_ec1():
    EC1.EnvironmentAndCamera1()


if __name__ == '__main__':
    process_list = [
        Process(target=init_ec1),
    ]
    [process.start() for process in process_list]
    [process.join() for process in process_list]