from code import interact
import os
from termios import VLNEXT
import threading
import platform
import re
import signal
import subprocess
import time
from logger_create import create_logger
import argparse


parser = argparse.ArgumentParser(description='cpu utilization monitor')
parser.add_argument('-p', '--process_name', default="HceAI", type=str, help='process name')
args = parser.parse_args()


def logger_cpu():
    global log_dir
    sj = time.strftime('%Y-%m-%d.%H:%M:%S', time.localtime(time.time()))
    if platform.system() == "Windows":
        sj = time.strftime('%Y_%m_%d.%H.%M.%S', time.localtime(time.time()))
    logger_name = "cpu_record.log"
    sublog_dir = "cpu_record_" + sj.replace(':', '_')

    os.makedirs('cpu_monitor_logs', exist_ok=True)
    log_dir = os.path.join('cpu_monitor_logs', sublog_dir)
    logger = create_logger(logger_name, sublog_dir).crete()
    return logger


logger = logger_cpu()

def run(cmd):
    return os.system(cmd) # nosec


def pipe_run(cmd):
    return subprocess.getstatusoutput(cmd) # nosec


class TopMonitorThread(threading.Thread):
    def __init__(self, interval=10):
        super(TopMonitorThread, self).__init__()
        self.peak_cpu_rate = 0
        self.peak_ram = 0
        self.stopped = False
        self.interval = interval
    
    def reset(self):
        self.peak_cpu_rate = 0
        self.peak_ram = 0
        self.stopped = False
 
    def run(self):
        self.reset()
        print('Start top monitor thread!')

        end = time.time()
        while not self.stopped:
            if time.time() - end < self.interval:
                continue
            end = time.time()
            '''
            1625393 smarted+  20   0   17.2g   4.1g  93820 S 700.0   1.6   3817:19 HceAILLInfServe
            1625282 smarted+  20   0   17.4g   3.8g  94024 S 635.0   1.5   3944:00 HceAILLInfServe
            1621264 smarted+  20   0   17.8g   4.1g  93540 S 500.0   1.6   3593:05 HceAILLInfServe
            1621201 smarted+  20   0   17.7g   4.0g  93708 S 425.0   1.6   3693:30 HceAILLInfServe
            1621103 smarted+  20   0   17.8g   3.7g  93944 S 225.0   1.5   3636:49 HceAILLInfServe
            1625106 smarted+  20   0   17.6g   4.1g  94004 S 180.0   1.6   3638:34 HceAILLInfServe
            1621199 smarted+  20   0   17.7g   3.7g  93880 S 145.0   1.5   3697:48 HceAILLInfServe
            1625868 smarted+  20   0   16.2g   3.6g  75808 S   0.0   1.4   3626:11 HceAILLInfServe

            '''
            r = os.popen("top -n 1 -b | grep {}".format(args.process_name)) # nosec
            top_info = r.readlines()
            cur_cpu_rate = 0
            cur_ram = 0
            active_pods = 0
            for ln in top_info:
                tmp = ln.strip().split()
                cur_cpu_rate += int(float(tmp[8]))
                if 'g' in tmp[5]:
                    cur_ram += float(tmp[5].replace('g', ''))
                if float(tmp[8]) > 0:
                    active_pods += 1
            if cur_cpu_rate > self.peak_cpu_rate:
                self.peak_cpu_rate = cur_cpu_rate
            if cur_ram > self.peak_ram:
                self.peak_ram = cur_ram

            logger.info("cpu: {}% (peak_cpu: {}%)\r".format(cur_cpu_rate, self.peak_cpu_rate))
            logger.info("ram: {:.02f}g (peak_ram: {:.02f}g)\r".format(cur_ram, self.peak_ram))

        print('Stop top monitor thread!')
 
    def stop(self):
        print('Send signal to stop top monitor thread!')
        self.stopped = True

def main():
    logger.info("CPU utilization monitoring start...")

    topMonitor = TopMonitorThread()
    topMonitor.start()
    while True:
        pass
        
    topMonitor.stop()
    topMonitor.join()




if __name__ == '__main__':
    main()
