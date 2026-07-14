# Generating a Model from Geti™ Software

This guide walks you through the process of installing the Geti™ software, setting up a pallet defect detection project, training a model, and deploying it.

## Prerequisites

- [Minimum Requirements for Geti™ Software Installation](https://docs.geti.intel.com/docs/user-guide/getting-started/installation/installation-guide).
- Internet connection for downloading Geti™ software and datasets
- Access to images for training your defect detection model

## Installation Steps

For detailed Geti™ software installation instructions, refer to the [Geti™ Installer Documentation](https://docs.geti.intel.com/docs/user-guide/getting-started/installation/installation-guide).

> **Note:** The standard Geti™ software installation includes the following steps:
>
> 1. Download the Geti™ software installer
> 2. Extract the installer archive
> 3. Prepare the system by creating necessary directories
> 4. Run the software installer with appropriate system privileges
>
> Please follow the official installation guide for the most up-to-date and accurate installation procedures.
>
> Upon successful completion, you will see the installation success confirmation as shown below:
>
> ![Geti™ Software Installation](../_assets/installation_geti.png)

## Setting Up Your Project

### Step 1: Sign In to Geti™ Software

Open `https://<host_ip>` in your browser, where `<host_ip>` is the IP address of the system
where you installed the Geti™ software server. Sign in with the credential which was set during installation:

![Sign In to Geti™ Software](../_assets/sign_in_geti.png)

### Step 2: Access Geti™ Software Dashboard

After successful authentication, you will see the Geti™ software dashboard:

![Geti™ Software Dashboard](../_assets/geti_dashboard.png)

### Step 3: Create a New Project

Click on "Create New Project" to start a new pallet defect detection project:

![Create New Project](../_assets/create_new_project.png)

For detailed information refer the tutorial: [Geti™ Software - Project Creation](https://docs.geti.intel.com/docs/user-guide/geti-fundamentals/project-management/#project-creation)

### Step 4: Select Detection Task

Select "Detection" and choose "Detection bounding box" as your annotation type:

![Select Detection - Bounding Box](../_assets/detection.png)

### Step 5: Create Labels

Define the labels for your defect detection task (e.g., "defect", "box", "shipping label", etc.):

![Create Labels](../_assets/create_labels.png)

For detailed information refer the tutorial: [Geti™ Software - Label Management](https://docs.geti.intel.com/docs/user-guide/geti-fundamentals/labels/labels-management)

## Data Annotation and Training

A dataset is a collection of images and videos in your project, together with the annotations used to train models. The Dataset screen is where you upload media, monitor annotation progress, and launch the annotator. For more information on datasets, see [Dataset Management](https://docs.geti.intel.com/docs/user-guide/geti-fundamentals/datasets/dataset-management).

To use the Geti™ software for dataset creation and annotation, see [Building a Good Dataset](https://docs.geti.intel.com/docs/user-guide/learn-geti/dataset-creation).


### Step 6: Upload Training Images

Browse and upload your training dataset images:

![Browse and Upload Images](../_assets/browse.png)

After uploading, your project dashboard will display the uploaded images:

![Pallet Defect Detection Dashboard](../_assets/pdd_dashboard.png)

### Step 7: Annotate Images Interactively and Train the Model

Click on "Annotate Interactively" on the top right side of the dashboard. Begin annotating your images manually:

![Annotate Images](../_assets/annotate.png)

After annotating a few frames, the Geti™ software will automatically start training the model. For more information on model training, see [Model Training](https://docs.geti.intel.com/docs/user-guide/geti-fundamentals/model-training-and-optimization/).

Annotate a minimum number of frames to trigger automatic model training within the Geti™ software. A real-time estimate of the remaining "Annotations Required" before training starts is displayed in the upper-right corner of the interface.

> **Note:** By default, the Geti™ software uses **MobileNetV2-ATSS** as the model backbone for your detection task. For more control over your model training, you can explore the [Advanced Guide](#advanced-guide) section below to:
>
> - Change model backbone to different architectures
> - Configure custom training parameters
> - Apply model optimization techniques (FP16, INT8)

### Step 8: Monitor Training Progress

You can monitor the model training progress in real-time:

![Model Training](../_assets/model_training.png)

### Step 9: Improve Model Accuracy (Optional)

Repeat the annotation process to improve model accuracy. More annotated data will lead to better model performance.

### Step 10: Download Model

#### Download Model

Click on the download icon next to the FP16 or INT8 model. A zip folder containing `model.bin` and `model.xml` will be downloaded. Replace the existing model files in your deployment resources:

```text
model.bin  <- Replace with downloaded version
model.xml  <- Replace with downloaded version
```

Alternatively, you can download the entire deployment folder and replace the existing deployment folder in your resources:

![Deployment Dashboard](../_assets/deployment_dashboard.png)

For an introduction to the Inference Pipeline concept, see [Inference Pipeline](https://docs.geti.intel.com/docs/user-guide/pipeline-management/introduction).

### Step 11: Deploy Model

Navigate to **Deployments** and click **Select model for deployment**:

![Select Deployment Package](../_assets/select_deployment.png)

In the "Select model for deployment" dialog:

1. Choose your desired **Architecture**
2. Select your **Optimization** level (FP16 or INT8)
3. Click **Download**

The deployment package will be downloaded. Replace the existing deployment folder inside your resources with this new package.

## Advanced Guide

The Advanced Guide section allows you to fine-tune your model training with more control over model architecture, parameters, and optimization.

### Model Backbone Change

Change the model backbone from the default architecture to other architectures for your specific requirements. For a complete list of supported model architectures, refer to [Geti™ Software - Supported Models Documentation](https://docs.geti.intel.com/docs/user-guide/learn-geti/computer-vision-tasks/ai-fundamentals-tasks#supported-deep-learning-models).

1. Click on **Models** from the left sidebar
2. Select **Train Model**
3. Click on **Advanced Settings**
4. Select your desired model type from the available options:
   - **YOLOX-Tiny**: Lightweight model for edge devices
   - **YOLOX-Small**: Small model with better accuracy
   - Other available backbone architectures
5. Click **Start** to begin training with your selected backbone

For detailed information, refer the tutorial: [Geti™ Software - Model Training and Optimization](https://docs.geti.intel.com/docs/user-guide/geti-fundamentals/model-training-and-optimization/)
![Advanced Model Training](../_assets/train_model.png)

Monitor your selected backbone training progress:

![YOLOX-Tiny Model Training](../_assets/yolox_tiny_model.png)

### Train Parameters

Configure custom training parameters to optimize model performance based on your dataset and requirements. For detailed information on available training parameters and their configurations, refer to [Training Parameters Documentation](https://docs.geti.intel.com/docs/user-guide/geti-fundamentals/model-training-and-optimization/evaluation#training-parameters).

Common parameters include:

- Learning rate
- Batch size
- Number of epochs
- Optimizer settings
- Augmentation options

![Training Parameters](../_assets/training.png)

### Model Optimization

After training completes, optimize your model for different deployment scenarios using quantization techniques. Choose the optimization level that best suits your deployment environment:

- **FP16**: Higher precision with good accuracy, requires more computational resources
- **INT8**: Optimized for edge deployment, significantly reduces model size and latency

Click on **Start Optimization** to generate your optimized model:

![Select Trained Model and Optimization](../_assets/trained_model.png)

After optimization, proceed with downloading and deploying your model.

## Next Steps

- Deploy the model to edge devices
- Monitor model performance
- Continuously improve accuracy by adding more annotated data
- Retrain as needed with new data

## Troubleshooting

For installation issues, refer to the [Geti™ Software Installation Guide](https://docs.geti.intel.com/docs/user-guide/getting-started/installation/installation-guide).
