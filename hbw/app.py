from flask import Flask, request, jsonify, abort
import json
from threading import Thread
import time
from datetime import datetime
import xmlrpc.client
import heapq
import requests
from flasgger import Swagger
from multiprocessing import Process

import HBW1

app = Flask(__name__)
swagger = Swagger(app)

list_of_valid_requests = []

hbw1_execution_rpc = None
heap_queue_hbw1_execution = []
hbw1_getter_setter_rpc = None
heap_queue_hbw1_getter_setter = []


"""
#####################################################################
#####################################################################
################## Initializing Web Server and Queue ################
#####################################################################
#####################################################################
"""


@app.errorhandler(400)
def bad_request(e):
    return jsonify(error=str(e)), 400


@app.errorhandler(404)
def bad_request(e):
    return jsonify(error=str(e)), 404


@app.errorhandler(417)
def precondition_not_fulfilled(e):
    return jsonify(error=str(e)), 417


@app.before_request
def before_request():
    if request.url == "http://127.0.0.1:5002/favicon.ico":
        print(request.url + " was called")
        return
    if request.url == "http://127.0.0.1:5002/apidocs/":
        return
    if request.url == "http://localhost:5002/apidocs/":
        return
    if request.url == "http://hbw:5002/apidocs/":
        return
    if "/flasgger_static/" in request.url:
        return
    if "apispec" in request.url:
        return

    path = request.path
    path_split = path.split("/")
    machine = path_split[1]
    task = path_split[2]
    dt = datetime.now()
    request.datetime = dt

    list_of_valid_requests.append(str(request))

    if request.args.get('machine'):
        machine_and_factory = request.args.get('machine')
        tmp_arr = machine_and_factory.split("_")
        factory = tmp_arr[1]
        request.factory = factory
    else:
        abort(404, 'No Machine is passed')

    # lower values in the priority queue are preferred over larger ones
    if request.args.get("prio"):
        priority = request.args.get("prio")
    else:
        priority = 3
    if task == "status_of_light_barrier" or \
            task == "get_amount_of_stored_workpieces" or \
            task == "state_of_machine" or \
            task == "set_motor_speed" or \
            task == "reset_all_motor_speeds" or \
            task == "get_motor_speed" or \
            task == "check_position" or \
            task == "get_slot_number_of_workpiece_by_color" or \
            task == "detect_color" or \
            task == "has_capacitive_sensor_registered_workpiece":
        if factory == "1":
            if machine == "hbw":
                heapq.heappush(heap_queue_hbw1_getter_setter, (priority, dt, request, path))

    else:
        if factory == "1":
            if machine == "hbw":
                heapq.heappush(heap_queue_hbw1_execution, (priority, dt, request, path))



def create_json(req, *args):
    end_dt = datetime.now()
    process_dt = end_dt - req.datetime

    str_start_dt = req.datetime.strftime("%d-%b-%Y (%H:%M:%S.%f)")
    str_end_dt = end_dt.strftime("%d-%b-%Y (%H:%M:%S.%f)")

    json_output = {
        "link": req.base_url,
        "start_time": str_start_dt,
        "end_time": str_end_dt,
        "process_time": str(process_dt),
        "attributes": args
    }

    return json_output


def check_heap_queue_hbw1_execution(req):
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :param req: Request
    :return: Nothing
    """
    tmp = True
    while tmp:
        if req.datetime == heap_queue_hbw1_execution[0][1] and req.path == heap_queue_hbw1_execution[0][3]:
            tmp = False


def pop_heap_queue_hbw1_execution():
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :return: Nothing
    """
    heapq.heappop(heap_queue_hbw1_execution)


def check_heap_queue_hbw1_getter_setter(req):
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :param req: Request
    :return: Nothing
    """
    tmp = True
    while tmp:
        if req.datetime == heap_queue_hbw1_getter_setter[0][1] and req.path == heap_queue_hbw1_getter_setter[0][3]:
            tmp = False


def pop_heap_queue_hbw1_getter_setter():
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :return: Nothing
    """
    heapq.heappop(heap_queue_hbw1_getter_setter)

def _get_status_of_light_barrier_hbw() -> bool:
    """
    Checks whether the light barrier of hbw is interrupted.
    :return: Bool
    """
    url = f"http://hbw:5002/hbw/status_of_light_barrier?machine=hbw_1" \
          f"&lb=1"
    response = requests.get(url, auth=('user', 'pass'))
    data = response.json()
    status = data['attributes'][0]['interrupted']
    return status

