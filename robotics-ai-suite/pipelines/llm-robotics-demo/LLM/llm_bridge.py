# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import torch
import time
from transformers import AutoTokenizer, AutoConfig, StoppingCriteriaList, StoppingCriteria
from optimum.intel.openvino import OVModelForCausalLM
import logging

print("execute logging basic Config")
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class StopOnTokens(StoppingCriteria):
    def __init__(self, token_ids):
        self.token_ids = token_ids

    def __call__(
            self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs
    ) -> bool:
        for stop_id in self.token_ids:
            if input_ids[0][-1] == stop_id:
                return True
        return False


class LLMBridge:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info('PrimGenerator Init')
        self.model_path = "/home/intel/ov_models/Phi-4-mini-instruct-int8-ov"

        ov_config = {"PERFORMANCE_HINT": "LATENCY", "NUM_STREAMS": "1", "CACHE_DIR": "model_cache"}
        self.model = OVModelForCausalLM.from_pretrained(self.model_path,
                                                        device='GPU',
                                                        ov_config=ov_config,
                                                        config=AutoConfig.from_pretrained(self.model_path, trust_remote_code=True),
                                                        use_cache=True,
                                                        trust_remote_code=True
                                                        ).eval()

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path,
                                                  trust_remote_code=True)

        self.PHI4_PROMPT_FORMAT = "<|user|>\n{prompt}<|end|>\n<|assistant|>\n"

        # remove CoT and emphasize the suck() function
        self.codegen_prompt = """
As an intelligent assistant specialized in robot control, your task involves a few critical steps to translate verbal commands into a sequence of precise control functions. Follow these steps carefully to ensure accuracy and adaptability in generating the function sequence:

1. **Analyze the Command**: Start by carefully reading the command. Identify the key actions (e.g., move, suck) and the objects involved (e.g., red apple, green box).

2. **Determine Necessary Functions**: Based on the actions identified, list the functions you will need to use. Remember, each action like get picking place, sucking, or placing an object corresponds to specific functions.

3. **Identify Parameters**: For each function you've listed, determine the parameters needed. This includes identifying the `obj_name` from the command for picking up, calling suck(), and identifying the `target_pose` mentioned in the command for placing.

4. **Generate the Code**: With the functions and parameters identified, you can now generate the sequence of control functions. Ensure that the `obj_name` parameters accurately reflect the objects specified in the command and the sucking step is included.

Below is a list of functions available for controlling the robot:

- `prepare_state()`: Resets the robot arm to its default position.
- `get_pick_pose(obj_name)`: Determines the picking position for the object identified by `obj_name` and return it.
- `get_place_pose(obj_name)`: Determines the placement position for the object identified by `obj_name` and return it.
- `move(target_pose)`: Moves the robot arm to the position specified by `target_pose`.
- `suck()`: Activates the suction cup to pick up an object.
- `release()`: Deactivates the suction cup to release an object.


Example command:

**Command**: "Pick up the red apple and place it into the green box, then return the robot to its default position."

**Expected Output**:
#code start
prepare_state()
target_pose = get_pick_pose('red apple')
move(target_pose)
suck()
target_pose = get_place_pose('green box')
move(target_pose)
release()
prepare_state()
#end
    """

        self.objextract_prompt = """
Given a command that instructs a robot to move an object to a specific destination, extract and list the object being moved and the destination. The command could be in various formats, such as 'Move [object] to [destination]', 'Pick up [object] and move it to [destination]', or 'Grab [object] and move it to [destination]'. For example, if the command is 'Pick up the book and move it to the table', your response should identify 'the book' as the object and 'the table' as the destination."

Examples:
1. Command: "Move the book to the table"
   Response:
   Object: The book
   Destination: The table

2. Command: "Pick up the red pen and move it to the drawer"
   Response:
   Object: The red pen
   Destination: The drawer

3. Command: "Grab the yellow orange and move it to the shelf"
   Response:
   Object: The yellow orange
   Destination: The shelf        
    """
        self.stop_tokens = [151643, 151645]
        self.stop_tokens = [StopOnTokens(self.stop_tokens)]
        # reduce max new token of the output
        self.n_predict = 100
        self.pad_token_id = 151645
        #if we want to show debug info ,we need to reset logging level because ipex may set it to INFO.
        self.logger.setLevel(logging.DEBUG)

    def phi4_generate(self, prompt, command):
        input = prompt + '\n\nPlease give the code of the following command strictly following **Expected Output**:\n**Command**:: ' + command
        phi4_prompt = self.PHI4_PROMPT_FORMAT.format(prompt=input)

        st = time.time()
        model_inputs = self.tokenizer([phi4_prompt], return_tensors="pt")
        generated_ids = self.model.generate(
            model_inputs.input_ids,
            max_new_tokens=self.n_predict,
            do_sample= False,
            stopping_criteria=StoppingCriteriaList(self.stop_tokens),
            pad_token_id=self.pad_token_id)
        generated_ids = [
            output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)]
        # generate the output token
        output_str = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
        end = time.time()

        self.logger.debug(f'\n**Command**:{command} \n\n**Output**:\n{output_str} \n\n**Inference time**:{end-st}s')
        return output_str


    def generate_prim_code(self, command):
#         pesudo_output='''
# #code start
# prepare_state()
# target_pose = get_pick_pose('The dog')
# move(target_pose)
# suck()
# target_pose = get_place_pose('Default')
# move(target_pose)
# release()
# prepare_state()
# #end
# '''
#         return pesudo_output
        return self.phi4_generate(self.codegen_prompt, command)

    def extract_object(self, command):
   #      return '''
   # Object: The dog
   # Destination: Default
   #      '''
        return self.phi4_generate(self.objextract_prompt, command)
