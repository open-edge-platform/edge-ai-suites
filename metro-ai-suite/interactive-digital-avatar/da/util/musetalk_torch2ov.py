import json
from pathlib import Path

import openvino as ov
import torch
from diffusers import AutoencoderKL, UNet2DConditionModel

from ext.musetalk.models.unet import PositionalEncoding


class VaeDecoderProxy(torch.nn.Module):

    def __init__(self):
        super().__init__()
        self.vae = AutoencoderKL.from_pretrained('resource/musetalk_models/sd-vae-ft-mse/')

    def forward(self, latent):
        latent = 5.489980785067252 * latent
        image = self.vae.decode(latent).sample
        image = (image / 2 + 0.5).clamp(0, 1)
        image = image.permute(0, 2, 3, 1)
        image = (image * 255).round().to(torch.uint8)
        image = image[..., [2, 1, 0]]
        return image


class UnetProxy(torch.nn.Module):

    def __init__(self):
        super().__init__()
        with open('resource/musetalk_models/musetalk/musetalk.json', 'r') as f:
            unet_config = json.load(f)
        self.unet = UNet2DConditionModel(**unet_config)
        weights = torch.load('resource/musetalk_models/musetalk/pytorch_model.bin', map_location="cpu")
        self.unet.load_state_dict(weights)
        self.pe = PositionalEncoding(d_model=384)

    def forward(self, audio_feature, video_feature, timestep):
        audio_feature_batch = self.pe(audio_feature)
        latent = self.unet(video_feature, timestep, encoder_hidden_states=audio_feature_batch).sample
        return latent


class UnetVaeProxy(torch.nn.Module):

    def __init__(self, unet, vae):
        super().__init__()
        self.unet = unet
        self.vae = vae

    def forward(self, audio_feature, video_feature, timestep):
        latent = self.unet(audio_feature, video_feature, timestep)
        image = self.vae(latent)
        return image


if __name__ == '__main__':
    batch_size = 4
    model_name = f'unet-vae-b{batch_size}'

    model = UnetVaeProxy(UnetProxy(), VaeDecoderProxy())
    model.eval()

    work_dir = "resource/musetalk_models/musetalk"

    # torch to onnx
    args = (torch.rand(batch_size, 50, 384), torch.rand(batch_size, 8, 32, 32), torch.rand(1))
    input_names = ('audio_feature', 'video_feature', 'timestep')
    onnx_path = f'{work_dir}/onnx/{model_name}.onnx'
    Path(onnx_path).parent.mkdir(exist_ok=True)
    torch.onnx.export(model, args, onnx_path, input_names=input_names)

    # onnx to openvino
    ov_model = ov.convert_model(onnx_path)
    ov.save_model(ov_model, f'{work_dir}/{model_name}.xml', compress_to_fp16=True)
