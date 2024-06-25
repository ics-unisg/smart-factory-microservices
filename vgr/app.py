from flask import Flask, request, jsonify, abort
import json
from threading import Thread
import time
from datetime import datetime
import xmlrpc.client
import heapq
from flasgger import Swagger
import VGR1
from multiprocessing import Process

app = Flask(__name__)
swagger = Swagger(app)

list_of_valid_requests = []

vgr1_execution_rpc = None
heap_queue_vgr1_execution = []
vgr1_getter_setter_rpc = None
heap_queue_vgr1_getter_setter = []


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
    if request.url == "http://127.0.0.1:5006/favicon.ico":
        print(request.url + " was called")
        return
    if request.url == "http://127.0.0.1:5006/apidocs/":
        return
    if request.url == "http://localhost:5006/apidocs/":
        return
    if request.url == "http://vgr:5006/apidocs/":
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
            if machine == "vgr":
                heapq.heappush(heap_queue_vgr1_getter_setter, (priority, dt, request, path))
    else:
        if factory == "1":
            if machine == "vgr":
                heapq.heappush(heap_queue_vgr1_execution, (priority, dt, request, path))


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

def check_heap_queue_vgr1_execution(req):
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :param req: Request
    :return: Nothing
    """
    tmp = True
    while tmp:
        if req.datetime == heap_queue_vgr1_execution[0][1] and req.path == heap_queue_vgr1_execution[0][3]:
            tmp = False


def pop_heap_queue_vgr1_execution():
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :return: Nothing
    """
    heapq.heappop(heap_queue_vgr1_execution)


