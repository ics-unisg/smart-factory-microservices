from flask import Flask, request, jsonify, abort
import json
from threading import Thread
import time
from datetime import datetime
import xmlrpc.client
import heapq

from flasgger import Swagger
import EC1
from multiprocessing import Process

app = Flask(__name__)
swagger = Swagger(app)

list_of_valid_requests = []

"""
#####################################################################
#####################################################################
################## Initializing Web Server and Queue ################
#####################################################################
#####################################################################
"""

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
    if request.url == "http://127.0.0.1:5001/favicon.ico":
        print(request.url + " was called")
        return
    if request.url == "http://127.0.0.1:5001/apidocs/":
        return
    if request.url == "http://localhost:5001/apidocs/":
        return
    if request.url == "http://ec:5001/apidocs/":
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
            pass


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


"""
#####################################################################
#####################################################################
############## Environment and Camera (SSC) #########################
################# Execution Webservices #############################
#####################################################################
#####################################################################
"""

# TODO: implement

"""
#####################################################################
#####################################################################
############## Environment and Camera (SSC) #########################
############ Getter and Setter Webservices ##########################
#####################################################################
#####################################################################
"""
# TODO: implement

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


def init_ec1():
    EC1.EnvironmentAndCamera1()

if __name__ == '__main__':

    process_list = [
        Process(target=init_ec1),
    ]
    [process.start() for process in process_list]
    [process.join() for process in process_list]

    thread_list = [
    ]

    [thread.start() for thread in thread_list]
    [thread.join() for thread in thread_list]

    app.run(host='0.0.0.0', port=5001)
