# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import torch
from lerobot.policies.pi05.modeling_pi05 import PI05Policy
import os

# -----------------------------
# Load PyTorch policy
# -----------------------------
print("LOADING MODEL")
policy = PI05Policy.from_pretrained("lerobot/pi05_base")
device = torch.device("cpu")  # force CPU to avoid mixed precision issues
policy.to(device)
policy.eval()
print("Done loading policy.")

# -----------------------------
# Define inference wrapper
# -----------------------------
class Pi0InferenceWrapper(torch.nn.Module):
    def __init__(self, pi0_policy):
        super().__init__()
        print("In here")
        self.model = pi0_policy.model

    def forward(self, images, img_masks, lang_tokens, lang_masks, state, actions):
        print("In forward")
        # Ensure all internal constants are float32
        images = images.float()
        state = state.float()
        actions = actions.float()
        
        # Convert masks to float if used in computations
        img_masks = img_masks
        lang_masks = lang_masks
        out = self.model(images, img_masks, lang_tokens, lang_masks, state, actions)

        if torch.is_complex(out):
            out = out.real
        
        torch.save(out, "validation/lerobot_pytorch_pi05_output.pt")
        return out

inference_model = Pi0InferenceWrapper(policy)
inference_model.to(device)
inference_model.eval()

# -----------------------------
# Cast parameters and buffers to float32
# -----------------------------
for name, buf in inference_model.named_buffers():
    if buf.dtype == torch.bfloat16:
        print("Casting buffer:", name)
        buf.data = buf.data.float()
    elif buf.dtype in [torch.int32, torch.int64]:
        # leave these alone (needed for Gather, indexing, etc.)
        pass

for name, param in inference_model.named_parameters():
    if param.dtype == torch.bfloat16:
        print("Casting param:", name)
        param.data = param.data.float()

# -----------------------------
# Create dummy inputs
# -----------------------------
vocab_size = 30522
T = policy.config.n_obs_steps
B = 1
C, H, W = 3, 224, 224
B_lang = 1
T_lang = policy.config.tokenizer_max_length

images = torch.randn(B, T, C, H, W, device=device).float()
img_masks = torch.ones(B, T, dtype=torch.bool, device=device)
lang_tokens = torch.randint(0, vocab_size, (B_lang, T_lang), device=device).long()
lang_masks = torch.ones(B_lang, T_lang, dtype=torch.bool, device=device)
state = torch.randn(B, policy.config.max_state_dim, device=device).float()
actions = torch.randn(B, policy.config.n_action_steps, policy.config.max_action_dim, device=device).float()

save_path = "validation/lerobot_pi05_input_tensor.pt"
torch.save({
    "images": images.cpu(),
    "img_masks": img_masks.cpu(),
    "lang_tokens": lang_tokens.cpu(),
    "lang_masks": lang_masks.cpu(),
    "state": state.cpu(),
    "actions": actions.cpu(),
}, save_path)

print(f"Saved to {save_path}")

# -----------------------------
# Export to ONNX
# -----------------------------

os.makedirs("pi05_onnx", exist_ok=True)
onnx_path = "pi05_onnx/pi05.onnx"


torch.onnx.export(
    inference_model,
    (images, img_masks, lang_tokens, lang_masks, state, actions),
    onnx_path,
    input_names=["images", "img_masks", "lang_tokens", "lang_masks", "state", "actions"],
    output_names=["actions_out"],
    opset_version=20,
    operator_export_type=torch.onnx.OperatorExportTypes.ONNX_ATEN_FALLBACK,
    do_constant_folding=False,
    dynamic_axes={
        "images": {0: "batch"},
        "img_masks": {0: "batch"},
        "lang_tokens": {0: "batch"},
        "lang_masks": {0: "batch"},
        "state": {0: "batch"},
        "actions": {0: "batch"},
        "actions_out": {0: "batch"},
    }
)

print(f"ONNX model exported to {onnx_path}")

