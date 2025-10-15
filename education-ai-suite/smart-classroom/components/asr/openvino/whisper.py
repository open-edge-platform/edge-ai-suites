from components.asr.base_asr import BaseASR
import soundfile as sf
import librosa, time
import openvino_genai as ov_genai
import logging
from utils.ensure_model import get_asr_model_path

logger = logging.getLogger(__name__)  
 
class Whisper(BaseASR):
   def __init__(self, model_name="whisper-small", device="CPU", revision=None,threads_limit=None):
        logger.info(f"Loading Model: model name={model_name}, device={device}")
        self.model_path = get_asr_model_path()
        config = {"INFERENCE_NUM_THREADS": str(threads_limit)} if threads_limit and threads_limit > 0 else {}
        self.model = ov_genai.WhisperPipeline( self.model_path, device=device,config=config)
 
   def transcribe(self, audio_path: str, temperature: float) -> str:
          audio, sr = self._load_wav_mono_16k(audio_path)
          result = self.model.generate(audio)
          return getattr(result, "text", str(result))
   
   def _load_wav_mono_16k(self, path):
    # load with soundfile and resample to 16 kHz if necessary
    audio, sr = sf.read(path, dtype='float32')
    if sr != 16000:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
        sr = 16000
    # if stereo, average channels
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return audio, sr