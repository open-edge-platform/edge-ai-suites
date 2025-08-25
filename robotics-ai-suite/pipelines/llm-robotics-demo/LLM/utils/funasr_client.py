# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
# -*- encoding: utf-8 -*-
import os
import time
import websockets, ssl
import asyncio

# import threading
import argparse
import json
import traceback
from multiprocessing import Process,Manager

import sys
#from ollama import Client
import logging

# voices = asyncio.Queue()
from queue import Queue
share_var = Manager().dict()
share_var['microphone_pause']=False
share_var['input_text']=""
share_var['input_text_full']=""
share_var['resume_input_text']=False
share_lock=Manager().Lock()
voices = Queue()
offline_msg_done = False


async def record_microphone(c_begin,chunk_interval,chunk_size0,chunk_size1,chunk_size2,hotword,use_itn,mode, encoder_chunk_look_back,decoder_chunk_look_back ):
    is_finished = False
    import pyaudio

    print("")
    global voices
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    chunk_size = 60 * chunk_size1 / chunk_interval
    CHUNK = int(RATE / 1000 * chunk_size)

    p = pyaudio.PyAudio()

    stream = p.open(
        format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
    )
    # hotwords
    fst_dict = {}
    hotword_msg = ""
    if hotword.strip() != "":
        if os.path.exists(hotword):
            f_scp = open(hotword)
            hot_lines = f_scp.readlines()
            for line in hot_lines:
                words = line.strip().split(" ")
                if len(words) < 2:
                    print("[ASR client] Please checkout format of hotwords")
                    continue
                try:
                    fst_dict[" ".join(words[:-1])] = int(words[-1])
                except ValueError:
                    print("[ASR client] Please checkout format of hotwords")
            hotword_msg = json.dumps(fst_dict)
        else:
            hotword_msg = hotword

    use_itn = True
    if use_itn == 0:
        use_itn = False

    message = json.dumps(
        {
            "mode": mode,
            "chunk_size": [chunk_size0,chunk_size1,chunk_size2],
            "chunk_interval": chunk_interval,
            "encoder_chunk_look_back": encoder_chunk_look_back,
            "decoder_chunk_look_back": decoder_chunk_look_back,
            "wav_name": "microphone",
            "is_speaking": True,
            "hotwords": hotword_msg,
            "itn": use_itn,
        }
    )
    # voices.put(message)
    await websocket.send(message)
    while True:
        share_lock.acquire()
        microphone_pause=share_var['microphone_pause']
        share_lock.release()
        if microphone_pause==False:
            data = stream.read(CHUNK)
            message = data
            # voices.put(message)
            await websocket.send(message)
            await asyncio.sleep(0.005)
        else:
            data = stream.read(CHUNK)