def _hbw_unload_thread(slot) -> None:
    """
    Represents the unload Process Thread.
    :return: Nothing
    """
    requests.get(f"http://hbw:5002/hbw/unload?machine=hbw_1&slot={slot}", auth=('user', 'pass'))

"""
#####################################################################
#####################################################################
################## High-Bay Warehouse ###############################
################# Execution Webservices #############################
#####################################################################
#####################################################################
"""


@app.route('/hbw/calibrate')
def hbw_calibrate() -> [None, json]:
    """
        Moves HBW to start position
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: vgr_1
            - name: motor
              in: path
              type: integer
              required: true
              description: Number of motor
        description: >
                    URL **hbw/calibrate?motor=2&machine=hbw_1**
                    [Example Link](http://127.0.0.1:5002/hbw/calibrate?motor=2&machine=hbw_1)
        responses:
            200:
                description: JSON
    """
    if request.args.get('motor'):
        motor = request.args.get('motor')
    else:
        motor = None

    if request.factory == "1":
        check_heap_queue_hbw1_execution(request)

        try:
            if motor is None:
                hbw1_execution_rpc.calibrate()
            else:
                hbw1_execution_rpc.calibrate(int(motor))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_hbw1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_hbw1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/hbw/store')
def hbw_store() -> [None, json]:
    """
        Stores a workpiece at a given slot (0-8) in HBW
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: hbw_1
            - name: slot
              in: path
              type: integer
              required: true
              description: Number of slot
        description: >
                    URL **hbw/store?slot=2&machine=hbw_1**
                    [Example Link](http://127.0.0.1:5002/hbw/store?slot=2&machine=hbw_1)
        responses:
            200:
                description: JSON
    """
    slot = None
    if request.args.get('slot'):
        slot = str(request.args.get('slot')).split("_")[1]
    color = request.args.get('color')
    if color:
        if request.factory == "1":
            check_heap_queue_hbw1_execution(request)

            try:
                hbw1_execution_rpc.store(int(slot) if slot is not None else "next", color)
            except xmlrpc.client.Fault as rpc_error:
                pop_heap_queue_hbw1_execution()
                abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
            pop_heap_queue_hbw1_execution()
        else:
            abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/hbw/unload')
def hbw_unload() -> [None, json]:
    """
        Unloads a workpiece at a given slot (0-8) in HBW
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: hbw_1
            - name: slot
              in: path
              type: integer
              required: true
              description: Number of slot
        description: >
                    URL **hbw/unload?machine=hbw_1&slot=1**
                    [Example Link](http://127.0.0.1:5002/hbw/unload?machine=hbw_1&slot=1)
        responses:
            200:
                description: JSON
    """
    slot = None
    if request.args.get('slot'):
        slot = request.args.get('slot')
    request.factory = "1"
    if request.factory == "1":
        check_heap_queue_hbw1_execution(request)

        try:
            hbw1_execution_rpc.unload(int(slot) if slot is not None else "next")
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_hbw1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_hbw1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route("/hbw/change_buckets")
def hbw_change_buckets() -> [None, json]:
    """
       Swaps two buckets. The parameters slot_one and slot_two take values between (1 - 9).
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: hbw_1
            - name: slot_one
              in: path
              type: integer
              required: true
              description: Number of slot1
            - name: slot_two
              in: path
              type: integer
              required: true
              description: Number of slot2
        description: >
                    URL **hbw/change_buckets?machine=hbw_1&slot_one=1&slot_two=2**
                    [Example Link](http://127.0.0.1:5002/hbw/change_buckets?machine=hbw_1&slot_one=1&slot_two=2)
        responses:
            200:
                description: JSON
    """
    slot_1 = None
    slot_2 = None

    if request.args.get('slot_one'):
        slot_1 = str(request.args.get('slot_one')).split("_")[0]
    if request.args.get('slot_two'):
        slot_2 = str(request.args.get('slot_two')).split("_")[0]
    if request.factory == "1" and request.args.get("slot_one") and request.args.get("slot_two"):
        check_heap_queue_hbw1_execution(request)

        try:
            hbw1_execution_rpc.change_buckets(int(slot_1) - 1,
                                              int(slot_2) - 1)
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_hbw1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_hbw1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)

