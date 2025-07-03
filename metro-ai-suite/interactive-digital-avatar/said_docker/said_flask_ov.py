from flask import Flask, request, jsonify
import json
import numpy as np
import torch
import torchaudio
from said.model.diffusion import SAID_UNet1D
from said.util.audio import fit_audio_unet, load_audio
from diffusers import DDIMScheduler
from time import time

app = Flask(__name__)

# config for said
init_samples = None
mask = None
unet_feature_dim = -1
prediction_type = "epsilon"
weights_path = "./said_models/SAiD.pth"
device = "gpu.1"
divisor_unet = 1
said_fps = 60
num_steps=100,
strength=1.0,
guidance_scale=2.0,
guidance_rescale=0.0,
eta=0.0,
save_intermediate=False,
show_process=True,

# configs for ov 
ov_model_path = "./ov_models"
use_ov = True
convert_model = False
dynamic_shape = False

# Load model
said_model = SAID_UNet1D(
    noise_scheduler=DDIMScheduler,
    feature_dim=unet_feature_dim,
    prediction_type=prediction_type,
    device_name = device.upper(),
    ov_model_path = ov_model_path,
    use_ov = use_ov,
    convert_model = convert_model,
    dynamic_shape = dynamic_shape,
)
said_model.load_state_dict(torch.load(weights_path, map_location="cpu"))
said_model.to("cpu")
said_model.eval()

@app.route('/post-endpoint', methods=['POST'])
def handle_post():

    data = request.json
    data = json.loads(data)
    audio = data["audio"]
    audio = np.array(audio)
    audio_fs = data["audio_fs"]
    print("len(audio)/audio_fs", len(audio)/audio_fs)
    t_start = time()
    waveform = torch.from_numpy(np.squeeze(audio)) 
    if audio_fs != said_model.sampling_rate:
        waveform = torchaudio.functional.resample(waveform, audio_fs, said_model.sampling_rate)

    # Fit the size of waveform
    fit_output = fit_audio_unet(waveform, said_model.sampling_rate, said_fps, divisor_unet)
    waveform = fit_output.waveform
    window_len = fit_output.window_size

    # Process the waveform
    waveform_processed = said_model.process_audio(waveform).to("cpu")

    with torch.no_grad():
        output = said_model.inference(
            waveform_processed=waveform_processed,
            init_samples=init_samples,
            mask=mask,
            num_inference_steps=num_steps[0],
            strength=strength[0],
            guidance_scale=guidance_scale[0],
            guidance_rescale=guidance_rescale[0],
            eta=eta[0],
            save_intermediate=save_intermediate,
            show_process=show_process,
        )

    result = output.result[0, :window_len].cpu().numpy()
    print("Time used for process the audio: ", time() - t_start)
    print("rtf is: ", (time() - t_start)/(len(audio)/audio_fs))
    
    return json.dumps({"arkit_points": result.tolist()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

