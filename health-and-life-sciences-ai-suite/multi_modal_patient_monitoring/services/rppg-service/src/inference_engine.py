"""
Inference Engine - Loads and runs MTTS-CAN model.
Uses HDF5 model with custom layers.
"""

import tensorflow as tf
from tensorflow import keras
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# Custom layers for MTTS-CAN
@keras.utils.register_keras_serializable(package='Custom')
class TSM(keras.layers.Layer):
    def __init__(self, n_frame=10, fold_div=3, **kwargs):
        super(TSM, self).__init__(**kwargs)
        self.n_frame = n_frame
        self.fold_div = fold_div
    
    def call(self, inputs, *args, **kwargs):
        """Pass-through temporal shift module.

        The original serialized MTTS-CAN model may pass keyword arguments
        like `n_frame` or `fold_div` into this layer's call. Accept
        *args/**kwargs to remain compatible with the saved HDF5 config
        and safely ignore any extra call-time arguments.
        """
        return inputs
    
    def get_config(self):
        config = super(TSM, self).get_config()
        config.update({'n_frame': self.n_frame, 'fold_div': self.fold_div})
        return config


@keras.utils.register_keras_serializable(package='Custom')
class Attention_mask(keras.layers.Layer):
    def __init__(self, **kwargs):
        super(Attention_mask, self).__init__(**kwargs)
    
    def call(self, inputs, *args, **kwargs):
        if isinstance(inputs, list) and len(inputs) == 2:
            attention, features = inputs
            attention = tf.repeat(attention, features.shape[-1], axis=-1)
            return attention * features
        return inputs
    
    def get_config(self):
        return super(Attention_mask, self).get_config()


class InferenceEngine:
    """MTTS-CAN inference engine."""
    
    def __init__(self, model_path: str = "/models/rppg/mtts_can.hdf5"):
        """Initialize inference engine."""
        self.model_path = Path(model_path)
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load MTTS-CAN model."""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        
        logger.info(f"Loading model from {self.model_path}")
        
        custom_objects = {'TSM': TSM, 'Attention_mask': Attention_mask}
        self.model = keras.models.load_model(
            str(self.model_path), 
            custom_objects=custom_objects,
            compile=False
        )
        
        logger.info("✓ Model loaded successfully")
        logger.info(f"  Inputs: {len(self.model.inputs)}")
        logger.info(f"  Outputs: {len(self.model.outputs)}")
    
    def infer(self, diff_frames: np.ndarray, app_frames: np.ndarray) -> np.ndarray:
        """Run inference on preprocessed frames."""
        if diff_frames.shape != app_frames.shape:
            raise ValueError(f"Shape mismatch: {diff_frames.shape} vs {app_frames.shape}")
        
        # Model expects: [appearance, motion]
        predictions = self.model.predict([app_frames, diff_frames], verbose=0)
        
        # Handle multiple outputs
        if isinstance(predictions, list):
            logger.debug(f"Model has {len(predictions)} outputs, using first")
            predictions = predictions[0]
        
        return predictions
    
    def get_model_info(self) -> dict:
        """Get model metadata."""
        # Handle both TensorFlow 2.x shape formats
        input_shapes = []
        output_shapes = []
        
        for inp in self.model.inputs:
            if hasattr(inp.shape, 'as_list'):
                input_shapes.append(inp.shape.as_list())
            else:
                input_shapes.append(list(inp.shape))
        
        for out in self.model.outputs:
            if hasattr(out.shape, 'as_list'):
                output_shapes.append(out.shape.as_list())
            else:
                output_shapes.append(list(out.shape))
        
        return {
            'inputs': len(self.model.inputs),
            'outputs': len(self.model.outputs),
            'parameters': self.model.count_params(),
            'input_shapes': input_shapes,
            'output_shapes': output_shapes
        }
