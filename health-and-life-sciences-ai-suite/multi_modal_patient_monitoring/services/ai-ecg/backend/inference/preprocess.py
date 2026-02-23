import util

class ECGPreprocessor:
    def __init__(self):
        self.preproc = util.load(".")
        self.valid_lengths = [17920, 8960]  # try larger first

    def process(self, ecg):
        """
        Split ECG into valid windows (8960 / 17920)
        Returns list of (tensor, window_length)
        """
        results = []
        ecg_len = len(ecg)

        for win_len in self.valid_lengths:
            if ecg_len >= win_len:
                step = win_len
                for i in range(0, ecg_len - win_len + 1, step):
                    window = ecg[i:i + win_len]
                    tensor = self.preproc.process_x([window])
                    results.append((tensor, win_len))
                return results

        raise RuntimeError("ECG too short for supported models")

    @property
    def int_to_class(self):
        return self.preproc.int_to_class
