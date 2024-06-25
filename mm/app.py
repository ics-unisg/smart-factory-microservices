from flask import Flask, request, jsonify, abort
import json
from threading import Thread
import time
from datetime import datetime
import xmlrpc.client
import heapq
from flasgger import Swagger
import MM1
from multiprocessing import Process

app = Flask(__name__)
swagger = Swagger(app)

list_of_valid_requests = []

mm1_execution_rpc = None
heap_queue_mm1_execution = []
mm1_getter_setter_rpc = None
heap_queue_mm1_getter_setter = []

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
    if request.url == "http://127.0.0.1:5003/favicon.ico":
        print(request.url + " was called")
        return
    if request.url == "http://127.0.0.1:5003/apidocs/":
        return
    if request.url == "http://localhost:5003/apidocs/":
        return
    if request.url == "http://mm:5003/apidocs/":
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
            if machine == "mm":
                heapq.heappush(heap_queue_mm1_getter_setter, (priority, dt, request, path))
    else:
        if factory == "1":
            if machine == "mm":
                heapq.heappush(heap_queue_mm1_execution, (priority, dt, request, path))


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



def check_heap_queue_mm1_execution(req):
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :param req: Request
    :return: Nothing
    """
    tmp = True
    while tmp:
        if req.datetime == heap_queue_mm1_execution[0][1] and req.path == heap_queue_mm1_execution[0][3]:
            tmp = False


def pop_heap_queue_mm1_execution():
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :return: Nothing
    """
    heapq.heappop(heap_queue_mm1_execution)

def check_heap_queue_mm1_getter_setter(req):
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :param req: Request
    :return: Nothing
    """
    tmp = True
    while tmp:
        if req.datetime == heap_queue_mm1_getter_setter[0][1] and req.path == heap_queue_mm1_getter_setter[0][3]:
            tmp = False


def pop_heap_queue_mm1_getter_setter():
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :return: Nothing
    """
    heapq.heappop(heap_queue_mm1_getter_setter)

"""
#####################################################################
#####################################################################
#### MULTI PROCESSING STATION - MILLING MACHINE #####################
################## Execution Webservices ############################
#####################################################################
#####################################################################
"""


