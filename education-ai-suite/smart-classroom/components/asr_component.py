from components.base_component import PipelineComponent
import os
import time
import torch
from utils.config_loader import config
from utils.storage_manager import StorageManager
from utils.runtime_config_loader import RuntimeConfig
from components.asr.openai.whisper import Whisper as OA_Whisper
from components.asr.diarization.pyannote_diarizer import PyannoteDiarizer
from components.asr.openvino.whisper import Whisper as OV_Whisper
from components.asr.funasr.paraformer import Paraformer
import logging
logger = logging.getLogger(__name__)

ENABLE_DIARIZATION = config.models.asr.diarization
DELETE_CHUNK_AFTER_USE =  config.pipeline.delete_chunks_after_use
threads_limit = config.models.asr.threads_limit
THREADS_LIMIT = threads_limit if threads_limit and threads_limit > 0 else None


# ===== Speaker label localization map =====

SPEAKER_LABEL_MAP = {
    "en": {"teacher": "TEACHER", "student": "STUDENT", "speaker": "SPEAKER"},
    "zh": {"teacher": "教师", "student": "学生", "speaker": "说话人"},
}

def get_speaker_labels(lang_code: str):
    if not lang_code:
        return SPEAKER_LABEL_MAP["en"]
    lang = lang_code.lower().split("-")[0]
    return SPEAKER_LABEL_MAP.get(lang, SPEAKER_LABEL_MAP["en"])

SUMMARIZER_LANG = getattr(config.models.summarizer, "language", "en")
LABELS = get_speaker_labels(SUMMARIZER_LANG)

LABEL_TEACHER = LABELS["teacher"]
LABEL_STUDENT = LABELS["student"]
LABEL_SPEAKER = LABELS["speaker"]

