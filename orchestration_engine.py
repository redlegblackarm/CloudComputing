"""
Authors : Hrishikesh S.   01FB16ECS139
Status  : back-end front-end communications are mostly working
          need to add upvote button to catetemplate.html and make upvote working
          pass ip_address and port_no as arguments (OPTIONAL)
Notes   : # for developer's comment/insight
          ## for removing code
          Modify IP address & Port before running with act_management_ms.py
          To access the V.M., get the .pem key and run
                $ ssh -i "MYOSHLinux.pem" ubuntu@public_dns
          Run pre-run.sh before running this code on terminal/CMD PROMPT
"""
# I.P. address should be a string
# enter I.P. address of your AWS instance
ip_address = '35.174.107.114'
origin = '18.212.26.145'

from flask import (
    Flask,
    render_template,
    url_for,
    Markup,
    send_from_directory,
    flash,
    request,
    jsonify
)

import os, ast
import json
from werkzeug import secure_filename, exceptions
import datetime
import shutil
import base64
import binascii
import re
import requests

http_methods = ['GET', 'POST']


# create application instance
app = Flask(__name__)
# generating a secret key for sessions
app.secret_key = os.urandom(16)

# port number should be a number
port_no = 80

# acts port numbers
act_port_init = 8000
act_port_end = 8001
act_public_dns_list = ['0.0.0.0']

# active containers
active_ports = {}
healthy_containers = []

# volume bindings
volume_bindings = { '/home/ubuntu/act_management' : {'bind' : '/app', 'mode' : 'rw'}}

from flask import (
    Flask,
    render_template,
    url_for,
    Markup,
    send_from_directory,
    flash,
    request
)

import os
import json
from werkzeug import secure_filename, exceptions
import datetime
import shutil
import base64
import binascii
import re
import requests
import time
# importing thread library
import threading
# importing docker-py to run and stop containers
import docker

# connect to docker daemon using default socket
docker_client = docker.from_env()

# decision pointer for deciding which container will be used
rr_pointer = 0

# http requests counter
n_http_requests = 0

# auto scale started flag
auto_scale_flag = 1
ft_scale_factor = 0

#creating lock
lock = threading.RLock()

#headers for POST
headers = {'Content-Type': 'application/json', 'Accept':'application/json'}

# fault tolerance blocker
ft_block = False

# custom lock
c_lock = 0

# get url
def get_url_rule():
    rule = None
    url_rule = request.url_rule
    if url_rule is not None:
        rule = url_rule.rule
    return rule

# critical task - RUN APP
def run_app():
	print("Name of thread : ", threading.current_thread().name)
	print("App running @ port 80")
	app.run(debug = True, use_reloader = False, host = '0.0.0.0', port = 80)

# critical task - FAULT TOLERANCE
def faultTolerance():
	global ft_block
	if(ft_block == False):
		print("Name of thread : ", threading.current_thread().name)
		print("Fault Tolerance")
		global n_http_requests, docker_client, active_ports, ft_scale_factor
		print("FT scale factor  = ", ft_scale_factor)
		print("Number of HTTP requests received ", n_http_requests)
		#try:
		##if(len(active_ports) == len(docker_client.containers.list())):
		##print("START FAULT TOLERANCE............CONDITION PASSED")
		##print(active_ports)
		for port_i in active_ports:
			print(active_ports)
			response = requests.get("http://" + act_public_dns_list[0] + ":" + str(port_i) + "/api/v1/_health")
			##time.sleep(3)
			print("STATUS CODE ", response.status_code)
			code = int(response.status_code)
			if(code == 500):
				container_id = active_ports[port_i]
				print("Fault found at port ", port_i)
				container_id = container_id[0].id
				print(container_id)
				container = docker_client.containers.get(container_id)
				container.stop(timeout = 0)
				##time.sleep(5)
				docker_client.containers.run("hrishikeshsuresh/acts:latest", ports = {'80':str(port_i)}, detach = True, volumes = volume_bindings, privileged = True)
				print("Faulty container restarted @ port ", port_i)
			else:
				print("No faulty container")
		##except RuntimeError as e:
			##print(e)
			##pass
	threading.Timer(1.0, faultTolerance).start()

def up_scale(scale_factor):
	print("Upscaling...")
	print(scale_factor)
	global n_http_requests, docker_client, act_port_init, act_port_end, active_ports
	act_port_end = act_port_end + scale_factor - 1
	print(act_port_init, act_port_end)
	for port_i in range(act_port_init, act_port_end):
		if(port_i not in active_ports):
			docker_client.containers.run("hrishikeshsuresh/acts:latest", ports = {'80' : str(port_i)}, detach = True, volumes = volume_bindings, privileged = True)
			##active_ports.append({port_i : docker_client.containers.list(limit = 1)})
			##time.sleep(5)
			active_ports[port_i] = docker_client.containers.list(limit = 1)
			print("New container started. Current active ports ", active_ports)
			print("New container @ port ", port_i)
	time.sleep(2)
	return

