from flask import Flask, request, jsonify, abort
import json
from threading import Thread
import time
from datetime import datetime
import xmlrpc.client
import heapq
from flasgger import Swagger
import SM1
from multiprocessing import Process

app = Flask(__name__)
swagger = Swagger(app)

list_of_valid_requests = []

sm1_execution_rpc = None
heap_queue_sm1_execution = []
sm1_getter_setter_rpc = None
heap_queue_sm1_getter_setter = []

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
    if request.url == "http://127.0.0.1:5005/favicon.ico":
        print(request.url + " was called")
        return
    if request.url == "http://127.0.0.1:5005/apidocs/":
        return
    if request.url == "http://localhost:5005/apidocs/":
        return
    if request.url == "http://sm:5005/apidocs/":
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
            if machine == "sm":
                heapq.heappush(heap_queue_sm1_getter_setter, (priority, dt, request, path))
    else:
        if factory == "1":
            if machine == "sm":
                heapq.heappush(heap_queue_sm1_execution, (priority, dt, request, path))


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

def check_heap_queue_sm1_execution(req):
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :param req: Request
    :return: Nothing
    """
    tmp = True
    while tmp:
        if req.datetime == heap_queue_sm1_execution[0][1] and req.path == heap_queue_sm1_execution[0][3]:
            tmp = False


def pop_heap_queue_sm1_execution():
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :return: Nothing
    """
    heapq.heappop(heap_queue_sm1_execution)

def check_heap_queue_sm1_getter_setter(req):
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :param req: Request
    :return: Nothing
    """
    tmp = True
    while tmp:
        if req.datetime == heap_queue_sm1_getter_setter[0][1] and req.path == heap_queue_sm1_getter_setter[0][3]:
            tmp = False


def pop_heap_queue_sm1_getter_setter():
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :return: Nothing
    """
    heapq.heappop(heap_queue_sm1_getter_setter)


"""
#####################################################################
#####################################################################
################## Sorting Machine ##################################
################## Execution Webservices ############################
#####################################################################
#####################################################################
"""

