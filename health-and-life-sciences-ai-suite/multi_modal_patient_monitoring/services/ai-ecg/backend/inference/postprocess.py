import numpy as np
import scipy.stats as sst

def postprocess(output, int_to_class):
    preds = np.argmax(output, axis=2).squeeze()
    final = sst.mode(preds, keepdims=True).mode[0]
    return int_to_class[int(final)], preds.tolist()
