eval "$(conda shell.bash hook)"
conda activate said_ov
python ./SAiD/script/inference.py \
    --weights_path "./said_models/SAiD.pth" \
    --audio_path "./test_materials/audio_test_for_ov.wav" \
    --output_path "./test_materials/output_test.csv" \
    --device "cpu" \
    --dynamic_shape True \
    --convert_model True \
    --ov_model_path "./ov_models" \
    --num_steps 1
python said_flask_ov.py