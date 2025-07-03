# SAiD on A770

## Quick start

### Model prepare
Please download `SAiD.pth` from huggingface and put it under the `said_models` folder.
Please prepare a .wav file with any audio content named `audio_test_for_ov.wav` under dir `test_materials` for model convertion.

### Build image
```bash
docker compose build
```

### Start the container
```bash
docker compose up
```

### Change device or num_steps
Please change line 19 for device and line 22 for num_steps in the script said_flask_ov.py.
Please re-build the image after modification.