@app.route("/sm/sort")
def sm_sort() -> [None, json]:
    """
        Starts the entire sorting machine process once.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: sm_1
            - name: start
              in: path
              type: string
              required: true
              description: initial
            - name: predefined_ejection_location
              in: path
              type: string
              required: true
              description: none
        description:
                    Starts the entire sorting machine process once. **/sm/sort?machine=sm_1&start=initial&predefined_ejection_location=none**
                    [Example URL](http://127.0.0.1:5005/sm/sort?machine=sm_1&start=initial&predefined_ejection_location=none)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1":
        check_heap_queue_sm1_execution(request)

        try:
            position = sm1_execution_rpc.sort(
                str(request.args.get('start')),
                bool(request.args.get('use_nfc')),
                str(request.args.get('predefined_ejection_location'))
            )
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_sm1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_sm1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")
    args = {"sink": position}

    if request and request.method == "GET":
        return jsonify(create_json(request,args))
    else:
        abort(404)


"""
#####################################################################
#####################################################################
################## Sorting Machine ##################################
############ Getter and Setter Webservices ##########################
#####################################################################
#####################################################################
"""


@app.route('/sm/state_of_machine')
def sm_state_of_machine() -> [None, json]:
    """
        Indicates the state of a machine
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: sm_1
        description: 
                    Indicates the state of a machine **sm/state_of_machine?machine=sm_1**
                    [Example URL](http://127.0.0.1:5005/sm/state_of_machine?machine=sm_1)
        responses:
            200:
                description: JSON
    """
    state = None
    if request.factory == "1":
        check_heap_queue_sm1_getter_setter(request)
        try:
            state = sm1_getter_setter_rpc.state_of_machine(1)
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_sm1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_sm1_getter_setter()

    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"state": state}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/sm/status_of_light_barrier')
def sm_status_of_light_barrier() -> [None, json]:
    """
        Indicates whether a light barrier is broken through or not.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: sm_1
            - name: lb
              in: path
              type: integer
              required: true
              description: Number of light barrier in SM
        description:
                    URL **sm/status_of_light_barrier?machine=sm_1&lb=1**
                    [Example Link](http://192.168.0.5:5000/sm/status_of_light_barrier?machine=sm_1&lb=1)
        responses:
            200:
                description: JSON
    """
    status = None
    if request.factory == "1" and request.args.get('lb'):
        check_heap_queue_sm1_getter_setter(request)
        try:
            status = sm1_getter_setter_rpc.status_of_light_barrier(int(request.args.get('lb')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_sm1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_sm1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"interrupted": status}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/sm/get_motor_speed')
def sm_get_motor_speed() -> [None, json]:
    """
        Gets the motor speed for the specified motor
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: sm_1
            - name: motor
              in: path
              type: integer
              required: true
              description: Number of motor
        description: 
                    URL **sm/get_motor_speed?machine=sm_1&motor=1**
                    [Example Link](http://127.0.0.1:5005/sm/get_motor_speed?machine=sm_1&motor=1)
        responses:
            200:
                description: JSON
    """
    motor_speed = None
    if request.factory == "1" and request.args.get('motor'):
        check_heap_queue_sm1_getter_setter(request)
        try:
            motor_speed = sm1_getter_setter_rpc.get_motor_speed(int(request.args.get('motor')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_sm1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_sm1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"motor_speed": motor_speed}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/sm/set_motor_speed')
def sm_set_motor_speed() -> [None, json]:
    """
        Sets the motor speed for the specified motor
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: sm_1
            - name: motor
              in: path
              type: integer
              required: true
              description: Number of motor
            - name: speed
              in: path
              type: integer
              required: true
              description: Motor speed
        description: 
                    URL **sm/set_motor_speed?machine=sm_1&motor=1&speed=400**
                    [Example Link](http://127.0.0.1:5005/sm/set_motor_speed?machine=sm_1&motor=1&speed=400)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1" and request.args.get('motor') and request.args.get('speed'):
        check_heap_queue_sm1_getter_setter(request)
        try:
            sm1_getter_setter_rpc.set_motor_speed(int(request.args.get('motor')), int(request.args.get('speed')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_sm1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_sm1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/sm/reset_all_motor_speeds')
def sm_reset_all_motor_speeds() -> [None, json]:
    """
        Resets all the motor speeds for the specified machine
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: sm_1
        description: 
                    Indicates the state of a machine **sm/reset_all_motor_speeds?machine=sm_1**
                    [Example Link](http://127.0.0.1:5005/sm/reset_all_motor_speeds?machine=sm_1)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1":
        check_heap_queue_sm1_getter_setter(request)
        try:
            sm1_getter_setter_rpc.reset_all_motor_speeds()
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_sm1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_sm1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


"""
####################################################################
################## favicon handling ################################
########## Browsers like Chrome ask for URL  #######################
######## /favicon.ico when they reload a page ######################
######## this webservice prevents it from raising an 404 error #####
####################################################################
"""


@app.route('/favicon.ico')
def handle_favicon():
    # Whenever a browser enters an URL this function gets called once the webservice finishes
    abort(404)


"""
####################################################################
#################### Start the App #################################
####################################################################
"""


def connect_to_sm1_execution_rpc():
    global sm1_execution_rpc
    try:
        sm1_execution_rpc = xmlrpc.client.ServerProxy("http://sm:8014/")
        print(sm1_execution_rpc.is_connected())
    except ConnectionRefusedError:  # as err:
        print("cannot connect to sm1 rpc server - sleeping for 2 seconds before trying to connect again.")
        time.sleep(2)
        connect_to_sm1_execution_rpc()
def connect_to_sm1_getter_setter_rpc():
    global sm1_getter_setter_rpc
    try:
        sm1_getter_setter_rpc = xmlrpc.client.ServerProxy("http://sm:7014/")
        print(sm1_getter_setter_rpc.is_connected())
    except ConnectionRefusedError:  # as err:
        print("cannot connect to sm1 rpc server - sleeping for 2 seconds before trying to connect again.")
        time.sleep(2)
        connect_to_sm1_getter_setter_rpc()

def init_sm1():
    SM1.SortingMachine1()

if __name__ == '__main__':
    process_list = [
        Process(target=init_sm1),
    ]
    [process.start() for process in process_list]
    [process.join() for process in process_list]

    thread_list = [
        Thread(target=connect_to_sm1_execution_rpc),
        Thread(target=connect_to_sm1_getter_setter_rpc),
    ]

    [thread.start() for thread in thread_list]
    [thread.join() for thread in thread_list]

    app.run(host='0.0.0.0', port=5005)
