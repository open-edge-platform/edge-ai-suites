# Generating Model from Geti™

This guide walks you through using Intel® Geti™ to create a detection project for worker safety gear detection, train a model on your own images, and deploy it in the pipeline.

## Prerequisites

- [Minimum Requirements for Geti™ Installation](https://docs.geti.intel.com/docs/user-guide/getting-started/installation/using-geti-installer#minimum-requirements).
- Internet connection for downloading Geti™ and datasets
- Images of workers (with and without safety gear) for training

## Installation Steps

For detailed Geti™ platform installation instructions, refer to the [Geti™ Installer Documentation](https://docs.geti.intel.com/docs/user-guide/getting-started/installation/using-geti-installer).

> **Note:** The standard Geti™ platform installation includes the following steps:
> 1. Download the Geti™ platform installer
> 2. Extract the installer archive
> 3. Prepare the system by creating necessary directories
> 4. Run the platform installer with appropriate system privileges
>
> Please follow the official installation guide for the most up-to-date and accurate installation procedures.
>
> Upon successful completion, you will see the installation success confirmation as shown below:
>
> ![Geti™ Installation](../_assets/installation_geti.png)

## Setting Up Your Project

### Step 4: Sign In to Geti™

Open `https://<host_ip>` in your browser, where `<host_ip>` is the IP address of the system where you installed Geti™. Sign in with the credentials set during installation.

![Sign In to Geti™](../_assets/sign_in_geti.png)

### Step 5: Access Geti™ Dashboard

After successful authentication, you will see the Geti™ dashboard.

![Geti™ Dashboard](../_assets/geti_dashboard.png)


### Step 6: Create a New Project

Click on **Create New Project** to start a new worker safety gear detection project.

![Create New Project](../_assets/create_new_project.png)

*Note: Image is for illustration purposes only.*

For detailed information refer to: [Geti™ - Project Creation](https://docs.geti.intel.com/docs/user-guide/geti-fundamentals/project-management/#project-creation)

### Step 7: Select Detection Task

Select **Detection** and choose **Detection bounding box** as your annotation type.

![Select Detection - Bounding Box](../_assets/detection.png)

*Note: Image is for illustration purposes only.*

### Step 8: Create Labels

Define the labels for your classification task (e.g., "Safety Helmet", "Safety Jacket")

For detailed information refer to: [Geti™ - Label Management](https://docs.geti.intel.com/docs/user-guide/geti-fundamentals/labels/labels-management)

![Create Labels](../_assets/create_labels.png)

*Note: Image is for illustration purposes only.*

## Data Annotation and Training

For comprehensive tutorials on data annotation and training workflows, refer to the [Geti™ Tutorials Documentation](https://docs.geti.intel.com/docs/user-guide/getting-started/use-geti/tutorials).

### Step 9: Upload Training Images

Upload your training dataset containing images of workers in various environments — with and without safety gear.

![Browse and Upload Images](../_assets/browse.png)


### Step 10: Annotate Images Interactively

Click on **Annotate Interactively** from the dashboard. Draw bounding boxes around each worker, helmet, and safety vest in the images.

After annotating a minimum number of frames, Geti™ will automatically start training the model.

![Annotate Images](../_assets/annotate.png)

*Note: Image is for illustration purposes only.*

> **Note:** By default, Geti™ uses **MobileNetV2-ATSS** as the model backbone for the detection task. For more control over your model training, explore the [Advanced Guide](#advanced-guide) section to:
> - Change the model backbone to different architectures (e.g., YOLOX-Tiny, YOLOX-Small)
> - Configure custom training parameters
> - Apply model optimization techniques (FP16, INT8)

### Step 11: Monitor Training Progress

Monitor the model training progress in real time from the Geti™ dashboard.

![Model Training](../_assets/model_training.png)

*Note: Image is for illustration purposes only.*

### Step 12: Improve Model Accuracy (Optional)

Repeat the annotation process with additional images to improve detection accuracy. Including a diverse range of environments, lighting conditions, and worker poses leads to better model generalization.

---

## Advanced Guide

### Model Backbone Change

Change the model architecture to suit your deployment requirements. Refer to [Geti™ - Supported Models Documentation](https://docs.geti.intel.com/docs/user-guide/getting-started/use-geti/supported-models) for the full list of supported architectures.

1. Click on **Models** from the left sidebar
2. Select **Train Model**
3. Click on **Advanced Settings**
4. Select your desired model architecture from the available options:
   - **YOLOX-Tiny**: Lightweight model for edge devices
   - **YOLOX-Small**: Small model with better accuracy
   - Other available backbone architectures
5. Click **Start** to begin training with the selected architecture

For detailed information refer to: [Geti™ - Model Training and Optimization](https://docs.geti.intel.com/docs/user-guide/geti-fundamentals/model-training-and-optimization/)

![Advanced Model Training](../_assets/train_model.png)

*Note: Image is for illustration purposes only.*

Monitor your selected backbone training progress:

![YOLOX-Tiny Model Training](../_assets/yolox_tiny_model.png)


### Train Parameters

Configure training parameters to optimize model performance:

- Learning rate
- Batch size
- Number of epochs
- Augmentation options

For detailed parameter descriptions, refer to [Training Parameters Documentation](https://docs.geti.intel.com/docs/user-guide/model-training/training-parameters).

![Training Parameters](../_assets/training.png)


### Model Optimization

After training completes, optimize your model for edge deployment using quantization:

- **FP16**: Higher precision, good accuracy, requires more computational resources
- **INT8**: Optimized for edge deployment — significantly reduces model size and inference latency

Click **Start Optimization** to generate the optimized model.

![Select Trained Model and Optimization](../_assets/trained_model.png)

*Note: Image is for illustration purposes only.*

#### Download Model

Click the download icon next to the FP16 or INT8 model. A zip folder containing `model.bin` and `model.xml` will be downloaded. Replace the existing model files in your deployment resources:

```
resources/models/worker-safety-gear-detection/deployment/Detection/model/model.bin  <- Replace with downloaded version
resources/models/worker-safety-gear-detection/deployment/Detection/model/model.xml  <- Replace with downloaded version
```

For detailed information, refer to: [Geti™ - Model Download](https://docs.geti.intel.com/docs/user-guide/geti-fundamentals/deployments/)

Alternatively, download the entire deployment folder and replace the existing deployment folder in your resources:

![Deployment Dashboard](../_assets/deployment_dashboard.png)

*Note: Image is for illustration purposes only.*

Navigate to **Deployments** and click **Select model for deployment**:

![Select Deployment Package](../_assets/select_deployment.png)

In the "Select model for deployment" dialog:

1. Choose your desired **Architecture**
2. Select your **Optimization** level (FP16 or INT8)
3. Click **Download**

Replace the existing deployment folder inside your resources with the downloaded package.

> **Advanced Option:** If you need to export PyTorch weights from Geti™ and convert them to OpenVINO IR format locally (for additional optimization using your own dataset), refer to [Export and Optimize Geti™ Model](./export-and-optimize-geti-model.md).

---

## Next Steps

- Deploy the model to edge devices
- Monitor model performance in production
- Continuously improve accuracy by adding more annotated images from your specific environment
- Retrain as needed to account for new safety gear types or site conditions

## Troubleshooting

For installation issues, refer to the [Geti™ Installation Guide](https://docs.geti.intel.com/docs/user-guide/getting-started/installation/using-geti-installer).
