import queue
import openvino_genai as ov_genai

class YieldingTextStreamer(ov_genai.StreamerBase):
    def __init__(self, tokenizer, skip_special_tokens=True):
        super().__init__()
        self.tokenizer = tokenizer
        self.skip_special_tokens = skip_special_tokens
        self._queue = queue.Queue()
        self.total_tokens = 0
        self.generation_start_time = None
        self._token_cache = []
        self._print_len = 0

    def get_stop_flag(self):
        """Check whether generation should be stopped."""
        return ov_genai.StreamingStatus.RUNNING

    def write(self, token) -> ov_genai.StreamingStatus:
        """Process token(s) and manage the decoding buffer."""
        # Handle both single token and list of tokens
        if isinstance(token, list):
            self._token_cache.extend(token)
            self.total_tokens += len(token)
        else:
            self._token_cache.append(token)
            self.total_tokens += 1

        text = self.tokenizer.decode(self._token_cache, skip_special_tokens=self.skip_special_tokens)
        new_text = text[self._print_len:]
        if not new_text:
            return ov_genai.StreamingStatus.RUNNING

        if self._is_safe_to_emit(new_text):
            self._queue.put(new_text)
            self._print_len = len(text)
        else:
            # Get the last token for boundary detection
            last_token = token if not isinstance(token, list) else token[-1]
            last_token_text = self.tokenizer.decode([last_token], skip_special_tokens=True)
            if last_token_text.startswith(" "):
                prev_chunk = text[self._print_len : len(text) - len(last_token_text)]
                if prev_chunk:
                    self._queue.put(prev_chunk)
                    self._print_len += len(prev_chunk)
        
        return self.get_stop_flag()

    def end(self):
        if self._token_cache:
            text = self.tokenizer.decode(self._token_cache, skip_special_tokens=self.skip_special_tokens)
            remaining = text[self._print_len:]
            if remaining:
                self._queue.put(remaining)
        self._queue.put(None)
        self._token_cache.clear()
        self._print_len = 0

    def __iter__(self):
        while True:
            token = self._queue.get()
            if token is None:
                break
            yield token
        
    def _is_safe_to_emit(self, text: str) -> bool:
        last_char = text[-1]
        cp = ord(last_char)
        return self._is_cjk(cp) or last_char.isspace() or last_char == "\n"

    @staticmethod
    def _is_cjk(cp: int) -> bool:
        return (
            0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0x20000 <= cp <= 0x2A6DF or
            0x2A700 <= cp <= 0x2B73F or 0x2B740 <= cp <= 0x2B81F or 0x2B820 <= cp <= 0x2CEAF or
            0xF900 <= cp <= 0xFAFF or 0x2F800 <= cp <= 0x2FA1F
        )
