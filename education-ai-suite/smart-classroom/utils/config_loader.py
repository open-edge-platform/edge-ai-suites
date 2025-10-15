import yaml
from types import SimpleNamespace
import os
import logging

logger = logging.getLogger(__name__)

def _dict_to_namespace(d):
    if isinstance(d, dict):
        return SimpleNamespace(**{k: _dict_to_namespace(v) for k, v in d.items()})
    return d

def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return _dict_to_namespace(data)

# Load once and expose
config = load_config()

logger.info("\n📦 CONFIGURATION START\n" + "-" * 40)
logger.info(yaml.dump(vars(config), sort_keys=False))
logger.info("\n" + "-" * 40 + "\n📦 CONFIGURATION END\n")
