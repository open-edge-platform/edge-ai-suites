# How to Create a Classification Model-proc file

In this tutorial you will learn how to create the model-proc file for your
own image classification or object attribute recognition CNN model that can be processed by Intel® Edge Video Infrastructure Reference Architecture.

## First-level items in model_proc.json file
```Json
{
    "json_schema_version": "1.0.0",
    "description": "string",
    "shared_postproc": {},
    "output_postproc": []
}
```
* **json_schema_version**: *Required*. Json schema version, currently it's `1.0.0` for classification model_proc file.

* **description**: *Required*. Describe model information.
* **shared_postproc**: *Optional*. Describe post processing related information to be shared with each output layer, such as: converter, method, activation, layer_name, attribute_name, labels, etc. Can be optional if you would like to write all the params in `output_postproc` field. More details can be found in [sec [1] shared_postproc](#1-shared_postproc).
* **output_postproc**: *Optional*. This field describes post processing parameters for every output layer, and inherit all params from `shared_postproc` field. More details can be found in [sec [2] output_postproc](#2-output_postproc).
> NOTE: at least one of `shared_postproc` or `output_postproc` should be specified.
>

## **[1] shared_postproc**
This field is designed to define the post processing parameters. Here's the Json Syntax for your reference:
```Json
"shared_postproc": {
    "layer_name": "string",
    "converter": "string",
    "method": "string",
    "activation": "string",
    "attribute_name": "string",
    "labels": ["string", "string", ...]
}
```
* **layer_name**: *Optional*. Model output layer name. If not specified, "ANY" will be used by default, if multiple output layers are expected, this field would be strongly recommended to be set.

* **converter**: *Required*. Converter name, `options: [label]`.
* **method**: *Optional*. Prediction method, `options: [max, min]`, "max" will be used by default.
* **activation**: *Optional*. Activation function, `options: [sigmoid, softmax]`, if not set, this field can be empty, and none activation will be applied on the outputs.
* **attribute_name**: *Optional*. Attribute name. If not specified, "classification" will be used by default, if you are using an object attribute recognition model, this field would be strongly recommended to be set.
* **labels**: *Required*. Labels definition, It must be paired one-to-one with the output of the model. If the model outputs with background label, the list of labels should start with `__background__`.

An example of this field from [vehicle-attributes-recognition-barrier-0039.model_proc.json](./vehicle-attributes-recognition-barrier-0039/vehicle-attributes-recognition-barrier-0039.model_proc.json):
```Json
"shared_postproc": {
    "converter": "label",
    "method": "max"
}
```

## **[2] output_postproc**
This field is designed to define the post processing parameters for each output layer. If this field. Here's the Json Syntax for your reference:
```Json
"output_postproc": [
    {
        "layer_name": "string",
        "converter": "string",
        "method": "string",
        "activation": "string",
        "attribute_name": "string",
        "labels": ["string", "string", ...]
    },
    ...
]
```
* All the fields are shared with the ones in [sec [1] shared_postproc](#1-shared_postproc)
> NOTE: since this field is configured for each output layer, the length should be the same with output layers num.
>
> 
An example of this field from [vehicle-attributes-recognition-barrier-0039.model_proc.json](./vehicle-attributes-recognition-barrier-0039/vehicle-attributes-recognition-barrier-0039.model_proc.json):
```Json
"output_postproc": [
    {
        "layer_name": "color",
        "attribute_name": "color",
        "labels": [
            "white",
            "gray",
            "yellow",
            "red",
            "green",
            "blue",
            "black"
        ]
    },
    {
        "layer_name": "type",
        "attribute_name": "type",
        "labels": [
            "car",
            "bus",
            "truck",
            "van"
        ]
    }
]
```

## [3] Write model_proc.json
We use one function node named `ClassificationNode` to infer with both classification model and attributes models, the difference between these two is mainly the number of output layers. So we can define a specific model_proc.json file for difference models through configuring `output_postproc` field.

## 3.1 Write a model_proc.json file for image classification models
An example of model type can be found from:

[resnet-50-pytorch.model_proc.json](./resnet-50-pytorch/resnet-50-pytorch.model_proc.json)


## 3.2 Write a model_proc.json file for object attribute models

An example of model type can be found from:

[vehicle-attributes-recognition-barrier-0039.model_proc.json](./vehicle-attributes-recognition-barrier-0039/vehicle-attributes-recognition-barrier-0039.model_proc.json)

## [4] Use defined model_proc.json
Once you have finished one specific model_proc.json file, you must put it on the folder: `/opt/models`, which is also the folder for model files.

Then the model_proc json file path can be set in pipeline config files with key: `ModelProcConfPath`, an example from pipeline config file [](../../test/configs/cpuLocalPerformance-yolov3-1020.json):

```Json
{
    "Nodes": [
        ...
        {
            "Node Class Name": "ClassificationNode",
            "Node Name": "Attribute",
            "Thread Number": "1",
            "Is Source Node": "false",
            "Configure String": "ModelPath=(STRING)vehicle-attributes-recognition-barrier-0039/FP16-INT8/vehicle-attributes-recognition-barrier-0039.xml;ModelProcConfPath=(STRING)vehicle-attributes-recognition-barrier-0039/vehicle-attributes-recognition-barrier-0039.model_proc.json"
        },
        ...
    ],
    "Links": [
        ...
    ]
}
```