import MM1
from multiprocessing import Process


def init_mm1():
    MM1.MillingMachine1()

if __name__ == '__main__':
    process_list = [
        Process(target=init_mm1),
    ]
    [process.start() for process in process_list]
    [process.join() for process in process_list]