@app.route('/mm/calibrate')
def mm_calibrate() -> [None, json]:
    """
        Calibrates the turntable. The turntable only moves to the starting position.
        However, since "calibrate" was always used, this is also done for usability reasons.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: mm_1
        description: 
                    URL **mm/calibrate?machine=mm_1**
                    [Example Link](http://127.0.0.1:5003/mm/calibrate?machine=mm_1)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1":
        check_heap_queue_mm1_execution(request)

        try:
            mm1_execution_rpc.calibrate()
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_mm1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_mm1_execution()
    else:
        abort(404)

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")


@app.route('/mm/mill')
def mm_mill() -> [None, json]:
    """
        Starts milling.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: mm_1
            - name: time
              in: path
              type: integer
              required: false
              description: time
            - name: start
              in: path
              type: string
              required: true
              description: Start Position
            - name: end
              in: path
              type: string
              required: true
              description: End Position
        description: >
                    If the workpiece moves to the milling machine, mills and then moves to the ejection position,
                    pushes the workpiece onto the conveyor belt, starts it for 10 seconds and then returns to the initial position.
                    **mm/mill?machine=mm_1&time=10&start=initial&end=ejection**
                    [Example Link](http://127.0.0.1:5003/mm/mill?machine=mm_1&time=10&start=initial&end=ejection)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1" and request.args.get('start') and request.args.get('end'):
        time_to_mill = request.args.get('time')
        check_heap_queue_mm1_execution(request)

        try:
            mm1_execution_rpc.mill(
                request.args.get('start'), request.args.get('end'),
                int(time_to_mill) if time_to_mill is not None else 2)
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_mm1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_mm1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/mm/move_from_to')
def mm_move_from_to() -> [None, json]:
    """
        Moves the turntable to the specified position.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: mm_1
            - name: start
              in: path
              type: string
              required: true
              description: Start Position
            - name: end
              in: path
              type: string
              required: true
              description: End Position
        description: >
                    If the workpiece moves to the milling machine, mills and then moves to the ejection position,
                    pushes the workpiece onto the conveyor belt, starts it for 10 seconds and then returns to the initial position.
                    **mm/move_from_to?machine=mm_1&start=initial&end=ejection**
                    [Example Link](http://127.0.0.1:5003/mm/move_from_to?machine=mm_1&start=initial&end=ejection)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1" and request.args.get('start') and request.args.get('end'):
        check_heap_queue_mm1_execution(request)

        try:
            mm1_execution_rpc.move_from_to(request.args.get('start'), request.args.get('end'))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_mm1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_mm1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/mm/transport_from_to')
def mm_transport_from_to() -> [None, json]:
    """
        Transports the workpiece on the turntable to the specified position.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: mm_1
            - name: start
              in: path
              type: string
              required: true
              description: Start Position
            - name: end
              in: path
              type: string
              required: true
              description: End Position
        description: >
                    Transports the workpiece on the turntable to the specified position.
                    **mm/transport_from_to?machine=mm_1&start=initial&end=ejection**
                    [Example Link](http://127.0.0.1:5003/mm/transport_from_to?machine=mm_1&start=initial&end=ejection)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1" and request.args.get('start') and request.args.get('end'):
        check_heap_queue_mm1_execution(request)

        try:
            mm1_execution_rpc.transport_from_to(request.args.get('start'), request.args.get('end'))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_mm1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_mm1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


"""
#####################################################################
#####################################################################
#### MULTI PROCESSING STATION - MILLING MACHINE #####################
############ Getter and Setter Webservices ##########################
#####################################################################
#####################################################################
"""

@app.route('/mm/state_of_machine')
def mm_state_of_machine() -> [None, json]:
    """
        Indicates the state of a machine.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: mm_1
        description: >
                    URL **mm/transport_from_to?machine=mm_1&start=initial&end=ejection**
                    [Example Link](http://127.0.0.1:5003/mm/state_of_machine?machine=mm_1)
        responses:
            200:
                description: JSON
    """
    state = None
    if request.factory == "1":
        check_heap_queue_mm1_getter_setter(request)
        try:
            state = mm1_getter_setter_rpc.state_of_machine(1)
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_mm1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_mm1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"state": state}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/mm/status_of_light_barrier')
def mm_status_of_light_barrier() -> [None, json]:
    """
        Indicates whether a light barrier is broken through or not.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: mm_1
            - name: lb
              in: path
              type: integer
              required: false
              description: number of light barrier
        description: >
                    URL **mm/status_of_light_barrier?machine=mm_1&lb=4**
                    [Example Link](http://127.0.0.1:5003/mm/status_of_light_barrier?machine=mm_1&lb=4)
        responses:
            200:
                description: JSON
    """
    status = None
    if request.factory == "1" and request.args.get('lb'):
        check_heap_queue_mm1_getter_setter(request)
        try:
            status = mm1_getter_setter_rpc.status_of_light_barrier(int(request.args.get('lb')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_mm1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_mm1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"interrupted": status}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/mm/get_motor_speed')
def mm_get_motor_speed() -> [None, json]:
    """
        Gets the motor speed for the specified motor
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: mm_1
            - name: motor
              in: path
              type: integer
              required: true
              description: number of motor
        description: >
                    URL **mm/status_of_light_barrier?machine=mm_1&lb=4**
                    [Example Link](http://127.0.0.1:5003/mm/get_motor_speed?machine=mm_1&motor=1)
        responses:
            200:
                description: JSON
    """
    motor_speed = None
    if request.factory == "1" and request.args.get('motor'):
        check_heap_queue_mm1_getter_setter(request)
        try:
            motor_speed = mm1_getter_setter_rpc.get_motor_speed(int(request.args.get('motor')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_mm1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_mm1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"motor_speed": motor_speed}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/mm/set_motor_speed')
def mm_set_motor_speed() -> [None, json]:
    """
        Sets the motor speed for the specified motor
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: mm_1
            - name: motor
              in: path
              type: integer
              required: false
              description: number of motor
            - name: speed
              in: path
              type: integer
              required: false
        description: >
                    URL **mm/set_motor_speed?machine=mm_1&motor=1&speed=400**
                    [Example Link](http://127.0.0.1:5003/mm/set_motor_speed?machine=mm_1&motor=1&speed=400)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1" and request.args.get('motor') and request.args.get('speed'):
        check_heap_queue_mm1_getter_setter(request)
        try:
            mm1_getter_setter_rpc.set_motor_speed(int(request.args.get('motor')), int(request.args.get('speed')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_mm1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_mm1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/mm/reset_all_motor_speeds')
def mm_reset_all_motor_speeds() -> [None, json]:
    """
        Resets all the motor speeds for the specified machine
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: mm_1
        description: >
                    URL **mm/reset_all_motor_speeds?machine=mm_1**
                    [Example Link](http://127.0.0.1:5003/mm/reset_all_motor_speeds?machine=mm_1)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1":
        check_heap_queue_mm1_getter_setter(request)
        try:
            mm1_getter_setter_rpc.reset_all_motor_speeds()
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_mm1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_mm1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/mm/check_position')
def mm_check_position() -> [None, json]:
    """
        Checks if the position of the machine matches the queried position
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: mm_1
            - name: position
              in: path
              type: string
              required: true
        description: >
                    URL **mm/check_position?machine=mm_1&position=initial**
                    [Example Link](http://127.0.0.1:5003/mm/check_position?machine=mm_1&position=initial)
        responses:
            200:
                description: JSON
    """
    check = None
    if request.factory == "1" and request.args.get('position'):
        check_heap_queue_mm1_getter_setter(request)
        try:
            check = mm1_getter_setter_rpc.check_position(request.args.get('position'))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_mm1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_mm1_getter_setter()
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

def connect_to_mm1_execution_rpc():
    global mm1_execution_rpc
    try:
        mm1_execution_rpc = xmlrpc.client.ServerProxy("http://mm:8011/")
        print(mm1_execution_rpc.is_connected())
    except ConnectionRefusedError:  # as err:
        print("cannot connect to mm1 rpc server - sleeping for 2 seconds before trying to connect again.")
        time.sleep(2)
        connect_to_mm1_execution_rpc()

def connect_to_mm1_getter_setter_rpc():
    global mm1_getter_setter_rpc
    try:
        mm1_getter_setter_rpc = xmlrpc.client.ServerProxy("http://mm:7011/")
        print(mm1_getter_setter_rpc.is_connected())
    except ConnectionRefusedError:  # as err:
        print("cannot connect to mm1 rpc server - sleeping for 2 seconds before trying to connect again.")
        time.sleep(2)
        connect_to_mm1_getter_setter_rpc()


def init_mm1():
    MM1.MillingMachine1()

if __name__ == '__main__':
    process_list = [
        Process(target=init_mm1),
    ]
    [process.start() for process in process_list]
    [process.join() for process in process_list]

    thread_list = [
        Thread(target=connect_to_mm1_execution_rpc),
        Thread(target=connect_to_mm1_getter_setter_rpc),
    ]

    [thread.start() for thread in thread_list]
    [thread.join() for thread in thread_list]

    app.run(host='0.0.0.0', port=5003)
