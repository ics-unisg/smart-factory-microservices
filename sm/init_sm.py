from multiprocessing import Process

import SM1


def init_sm1():
    SM1.SortingMachine1()

if __name__ == '__main__':
    process_list = [
        Process(target=init_sm1),
    ]
    [process.start() for process in process_list]
    [process.join() for process in process_list]