@app.route("/hbw/get_workpiece_by_color")
def hbw_get_workpiece_by_color() -> [None, json]:
    """
       Unloads workpiece from HBW by workpiece color
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: hbw_1
            - name: color
              in: path
              type: string
              required: true
              description: Color of workpiece
        description: >
                    URL **hbw/get_workpiece_by_color?color=red&machine=hbw_1**
                    [Example Link](http://127.0.0.1:5002/hbw/get_workpiece_by_color?color=red&machine=hbw_1)
        responses:
            200:
                description: JSON
    """
    color = request.args.get('color')
    if color:
        requests.get(f"http://hbw:5002/hbw/calibrate?machine=hbw_1", auth=('user', 'pass'))
        requests.get(f"http://vgr:5006/vgr/calibrate?machine=vgr_1", auth=('user', 'pass'))
        response = requests.get(f"http://hbw:5002/hbw/get_slot_number_of_workpiece_by_color?color={color}&machine=hbw_1")
        data = response.json()
        slot = data['attributes'][0]['slot_number']
        if slot == -1:
            error = f"No Workpiece with color {color} available"
            return jsonify(error=str(error)), 500

        Thread(target=_hbw_unload_thread, args=(int(slot),)).start()

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)

@app.route("/hbw/wait_until_light_barrier_is_interrupted")
def hbw_wait_until_light_barrier_is_interrupted() -> [None, json]:
    while not _get_status_of_light_barrier_hbw():
        time.sleep(0.5)
        pass
    return jsonify(create_json(request))


"""
#####################################################################
#####################################################################
################## High-Bay Warehouse ###############################
############ Getter and Setter Webservices ##########################
#####################################################################
#####################################################################
"""