async def message(id,words_max_print):
    global websocket, voices, offline_msg_done
    text_print = ""
    text_print_2pass_online = ""
    text_print_2pass_offline = ""
    ibest_writer = None
    try:
        while True:

            meg = await websocket.recv()
            meg = json.loads(meg)
            wav_name = meg.get("wav_name", "demo")
            text = meg["text"]
            timestamp = ""
            offline_msg_done = meg.get("is_final", False)
            if "timestamp" in meg:
                timestamp = meg["timestamp"]

            if ibest_writer is not None:
                if timestamp != "":
                    text_write_line = "{}\t{}\t{}\n".format(wav_name, text, timestamp)
                else:
                    text_write_line = "{}\t{}\n".format(wav_name, text)
                ibest_writer.write(text_write_line)

            if "mode" not in meg:
                continue
            if meg["mode"] == "online":
                print("[ASR client] online mode")
                text_print += "{}".format(text)
                text_print = text_print[-words_max_print :]
                os.system("clear")
                print("\r[ASR client] pid" + str(id) + ": " + text_print)
            elif meg["mode"] == "offline":
                print("[ASR client] offline")
                if timestamp != "":
                    text_print += "{} timestamp: {}".format(text, timestamp)
                else:
                    text_print += "{}".format(text)

                # text_print = text_print[-args.words_max_print:]
                # os.system('clear')
                print("\r[ASR client] pid" + str(id) + ": " + wav_name + ": " + text_print)
                offline_msg_done = True
            else:
                print("[ASR client] mode==",meg["mode"])
                share_lock.acquire()
                if share_var['resume_input_text']==True:
                    text_print_2pass_online =""
                    text_print=""
                    text_print_2pass_offline=""
                    share_var['resume_input_text']=False
                share_lock.release()
                if meg["mode"] == "2pass-online":
                    text_print_2pass_online += "{}".format(text)
                    text_print = text_print_2pass_offline + text_print_2pass_online
                else:
                    text_print_2pass_online = ""
                    text_print = text_print_2pass_offline + "{}".format(text)
                    text_print_2pass_offline += "{}".format(text)
                text_print = text_print[-words_max_print :]

                # remove punctuation
                while   text_print.startswith("，") or  text_print.startswith(",")  or  text_print.startswith(".")  or  text_print.startswith("。")  or  text_print.startswith("？") or  text_print.startswith("?") or  text_print.startswith("!")  or  text_print.startswith("！") or  text_print.startswith(" ")  or  text_print.startswith(" "):
                        text_print = text_print[1:]

                #os.system("clear")
                print("\r[ASR client] pid" + str(id) + ": " + text_print) 
                #share_text=format(text)
                print("\r[ASR client] pid" + str(id) + ": " + format(text))
                share_lock.acquire()
                share_var['input_text']= text_print
                share_var['input_text_full']= text_print
                share_lock.release()

                # offline_msg_done=True
                #question=format(text)
                #response = client.chat(model='llama3', messages=[
                #{
                #    'role': 'user',
                #    'content': '请用中文回答,'+question,
                #}
                #])
                #print("ollama3: ",response['message']['content'])

    except Exception as e:
        print("[ASR client] Exception:", e)
        # traceback.print_exc()
        # await websocket.close()


async def ws_client(id, chunk_begin, chunk_size0,chunk_size1,chunk_size2,ssl,host,port,chunk_interval,hotword,use_itn,mode, encoder_chunk_look_back,decoder_chunk_look_back,words_max_print):
    chunk_begin = 0
    chunk_size = 1
    global websocket, voices, offline_msg_done

    for i in range(chunk_begin, chunk_begin + chunk_size):
        offline_msg_done = False
        voices = Queue()
        if ssl == 1:
            ssl_context = ssl.SSLContext()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            uri = "wss://{}:{}".format(host, port)
        else:
            uri = "ws://{}:{}".format(host, port)
            ssl_context = None

        print("[ASR client] connect to", uri)
        async with websockets.connect(
            uri, subprotocols=["binary"], ping_interval=None, ssl=ssl_context
        ) as websocket:
            task = asyncio.create_task(record_microphone(chunk_begin,chunk_interval,chunk_size0,chunk_size1,chunk_size2,hotword,use_itn,mode, encoder_chunk_look_back,decoder_chunk_look_back))
            task3 = asyncio.create_task(message(str(id) + "_" + str(i),words_max_print))  # processid+fileid
            await asyncio.gather(task, task3)
    exit(0)


def one_thread(id, chunk_begin, chunk_size0, chunk_size1, chunk_size2,ssl,host,port,chunk_interval,hotword,use_itn,mode, encoder_chunk_look_back,decoder_chunk_look_back,words_max_print):
    asyncio.get_event_loop().run_until_complete(ws_client(id, chunk_begin, chunk_size0,chunk_size1,chunk_size2,ssl,host,port,chunk_interval,
        hotword,use_itn,mode, encoder_chunk_look_back,decoder_chunk_look_back,words_max_print))
    asyncio.get_event_loop().run_forever()


import threading
import socket
import time