def down_scale(scale_factor):
	print("Downscaling...")
	print(scale_factor)
	global n_http_requests, docker_client, act_port_init, act_port_end, active_ports, ft_scale_factor
	# scale_factor is negative, so we add
	print(act_port_end + scale_factor, act_port_end)
	for port_i in range(act_port_end + scale_factor, act_port_end):
		if(port_i in active_ports):
			container_to_be_stopped = active_ports[port_i]
			container_to_be_stopped[0].stop(timeout = 0)
			# None to prevent error
			active_ports.pop(port_i, None)
			print("Container removed @ port ", port_i)
	# scale_factor is negative, so we add
	act_port_end = act_port_end + scale_factor
	ft_scale_factor = 0
	return

# critical task - AUTO SCALING MAIN
def auto_scaling():
	# start timer only if first requests
	print("Name of thread : ", threading.current_thread().name)
	global n_http_requests, auto_scale_flag, docker_client, act_port_init, act_port_end, active_ports, ft_scale_factor, ft_block
	print("Number of containers running ", len(active_ports))
	##if(n_http_requests < 20 and act_ports[0] not in active_ports):
	print("INIT PORT ", act_port_init)
	print("ACTIVE PORT ", active_ports)
	print(act_port_init not in active_ports)
	# one container will start immediately
	# container starts before first incoming requests
	if(act_port_init not in active_ports):
		docker_client.containers.run("hrishikeshsuresh/acts:latest", ports = {'80' : str(act_port_init)}, detach = True, volumes = volume_bindings, privileged = True)
		##active_ports.append({act_ports[0] : docker_client.containers.list(limit = 1)})
		active_ports[act_port_init] = docker_client.containers.list(limit = 1)
		print("First container started. Current active ports ", active_ports)
		act_port_end = act_port_end + 1
	# wait till we get the first request
	while(auto_scale_flag == 1):
		time.sleep(0.5)
		print("Waiting for first request")
		if n_http_requests >= 1:
			auto_scale_flag = 0
			time.sleep(120)
	##lock.acquire()
	ft_block = True
	print("BLOCK ACTIVATED")
	# number of containers to be created
	containers_to_be_created = n_http_requests // 20
	# to decide port range for next iterations
	# formula scale_factor = r - n + 1
	print("Deciding scale factor")
	scale_factor = containers_to_be_created - len(active_ports) + 1
	if(scale_factor > 0):
		up_scale(scale_factor)
	elif(scale_factor < 0):
		down_scale(scale_factor)
		ft_scale_factor = scale_factor
	else:
		print("No scaling...")
	##next_act_port_end = act_port_end + containers_to_be_created
	##for port_i in range(act_port_init, act_port_end + containers_to_be_created):
	##if(containers_to_be_created >= 1 and port_i not in active_ports):
	    ##docker_client.containers.run("hrishikeshsuresh/acts:latest", ports = {'80' : str(port_i)})
	    ##active_ports.append({port_i : docker_client.containers.list(limit = 1)})
	    ##print("New container started. Current active ports ", active_ports)
	    ##act_port_end = act_port_end + 1
	    ##containers_to_be_created = containers_to_be_created - 1
	##act_port_end = new_act_port_end

	# start timer and execute every 2 minutes
	print("starting timer...")
	n_http_requests = 0
	ft_block = False
	print("BLOCK DEACTIVATED")
	threading.Timer(120.0, auto_scaling).start()

