# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import torch
import torch.nn.functional as F
import os

def load_and_compare_tensors(file_path_a: str, file_path_b: str, tolerance: float = 1e-4):
    """
    Loads two PyTorch tensors and calculates the Root Mean Square Error (RMSE) 
    between them to determine similarity.
    """
    # 1. Check for file existence and load the tensors
    if not (os.path.exists(file_path_a) and os.path.exists(file_path_b)):
        print("ERROR: One or both tensor files were not found.")
        return None, False
    print("File A:", file_path_a)
    print("File B:", file_path_b)
    try:
        tensor_a = torch.load(file_path_a, map_location='cpu')
        tensor_b = torch.load(file_path_b, map_location='cpu')
    except Exception as e:
        print(f"ERROR: Failed to load tensors. Details: {e}")
        return None, False

    print(f"Loaded Tensor A (Shape: {tensor_a.shape}) and Tensor B (Shape: {tensor_b.shape})")

    # 2. Check for shape compatibility
    if tensor_a.shape != tensor_b.shape:
        print("ERROR: Tensors have different shapes and cannot be compared.")
        return None, False

    # 3. Calculate RMSE
    # F.mse_loss calculates the Mean Squared Error (MSE)
    mse = F.mse_loss(tensor_a, tensor_b, reduction='mean')
    
    # Take the square root of MSE to get RMSE
    rmse = torch.sqrt(mse)
    rmse_value = rmse.item()
    
    # 4. Determine similarity based on tolerance
    is_similar = rmse_value < tolerance

    print("\n--- Comparison Results ---")
    print(f"Mean Squared Error (MSE): {mse.item():.8f}")

    return rmse_value, is_similar

# --- Execution ---

file1 = 'openvino_pi05_INT8_output.pt'
file2 = 'lerobot_pytorch_pi05_output.pt'
# ov_ir_fp16_x_t.pt
# Set a low tolerance (e.g., 1e-4) to determine if the floating-point tensors are nearly identical
custom_tolerance = 1e-4

# You will need to ensure these two files exist in the same directory as your script
# (or provide their full paths).
rmse, same = load_and_compare_tensors(file1, file2, tolerance=custom_tolerance)
