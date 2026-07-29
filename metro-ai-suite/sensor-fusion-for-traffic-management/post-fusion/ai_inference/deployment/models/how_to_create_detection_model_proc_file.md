# How to Create a Detection Model-proc file

In this tutorial you will learn how to create the model-proc file for your
own detection CNN model that can be processed by Intel® Edge Video Infrastructure Reference Architecture.

## First-level items in model_proc.json file
```Json
{
    "json_schema_version": "1.1.0",
    "model_type": "detection",
    "labels_table": {},
    "model_input": {},
    "model_output": {},
    "post_proc_output": {}
}
```
* **json_schema_version**: *Required*. Json schema version, currently it's `1.1.0` for detection model_proc file.

* **model_type**: *Required*. Describe model type.

* **labels_table**: define a series labels table, will be recognized and referenced by `model_output` field. More details can be found in [sec [1] labels_table](#1-labelstable).

* **model_input**: *Required*. Describe model input related infomation, such as: layout, color_format, precision, etc. More details can be found in [sec [2] model_input](#2-modelinput).

* **model_output**: *Required*. Describe model output related information, includes format and output label definition. More details can be found in [sec [3] model_output](#3-modeloutput).

* **post_proc_output**: *Required*. Describe post processing related information, such as: output format, process schedule list, how to map post process outputs to pre-defined format, etc. More details can be found in [sec [4] post_proc_output](#4-postprocoutput).

***Some main fields will be detailed described in the following sections.***

## **[1] labels_table**
------------------------------
This field is designed to pre-defined detection label dictionary. The key-value pair describes one set of labels. Here's the Json Syntax for your reference:

```Json
"labels_table": [
    {
        "name": "string",
        "labels": ["string", "string", ...]
    },
    ...
]
```
* **name**: *Required*. Label table name, it will be recognized and referenced by `model_output` field.
* **labels**: *Required*. Labels definition, It must be paired one-to-one with the output of the model. If the model outputs with background label, the list of labels should start with `__background__`.

An example of this field from [person-vehicle-bike-detection-crossroad-1016.model_proc.json](./person-vehicle-bike-detection-crossroad-1016/person-vehicle-bike-detection-crossroad-1016.model_proc.json):
```Json
"labels_table": [
    {
        "name": "traffic",
        "labels": [
            "__background__",
            "vehicle",
            "person",
            "bike"
        ]
    }
]
```

## **[2] model_input**
------------------------------
This field is designed to describe input related information. Here's the Json Syntax for your reference:

```Json
"model_input": {
    "format": {
        "layout": "string",
        "color_format": "string",
        "layer_name": "string",
        "precision": "string"
    }
}
```
* **format**:
  * **layout**: *Required*. Model input layer layout, `options: [NCHW, NHWC]`.
  * **color_format**: *Optional*. Model input color format, `options: [BGR, RGB]`. If not specified, "BGR" will be used by default.
  * **layer_name**: *Optional*. Model input layer name. If not specified, "ANY" will be used by default.
  * **precision**: *Optional*. Model input precision, currently only `U8` is supported.

An example of this field from [person-vehicle-bike-detection-crossroad-yolov3-1020.model_proc.json](./person-vehicle-bike-detection-crossroad-yolov3-1020/person-vehicle-bike-detection-crossroad-yolov3-1020.model_proc.json):
```Json
"model_input": {
    "format": {
        "layout": "NCHW",
        "color_format": "BGR",
        "precision": "U8"
    }
}
```


## **[3] model_output**
------------------------------
This field is designed to describe model output related information. Here's the Json Syntax for your reference:

```Json
"model_output": {
    "format": {
        "layout": "string",
        "detection_output": {
            "size": "integer",
            "bbox_format": "string",
            "location_index": ["integer", "integer", "integer", "integer"],
            "confidence_index": "integer",
            "first_class_prob_index": "integer",
            "predict_label_index": "integer",
            "batchid_index": "integer"
        }
    },
    "class_label_table": "string"
}
```
* **format**:
  * **layout**: *Required*. Model output dimensions layout, `options: [B, BCxCy, CxCyB]`. More details can be found in [sec 3.1 model_output.format.layout](#31-modeloutputformatlayout).

  * **detection_output**: *Optional*. Also known as `B`-dimensional vector, it's the detection summary info. More details can be found in [sec 3.2 model_output.format.detection_output](#32-modeloutputformatdetectionoutput).

    * **size**: *Required*. Specifically refers to the length of the detection_output vector.
  
    * **bbox_format**: *Required*. Predicted bounding box's format, `options: [CENTER_SIZE, CORNER_SIZE, CORNER]`. More details can be found in [sec 3.2.1 model_output.format.detection_output.bbox_format](#321-modeloutputformatdetectionoutputbboxformat).

    * **location_index**: *Required*. The indices of bounding box coordinate, length of array should be 4.

    * **confidence_index**: *Optional*. Specify the index of predicted confidence score.

    * **first_class_prob_index**: *Optional*. The start index and the following `num_classes` of values should be the predicted probability for each class. The one with max value of class probs can also be treated as the predicted label index, and the final predicted score = confidence * max_class_prob.

    * **predict_label_index**:*Optional*. Specify the index of predicted detection label.
    * 
    * **batchid_index**:*Optional*. Specify the index of batchid.
    > NOTE-1: at least one of `confidence_index` or `first_class_prob_index` should be specified.
    >
    > NOTE-2: at least one of `first_class_prob_index` or `predict_label_index` should be specified.

* **class_label_table**: *Required*. Refer to the pre-defined labels table in [sec [1] labels_table](#1-labelstable).


An example of this field from [person-vehicle-bike-detection-crossroad-yolov3-1020.model_proc.json](./person-vehicle-bike-detection-crossroad-yolov3-1020/person-vehicle-bike-detection-crossroad-yolov3-1020.model_proc.json):
```Json
"model_output": {
    "format": {
        "layout": "BCxCy",
        "detection_output": {
            "size": 85,
            "bbox_format": "CENTER_SIZE",
            "location_index": [0, 1, 2, 3],
            "confidence_index": 4,
            "first_class_prob_index": 5
        }
    },
    "class_label_table": "coco-variant"
}
```

### **3.1 model_output.format.layout**

Layout here describes output dimension layout definition:
- `Cx`: Output feature map cell index x
- `Cy`: Output feature map cell index y
- `B`: Predicted detection outputs, such as: [x, y, w, h, class_0, class_1, ...], e.g, 85 for coco.

> If one outputs with shape: 1, 85, then the output dimension layout may be described as `B`.
> 
> If one outputs with shape: 1, N\*85, 52, 52 (N here means prior anchor boxes), then the output dimension layout may be described as `BCxCy`.
> 
> If one outputs with shape: 1, 52, 52, N\*85 (N here means prior anchor boxes), then the output dimension layout may be described as `CxCyB`.

### **3.2 model_output.format.detection_output**

The order of the detection_output vector values depends on the configuration of the using detection model. A typical detection_output vector should at least contain the predicted bounding-box, confidence and label. 

The requirement of `detection_output` field depends on the using post-proc function. If the in-scope function will be used (i.e, post_proc_output.function_name is "HVA_det_postproc"), then this field must be specified.

Some examples of detection_output vectors for your reference:
- [SSD-MV2: person-vehicle-bike-detection-crossroad-1016](./person-vehicle-bike-detection-crossroad-1016/FP16-INT8/person-vehicle-bike-detection-crossroad-1016.xml)
 
  The output detection box has format [image_id, label, conf, x_min, y_min, x_max, y_max], where:

> - image_id - ID of the image in the batch 
> - label - predicted class ID 
> - conf - confidence for the predicted class 
> - (x_min, y_min) - coordinates of the top left bounding box corner 
> - (x_max, y_max) - coordinates of the bottom right bounding box corner.

- [YoloV3: person-vehicle-bike-detection-crossroad-yolov3-1020](./person-vehicle-bike-detection-crossroad-yolov3-1020/FP16-INT8/person-vehicle-bike-detection-crossroad-yolov3-1020.xml)
  
  The output detection box has format [x, y, w, h, box_score, class_no_1, ...,class_no_80].
> - (x, y) - coordinates of box center relative to the cell 
> - (w, h) - raw height and width of box, apply exponential function and multiply them by the corresponding anchors to get the absolute height and width values 
> - box_score - confidence of detection box in [0, 1] range 
> - class_no_1, …, class_no_80 - probability distribution over the classes in the [0, 1] range, multiply them by the confidence value box_score to get confidence of each class 

#### **3.2.1 model_output.format.detection_output.bbox_format**

This field is very important for the later processing stage, because different models can define different prediction bounding box formats, so we must explicitly specify it here.

- `CENTER_SIZE`: [x_center, y_center, bbox_width, bbox_height]
- `CORNER_SIZE`: [x_min, y_min, bbox_width, bbox_height]
- `CORNER`: [x_min, y_min, x_max, y_max]
> NOTE:
> - (x_center, y_center) - coordinates of the center of bounding box.
> - (bbox_width, bbox_height) - size of bounding box.
> - (x_min,y_min) - coordinates of the top left bounding box corner.
> - (x_max, y_max) - coordinates of the bottom right bounding box corner.


## **[4] post_proc_output**
------------------------------
This field is designed to define the post processing procedure. Mainly includes output format definition, processors list, mapping actions. Here's the Json Syntax for your reference:

```Json
"post_proc_output": {
    "function_name": "string",
    "format": {
        "^[a-zA-Z0-9-_]*$": "string",
        ...
    },
    "process": [
        {
            "name": "string",
            "params": {}
        },
        ...
    ],
    "mapping": {
        "bbox": {},
        "label_id": {},
        "confidence": {}
    }
}
```
* **function_name**: *Required*. Specify the post-process function name. Currently we use one unified post process function to do post-processings, named as `HVA_det_postproc`. <!-- Or users should write their own pp functions with dynamic link libraries. -->

* **format**: *Required*. All post-processed detection results will be formed with serialized json string, this field is responsible for defining the output keys and the corresponding data types. More details can be found in [sec 4.1 post_proc_output.format](#41-postprocoutputformat).

* **process**: *Optional*. A list of processors will be conducted one-by-one. More details can be found in [sec 4.2 post_proc_output.process](#42-postprocoutputprocess).
  * **name**: *Required*. Processor name, `options: [bbox_transform, anchor_transform, NMS]`
  * **params**: *Required*. Processor parameters.

* **mapping**: *Optional*. This field defines the mapping actions to map results to corresponding post-processing output keys. More details can be found in [sec 4.2 post_proc_output.mapping](#42-postprocoutputmapping).


### **4.1 post_proc_output.format**
All post-processed detection results will be formed with serialized json string, this field is responsible for defining the output keys and the corresponding data types. The minimum requirements of outputs are: [`bbox`, `label_id`, `confidence`], and the `type options: [FLOAT_ARRAY, FLOAT, INT],`

Besides, it can be easily scalable through adding keys and the corresponding types.  remember to define the mapping actions in the field `mapping`. Here's the Json Syntax for your reference:
```Json
"format": {
    "bbox": "string",
    "label_id": "string",
    "confidence": "string",
    ...
}
```

* **bbox**: *Required*. One of the minimum requirements of detection post-processing outputs, it describes the field of detected `bounding boxes` data type, should be `FLOAT_ARRAY`.

* **label_id**: *Required*. One of the minimum requirements of detection post-processing outputs, it describes the field of predicted `label_id` data type, should be `INT`.

* **confidence**: *Required*. One of the minimum requirements of detection post-processing outputs, should be `FLOAT`.


An example of this field from [person-vehicle-bike-detection-crossroad-1016.model_proc.json](./person-vehicle-bike-detection-crossroad-1016/person-vehicle-bike-detection-crossroad-1016.model_proc.json):

```Json
"format": {
    "bbox": "FLOAT_ARRAY",
    "label_id": "INT",
    "confidence": "FLOAT"
}
```

> **Scalability**:
> 
> This field can be easily extensible, for example, we have one more prediction info in the model output: quality_score, then you can write this field as:
> ```Json
>   "format": {
>       "bbox": "FLOAT_ARRAY",
>       "label_id": "INT",
>       "confidence": "FLOAT",
>       "quality_score": "FLOAT"   
>   }
>```
> Please remember to define the mapping actions in the field `mapping`, see details in [sec 4.3 post_proc_output.mapping](#43-postprocoutputmapping)
> 

### **4.2 post_proc_output.process**

The requirement of `process` field depends on the using post-proc function. If the in-scope function will be used (i.e, post_proc_output.function_name is "HVA_det_postproc"), then this field must be specified. Otherwise this field can be optional.

In this section, we will introduce the supported processors. These are the important parts of post-processing scope, currently, the processors we've supported are: [`bbox_transform`, `anchor_transform`, `NMS`].

#### **4.2.1 processor: bbox_transform**

This processor is used to do bounding box transformation, including bbox_format converting, scaling and out-bounded clipping. Here's the Json Syntax for your reference:
```Json
{
    "name": "string",
    "params": {
        "apply_to_layer": "string",
        "target_type": "string",
        "scale_h": "float",
        "scale_w": "float",
        "clip_normalized_rect": "boolean"
    }
}
```
- **name**: *Required*. Processor name.

- **params**: *Required*.
  - **apply_to_layer**: *Optional*. Processor will only apply to the specific layer, `reserved options:[ANY, ALL]`. If not specified, "ANY" will be used by default, that means this processor will be applied to every single output layer.

  - **target_type**: *Required*. Target bbox_format, for more details bbox_format, please refer to [sec 3.2.1 model_output.format.detection_output.bbox_format](#321-modeloutputformatdetectionoutputbboxformat).

  - **scale_h**: *Optional*. Predicted y and h will be divided with scale_h.

  - **scale_w**: *Optional*. Predicted x and w will be divided with scale_w.

  - **clip_normalized_rect**: *Optional*. Will clip predicted bunding box within 0~1.0?


An example of this field from [person-vehicle-bike-detection-crossroad-1016.model_proc.json](./person-vehicle-bike-detection-crossroad-1016/person-vehicle-bike-detection-crossroad-1016.model_proc.json):
```Json
{
    "name": "bbox_transform",
    "params": {
        "apply_to_layer": "ANY",
        "target_type": "CORNER_SIZE",
        "scale_h": 1,
        "scale_w": 1,
        "clip_normalized_rect": true
    }
}
```

#### **4.2.2 processor: anchor_transform**

This processor is used to do anchor transformation, including anchors applying on output cells, bbox_prediction and out-bounded clipping. Here's the Json Syntax for your reference:
```Json
{
    "name": "string",
    "params": {
        "apply_to_layer": "string",
        "out_feature": [
            "integer",
            "integer"
        ],
        "anchors": [
            "float",
            "float",
            ...
        ],
        "bbox_prediction": {
            "pred_bbox_xy": {
                "factor": "float",
                "grid_offset": "float",
                "scale_w": "float",
                "scale_h": "float"
            },
            "pred_bbox_wh": {
                "factor": "float",
                "transform": "string",
                "scale_w": "float",
                "scale_h": "float"
            }
        },
        "clip_normalized_rect": "boolean"
    }
}
```
- **name**: *Required*. Processor name.

- **params**: *Required*.

  - **apply_to_layer**: *Optional*. Processor will only apply to the specific layer, `reserved options:[ANY, ALL]`. If not specified, "ANY" will be used by default. Usually `anchor_transform` should be applied to the specified output layer, different anchors may be pre-defined according to the receptive field.

  - **out_feature**: *Required*. Model output feature size: (width, height).

  - **anchors**: *Required*. Predefined anchor boxes, a series of (w, h).

  - **bbox_prediction**: *Required*. Transform coefficients.

    - **pred_bbox_xy**: *Required*. Transform coefficients for bounding box (x, y).

      - **factor**: *Required*. Model output of raw_x and raw_y will multiply with factor.

      - **grid_offset**: Required*. Model output of cell_index will add with grid_offset.

      - **scale_w**: *Optional*. Predicted x will be divided with scale_w.

      - **scale_h**: *Optional*. Predicted y will be divided with scale_h.

    - **pred_bbox_xy**: *Required*. Transform coefficients for bounding box (w, h).

      - **factor**: *Required*. Model output of raw_w and raw_h will multiply with factor.

      - **transform**: Required*. Model output of raw_w and raw_h will be transformed with the defined transform function.

      - **scale_w**: *Required*. Predicted width will be divided with scale_w.

      - **scale_h**: *Required*. Predicted height will be divided with scale_h.
    
  - **clip_normalized_rect**: *Optional*. Will clip predicted bunding box within 0~1.0?


An example of this field from [person-vehicle-bike-detection-crossroad-yolov3-1020.model_proc.json](./person-vehicle-bike-detection-crossroad-yolov3-1020/person-vehicle-bike-detection-crossroad-yolov3-1020.model_proc.json), which has three-layers outputs: 
> NOTE:
> 
> The array of detection summary info, name: conv2d_58/Conv2D/YoloRegion, shape: 1, 255, 13, 13. The
> anchor values are 116,90, 156,198, 373,326. 
> 
> The array of detection summary info, name: conv2d_66/Conv2D/YoloRegion, shape: 1, 255, 26, 26. The
> anchor values are 30,61, 62,45, 59,119. 
> 
> The array of detection summary info, name: conv2d_74/Conv2D/YoloRegion, shape: 1, 255, 52, 52. The
> anchor values are 10,13, 16,30, 33,23. 
> 
```Json
{
    "name": "anchor_transform",
    "params": {
        "apply_to_layer": "conv2d_74/Conv2D/YoloRegion",
        "out_feature": [
            52,
            52
        ],
        "anchors": [
            10.0,
            13.0,
            16.0,
            30.0,
            33.0,
            23.0
        ],
        "bbox_prediction": {
            "pred_bbox_xy": {
                "factor": 1,
                "grid_offset": 0,
                "scale_w": 52,
                "scale_h": 52
            },
            "pred_bbox_wh": {
                "factor": 1,
                "transform": "exponential",
                "scale_w": 416,
                "scale_h": 416
            }
        },
        "clip_normalized_rect": true
    }
},
{
    "name": "anchor_transform",
    "params": {
        "apply_to_layer": "conv2d_66/Conv2D/YoloRegion",
        "out_feature": [
            26,
            26
        ],
        "anchors": [
            30.0,
            61.0,
            62.0,
            45.0,
            59.0,
            119.0
        ],
        "bbox_prediction": {
            "pred_bbox_xy": {
                "factor": 1,
                "grid_offset": 0,
                "scale_w": 26,
                "scale_h": 26
            },
            "pred_bbox_wh": {
                "factor": 1,
                "transform": "exponential",
                "scale_w": 416,
                "scale_h": 416
            }
        },
        "clip_normalized_rect": true
    }
},
{
    "name": "anchor_transform",
    "params": {
        "apply_to_layer": "conv2d_58/Conv2D/YoloRegion",
        "out_feature": [
            13,
            13
        ],
        "anchors": [
            116.0,
            90.0,
            156.0,
            198.0,
            373.0,
            326.0
        ],
        "bbox_prediction": {
            "pred_bbox_xy": {
                "factor": 1,
                "grid_offset": 0,
                "scale_w": 13,
                "scale_h": 13
            },
            "pred_bbox_wh": {
                "factor": 1,
                "transform": "exponential",
                "scale_w": 416,
                "scale_h": 416
            }
        },
        "clip_normalized_rect": true
    }
}
```


#### **4.2.3 processor: NMS**

This processor is used to run NMS (Non-Maximum-Suppression), the NMS is a computer vision method that selects a single out of many overlapping predicted bounding boxes over a given IoU (Intersection over Union) threshold. Here's the Json Syntax for your reference:
```Json
{
    "name": "string",
    "params": {
        "apply_to_layer": "string",
        "iou_threshold": "float",
        "class_agnostic": "boolean"
    }
}
```
- **name**: *Required*. Processor name.

- **params**: *Required*.
  - **apply_to_layer**: *Optional*. Processor will only apply to the specific layer, `reserved options:[ANY, ALL]`. If not specified, "ANY" will be used by default. But usually `NMS` should be applied to all layers in one time, so it's suggested to set as `ALL` here.

  - **iou_threshold**: *Required*. NMS param for iou threshold.

  - **class_agnostic**: *Optional*. Will NMS been done over all classes or each class? It's set as `false` by default, that means NMS will be conducted on each class.


An example of this field from [person-vehicle-bike-detection-crossroad-yolov3-1020.model_proc.json](./person-vehicle-bike-detection-crossroad-yolov3-1020/person-vehicle-bike-detection-crossroad-yolov3-1020.model_proc.json):
```Json
{
    "name": "NMS",
    "params": {
        "apply_to_layer": "ALL",
        "iou_threshold": 0.5,
        "class_agnostic": false
    }
}
```

### **4.3 post_proc_output.mapping**

The requirement of `mapping` field depends on the using post-proc function. If the in-scope function will be used (i.e, post_proc_output.function_name is "HVA_det_postproc"), then this field must be specified. Otherwise this field can be optional.

This field is designed to define the mapping actions to map results to corresponding post-processing output keys. Each mapping rule for converting results to [sec 4.1 post_proc_output.format](#41-postprocoutputformat). Here's the Json Syntax for your reference:

```Json
"mapping": {
    "^[a-zA-Z0-9-_]*$": {
        "input": {
            "index": ["integer", "integer", "integer", "integer"]
        },
        "op": [
            {
                "name": "string",
                "params": {}
            }
        ]
    },
    ...
}
```
- **^[a-zA-Z0-9-_]\*\$**: *Required*. Key name pattern, such as: "bbox", "label_id", "confidence", etc.
  
  - **input**: *Required*. Mapping input args.
    - **index**: *Required*. Mapping input indices referring to the [detection_output](#32-modeloutputformatdetectionoutput) vector.
  - **op**: *Required*. A list of operators will be conducted one-by-one. More details can be found in [sec 4.3.2 mapping operaters](#432-mapping-operaters).
    - **name**: *Required*. OP name.
    - **params**: *Required*. OP parameters.


#### **4.3.2 mapping operaters**
In this section, we will introduce the supported operators. These are the important parts of mapping scope, currently, the operators we've supported are: [`identity`, `sigmoid`, `yolo_multiply`, `argmax`, `argmin`, `max`, `min`].

These operators will do a series transformations from detection_output to target key.

- **identity**: Do nothing.
- **sigmoid**: Sigmoid function.
- **yolo_multiply**: Yolo-style multiplication to get the final confidence score: bbox_score * cls_prob_score. More specificly, input.index[0] refer to the bbox_score index, while input.index[1, ...] refer to the cls_prob_score from class_0 to class_N, cls_prob_score = max([class_0, class_1, ...])
- **argmax**: Get the index with the max value of inputs.
- **argmin**: Get the index with the min value of inputs.
- **max**: Get the max value of inputs.
- **min**: Get the min value of inputs.

An example of this field from [person-vehicle-bike-detection-crossroad-yolov3-1020.model_proc.json](./person-vehicle-bike-detection-crossroad-yolov3-1020/person-vehicle-bike-detection-crossroad-yolov3-1020.model_proc.json):
```Json
"mapping": {
    "bbox": {
        "input": {
            "index": [0, 1, 2, 3]
        },
        "op": [
            {
                "name": "identity",
                "params": {}
            }
        ]
    },
    "label_id": {
        "input": {
            "index": [5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21,
            22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38,
            39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55,
            56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72,
            73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84]
        },
        "op": [
            {
                "name": "argmax",
                "params": {}
            }
        ]
    },
    "confidence": {
        "input": {
            "index": [4, 5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21,
            22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38,
            39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55,
            56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72,
            73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84]
        },
        "op": [
            {
                "name": "yolo_multiply",
                "params": {}
            }
        ]
    }
}
```

## [5] Custom post-processing library
These steps in this section describe how to add your own post-processing methods.

### Write custom post-processing library source code
Add the library source code file to [this path](../../source/modules/inference_util/custom_post_process/) and he interface example is as follows:
``` CPP
/**
 * @brief custom post-process function: SSDPostProc
 * @param ptrBlobs Inference blob data
 * @param class_conf_thresh Filter Confidence Threshold
 * @return std::string, results with json format
 */
std::string SSDPostProc(std::map<std::string, InferenceEngine::Blob::Ptr> ptrBlobs,
                           float class_conf_thresh)
```

### Compile and generate dynamic link library
Compile the dynamic library to this path `/opt/models/custom-pp/<your-library-name>` such as `/opt/models/custom-pp/libssd_postproc.so`. Refer to the following compilation steps.

Build and generate dynamic library
``` Shell
cd /opt/hce-core/middleware/ai/ai_inference/ai_inference/source/modules/inference_util/custom_post_process
mkdir -p build && cd build
cmake .. && make -j
cp ../ai_inference/deployment/models/custom-pp/libssd_postproc.so /opt/models/custom-pp/libssd_postproc.so

```

### Create config file
Create custom post-processing config file, an example from pipeline config file [cpuLocalImageAiPipeline-custom-pp.json](../../test/configs/cpuLocalImageAiPipeline-custom-pp.json)

You can set the detection config file path with key: `ModelProcConfPath` and set the library path with key: `ModelProcLibPath`.
``` Json
{
    "Nodes": [
        ...
        {
            "Node Class Name": "DetectionNode",
            "Node Name": "Detection",
            "Thread Number": "1",
            "Is Source Node": "false",
            "Configure String": "InferReqNumber=(INT)6;InferStreams=(INT)6;ModelPath=(STRING)vehicle-detection-evi-0.0.1/FP16-INT8/vehicle-detection-evi-001.xml;ModelProcConfPath=(STRING)custom-pp/vehicle-detection-evi-001.custom.model_proc.json;Threshold=(FLOAT)0.8;MaxROI=(INT)0;ModelProcLibPath=(STRING)/opt/models/custom-pp/libssd_postproc.so"
        },
        ...
    ]
}
```
Create model config file for detection post processing : an example: `/opt/models/custom-pp/<json-file-name>`, an example from vehicle detection file [vehicle-detection-evi-001.custom.model_proc.json](../../deployment/models/custom-pp/vehicle-detection-evi-001.custom.model_proc.json)

You can set the custom post-processing function name in the post-processing library with key: `function_name`.
``` Json
{
    ...
    "post_proc_output": {
        "function_name": "SSDPostProc",
        "format": {
            "bbox": "FLOAT_ARRAY",
            "label_id": "INT",
            "confidence": "FLOAT"
        }
    },
    "labels_table": [
        {
            "name": "traffic",
            "labels": [
                "__background__",
                "vehicle"
            ]
        }
    ]
}
```

## [6] Use defined model_proc.json
Once you have finished one specific model_proc.json file, you must put it on the folder: `/opt/models`, which is also the folder for model files.

Then the model_proc json file path can be set in pipeline config files with key: `ModelProcConfPath`, an example from pipeline config file [](../../test/configs/cpuLocalPerformance-yolov3-1020.json):

```Json
{
    "Nodes": [
        ...
        {
            "Node Class Name": "DetectionNode",
            "Node Name": "Detection",
            "Thread Number": "1",
            "Is Source Node": "false",
            "Configure String": "InferReqNumber=(INT)6;InferStreams=(INT)6;InferDevice=(STRING)CPU;ModelPath=(STRING)person-vehicle-bike-detection-crossroad-yolov3-1020/FP16-INT8/person-vehicle-bike-detection-crossroad-yolov3-1020.xml;ModelProcConfPath=(STRING)person-vehicle-bike-detection-crossroad-yolov3-1020/person-vehicle-bike-detection-crossroad-yolov3-1020.model_proc.json;Threshold=(FLOAT)0.5;MaxROI=(INT)0"
        },
        ...
    ],
    "Links": [
        ...
    ]
}
```
