import yaml


class qwen:
    """
    Config for qwen llm server
    """

    class remote:
        base_url = str()

    class local:
        ov_model_dir = str()
        max_tokens = int()


class ecrag:
    """
    Config for ecrag llm server
    """
    base_url = str()


class zhipu:
    """
    Config for qwen llm server
    """

    base_url = str()
    token = str()
    knowledge_id = str()


class llama:
    """
    Config for qwen llm server
    """

    base_url = str()


class ov:
    """
    Config for OpenVINO models
    """
    device = str()


class mic:
    """
    Config for mic inputs
    """
    channels = int()
    bits = int()
    rate = int()
    chunk_size = int()


class wake:
    """
    Config for wake word
    """
    wake_words = set()


class tts:
    male_voice = bool()
    qa_transition_wav = str()
    male_hello_wav = str()
    female_hello_wav = str()


class avatar2d:
    render_fps = int()


class avatar3d:
    sio_addr = str()
    said_addr = str()
    said_fps = int()
    pose_sync_fps = int()


def load_config(config: dict, predix=""):
    for key, value in config.items():
        key = f"{predix}.{key}" if predix else key
        if isinstance(value, dict):
            load_config(value, key)
        else:
            if isinstance(value, str):
                exec(f"{key} = '{value}'")
            else:
                exec(f"{key} = {value}")


def load_config_from_file(config_path: str):
    # dynamic set config class values
    with open(config_path, "r", encoding="utf-8") as file:
        yaml_content = yaml.safe_load(file)

    load_config(yaml_content)


# load default config file as module imported
load_config_from_file("resource/config.yaml")
