import psutil
import shutil
import pythoncom
import wmi 
import cpuinfo
import math
from utils.config_loader import config  


def get_intel_igpu_wmi():
    try:
        pythoncom.CoInitialize()
        w = wmi.WMI()
        igpus = []
        for gpu in w.Win32_VideoController():
            if "intel" in gpu.Name.lower():
                igpus.append(gpu.Name)
        return ", ".join(igpus) if igpus else "Intel Graphics"
    except Exception as e:
        return f"Intel Graphics"
    finally:
        pythoncom.CoUninitialize()


def detect_intel_npu():
    try:
        pythoncom.CoInitialize()
        c = wmi.WMI()
        for device in c.Win32_PnPEntity():
            if device.Name and "Intel" in device.Name and "AI Boost" in device.Name:
                return device.Name
        return "Intel AI Boost"
    except Exception as e:
        return f"Intel AI Boost"
    finally:
        pythoncom.CoUninitialize()

def format_size_gb(size_bytes: int, is_storage: bool = False) -> str:
    gb = size_bytes / (1024 ** 3)
    if is_storage:
        tb = gb / 931 
        return f"{round(tb)} TB" if abs(tb - round(tb)) < 0.05 else f"{tb:.2f} TB"
    else:
        return f"{math.ceil(gb)} GB"


def get_platform_and_model_info():
    info = {}
    
    #Processor
    try:
       info['Processor'] = cpuinfo.get_cpu_info()['brand_raw']
    except Exception :
        info['Processor'] = f"Intel Processor"

    # Memory
    try:
        mem = psutil.virtual_memory()
        info['Memory'] = format_size_gb(mem.total)
    except Exception:
        info['Memory']="--"
    
    #storage
    try:
        disk = shutil.disk_usage("/")
        info['Storage'] = format_size_gb(disk.total, is_storage=True)
    except Exception:
        info['Storage']='--'
    
    # GPU/NPU Info
    info['iGPU'] = get_intel_igpu_wmi()
    info['NPU'] = detect_intel_npu()

    # Model Info 
    try:
        info['asr_model'] = f"{config.models.asr.provider}/{config.models.asr.name}"
    except Exception:
        info['asr_model'] = "--"

    try:
        info['summarizer_model'] = f"{config.models.summarizer.provider}/{config.models.summarizer.name}"
    except Exception:
        info['summarizer_model'] = "--"

    return info



