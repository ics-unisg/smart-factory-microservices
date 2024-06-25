from flask import Flask, request, jsonify, abort
import json
from threading import Thread
import time
from datetime import datetime
import xmlrpc.client
import heapq
from flasgger import Swagger
import OV1
from multiprocessing import Process

app = Flask(__name__)
swagger = Swagger(app)


list_of_valid_requests = []

ov1_execution_rpc = None
wt1_execution_rpc = None

heap_queue_ov1_execution = []
heap_queue_wt1_execution = []

ov1_getter_setter_rpc = None
wt1_getter_setter_rpc = None

heap_queue_ov1_getter_setter = []
heap_queue_wt1_getter_setter = []

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
    if request.url == "http://127.0.0.1:5004/favicon.ico":
        print(request.url + " was called")
        return
    if request.url == "http://127.0.0.1:5004/apidocs/":
        return
    if request.url == "http://localhost:5004/apidocs/":
        return
    if request.url == "http://ov:5004/apidocs/":
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
            if machine == "ov":
                heapq.heappush(heap_queue_ov1_getter_setter, (priority, dt, request, path))
            elif machine == "wt":
                heapq.heappush(heap_queue_wt1_getter_setter, (priority, dt, request, path))
    else:
        if factory == "1":
            if machine == "ov":
                heapq.heappush(heap_queue_ov1_execution, (priority, dt, request, path))
            elif machine == "wt":
                heapq.heappush(heap_queue_wt1_execution, (priority, dt, request, path))


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


def check_heap_queue_ov1_execution(req):
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :param req: Request
    :return: Nothing
    """
    tmp = True
    while tmp:
        if req.datetime == heap_queue_ov1_execution[0][1] and req.path == heap_queue_ov1_execution[0][3]:
            tmp = False


def pop_heap_queue_ov1_execution():
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :return: Nothing
    """
    heapq.heappop(heap_queue_ov1_execution)


def check_heap_queue_wt1_execution(req):
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :param req: Request
    :return: Nothing
    """
    tmp = True
    while tmp:
        if req.datetime == heap_queue_wt1_execution[0][1] and req.path == heap_queue_wt1_execution[0][3]:
            tmp = False


def pop_heap_queue_wt1_execution():
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :return: Nothing
    """
    heapq.heappop(heap_queue_wt1_execution)

def check_heap_queue_ov1_getter_setter(req):
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :param req: Request
    :return: Nothing
    """
    tmp = True
    while tmp:
        if req.datetime == heap_queue_ov1_getter_setter[0][1] and req.path == heap_queue_ov1_getter_setter[0][3]:
            tmp = False


def pop_heap_queue_ov1_getter_setter():
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :return: Nothing
    """
    heapq.heappop(heap_queue_ov1_getter_setter)


def check_heap_queue_wt1_getter_setter(req):
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :param req: Request
    :return: Nothing
    """
    tmp = True
    while tmp:
        if req.datetime == heap_queue_wt1_getter_setter[0][1] and req.path == heap_queue_wt1_getter_setter[0][3]:
            tmp = False


def pop_heap_queue_wt1_getter_setter():
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :return: Nothing
    """
    heapq.heappop(heap_queue_wt1_getter_setter)


"""
#####################################################################
#####################################################################
############### MULTI PROCESSING STATION - Oven #####################
################## Execution Webservices ############################
#####################################################################
#####################################################################
"""


