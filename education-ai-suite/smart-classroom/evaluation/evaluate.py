import argparse
import requests
import os
import json
import time
import sys
import psutil
from pathlib import Path
from typing import Optional
from pydub import AudioSegment
import yaml

# Ensure the parent directory is in sys.path for direct script execution
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from components.asr.funasr.paraformer import Paraformer
from components.asr.openai.whisper import Whisper
from components.llm.ipex.summarizer import Summarizer as IpexSummarizer
from components.llm.openvino.summarizer import Summarizer as OvSummarizer

from utils.ensure_model import ensure_model
from utils.config_loader import config
from monitoring.monitor import start_monitoring, stop_monitoring, get_metrics

from evaluation.template import templ_sum_en, templ_sum_zh, templ_score_en, templ_score_zh, sys_prompt_score_en, sys_prompt_score_zh


JWT_token = "{your JWT token}"

def set_process_affinity_to_cores(core_indices):
    """
    Set the current process affinity to specific CPU cores.

    Args:
        core_indices (list of int): List of CPU core indices to bind the process to.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        # Get the current process
        process = psutil.Process(os.getpid())

        # Set the process affinity
        process.cpu_affinity(core_indices)

        print("Successfully bound the process to CPU cores:", core_indices)
        return True
    except Exception as e:
        print("Failed to bind the process. Error:", e)
        return False

def parse_core_indices(core_str):
    """Parse a comma-separated string of core indices into a list of ints."""
    try:
        return [int(x) for x in core_str.split(",") if x.strip() != ""]
    except Exception as e:
        print(f"Failed to parse cpu_cores: {e}")
        return []

def get_message(input, language):
    system_prompt = config.models.summarizer.system_prompt.en if language=="en" else config.models.summarizer.system_prompt.zh
    return [
            {"role": "system", "content": f"{system_prompt}"},
            {"role": "user", "content": f"{input}"}
        ]

def get_audio_length_pydub(wav_file: str) -> float:
    """Return the length of the audio file in seconds."""
    audio = AudioSegment.from_file(wav_file)
    return len(audio) / 1000.0  # Convert ms to seconds

def transcribe(model_name: str, local_audio_path: str) -> str:
    """Transcribe audio using ASR model."""
    if "paraformer" in model_name:
        model = Paraformer(model_name, device="cpu")
    elif "whisper" in model_name:
        model = Whisper(model_name, device="cpu")
    else:
        print("Unknown transcription model")
        return None
    
    start = time.time()
    result = model.transcribe(local_audio_path, 0.0)
    end = time.time()
    return result, end-start

def summarize(model_name: str, prompt, provider, device, temperature) -> str:
    """Generate a summary using the Summarizer model."""
    if provider == "openvino":
        model = OvSummarizer(model_name, device, temperature=temperature)
    elif provider == "ipex":
        model = IpexSummarizer(model_name, device.lower(), temperature=temperature)
    else:
        print("Unknown summarization model")
        return None
    prompt = model.tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True)
    result = ""
    num_tokens = 0
    start = time.time()
    for response in model.generate(prompt):
        result += response
        num_tokens += 1
    end = time.time()
    return result, num_tokens, end-start

def evaluate(eval_model: str, prompt: str, request_url: str, language) -> str:
    """Evaluate the summary using an external API."""
    system_prompt = sys_prompt_score_en if language=="en" else sys_prompt_score_zh
    payload = {
        "model": eval_model,
        "messages": [
            {"role": "system", "content": f"{system_prompt}"},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "temperature": 0,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {JWT_token}",
    }
    try:
        response = requests.post(request_url, json=payload, headers=headers, verify=False)
        response.raise_for_status()
        completion = response.json()
        result = completion['choices'][0]['message']['content']
        return result
    except Exception as e:
        print(f"Evaluation request failed: {e}")
        return ""

def main():
    parser = argparse.ArgumentParser(description="Evaluate transcript summary")
    parser.add_argument("--asr_model", help="ASR model")
    parser.add_argument("--audio_file", help="Audio file", required=True)
    parser.add_argument("--sum_model", help="Summarizer model")
    parser.add_argument("--sum_provider", help="Summarizer model provider, ov or ipex")
    parser.add_argument("--request_url", help="Request URL for API", default="https://deepseek.intel.com/api/chat/completions")
    parser.add_argument("--eval_model", help="Evaluation model", default="emr./models/DeepSeek-R1-Channel-INT8")
    parser.add_argument("--language", help="Language for the prompt, en or zh", default="en")
    parser.add_argument("--result_dir", help="Directory to save results")
    parser.add_argument("--sum_result_file", help="File to save summary result", default="summary.txt")
    parser.add_argument("--transcript_file", help="File to save transcript result", default="transcript.txt")
    parser.add_argument("--eval_report_file", help="File to save evaluation report", default="eval_report.txt")
    parser.add_argument("--skip_transcribe", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--skip_summarize", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--skip_evaluate", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--monitor_asr", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--metrics_logs", help="Directory to save monitoring logs", default="./logs")
    parser.add_argument("--cpu_cores", type=str, default="", help="Comma-separated list of CPU core indices to bind (leave empty to not set affinity)")
    args = parser.parse_args()

    # Get asr_model from args or config
    asr_model = args.asr_model
    if not asr_model:
        asr_model = config.models.asr.name
        if not asr_model:
            print("asr_model must be specified via --asr_model or in config.yaml")
            sys.exit(1)

    # Get sum_model from args or config
    sum_model = args.sum_model
    if not sum_model:
        sum_model = config.models.summarizer.name
        if not sum_model:
            print("sum_model must be specified via --sum_model or in config.yaml")
            sys.exit(1)

    # Get sum_provider from args or config
    sum_provider = args.sum_provider
    if not sum_provider:
        sum_provider = config.models.summarizer.provider
        if not sum_provider:
            print("sum_provider must be specified via --sum_provider or in config.yaml (provider=openvino/ipex)")
            sys.exit(1)

    if sum_provider.lower() not in ["openvino", "ipex"]:
        print("sum_provider must be either openvino or ipex")
        exit(0)

    if sum_provider.lower()  == "openvino":
        ensure_model()

    language = args.language
    if not language:
        language = config.models.summarizer.language
        if not language:
            print("language must be specified via --language or in config.yaml")
            sys.exit(1)

    if language == "en":
        sum_prompt = templ_sum_en
        score_prompt = templ_score_en
    elif language == "zh":
        sum_prompt = templ_sum_zh
        score_prompt = templ_score_zh
    else:
        print("Unknown language option")
        exit(0)

    metrics_logs = args.metrics_logs
    monitor_asr = args.monitor_asr

    # Clear files in metrics_logs before running
    if metrics_logs:
        logs_path = Path(metrics_logs)
        if logs_path.exists() and logs_path.is_dir():
            for file in logs_path.iterdir():
                if file.is_file():
                    try:
                        file.unlink()
                    except Exception as e:
                        print(f"Failed to remove log file {file}: {e}")

    if args.cpu_cores.strip():
        core_indices = parse_core_indices(args.cpu_cores)
        if core_indices:
            set_process_affinity_to_cores(core_indices)
        else:
            print("No valid CPU cores specified, skipping affinity setting.")

    request_url = args.request_url
    eval_model = args.eval_model

    sum_result_file = args.sum_result_file
    transcript_file = args.transcript_file
    eval_report_file = args.eval_report_file
    
    skip_transcribe = args.skip_transcribe
    skip_summarize = args.skip_summarize
    skip_evaluate = args.skip_evaluate

    temperature = config.models.summarizer.temperature

    audio_path = Path(args.audio_file)
    if args.result_dir is None:
        result_dir = audio_path.with_suffix('')
    else:
        result_dir = Path(args.result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)

    e_start = e_end = 0

    # transcribe
    if not skip_transcribe:
        if monitor_asr:
            start_monitoring(metrics_logs)
            time.sleep(1)  # Give monitor a moment to start
        transcript, asr_time_elapsed = transcribe(asr_model, str(audio_path))
        if monitor_asr:
            stop_monitoring()
            time.sleep(1)  # Ensure logs are flushed
        try:
            with open(result_dir / transcript_file, 'w', encoding='utf-8') as output_file:
                output_file.write(transcript)
            print(f"transcript saved to {result_dir / transcript_file}")
        except Exception as e:
            print(f"Failed to save transcript: {e}")
            sys.exit(1)

    # summarize
    if not skip_summarize:
        if skip_transcribe:
            transcript_path = result_dir / transcript_file
            if not transcript_path.exists():
                print(f"transcript_file not found at {transcript_path}, please make sure transcript exists before running skip_transcribe")
                sys.exit(1)
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    transcript = f.read()
            except Exception as e:
                print(f"Failed to read transcript: {e}")
                sys.exit(1)
        sum_prompt_filled = sum_prompt.format(transcript=transcript)
        device = config.models.summarizer.device if config.models.summarizer.device else "GPU"
        summary, num_tokens, sum_gen_time = summarize(sum_model, get_message(sum_prompt_filled, language), sum_provider, device, temperature)
        try:
            with open(result_dir / sum_result_file, 'w', encoding='utf-8') as output_file:
                output_file.write(summary)
            print(f"summary saved to {result_dir / sum_result_file}")
        except Exception as e:
            print(f"Failed to save summary: {e}")
            sys.exit(1)

    # evaluate
    if not skip_evaluate:
        if skip_transcribe:
            transcript_path = result_dir / transcript_file
            if not transcript_path.exists():
                print(f"transcript_file not found at {transcript_path}, please make sure transcript exists before running skip_transcribe")
                sys.exit(1)
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    transcript = f.read()
            except Exception as e:
                print(f"Failed to read transcript: {e}")
                sys.exit(1)
        if skip_summarize:
            summary_path = result_dir / sum_result_file
            if not summary_path.exists():
                print(f"sum_result_file not found at {summary_path}, please make sure summary exists before running skip_summarize")
                sys.exit(1)
            try:
                with open(summary_path, 'r', encoding='utf-8') as f:
                    summary = f.read()
            except Exception as e:
                print(f"Failed to read summary: {e}")
                sys.exit(1)
        score_prompt_filled = score_prompt.format(summary=summary, transcript=transcript)
        e_start = time.time()
        result = evaluate(eval_model, score_prompt_filled, request_url, language)
        e_end = time.time()
        try:
            with open(result_dir / eval_report_file, 'w', encoding='utf-8') as output_file:
                output_file.write(result)
            print(f"Evaluation report saved to {result_dir / eval_report_file}")
        except Exception as e:
            print(f"Failed to save evaluation report: {e}")
            sys.exit(1)

    try:
        total_audio_length = get_audio_length_pydub(str(audio_path))
        print(f"Audio length: {total_audio_length:.2f} seconds")
    except Exception as e:
        print(f"Failed to get audio length: {e}")

    if not skip_transcribe:
        print(f"Transcription time: {asr_time_elapsed:.2f} seconds")
        if monitor_asr:
            # Read CPU utilization metrics
            metrics = get_metrics(metrics_logs)
            cpu_data = metrics.get("cpu_utilization", [])
            cpu_utils = [row[1] for row in cpu_data if len(row) > 1]
            if cpu_utils:
                avg_cpu = sum(cpu_utils) / len(cpu_utils)
            else:
                avg_cpu = 0.0
            
            if total_audio_length and total_audio_length > 0:
                rtf = asr_time_elapsed / total_audio_length
                print(f"RTF (Real Time Factor): {rtf:.3f}")
            print(f"CPU average utilization: {avg_cpu:.2f}%")
    if not skip_summarize:
        print(f"Summarization time: {sum_gen_time:.2f} seconds")
        print(f"Summarization output token number: {num_tokens}")
    if not skip_evaluate:
        print(f"Evaluation time: {e_end-e_start:.2f} seconds")

if __name__ == "__main__":
    main()
