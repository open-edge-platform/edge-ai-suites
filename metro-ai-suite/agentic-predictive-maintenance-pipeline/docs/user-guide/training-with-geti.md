# Training a Defect Detection Model with Intel Geti

This release does not include a production-trained pipeline defect detection model because a
representative, properly licensed, and sufficiently labeled defect dataset is not available for
release validation. The supplied model and configuration are intended as a reference integration
path for DL Streamer, storage, and the agent workflow.

Use Intel Geti to train and export a deployment-ready detector when you have a production dataset
for your inspection scenario.

## Training Workflow

1. Collect representative images or video frames from the target environment. Include normal
   examples and each defect class that the application must detect.
2. Create a Geti object detection project.
3. Define the defect labels. For the reference pipeline use case, the application configuration
   expects these labels:

   ```text
   Rupture
   Deformation
   Disconnect
   Obstacle
   ```

   If you use different labels, update the APM configuration files listed in
   [Update APM Configuration](#update-apm-configuration).
4. Upload the dataset and annotate bounding boxes for each defect instance.
5. Train the model in Geti and review validation metrics. Do not proceed to deployment until the
   dataset covers expected camera angles, lighting, backgrounds, defect sizes, and negative samples.
6. Export the trained model in OpenVINO Intermediate Representation (IR) format. The exported model
   should include `.xml` and `.bin` artifacts.

## Install the Exported Model

Place the exported OpenVINO model artifacts in the use-case model directory. The default
`pipeline-server-config.json` expects the detector at this path inside the DL Streamer Pipeline
Server container:

```text
/home/pipeline-server/models/pipeline-defect-detection.xml
```

That container path maps to the host directory selected by `USE_CASE_MODELS_DIR`, which is normally:

```text
apps/pipeline-defect-detection/models/
```

For the reference use case, copy or rename the exported files to:

```text
apps/pipeline-defect-detection/models/pipeline-defect-detection.xml
apps/pipeline-defect-detection/models/pipeline-defect-detection.bin
```

If you use a different model filename, update every CPU/GPU/NPU pipeline entry in:

```text
apps/pipeline-defect-detection/configs/pipeline-server-config.json
```

For example:

```json
"pipeline": "{auto_source} name=source ! decodebin3 ! gvadetect model=/home/pipeline-server/models/pipeline-defect-detection.xml device=CPU threshold=0.4 name=detection ! gvametaconvert add-empty-results=true name=metaconvert ! queue ! gvafpscounter ! appsink name=destination"
```

Update the `model=` value for each device-specific pipeline if your model path changes.

## Update APM Configuration

The detector labels must stay aligned with the reasoning and fallback configuration:

| File | What to update |
|------|----------------|
| `apps/pipeline-defect-detection/configs/agents.yaml` | `policy.defect_classes`, critical classes, and severity mapping |
| `apps/pipeline-defect-detection/configs/policy_fallback.json` | Per-class confidence thresholds and fallback actions |
| `apps/pipeline-defect-detection/prompts/pipeline-defect-detection.txt` | Defect class descriptions and reasoning instructions |
| `apps/pipeline-defect-detection/configs/pipeline-server-config.json` | Model path and detection threshold |

If you create a new use case, copy the full use-case directory and update the file names and
`use_case_id` consistently:

```bash
cp -r apps/pipeline-defect-detection apps/<new-use-case>
```

## Validate the Trained Model

After installing the exported model:

1. Start the application:

   ```bash
   source ./setup.sh --use-case pipeline-defect-detection
   ```

2. Open the dashboard and run an inspection on a validation video.
3. Confirm detections are stored:

   ```bash
   curl http://localhost:8080/api/storage/detections/summary
   ```

4. Review DL Streamer logs if detections are missing:

   ```bash
   docker logs apm-dlstreamer
   docker logs apm-detection
   ```

5. Tune the `gvadetect threshold=` value in `pipeline-server-config.json` and the policy thresholds
   in `policy_fallback.json` based on validation results.

## Dataset Readiness Guidance

Before treating a model as release-ready, verify that the dataset includes:

- Representative production camera views and image quality.
- Enough examples for each defect class and enough negative or no-defect examples.
- Variation in lighting, backgrounds, object scale, occlusion, and motion blur.
- A separate validation set that was not used for training.
- Clear label definitions so annotators apply bounding boxes consistently.

Do not use the reference model as evidence of production defect detection accuracy. It is provided
only to demonstrate the APM application flow.
