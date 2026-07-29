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
        import os
        home_dir = os.path.expanduser("~")
        self.model_path = os.path.join(home_dir, "ov_models/Phi-4-mini-instruct-int8-ov")
        print(f"Loading LLM model from {self.model_path}...")

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

        self.LLM_PROMPT_FORMAT = "<|user|>\n{prompt}<|end|>\n<|assistant|>\n"

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
        # for Qwen model, use below prompt.
        if "Qwen" in self.model_path:
            self.codegen_prompt = """
You are a robot control code generator.

CRITICAL RULES (MUST FOLLOW):
- ONLY output code
- DO NOT output <think> or any reasoning
- DO NOT explain anything
- DO NOT add any text before or after the code
- DO NOT output comments
- If you output anything other than the required format, the answer is invalid
- If you generate "<think>", the answer is invalid

OUTPUT FORMAT (STRICT):
Your output must be EXACTLY:

#code start
...code...
#end

CODE RULES:
- Use ONLY the provided functions
- DO NOT invent new functions
- Always follow correct sequence
- Use variable name exactly: target_pose

ACTION RULES:
- Picking MUST follow:
  get_pick_pose → move → suck
- Placing MUST follow:
  get_place_pose → move → release
- Always start with prepare_state()
- Always end with prepare_state()

AVAILABLE FUNCTIONS:
- prepare_state()
- get_pick_pose(obj_name)
- get_place_pose(obj_name)
- move(target_pose)
- suck()
- release()

EXAMPLE:

Command: Pick up the red apple and place it into the green box, then return the robot to its default position.

Output:
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

TASK:

Command: {your_command_here}

Output:
Output MUST start directly with "#code start".
#code start
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
        # for Qwen model, use below prompt
        if "Qwen" in self.model_path:
            self.objextract_prompt = """
You are an information extractor.

TASK:
From the given command, extract:
1) the object being moved
2) the destination (where the object should be moved to)

OUTPUT FORMAT (STRICT):
Return EXACTLY two lines and nothing else:
Object: <object text>
Destination: <destination text>

RULES:
- Do NOT explain.
- Do NOT output examples.
- Do NOT output <think> or any reasoning.
- Preserve the original wording from the command as much as possible.
- If either field is missing or unclear, output "UNKNOWN" for that field.

Examples:
Command: Move the book to the table
Object: the book
Destination: the table

Command: Pick up the red pen and move it to the drawer
Object: the red pen
Destination: the drawer

Command: Grab the yellow orange and move it to the shelf
Object: the yellow orange
Destination: the shelf

Now extract from this command:
Command: "{command}"
"""

        self.stop_tokens = [151643, 151645]
        self.stop_tokens = [StopOnTokens(self.stop_tokens)]
        # reduce max new token of the output
        self.n_predict = 100
        self.pad_token_id = 151645
        #if we want to show debug info ,we need to reset logging level because ipex may set it to INFO.
        self.logger.setLevel(logging.DEBUG)

    def llm_generate(self, prompt, command):
        input = prompt + '\n\nPlease give the code of the following command strictly following **Expected Output**:\n**Command**:: ' + command
        llm_prompt = self.LLM_PROMPT_FORMAT.format(prompt=input)

        # for Qwen model, use below prompt
        if "Qwen" in self.model_path:
            messages = []
            output_example = """
prepare_state()
target_pose = get_pick_pose('{object}')
move(target_pose)
suck()
target_pose = get_place_pose('{place}')
move(target_pose)
release()
prepare_state()
"""
            g_prompt = input+'\n'+output_example
            messages.append({"role": "system", "content": g_prompt})
            messages.append({"role": "user", "content": command})
            llm_prompt = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True
                )

        # add bad words
        bad_words = ["<think>"]
        bad_words_ids = self.tokenizer(bad_words, add_special_tokens=False).input_ids

        st = time.time()
        model_inputs = self.tokenizer([llm_prompt], return_tensors="pt")
        generated_ids = self.model.generate(
            model_inputs.input_ids,
            max_new_tokens=self.n_predict,
            do_sample= False,
            stopping_criteria=StoppingCriteriaList(self.stop_tokens),
            bad_words_ids=bad_words_ids,
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
        return self.llm_generate(self.codegen_prompt, command)

    def extract_object(self, command):
   #      return '''
   # Object: The dog
   # Destination: Default
   #      '''
        return self.llm_generate(self.objextract_prompt, command)