@app.route("/ov/calibrate")
def ov_calibrate() -> [None, json]:
    """
        Calibrates the Oven
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: ov_1
        description: >
                    URL **mm/check_position?machine=ov_1**
                    [Example Link](http://127.0.0.1:5004/mm/check_position?machine=ov_1)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1":
        check_heap_queue_ov1_execution(request)

        try:
            ov1_execution_rpc.calibrate()
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_ov1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_ov1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route("/ov/burn")
def ov_burn() -> [None, json]:
    """
        This process moves a workpiece into the oven, burns it and then moves it out of the furnace again.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: ov_1
            - name: time
              in: path
              type: integer
              required: false
              description: If no time
        description: >
                    The GET parameter (time) can be transferred and specifies the firing time. If no parameter is passed,
                    the default value is used. **ov/burn?machine=ov_1&time=40**
                    [Example Link](http://127.0.0.1:5004/ov/burn?machine=ov_1)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1":
        time_to_burn = request.args.get('time')
        check_heap_queue_ov1_execution(request)
        try:
            ov1_execution_rpc.burn(int(time_to_burn) if time_to_burn is not None else 2)
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_ov1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_ov1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


"""
#####################################################################
#####################################################################
############### MULTI PROCESSING STATION - Oven #####################
############ Getter and Setter Webservices ##########################
#####################################################################
#####################################################################
"""


@app.route('/ov/state_of_machine')
def ov_state_of_machine() -> [None, json]:
    """
        Indicates the state of a machine
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: ov_1
        description: >
                    URL **ov/state_of_machine?machine=ov_1**
                    [Example Link](http://127.0.0.1:5004/ov/state_of_machine?machine=ov_1)
        responses:
            200:
                description: JSON
    """
    state = None
    if request.factory == "1":
        check_heap_queue_ov1_getter_setter(request)
        try:
            state = ov1_getter_setter_rpc.state_of_machine(1)
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_ov1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_ov1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"state": state}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/ov/status_of_light_barrier')
def ov_status_of_light_barrier() -> [None, json]:
    """
        Indicates whether a light barrier is broken through or not.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: ov_1
            - name: lb
              in: path
              type: integer
              required: true
              description: number of light barrier
        description: >
                    URL **ov/status_of_light_barrier?machine=ov_1&lb=5**
                    [Example Link](http://127.0.0.1:5004/ov/status_of_light_barrier?machine=ov_1&lb=5)
        responses:
            200:
                description: JSON
    """
    status = None
    if request.factory == "1" and request.args.get('lb'):
        check_heap_queue_ov1_getter_setter(request)
        try:
            status = ov1_getter_setter_rpc.status_of_light_barrier(int(request.args.get('lb')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_ov1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_ov1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"interrupted": status}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/ov/get_motor_speed')
def ov_get_motor_speed() -> [None, json]:
    """
        Gets the motor speed for the specified motor
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: ov_1
            - name: motor
              in: path
              type: integer
              required: true
              description: number of motor
        description: >
                    URL **ov/get_motor_speed?machine=ov_1&motor=1**
                    [Example Link](http://127.0.0.1:5004/ov/get_motor_speed?machine=ov_1&motor=1)
        responses:
            200:
                description: JSON
    """
    motor_speed = None
    if request.factory == "1" and request.args.get('motor'):
        check_heap_queue_ov1_getter_setter(request)
        try:
            motor_speed = ov1_getter_setter_rpc.get_motor_speed(int(request.args.get('motor')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_ov1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_ov1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"motor_speed": motor_speed}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/ov/set_motor_speed')
def ov_set_motor_speed() -> [None, json]:
    """
        Sets the motor speed for the specified motor
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: ov_1
            - name: motor
              in: path
              type: integer
              required: true
              description: number of motor
            - name: speed
              in: path
              type: integer
              required: true
        description: >
                    URL **ov/get_motor_speed?machine=ov_1&motor=1**
                    [Example Link](http://127.0.0.1:5004/ov/set_motor_speed?machine=ov_1&motor=1&speed=400)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1" and request.args.get('motor') and request.args.get('speed'):
        check_heap_queue_ov1_getter_setter(request)
        try:
            ov1_getter_setter_rpc.set_motor_speed(int(request.args.get('motor')), int(request.args.get('speed')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_ov1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_ov1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/ov/reset_all_motor_speeds')
def ov_reset_all_motor_speeds() -> [None, json]:
    """
        Resets all the motor speeds for the specified machine
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: ov_1
        description: >
                    URL **ov/reset_all_motor_speeds?machine=ov_1**
                    [Example Link](http://127.0.0.1:5004/ov/reset_all_motor_speeds?machine=ov_1)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1":
        check_heap_queue_ov1_getter_setter(request)
        try:
            ov1_getter_setter_rpc.reset_all_motor_speeds()
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_ov1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_ov1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


"""
#####################################################################
#####################################################################
###### MULTI PROCESSING STATION - Workstation Transport #############
################## Execution Webservices ############################
#####################################################################
#####################################################################
"""


@app.route("/wt/calibrate/")
def wt_calibrate() -> [None, json]:
    """
        Calibrates the Workstation Transport.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: wt_1
        description: >
                    URL **wt/calibrate?machine=wt_1**
                    [Example Link](http://127.0.0.1:5004/wt/calibrate?machine=wt_1)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1":
        check_heap_queue_wt1_execution(request)

        try:
            wt1_execution_rpc.wt_calibrate()
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_wt1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_wt1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route("/wt/move_to")
def wt_move_to() -> [None, json]:
    """
        Moves the crane of the multi-processing station either to the furnace or to the milling machine.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: wt_1
            - name: position
              in: path
              schema:
                type: string
                enum: [oven,milling_machine]
              required: true
        description: >
                    URL **wt/move_to?machine=wt_1&position=oven**
                    [Example Link](http://127.0.0.1:5004/wt/move_to?machine=wt_1&position=oven)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1" and request.args.get('position'):
        check_heap_queue_wt1_execution(request)
        try:
            wt1_execution_rpc.wt_move_to(request.args.get('position'))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_wt1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_wt1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route("/wt/pick_up_and_transport")
def wt_pick_up_and_transport() -> [None, json]:
    """
        The crane picks up the workpiece at the current position and moves it to another position and places it there.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: wt_1
            - name: start
              in: path
              schema:
                type: string
                enum: [oven,milling_machine]
              required: true
            - name: end
              in: path
              schema:
                type: string
                enum: [oven,milling_machine]
              required: true
        description: >
                    URL **wt/pick_up_and_transport?machine=wt_1&start=milling_machine&end=oven**
                    [Example Link](http://127.0.0.1:5004/wt/pick_up_and_transport?machine=wt_1&start=milling_machine&end=oven)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1" and request.args.get('start') and request.args.get('end'):
        check_heap_queue_wt1_execution(request)

        try:
            wt1_execution_rpc.wt_pick_up_and_transport(request.args.get('start'), request.args.get('end'))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_wt1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_wt1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


"""
#####################################################################
#####################################################################
###### MULTI PROCESSING STATION - Workstation Transport #############
############ Getter and Setter Webservices ##########################
#####################################################################
#####################################################################
"""


@app.route('/wt/state_of_machine')
def wt_state_of_machine() -> [None, json]:
    """
        Indicates the state of a machine
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: wt_1
        description: >
                    URL **wt/state_of_machine?machine=wt_1**
                    [Example Link](http://127.0.0.1:5004/wt/state_of_machine?machine=wt_1)
        responses:
            200:
                description: JSON
    """
    state = None
    if request.factory == "1":
        check_heap_queue_wt1_getter_setter(request)
        try:
            state = wt1_getter_setter_rpc.wt_state_of_machine(2)
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_wt1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_wt1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"state": state}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/wt/get_motor_speed')
def wt_get_motor_speed() -> [None, json]:
    """
        Gets the motor speed for the specified motor
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: wt_1
            - name: motor
              in: path
              type: integer
              required: true
              description: Number of motor
        description: >
                    URL **wt/get_motor_speed?machine=wt_1&motor=2**
                    [Example Link](http://127.0.0.1:5004/wt/get_motor_speed?machine=wt_1&motor=2)
        responses:
            200:
                description: JSON
    """
    motor_speed = None
    if request.factory == "1" and request.args.get('motor'):
        check_heap_queue_wt1_getter_setter(request)
        try:
            motor_speed = wt1_getter_setter_rpc.wt_get_motor_speed(int(request.args.get('motor')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_wt1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_wt1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"motor_speed": motor_speed}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/wt/set_motor_speed')
def wt_set_motor_speed() -> [None, json]:
    """
        Sets the motor speed for the specified motor
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: wt_1
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
                    URL **wt/set_motor_speed?machine=wt_1&motor=1&speed=400**
                    [Example Link](http://127.0.0.1:5004/wt/set_motor_speed?machine=wt_1&motor=1&speed=400)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1" and request.args.get('motor') and request.args.get('speed'):
        check_heap_queue_wt1_getter_setter(request)
        try:
            wt1_getter_setter_rpc.wt_set_motor_speed(int(request.args.get('motor')), int(request.args.get('speed')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_wt1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_wt1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/wt/reset_all_motor_speeds')
def wt_reset_all_motor_speeds() -> [None, json]:
    """
        Resets all the motor speeds for the specified machine
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: wt_1
        description: >
                    URL **wt/reset_all_motor_speeds?machine=wt_1**
                    [Example Link](http://127.0.0.1:5004/wt/reset_all_motor_speeds?machine=wt_1)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1":
        check_heap_queue_wt1_getter_setter(request)
        try:
            wt1_getter_setter_rpc.wt_reset_all_motor_speeds()
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_wt1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_wt1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/wt/check_position')
def wt_check_position() -> [None, json]:
    """
        Checks if the position of the machine matches the queried position
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: wt_1
            - name: position
              in: path
              type: string
              required: true
        description: >
                    URL **wt/check_position?machine=mm_1&position=initial**
                    [Example Link](http://127.0.0.1:5004/wt/check_position?machine=wt_1&position=initial)
        responses:
            200:
                description: JSON
    """
    check = None
    if request.factory == "1" and request.args.get('position'):
        check_heap_queue_wt1_getter_setter(request)
        try:
            check = wt1_getter_setter_rpc.wt_check_position(request.args.get('position'))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_wt1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_wt1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"is_at_queried_position": check}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)

@app.route('/favicon.ico')
def handle_favicon():
    # Whenever a browser enters an URL this function gets called once the webservice finishes
    abort(404)


"""
####################################################################
#################### Start the App #################################
####################################################################
"""

def connect_to_ov1_execution_rpc():
    global ov1_execution_rpc
    try:
        ov1_execution_rpc = xmlrpc.client.ServerProxy("http://ov:8015/")
        print(f"{ov1_execution_rpc.is_connected()} - Oven")
    except ConnectionRefusedError:  # as err:
        print("cannot connect to ov1 rpc server - sleeping for 2 seconds before trying to connect again.")
        time.sleep(2)
        connect_to_ov1_execution_rpc()


def connect_to_wt1_execution_rpc():
    global wt1_execution_rpc
    try:
        wt1_execution_rpc = xmlrpc.client.ServerProxy("http://ov:8415/")
        print(f"{wt1_execution_rpc.wt_is_connected()} - WT")
    except ConnectionRefusedError:  # as err:
        print("cannot connect to wt1 rpc server - sleeping for 2 seconds before trying to connect again.")
        time.sleep(2)
        connect_to_wt1_execution_rpc()

def connect_to_ov1_getter_setter_rpc():
    global ov1_getter_setter_rpc
    try:
        ov1_getter_setter_rpc = xmlrpc.client.ServerProxy("http://ov:7015/")
        print(f"{ov1_getter_setter_rpc.is_connected()} - Oven")
    except ConnectionRefusedError:  # as err:
        print("cannot connect to ov1 rpc server - sleeping for 2 seconds before trying to connect again.")
        time.sleep(2)
        connect_to_ov1_getter_setter_rpc()


def connect_to_wt1_getter_setter_rpc():
    global wt1_getter_setter_rpc
    try:
        wt1_getter_setter_rpc = xmlrpc.client.ServerProxy("http://ov:7615/")
        print(f"{wt1_getter_setter_rpc.wt_is_connected()} - WT")
    except ConnectionRefusedError:  # as err:
        print("cannot connect to wt1 rpc server - sleeping for 2 seconds before trying to connect again.")
        time.sleep(2)
        connect_to_wt1_getter_setter_rpc()



def init_ov1():
    OV1.OvenAndWTAndWT1()

if __name__ == '__main__':
    process_list = [
        Process(target=init_ov1),
    ]
    [process.start() for process in process_list]
    [process.join() for process in process_list]

    thread_list = [
        Thread(target=connect_to_ov1_execution_rpc),
        Thread(target=connect_to_wt1_execution_rpc),
        Thread(target=connect_to_ov1_getter_setter_rpc),
        Thread(target=connect_to_wt1_getter_setter_rpc),
    ]

    [thread.start() for thread in thread_list]
    [thread.join() for thread in thread_list]

    app.run(host='0.0.0.0', port=5004)
