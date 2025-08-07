# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation

from llm_bridge import LLMBridge
from primitives import *
import logging
import socket
from mobilesam_inference_thread import InferenceThread
from queue import Queue
from threading import Lock
from PIL import Image
import numpy as np
import time
import json
import re

llm_bridge = LLMBridge()
input_queue = Queue()
input_lock = Lock()
output_queue = Queue()
output_lock = Lock()

class PrimitiveActionClient:

    def __init__(self, logger, host='localhost', port=8099):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._addr = (host, port)
        self.logger = logger

    def read(self):
        try:
            data = self._sock.recv(1024).decode()
        except Exception as e:
            self.logger.info(f"recv failed: {e}")
            return False
        self.logger.info(f"[R {data}]")
        return True

    def write(self, code_snippet):
        msg = code_snippet
        try:
            self._sock.send(msg.encode())
        except Exception as e:
            logging.info(f"send failed: {e}")
            return False
        return True


    def run(self, code_snippet):
        self._sock.connect(self._addr)
        self.write(code_snippet)
        self.read()
        self._sock.close()

def verify_code_snippets(content, logger):
    code_snippet = content
    code_statements = code_snippet.split('\n')

    for statement in code_statements:
        try:
            logger.info(f"Executed: {statement}")
            exec(statement)
        except Exception as e:
            logger.info(f"Error executing statement: {statement}\nException: {e}")
            return False

def execute_code_snippets(content, logger):

    code_snippet = content
    # #execute all statement
    # exec(code_snippet)
    try:
        primitive_action_client = PrimitiveActionClient(logger)
        primitive_action_client.run(code_snippet)
    except Exception as e:
        logger.info(f"Error sending to server. Exception: {e}")
        return False

    return True

pose_prim_template = '''
set_obj_info(\'{input_obj_info}\')
'''

def gen_code_1(command, obj_info, logger):
    global llm_bridge
    content = llm_bridge.generate_prim_code(command)
    # change the start_marker since the output may not contain #code start
    start_marker = "prepare_state()"
    end_marker = "#end"
    start_index = content.find(start_marker)
    end_index = content.find(end_marker)
    code_snippet = content[start_index:end_index].strip()
    code_snippet = re.sub(r"get_pick_pose\('[^']+'\)",
                          f"get_pick_pose('{obj_info['Obj']['Name']}')",
                          code_snippet)
    code_snippet = re.sub(r"get_place_pose\('[^']+'\)",
                          f"get_place_pose('{obj_info['Dest']['Name']}')",
                          code_snippet)
    try:
        verify_code_snippets(code_snippet, logger)
    except Exception as e:
        logger.info(f"LLM generated code can't execute success. Exception: {e}")
        return None
    obj_info_str = json.dumps(obj_info)
    code = pose_prim_template.format(input_obj_info=obj_info_str) + '\n' \
        + code_snippet
    logger.info(code)
    return code

def gen_code_2(command, obj_info, logger):
    global pose_prim_template
    code_template = '''
prepare_state()
target_pose = get_pick_pose(\'{ObjName}\')
move(target_pose)
suck()
target_pose = get_place_pose(\'{DestName}\')
move(target_pose)
release()
prepare_state()

'''
    obj_info_str = json.dumps(obj_info)
    code = pose_prim_template.format(input_obj_info=obj_info_str) + '\n' \
        + code_template.format(ObjName=obj_info['Obj']['Name'],
                               DestName=obj_info['Dest']['Name'])
    logger.info(code)
    return code

def parse_llm_objextract_ret(output):
    result = {}
    lines = output.split('\n')
    for line in lines:
        if "Object:" in line:
            obj = line.split("Object:")[1].strip()
            result['Obj'] = {'Name':obj}
        elif "Destination:" in line:
            dest = line.split("Destination:")[1].strip()
            result['Dest'] = {'Name':dest}
    return result

def get_obj_info(command, color_image, depth_image, depth_scale, depth_intrinsics):
    global llm_bridge, input_queue, input_lock, output_queue, output_lock
    ret = parse_llm_objextract_ret(llm_bridge.extract_object(command))
    if not 'Obj' in ret.keys():
        return 'NO_OBJ_IN_COMMAND', None
    if not 'Dest' in ret.keys():
        ret["Dest"] = {'Name':'default'}

#    image_path = './data/coco_bike.jpg'
#    image = Image.open(image_path)
#    color_image = np.asanyarray(image).copy()
    frame_data = {
        'color_frame': color_image,
        'text_prompt': ret["Obj"]["Name"],
        'depth_frame': depth_image,
        'depth_scale': depth_scale,
        'depth_intrinsics': depth_intrinsics
    }
    input_lock.acquire()
    input_queue.put(frame_data)
    input_lock.release()

    while output_queue.empty() == True:
        time.sleep(0.1)

    output_lock.acquire()
    inf_result = output_queue.get()
    output_lock.release()

    if not 'centerX' in inf_result.keys():
        return 'NO_NO_OBJ_IN_FRAME', None

    if inf_result['score'].item() < 60:
        return 'NO_NO_OBJ_IN_FRAME', None

    print(f" inf result: {inf_result}")
    ret["Obj"]['centerX'] = inf_result['centerX']
    ret["Obj"]['centerY'] = inf_result['centerY']
    ret["Obj"]['centerZ'] = inf_result['centerZ']
    ret["Obj"]['score'] = inf_result['score'].item()

    return 'SUCCESS', ret

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    command = 'Grab dog and place it into red box.'
    max_attempts = 3
    inference_thread = InferenceThread(input_queue, input_lock, output_queue, output_lock)
    inference_thread.start()
    while True:
        input_str = input("Please input your command:")
        if input_str == 'exit':
            inference_thread.stopWorker()
            break
        else:
            if input_str != '':
                command = input_str
        print(f"Command is {command}")
        input_str = input("Please input code generation mode [1 or 2]:")
        code_gen_func = gen_code_2
        if input_str == '1' or input_str =='' :
            code_gen_func = gen_code_1

        status, obj_info = get_obj_info(command)
        if status == 'SUCCESS':
            for i in range(max_attempts):
                content = code_gen_func(command, obj_info)
                if content is None:
                    continue
                result = execute_code_snippets(content, logger)
                if result:
                    break
            if i < max_attempts:
                logger.info(f"Primitive generated & executed successfully in {i + 1} trial!")
            else:
                logger.info("Max attempts reached!")
        else:
            logger.info(f"The input has error {status}, please adjust your command!")
