import numpy as np
from gstgva import VideoFrame

COLOR_LABELS = ["black", "silver"]

class Process:
    def process_frame(self, frame: VideoFrame):
        for region in frame.regions():
            for tensor in region.tensors():
                if tensor.name() in ["classification_layer_name:output"]:
                    try:
                        logits = np.array([float(x) for x in tensor.label().split(",")])
                        color_logits = logits[:2]  # color
                        color = COLOR_LABELS[np.argmax(color_logits)]
                        formatted_label =  f'{color}'
                        tensor.set_name("color")
                        tensor.set_label(formatted_label)
                    except Exception as e:
                        pass
        return True