@app.route('/hbw/state_of_machine')
def hbw_state_of_machine() -> [None, json]:
    """
       Indicates the state of a machine
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: hbw_1
        description: >
                    URL **hbw/state_of_machine?machine=hbw_1**
                    [Example Link](http://127.0.0.1:5002/hbw/state_of_machine?machine=hbw_1)
        responses:
            200:
                description: JSON
    """
    state = None
    if request.factory == "1":
        check_heap_queue_hbw1_getter_setter(request)
        try:
            state = hbw1_getter_setter_rpc.state_of_machine(1)
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_hbw1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_hbw1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"state": state}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/hbw/status_of_light_barrier')
def hbw_status_of_light_barrier() -> [None, json]:
    """
       Indicates whether a light barrier is broken through or not.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: hbw_1
            - name: lb
              in: path
              type: integer
              required: true
              description: Number of light barrier
        description: >
                    URL **hbw/status_of_light_barrier?machine=hbw_1&lb=1**
                    [Example Link](http://127.0.0.1:5002/hbw/status_of_light_barrier?machine=hbw_1&lb=1)
        responses:
            200:
                description: JSON
    """
    status = None
    if request.factory == "1" and request.args.get('lb'):
        check_heap_queue_hbw1_getter_setter(request)
        try:
            status = hbw1_getter_setter_rpc.status_of_light_barrier(int(request.args.get('lb')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_hbw1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_hbw1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"interrupted": status}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/hbw/get_motor_speed')
def hbw_get_motor_speed() -> [None, json]:
    """
       Gets the motor speed for the specified motor
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: hbw_1
            - name: motor
              in: path
              type: integer
              required: true
              description: Number of motor
        description: >
                    URL **hbw/get_motor_speed?machine=hbw_1&motor=1**
                    [Example Link](http://127.0.0.1:5002/hbw/get_motor_speed?machine=hbw_1&motor=1)
        responses:
            200:
                description: JSON
    """
    motor_speed = None
    if request.factory == "1" and request.args.get('motor'):
        check_heap_queue_hbw1_getter_setter(request)
        try:
            motor_speed = hbw1_getter_setter_rpc.get_motor_speed(int(request.args.get('motor')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_hbw1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_hbw1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"motor_speed": motor_speed}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/hbw/set_motor_speed')
def hbw_set_motor_speed() -> [None, json]:
    """
       Sets the motor speed for the specified motor
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: hbw_1
            - name: motor
              in: path
              type: integer
              required: true
              description: Number of motor
            - name: speed
              in: path
              type: integer
              required: true
        description: >
                    URL **hbw/set_motor_speed?machine=hbw_1&motor=1&speed=400**
                    [Example Link](http://127.0.0.1:5002/hbw/set_motor_speed?machine=hbw_1&motor=1&speed=400)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1" and request.args.get('motor') and request.args.get('speed'):
        check_heap_queue_hbw1_getter_setter(request)
        try:
            hbw1_getter_setter_rpc.set_motor_speed(int(request.args.get('motor')), int(request.args.get('speed')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_hbw1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_hbw1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/hbw/reset_all_motor_speeds')
def hbw_reset_all_motor_speeds() -> [None, json]:
    """
       Resets all the motor speeds for the specified machine
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: hbw_1
        description: >
                    URL **hbw/reset_all_motor_speeds?machine=hbw_1**
                    [Example Link](http://127.0.0.1:5002/hbw/reset_all_motor_speeds?machine=hbw_1)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1":
        check_heap_queue_hbw1_getter_setter(request)
        try:
            hbw1_getter_setter_rpc.reset_all_motor_speeds()
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_hbw1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_hbw1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/hbw/get_amount_of_stored_workpieces')
def hbw_amount_of_stored_workpieces() -> [None, json]:
    """
       Returns the number of stored workpieces.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: hbw_1
        description: >
                    URL **hbw/get_amount_of_stored_workpieces?machine=hbw_1**
                    [Example Link](http://127.0.0.1:5002/hbw/get_amount_of_stored_workpieces?machine=hbw_1)
        responses:
            200:
                description: JSON
    """
    number = None
    if request.factory == "1":
        check_heap_queue_hbw1_getter_setter(request)
        try:
            number = hbw1_getter_setter_rpc.get_amount_of_stored_workpieces()
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_hbw1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_hbw1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"number": number}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)

@app.route('/hbw/get_slot_number_of_workpiece_by_color')
def hbw_get_slot_number_of_workpiece_by_color() -> [None, json]:
    """
       Returns the number of slot where a workpiece with given color is stored
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: hbw_1
            - name: color
              in: path
              type: string
              required: true
        description: >
                    URL **hbw/get_slot_of_workpiece_by_color?color=red**
                    [Example Link](http://127.0.0.1:5002/hbw/get_slot_of_workpiece_by_color?color=red)
        responses:
            200:
                description: JSON
    """
    slot_number = None
    if request.factory == "1" and request.args.get('color'):
        check_heap_queue_hbw1_getter_setter(request)
        color = request.args.get('color')
        try:
            slot_number = hbw1_getter_setter_rpc.get_slot_number_of_workpiece_by_color(color)
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_hbw1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_hbw1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"slot_number": slot_number}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


"""
####################################################################
#################### Start the App #################################
####################################################################
"""

def connect_to_hbw1_execution_rpc():
    global hbw1_execution_rpc
    try:
        hbw1_execution_rpc = xmlrpc.client.ServerProxy("http://hbw:8012/")
        print(hbw1_execution_rpc.is_connected())
    except ConnectionRefusedError:  # as err:
        print("cannot connect to hbw1 rpc server - sleeping for 2 seconds before trying to connect again.")
        time.sleep(2)
        connect_to_hbw1_execution_rpc()


def connect_to_hbw1_getter_setter_rpc():
    global hbw1_getter_setter_rpc
    try:
        hbw1_getter_setter_rpc = xmlrpc.client.ServerProxy("http://hbw:7012/")
        print(hbw1_getter_setter_rpc.is_connected())
    except ConnectionRefusedError:  # as err:
        print("cannot connect to hbw1 rpc server - sleeping for 2 seconds before trying to connect again.")
        time.sleep(2)
        connect_to_hbw1_getter_setter_rpc()

def init_hbw1():
    HBW1.HighBayWarehouse1()

if __name__ == '__main__':
    process_list = [
        Process(target=init_hbw1),
    ]
    [process.start() for process in process_list]
    [process.join() for process in process_list]

    thread_list = [
        Thread(target=connect_to_hbw1_execution_rpc),
        Thread(target=connect_to_hbw1_getter_setter_rpc),
    ]

    [thread.start() for thread in thread_list]
    [thread.join() for thread in thread_list]

    app.run(host='0.0.0.0', port=5002)