def check_heap_queue_vgr1_getter_setter(req):
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :param req: Request
    :return: Nothing
    """
    tmp = True
    while tmp:
        if req.datetime == heap_queue_vgr1_getter_setter[0][1] and req.path == heap_queue_vgr1_getter_setter[0][3]:
            tmp = False


def pop_heap_queue_vgr1_getter_setter():
    """
    Checks whether the given request is at the first position of the queue. This is executed until it is the case.
    :return: Nothing
    """
    heapq.heappop(heap_queue_vgr1_getter_setter)


"""
#####################################################################
#####################################################################
################## Vacuum Gripper Robot #############################
################## Execution Webservices ############################
#####################################################################
#####################################################################
"""


@app.route('/vgr/calibrate')
def vgr_calibrate() -> [None, json]:
    """
        Pass as get parameter (motor=x) where x must be either 1, 2, or 3. 
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: vgr_1
            - name: motor
              in: path
              schema:
                type: integer
                enum: [1,2,3]
              required: true
        description: >
                    If no parameter is passed, all motors are calibrated. **vgr/calibrate?machine=vgr_1&motor=1**
                    [Example Link](http://127.0.0.1:5006/vgr/calibrate?machine=vgr_1&motor=1)
        responses:
            200:
                description: JSON
    """
    if request.args.get('motor'):
        motor = request.args.get('motor')
    else:
        motor = None

    if request.factory == "1":
        check_heap_queue_vgr1_execution(request)
        try:
            if motor is None:
                vgr1_execution_rpc.calibrate()
            else:
                vgr1_execution_rpc.calibrate(int(motor))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_vgr1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_vgr1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/vgr/pick_up_and_transport')
def vgr_pick_up_and_transport() -> [None, json]:
    """
        Transports workpiece from start position to end position.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: vgr_1
            - name: start
              in: path
              type: string
              required: true
            - name: end
              in: path
              type: string
              required: true
        description: >
                    URL **vgr/pick_up_and_transport?machine=vgr_1&start=sink_2&end=oven**
                    [Example Link](http://127.0.0.1:5006/vgr/pick_up_and_transport?machine=vgr_1&start=sink_2&end=oven)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1" and request.args.get('start') and request.args.get('end'):
        check_heap_queue_vgr1_execution(request)

        try:
            vgr1_execution_rpc.pick_up_and_transport(request.args.get('start'), request.args.get('end'))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_vgr1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_vgr1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/vgr/stop_vacuum_suction')
def vgr_stop_vacuum_suction() -> [None, json]:
    """
        Stops the vacuum suction of VGR
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: vgr_1
        description: >
                    URL **vgr/stop_vacuum_suction?machine=vgr_1**
                    [Example Link](http://127.0.0.1:5006/vgr/stop_vacuum_suction?machine=vgr_1)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1":
        check_heap_queue_vgr1_execution(request)
        try:
            vgr1_execution_rpc.stop_vacuum_suction()
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_vgr1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_vgr1_execution()

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/vgr/move_to')
def vgr_move_to() -> [None, json]:
    """
        Moves to the given position
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: vgr_1
            - name: start
              in: path
              type: string
              required: true
              description: Start Position
            - name: position
              in: path
              type: string
              required: true
              description: End Position
        description: >
                    URL **vgr/move_to?machine=vgr_1&start=sink_1&position=oven**
                    [Example Link](http://127.0.0.1:5006/vgr/move_to?machine=vgr_1&start=sink_1&position=oven)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1" and request.args.get('position'):
        check_heap_queue_vgr1_execution(request)

        try:
            vgr1_execution_rpc.move_to(request.args.get('position'))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_vgr1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_vgr1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/vgr/read_color')
def vgr_read_color() -> [None, json]:
    """
        Read the color from the VGR's color sensor at the DPS station.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: vgr_1
        description: >
                    URL **vgr/read_color?machine=vgr_1**
                    [Example Link](http://127.0.0.1:5006/vgr/read_color?machine=vgr_1)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1":
        check_heap_queue_vgr1_execution(request)

        try:
            color = vgr1_execution_rpc.read_color()
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_vgr1_execution()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_vgr1_execution()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"current_color": color}
    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


"""
#####################################################################
#####################################################################
################## Vacuum Gripper Robot #############################
############ Getter and Setter Webservices ##########################
#####################################################################
#####################################################################
"""


@app.route('/vgr/state_of_machine')
def vgr_state_of_machine() -> [None, json]:
    """
        Indicates the state of a machine
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: vgr_1
        description: >
                    URL **vgr/state_of_machine?machine=vgr_1**
                    [Example Link](http://127.0.0.1:5006/vgr/state_of_machine?machine=vgr_1)
        responses:
            200:
                description: JSON
    """
    state = None
    if request.factory == "1":
        check_heap_queue_vgr1_getter_setter(request)
        try:
            state = vgr1_getter_setter_rpc.state_of_machine(1)
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_vgr1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_vgr1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"state": state}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/vgr/get_motor_speed')
def vgr_get_motor_speed() -> [None, json]:
    """
        Gets the motor speed for the specified motor
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
                    URL **vgr/get_motor_speed?machine=vgr_1&motor=1**
                    [Example Link](http://127.0.0.1:5006/vgr/get_motor_speed?machine=vgr_1&motor=1)
        responses:
            200:
                description: JSON
    """
    motor_speed = None
    if request.factory == "1" and request.args.get('motor'):
        check_heap_queue_vgr1_getter_setter(request)
        try:
            motor_speed = vgr1_getter_setter_rpc.get_motor_speed(int(request.args.get('motor')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_vgr1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_vgr1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"motor_speed": motor_speed}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/vgr/set_motor_speed')
def vgr_set_motor_speed() -> [None, json]:
    """
        Sets the motor speed for the specified motor
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
            - name: speed
              in: path
              type: integer
              required: true
              description: Number of motor
        description: >
                    URL **vgr/set_motor_speed?machine=vgr_1&motor=1&speed=400**
                    [Example Link](http://127.0.0.1:5006/vgr/set_motor_speed?machine=vgr_1&motor=1&speed=400)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1" and request.args.get('motor') and request.args.get('speed'):
        check_heap_queue_vgr1_getter_setter(request)
        try:
            vgr1_getter_setter_rpc.set_motor_speed(int(request.args.get('motor')), int(request.args.get('speed')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_vgr1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_vgr1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/vgr/reset_all_motor_speeds')
def vgr_reset_all_motor_speeds() -> [None, json]:
    """
        Resets all the motor speeds for the specified machine
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: vgr_1
        description: >
                    URL **vgr/reset_all_motor_speeds?machine=vgr_1**
                    [Example Link](http://127.0.0.1:5006/vgr/reset_all_motor_speeds?machine=vgr_1)
        responses:
            200:
                description: JSON
    """
    if request.factory == "1":
        check_heap_queue_vgr1_getter_setter(request)
        try:
            vgr1_getter_setter_rpc.reset_all_motor_speeds()
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_vgr1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_vgr1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    if request and request.method == "GET":
        return jsonify(create_json(request))
    else:
        abort(404)


@app.route('/vgr/check_position')
def vgr_check_position() -> [None, json]:
    """
        Checks if the position of the machine matches the queried position
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: vgr_1
            - name: position
              in: path
              type: string
              required: true
        description: >
                    URL **vgr/check_position?machine=vgr_1&position=initial**
                    [Example Link](http://127.0.0.1:5006/vgr/check_position?machine=vgr_1&position=initial)
        responses:
            200:
                description: JSON
    """
    check = None
    if request.factory == "1" and request.args.get('position'):
        check_heap_queue_vgr1_getter_setter(request)
        try:
            check = vgr1_getter_setter_rpc.check_position(request.args.get('position'))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_vgr1_getter_setter()
            abort(400, f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_vgr1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"is_at_queried_position": check}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
    else:
        abort(404)


@app.route('/vgr/status_of_light_barrier')
def vgr_status_of_light_barrier() -> [None, json]:
    """
        Indicates whether a light barrier is broken through or not.
        ---
        parameters:
            - name: machine
              in: path
              type: string
              required: true
              description: vgr_1
            - name: lb
              in: path
              type: integer
              required: true
              description: number of the light barrier
        description: >
                    URL **vgr/status_of_light_barrier?machine=vgr_1&lb=7**
                    [Example Link](http://127.0.0.1:5006/vgr/status_of_light_barrier?machine=vgr_1&lb=7)
        responses:
            200:
                description: JSON
    """
    status = None
    if request.factory == "1" and request.args.get('lb'):
        check_heap_queue_vgr1_getter_setter(request)
        try:
            status = vgr1_getter_setter_rpc.status_of_light_barrier(int(request.args.get('lb')))
        except xmlrpc.client.Fault as rpc_error:
            pop_heap_queue_vgr1_getter_setter()
            abort(400,
                  f"The machine controller of the addressed machine encountered an error: {rpc_error.faultString}")
        pop_heap_queue_vgr1_getter_setter()
    else:
        abort(404, "Please make sure that the value of the parameter for the machine is 1")

    args = {"interrupted": status}

    if request and request.method == "GET":
        return jsonify(create_json(request, args))
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
def connect_to_vgr1_execution_rpc():
    global vgr1_execution_rpc
    try:
        vgr1_execution_rpc = xmlrpc.client.ServerProxy("http://vgr:8013/")
        print(vgr1_execution_rpc.is_connected())
    except ConnectionRefusedError:  # as err:
        print("cannot connect to vgr1 rpc server - sleeping for 2 seconds before trying to connect again.")
        time.sleep(2)
        connect_to_vgr1_execution_rpc()

def connect_to_vgr1_getter_setter_rpc():
    global vgr1_getter_setter_rpc
    try:
        vgr1_getter_setter_rpc = xmlrpc.client.ServerProxy("http://vgr:7013/")
        print(vgr1_getter_setter_rpc.is_connected())
    except ConnectionRefusedError:  # as err:
        print("cannot connect to vgr1 rpc server - sleeping for 2 seconds before trying to connect again.")
        time.sleep(2)
        connect_to_vgr1_getter_setter_rpc()

def init_vgr1():
    VGR1.VacuumGripperRobot1()

if __name__ == '__main__':
    process_list = [
        Process(target=init_vgr1),
    ]

    thread_list = [
        Thread(target=connect_to_vgr1_execution_rpc),
        Thread(target=connect_to_vgr1_getter_setter_rpc),
    ]

    [thread.start() for thread in thread_list]
    [thread.join() for thread in thread_list]

    app.run(host='0.0.0.0', port=5006)
