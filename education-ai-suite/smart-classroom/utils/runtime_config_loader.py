import yaml
import os

class RuntimeConfig:
    CONFIG_PATH = "runtime_config.yaml"

    @staticmethod
    def load(path: str = None) -> dict:
        path = path or RuntimeConfig.CONFIG_PATH
        if not os.path.exists(path):
            RuntimeConfig._create_default(path)
        with open(path, "r") as f:
            return yaml.safe_load(f)

    @staticmethod
    def save(data: dict, path: str = None):
        path = path or RuntimeConfig.CONFIG_PATH
        with open(path, "w") as f:
            yaml.dump(data, f, default_style='"', sort_keys=False)
        

    @staticmethod
    def update_section(section: str, updates: dict, path: str = None) -> dict:
        path = path or RuntimeConfig.CONFIG_PATH
        config = RuntimeConfig.load(path)
        if section not in config:
            config[section] = {}
        config[section].update(updates)
        RuntimeConfig.save(config, path)
        return config

    @staticmethod
    def get_section(section: str, path: str = None) -> dict:
        path = path or RuntimeConfig.CONFIG_PATH
        config = RuntimeConfig.load(path)
        return config.get(section, {})

    @staticmethod
    def _create_default(path: str):
        default = {
            "Project": {
                "name": "smart-classroom",
                "location": "./storage",
                "microphone": ""
            }
        }
        RuntimeConfig.save(default, path)

    @staticmethod
    def ensure_config_exists():
        path = RuntimeConfig.CONFIG_PATH
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            RuntimeConfig._create_default(path)
