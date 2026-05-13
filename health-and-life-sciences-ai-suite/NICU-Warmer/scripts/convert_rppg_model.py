"""Convert MTTS-CAN HDF5 model to OpenVINO IR format."""
import tensorflow as tf
from tensorflow import keras
from tensorflow.python.keras import backend as K


class Attention_mask(keras.layers.Layer):
    def call(self, x):
        xsum = K.sum(x, axis=1, keepdims=True)
        xsum = K.sum(xsum, axis=2, keepdims=True)
        xshape = K.int_shape(x)
        return x / xsum * xshape[1] * xshape[2] * 0.5

    def get_config(self):
        return super().get_config()


class TSM(keras.layers.Layer):
    def call(self, x, n_frame=10, fold_div=3):
        nt, h, w, c = x.shape
        x = K.reshape(x, (-1, n_frame, h, w, c))
        fold = c // fold_div
        last_fold = c - (fold_div - 1) * fold
        out1, out2, out3 = tf.split(x, [fold, fold, last_fold], axis=-1)
        padding_1 = tf.zeros_like(out1)
        padding_1 = padding_1[:, -1, :, :, :]
        padding_1 = tf.expand_dims(padding_1, 1)
        _, out1 = tf.split(out1, [1, n_frame - 1], axis=1)
        out1 = tf.concat([out1, padding_1], axis=1)
        padding_2 = tf.zeros_like(out2)
        padding_2 = padding_2[:, 0, :, :, :]
        padding_2 = tf.expand_dims(padding_2, 1)
        out2, _ = tf.split(out2, [n_frame - 1, 1], axis=1)
        out2 = tf.concat([padding_2, out2], axis=1)
        out = tf.concat([out1, out2, out3], axis=-1)
        out = K.reshape(out, (-1, h, w, c))
        return out

    def get_config(self):
        return super().get_config()


custom_objects = {"TSM": TSM, "Attention_mask": Attention_mask}

with keras.utils.custom_object_scope(custom_objects):
    model = keras.models.load_model("/tmp/mtts_can.hdf5")
    print("Loaded:", model.name)
    print("Inputs:", [(i.name, i.shape) for i in model.inputs])
    print("Outputs:", [(o.name, o.shape) for o in model.outputs])

import openvino as ov
ov_model = ov.convert_model(model)
ov.save_model(ov_model, "/tmp/mtts_can.xml")
import os
print("xml:", os.path.getsize("/tmp/mtts_can.xml"))
print("bin:", os.path.getsize("/tmp/mtts_can.bin"))
print("SUCCESS")
