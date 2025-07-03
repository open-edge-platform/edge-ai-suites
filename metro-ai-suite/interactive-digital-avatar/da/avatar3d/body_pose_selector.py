import json
import random


def jsonl_to_body_pose(file: str) -> list[dict]:
    with open(file, 'r', encoding='utf-8') as f:
        return [json.loads(line) for line in f]


idle = jsonl_to_body_pose("resource/avatar3d/idle.jsonl")
show = jsonl_to_body_pose("resource/avatar3d/show.jsonl")
speak01 = jsonl_to_body_pose("resource/avatar3d/speak01.jsonl")
speak02 = jsonl_to_body_pose("resource/avatar3d/speak02.jsonl")
speak03 = jsonl_to_body_pose("resource/avatar3d/speak03.jsonl")
think01 = jsonl_to_body_pose("resource/avatar3d/think01.jsonl")
think02 = jsonl_to_body_pose("resource/avatar3d/think02.jsonl")
wave = jsonl_to_body_pose("resource/avatar3d/wave.jsonl")

idle_probabilities = [
    (idle, 0.8),
    (think01, 0.1),
    (think02, 0.1),
]

speaking_probabilities = [
    (idle, 0.4),
    (show, 0.15),
    (speak01, 0.15),
    (speak02, 0.15),
    (speak03, 0.15),
]


def select_random_pose(is_speaking: bool) -> list[dict]:
    prob = speaking_probabilities if is_speaking else idle_probabilities
    items, probabilities = zip(*prob)
    return random.choices(items, probabilities, k=1)[0]