class ASRComponent(PipelineComponent):

    _model = None
    _config = None

    def __init__(self, session_id, provider="openai", model_name="whisper-small", device="CPU", temperature=0.0):

        self.session_id = session_id
        self.temperature = temperature
        self.provider = provider
        self.model_name = model_name
        self.speaker_text_len = {}   # accumulate across chunks
        self.threads_limit = THREADS_LIMIT
        self.enable_diarization = ENABLE_DIARIZATION
        self.all_segments = []
        provider, model_name = provider.lower(), model_name.lower()
        model_config_key = (provider, model_name, device)

        # Reload only if config changed
        if ASRComponent._model is None or ASRComponent._config != model_config_key:
            if provider == "openai" and "whisper" in model_name:
                ASRComponent._model = OA_Whisper(model_name, device, None)
            elif provider == "openvino" and "whisper" in model_name:
                ASRComponent._model = OV_Whisper(model_name, device, None,self.threads_limit)
            elif provider == "funasr" and "paraformer" in model_name:
                ASRComponent._model = Paraformer(model_name, device.lower(), None)
            else:
                raise ValueError(f"Unsupported ASR provider/model: {provider}/{model_name}")
            ASRComponent._config = model_config_key

        self.asr = ASRComponent._model
        
        self.pyannote_diarizer = None
        if self.enable_diarization:
            self.pyannote_diarizer = PyannoteDiarizer(
                hf_token=config.models.asr.hf_token
            )

    def process(self, input_generator):

        project_config = RuntimeConfig.get_section("Project")
        project_path = os.path.join(project_config.get("location"), project_config.get("name"), self.session_id)

        transcript_path = os.path.join(project_path, "transcription.txt")
        StorageManager.save(transcript_path, "", append=False)

        start_time = time.perf_counter()
        default_torch_threads = None

        try:
            if self.provider in ["openai", "funasr"] and self.threads_limit:
                default_torch_threads = torch.get_num_threads()
                torch.set_num_threads(self.threads_limit)

            for chunk_data in input_generator:
                chunk_path = chunk_data["chunk_path"]
                transcription = self.asr.transcribe(chunk_path, temperature=self.temperature)

                ui_segments = []
                transcribed_lines = []

                if self.enable_diarization and transcription["segments"]:

                    speaker_turns = self.pyannote_diarizer.diarize(chunk_path)

                    for sent in transcription["segments"]:
                        if not sent["text"].strip():
                            continue

                        mid = (sent["start"] + sent["end"]) / 2.0

                        speaker = LABEL_SPEAKER
                        for turn in speaker_turns:
                            if turn["start"] <= mid <= turn["end"]:
                                raw_spk = turn["speaker"]
                                if raw_spk.startswith("SPEAKER_"):
                                    speaker = raw_spk.replace("SPEAKER_", f"{LABEL_SPEAKER}_")
                                break

                        text = sent["text"].strip()

                        # Global chunk offset from chunker
                        chunk_offset = float(chunk_data.get("start_time", 0.0))

                        # Convert local Whisper timestamps → global timestamps
                        start = float(sent["start"]) + chunk_offset
                        end   = float(sent["end"])   + chunk_offset


                        ui_segments.append({
                            "speaker": speaker,
                            "text": text,
                            "start": start,
                            "end": end
                        })

                        if speaker != LABEL_SPEAKER:
                            self.speaker_text_len[speaker] = (
                                self.speaker_text_len.get(speaker, 0) + len(text)
                            )

                        transcribed_lines.append(f"{speaker}: {text}")

                    transcribed_text = "\n".join(transcribed_lines) + "\n"

                else:
                    transcribed_text = transcription["text"]
                    ui_segments = [{
                        "speaker": None,
                        "text": transcribed_text,
                        "start": 0.0,
                        "end": 0.0
                    }]

                self.all_segments.extend(ui_segments)
                if os.path.exists(chunk_path) and DELETE_CHUNK_AFTER_USE:
                    os.remove(chunk_path)

                StorageManager.save_async(transcript_path, transcribed_text, append=True)

                yield {
                    **chunk_data,
                    "text": transcribed_text,
                    "segments": ui_segments
                }

            # ========== FINALIZATION ==========
            teacher_speaker = None
            if self.speaker_text_len:
                teacher_speaker = max(self.speaker_text_len, key=self.speaker_text_len.get)

            if teacher_speaker:

                raw_segments = []

                teacher_lines_with_time = []
                full_updated_lines = []

                for seg in self.all_segments:
                    spk = seg["speaker"]
                    text = seg["text"].strip()
                    start = round(seg["start"], 2)
                    end = round(seg["end"], 2)

                    # Identify teacher
                    if spk == teacher_speaker:
                        speaker_label = LABEL_TEACHER
                        line = f"[{start} - {end}] {speaker_label}: {text}"
                        teacher_lines_with_time.append(line)
                    else:
                        # relabel other speakers
                        if spk.startswith(f"{LABEL_SPEAKER}_"):
                            speaker_label = spk.replace(f"{LABEL_SPEAKER}_", f"{LABEL_STUDENT}_")
                        elif spk == LABEL_SPEAKER:
                            speaker_label = LABEL_STUDENT
                        else:
                            speaker_label = spk

                        line = f"[{start} - {end}] {speaker_label}: {text}"

                    full_updated_lines.append(line)

                # Save full timestamped transcript
                StorageManager.save(
                    transcript_path,
                    "\n".join(full_updated_lines) + "\n",
                    append=False
                )

                # Save teacher-only timestamped transcript
                StorageManager.save(
                    os.path.join(project_path, "teacher_transcription.txt"),
                    "\n".join(teacher_lines_with_time) + "\n",
                    append=False
                )

            yield {
                "event": "final",
                "teacher_speaker": teacher_speaker,
                "speaker_text_stats": self.speaker_text_len
            }

        finally:
            if default_torch_threads is not None:
                torch.set_num_threads(default_torch_threads)

            end_time = time.perf_counter()
            transcription_time = end_time - start_time

            StorageManager.update_csv(
                path=os.path.join(project_path, "performance_metrics.csv"),
                new_data={
                    "configuration.asr_model": f"{self.provider}/{self.model_name}",
                    "performance.transcription_time": round(transcription_time, 4)
                }
            )

            logger.info(f"Transcription Complete: {self.session_id}")


                