class ThreadClient(threading.Thread):
    def __init__(self, host='localhost', port=10095,chunk_size=[5, 10, 5],encoder_chunk_look_back=4,decoder_chunk_look_back=0,
            chunk_interval=10,hotword="",audio_in=None,audio_fs=16000,words_max_print=10000,output_dir=None,
            send_without_sleep=True,thread_num=1,ssl=0,use_itn=1,mode="2pass"#"offline“
        ):
        super().__init__()
        self.host = host
        self.port = port
        self.asr_input_flag=False
        self.asr_input_text=''
        self.asr_input_text_full=''
        self.chunk_size=chunk_size
        print("[ASR client] chunk_size=",chunk_size)
        self.encoder_chunk_look_back=encoder_chunk_look_back
        self.decoder_chunk_look_back=decoder_chunk_look_back
        self.chunk_interval=chunk_interval
        self.hotword=hotword
        self.audio_in=audio_in
        self.audio_fs=audio_fs
        self.words_max_print=words_max_print
        self.output_dir=output_dir
        self.send_without_sleep=send_without_sleep
        self.thread_num=thread_num
        self.ssl=ssl
        self.use_itn=use_itn
        self.mode=mode

        self.running = False
        self.input_running = True
        self.asr_p = Process(target=one_thread, args=(0, 0, self.chunk_size[0],self.chunk_size[1],self.chunk_size[2],self.ssl,self.host,self.port,self.chunk_interval
            ,self.hotword,self.use_itn,self.mode,self.encoder_chunk_look_back,self.decoder_chunk_look_back,self.words_max_print))
        self.asr_p.start()

    def run(self):
        self.running = True

        print("[ASR client] asr_p start")
        while self.running:
            time.sleep(1)
            share_lock.acquire()
            input_text=share_var['input_text']
            input_text_full=share_var['input_text_full']
            share_var['input_text']=""
            share_var['input_text_full']=""
            share_lock.release()
            if(input_text!=''):
                self.asr_input_text=input_text
                self.asr_input_text_full=input_text_full
                self.asr_input_flag=True

    def stop(self):
        self.running = False
        print("[ASR client] asr_p stop")

    def pause(self):
        self.input_running = False
        share_lock.acquire()
        share_var['microphone_pause']=True
        share_lock.release()

    def resume(self):
        self.input_running = True
        share_lock.acquire()
        share_var['resume_input_text']=True
        share_var['microphone_pause']=False
        share_lock.release()

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host", type=str, default="localhost", required=False, help="host ip, localhost, 0.0.0.0"
        )
    parser.add_argument("--port", type=int, default=10095, required=False, help="grpc server port")
    parser.add_argument("--chunk_size", type=str, default="5, 10, 5", help="chunk")
    parser.add_argument("--encoder_chunk_look_back", type=int, default=4, help="chunk")
    parser.add_argument("--decoder_chunk_look_back", type=int, default=0, help="chunk")
    parser.add_argument("--chunk_interval", type=int, default=10, help="chunk")
    parser.add_argument(
        "--hotword",
        type=str,
        default="",
        help="hotword file path, one hotword perline (e.g.:阿里巴巴 20)",
        )
    parser.add_argument("--audio_in", type=str, default=None, help="audio_in")
    parser.add_argument("--audio_fs", type=int, default=16000, help="audio_fs")
    parser.add_argument(
            "--send_without_sleep",
            action="store_true",
            default=True,
            help="if audio_in is set, send_without_sleep",
            )
    parser.add_argument("--thread_num", type=int, default=1, help="thread_num")
    parser.add_argument("--words_max_print", type=int, default=10000, help="chunk")
    parser.add_argument("--output_dir", type=str, default=None, help="output_dir")
    parser.add_argument("--ssl", type=int, default=1, help="1 for ssl connect, 0 for no ssl")
    parser.add_argument("--use_itn", type=int, default=1, help="1 for using itn, 0 for not itn")
    parser.add_argument("--mode", type=str, default="2pass", help="offline, online, 2pass")
    args = parser.parse_args()
    args.chunk_size = [int(x) for x in args.chunk_size.split(",")]
    print(args)

    if args.output_dir is not None:
        if not os.path.exists(args.output_dir):
            os.makedirs(args.output_dir)

    AsrClient = ThreadClient()
    AsrClient.start()

    try:
        while True:
            time.sleep(10)
            print("[ASR client] timer 30")
            share_lock.acquire()
            microphone_pause=share_var['microphone_pause']
            share_lock.release()
            if(AsrClient.asr_input_flag==True):
                print("[ASR client] input:",AsrClient.asr_input_text_full)
                AsrClient.asr_input_text=""
                AsrClient.asr_input_text_full=""
                AsrClient.asr_input_flag=False
            if microphone_pause==False :
                AsrClient.pause()
            else :
                AsrClient.resume()

    except KeyboardInterrupt:
        AsrClient.stop()
        print("[ASR client] Client stopped.")
