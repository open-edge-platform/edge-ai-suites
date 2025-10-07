## Prepare QnA service API keys

1. Login https://deepseek.intel.com/
2. Go to Personal Settings - Account
3. Show and get API keys - JWT Token
4. Replace `{your JWT token}` in `evaluate.py`


## Evaluate
**Note**: ASR accuracy is not measured in the script below, summarization quality depends on both ASR quality and LLM prompt design/model inference.


### Evaluate summarization quality
```
cd education-ai-suite/smart-classroom
# read models from config.yaml
python .\evaluation\evaluate.py --audio_file <audio_file>

# OR specify via command line options
python .\evaluation\evaluate.py --audio_file <audio_file> --asr_model <asr_model_name> --sum_model <sum_model_name> --sum_provider <openvino/ipex> --language <en/zh>
```

Output log should be like:
```
transcript saved to <some_dir>\transcript.txt
summary saved to <some_dir>\summary.txt
Evaluation report saved to <some_dir>\eval_report.txt
Audio length: xxxx seconds
Transcription time: xxx seconds
Summarization time: xxx seconds
Summarization output token number: xxx
Evaluation time: xxx seconds
```

Go to the evaluation report directory, check the scores at the end of report:
```json
{
  "score_completeness": xx,
  "score_reliability": xx,
  "total_score": xx
}
```

The script does transcription -> summarization -> summary evaluation. To skip steps, for example skip transcription and do summarization and evaluation, try
```
python .\evaluation\evaluate.py --audio_file <audio_file> --skip_transcribe
```


### Evaluate ASR performance
Skip summarization and evaluation to save time. Bind process to certain CPU core to limit CPU utilization.
```
cd education-ai-suite/smart-classroom
# read models from config.yaml
python .\evaluation\evaluate.py --audio_file <audio_file> --monitor_asr --skip_summarize --skip_evaluate --cpu_cores 5,6
```

Output log should be like:
```
Audio length: xxxx seconds
Transcription time: xxx seconds
RTF (Real Time Factor): 0.xxx
CPU average utilization: x%
```