# list all categories
@app.route('/api/v1/categories', methods = ['GET'])
def listCategories():
	global rr_pointer, n_http_requests, act_public_dns_list, active_ports
	n_http_requests = n_http_requests + 1
	global c_lock
	if request.method == 'GET':
		##lock.acquire()
		##while(c_lock != 0):
			##if(c_lock == 0):
				##break
		##c_lock = 1
		print(list(active_ports)[rr_pointer])
		response = requests.get('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer])+'/api/v1/categories')
		# increment rr pointer after usage
		rr_pointer = (rr_pointer+1)%(len(docker_client.containers.list()))
		##lock.release()
		##c_lock = 0
		print(response.text)
		return response.text, 200
	else:
		return jsonify({}), 405

# add a category
# input should be JSON ARRAY []
@app.route('/api/v1/categories', methods = ['POST'])
def addCategory():
	global rr_pointer, n_http_requests, act_public_dns_list, active_ports, headers
	n_http_requests = n_http_requests + 1
	if request.method == 'POST':
		data = request.get_data().decode()
		print(data)
		##data = ast.literal_eval(json.dumps(data))
		##print("RAW DATA : ", data)
		##print(type(data))
		##data = data[1:-1].replace('\'','').replace(', ',',').split(sep = ",")
		##data = data.replace('\"', '').strip('][')
		##data = ''.join(x for x in data)
		##json_data = list([])
		##json_data.insert(0,data)
		##data = json.loads(data)
		##data = [data]
		##print("FORMATTED DATA : ", data)
		##print(type(data))
		rr_pointer = (rr_pointer+1)%(len(active_ports))
		print('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer])+'/api/v1/categories')
		response = requests.post('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer])+'/api/v1/categories', data = data, headers = headers)
		##print('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer])+'/api/v1/categories')
		# increment rr pointer after usage
		##print(response.text)
		##rr_pointer = (rr_pointer+1)%(len(active_ports))
		print(response.text)
		return response.text, 200
	else:
		return jsonify({}), 405

# remove a category
@app.route('/api/v1/categories/<categoryName>', methods = ['DELETE'])
def removecategory(categoryName):
	global rr_pointer, n_http_requests, act_public_dns_list, active_ports
	n_http_requests = n_http_requests + 1
	if request.method == 'DELETE':
		print(categoryName)
		rr_pointer = (rr_pointer+1)%(len(active_ports))
		print('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer])+'/api/v1/categories')
		response = requests.delete('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer]) +'/api/v1/categories/' + categoryName)
		# increment rr pointer after usage
		print(response.text)
		##rr_pointer = (rr_pointer+1)%(len(active_ports))
		return jsonify(response.text), 200
	else:
		return jsonify({}), 405

@app.route('/api/v1/categories/<categoryName>/acts', methods = ['GET'])
def listActs(categoryName):
	global rr_pointer, n_http_requests, act_public_dns_list, active_ports
	n_http_requests = n_http_requests + 1
	if request.method == 'GET':
		rr_pointer = (rr_pointer+1)%(len(active_ports))
		print('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer])+'/api/v1/categories')
		response = requests.get('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer]) +'/api/v1/categories/' + categoryName + '/acts')
		##rr_pointer = (rr_pointer+1)%(len(active_ports))
		print(response.text)
		return response.text, 200
	else:
		return jsonify({}), 405

@app.route('/api/v1/categories/<categoryName>/acts/size', methods = ['GET'])
def listNoOfActs(categoryName):
	global rr_pointer, n_http_requests, act_public_dns_list, active_ports
	n_http_requests = n_http_requests + 1
	if request.method == 'GET':
		rr_pointer = (rr_pointer+1)%(len(active_ports))
		print('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer])+'/api/v1/categories')
		response = requests.get('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer]) +'/api/v1/categories/' + categoryName + '/acts/size')
		##rr_pointer = (rr_pointer+1)%(len(active_ports))
		print(response.text)
		return response.text, 200
	else:
	    return jsonify({}), 405

@app.route('/api/v1/categories/<categoryName>/acts?start=<startRange>&end=<endRange>', methods = ['GET'])
def listActsInGivenRange(categoryName, startRange, endRange):
	global rr_pointer, n_http_requests, act_public_dns_list, active_ports
	n_http_requests = n_http_requests + 1
	if request.method == 'GET':
		rr_pointer = (rr_pointer+1)%(len(active_ports))
		response = requests.get('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer]) +'/api/v1/categories/' + categoryName + '/acts?start=' + startRange + '&end=' + endRange)
		##rr_pointer = (rr_pointer+1)%(len(active_ports))
		print(response.text)
		return response.text, 200
	else:
		return jsonify({}), 405

@app.route('/api/v1/acts/upvote', methods = ['POST'])
def upvoteAct():
	global rr_pointer, n_http_requests, act_public_dns_list, active_ports
	n_http_requests = n_http_requests + 1
	if request.method == 'POST':
		data = request.get_data().decode()
		print(data)
		rr_pointer = (rr_pointer+1)%(len(active_ports))
		print('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer])+'/api/v1/acts')
		response = requests.post('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer]) +'/api/v1/acts/upvote', data = data)
		##rr_pointer = (rr_pointer+1)%(len(active_ports))
		print(response.text)
		return response.text, 200
	else:
		return jsonify({}), 405

@app.route('/api/v1/acts/<actId>', methods = ['DELETE'])
def removeAct(actId):
	global rr_pointer, n_http_requests, act_public_dns_list, active_ports
	n_http_requests = n_http_requests + 1
	if request.method == 'DELETE':
		print(actId)
		rr_pointer = (rr_pointer+1)%(len(active_ports))
		print('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer])+'/api/v1/acts')
		response = requests.delete('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer]) + '/api/v1/acts/' + actId)
		##rr_pointer = (rr_pointer+1)%(len(active_ports))
		print(response.text)
		return response.text, 200
	else:
		return jsonify({}), 405

@app.route('/api/v1/acts', methods = ['POST'])
def uploadAct():
	global rr_pointer, n_http_requests, act_public_dns_list, active_ports
	n_http_requests = n_http_requests + 1
	if request.method == 'POST':
		data = request.get_data().decode()
		print(data)
		rr_pointer = (rr_pointer+1)%(len(active_ports))
		print('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer])+'/api/v1/acts')
		response = requests.post('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer]) +'/api/v1/acts', data = data)
		##rr_pointer = (rr_pointer+1)%(len(active_ports))
		print(response.text)
		return response.text, 200
	else:
		return jsonify({}), 405

@app.route('/api/v1/_count', methods = ['GET'])
def count_http_request():
	global rr_pointer, n_http_requests, act_public_dns_list, active_ports
	n_http_requests = n_http_requests + 1
	if request.method == 'GET':
		rr_pointer = (rr_pointer+1)%(len(active_ports))
		print('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer])+'/api/v1/acts')
		response = requests.get('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer]) +'/api/v1/_count')
		##rr_pointer = (rr_pointer+1)%(len(active_ports))
		print(response.text)
		return response.text, 200
	else:
		return jsonify({}), 405

@app.route('/api/v1/_count', methods = ['DELETE'])
def reset_http_request():
	global rr_pointer, n_http_requests, act_public_dns_list, active_ports
	n_http_requests = n_http_requests + 1
	if request.method == 'DELETE':
		rr_pointer = (rr_pointer+1)%(len(active_ports))
		print('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer])+'/api/v1/acts')
		response = requests.delete('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer]) +'/api/v1/_count')
		##rr_pointer = (rr_pointer+1)%(len(active_ports))
		print(response.text)
		return response.text, 200
	else:
		return "invalid"

@app.route('/api/v1/acts/count', methods = ['GET'])
def countAllActs():
	global rr_pointer, n_http_requests, act_public_dns_list, active_ports
	n_http_requests = n_http_requests + 1
	if request.method == 'GET':
		rr_pointer = (rr_pointer+1)%(len(active_ports))
		print('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer])+'/api/v1/acts')
		response = requests.get('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer]) +'/api/v1/acts/count')
		##rr_pointer = (rr_pointer+1)%(len(active_ports))
		print(response.text)
		return response.text, 200
	else:
		return jsonify({}), 405

# health check
@app.route('/api/v1/_health', methods = ['GET'])
def health():
	global rr_pointer, n_http_requests, act_public_dns_list, active_ports
	n_http_requests = n_http_requests + 1
	if request.method == 'GET':
		rr_pointer = (rr_pointer+1)%(len(active_ports))
		print('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer])+'/api/v1/_health')
		response = requests.get('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer]) +'/api/v1/_health' + categoryName)
		##rr_pointer = (rr_pointer+1)%(len(active_ports))
		print(response.text)
		return response.text, 200
	else:
		return jsonify({}), 405

# crash server
@app.route('/api/v1/_crash', methods = ['POST'])
def crash():
	global rr_pointer, n_http_requests, act_public_dns_list, active_ports
	n_http_requests = n_http_requests + 1
	if request.method == 'POST':
		data = request.get_data().decode()
		print(data)
		rr_pointer = (rr_pointer+1)%(len(active_ports))
		print('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer])+'/api/v1/_crash')
		response = requests.post('http://' + act_public_dns_list[0] + ':' + str(list(active_ports)[rr_pointer]) +'/api/v1/_crash', data = data)
		##rr_pointer = (rr_pointer+1)%(len(active_ports))
		print(response.text)
		return response.text, 200
	else:
		return jsonify({}), 405

if __name__ == '__main__':
	# creating threads
	auto_scale_thread = threading.Thread(target = auto_scaling, name = 'AUTO SCALE')
	fault_tolerance_thread = threading.Thread(target = faultTolerance, name = 'FAULT TOLERANCE')
	##threading.Timer(120.0, auto_scaling).start()
	app_thread = threading.Thread(target = run_app, name = 'RUN APP')
	# starting threads
	auto_scale_thread.start()
	fault_tolerance_thread.start()
	app_thread.start()

	auto_scale_thread.join()
	fault_tolerance_thread.join()
	app_thread.join()
