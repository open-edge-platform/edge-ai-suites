import cv2
import numpy as np
import openvino.runtime as ov

# Load OpenVINO Model
core = ov.Core()
model = core.read_model(model="colorcls2.xml")  # Adjust path if needed
compiled_model = core.compile_model(model, "CPU")  # Use "GPU" if running on GPU

# Get Input Information
input_layer = compiled_model.input(0)
input_shape = input_layer.shape  # (batch, channels, height, width)

# Load and Preprocess Image
image_path = "test.jpg"  # Change to your image path
image = cv2.imread(image_path)
image = cv2.resize(image, (input_shape[2], input_shape[3]))  # Resize to model's input size
image = image.transpose(2, 0, 1)  # Convert HWC to CHW
image = image[np.newaxis, :]  # Add batch dimension
image = image.astype(np.float32)  # Adjust dtype if needed

# Run Inference
output = compiled_model([image])

# Print Output
print("Model Output:", output)

