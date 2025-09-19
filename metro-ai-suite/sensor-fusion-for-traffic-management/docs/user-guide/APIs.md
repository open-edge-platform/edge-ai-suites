# APIs

This document describes the syntax and examples of APIs exposed by the AI Inference Service.

## RESTful API
### Overview

-   ***Verb***:
```
POST
```
-   ***URL***:
```
/run
```
-   ***Headers***:

> The only required header is the content-length, which should be correct and valid according to the body length.

***JSON syntax of Request:***
```vim
{

"pipelineConfig": string,

"mediaUri": string, string, ...,

"suggestedWeight": unsigned

}
```

***JSON syntax of Respse:***
```vim
{

"result": [
    {    
        "status_code": int,    
        "description": string,
        "roi_info": [    
            "roi": [int, int, int, int],    
            "media_birdview_roi": [float, float, float, float],    
            "roi_class": string,    
            "roi_score": float,    
            "tack_id": int,
            "track_status": string,    
            "fusion_roi_state": [float, float, float, float],    
            "fusion_roi_size": [float, float],    
            "latency": int
         ]
    },
    ...

}

```
### Request
| Property Name   | Value | Description                 | Notes      |
|---|---|---|----|
| pipelineConfig         | string     | Contains the pipeline topology that server will execute. The syntax should follow HVA pipeline framework serialized pipeline format. | Serialized from a JSON structure above|
|mediaUri|string|This property contains the descriptor or the actual contents in inputs to a specified pipeline. The actual format depends on the input node within the pipeline parsing this value.|Supported three different input types|
|suggestedWeight|unsigned|Optional, an unsigned integer value suggesting the workload of the specified pipeline|Default value: 0|

<center> Table 1. Properties of Request in RESTful API. </center>

#### pipelineConfig

This parameter is serialized from a JSON structure, which contains the topology of a pipeline executed by a server. Its syntax should follow the serialized pipeline format defined in the HVA pipeline framework.

The definition of a pipeline topology includes four parts:

-   InputNode

-   DecoderNode

-   SomeAIProcessingNode

-   OutputNode

The part "ProcessingNode" should contain at least one node and other parts must contain exactly one node.

Besides, the link topology in pipeline topology should also be defined.

#### mediaUri

This property contains a list of input items. It should contain the descriptor or the actual contents in inputs to the specified pipeline. Its actual format depends on the ***InputNode*** within the pipeline parsing this value.

-   Image / radar bin file local path: the pipeline uses ***InputNode:
    LocalMultiSensorInputNode***
```vim
[

"/path/to/binFileFolder",

]
```

When using this type of ***InputNode***, the media type should be image and media index and radar index should be set.

Here's a pipeline definition example for this type of ***InputNode***
```json
{
    "Node Class Name": "LocalMultiSensorInputNode",
    "Node Name": "Input",
    "Thread Number": "1",
    "Is Source Node": "true",
    "Configure String":
    "MediaType=(STRING)image;MediaIndex=(INT)0;RadarIndex=(INT)1 "
}
```
-   Image / video local path, the pipeline uses ***InputNode:
    LocalMediaInputNode***
```vim
[
    "/path/to/media1",
    "/path/to/media2",
    "/path/to/media3",
]
```
When using this type of ***InputNode***, the media type should be well defined to inform AI Inference Service which type of media, image, or video will be received. Here are pipeline definition examples for processing image and video respectively.

-   For image
```json
{
    "Node Class Name": "LocalMediaInputNode",
    "Node Name": "Input",
    "Thread Number": "1",
    "Is Source Node": "true",
    "Configure String":
    "MediaType=(STRING)image;DataSource=(STRING)vehicle"
}
```
-   For video
```json
{
    "Node Class Name": "LocalMediaInputNode",
    "Node Name": "Input",
    "Thread Number": "1",
    "Is Source Node": "true",
    "Configure String":
    "MediaType=(STRING)video;DataSource=(STRING)vehicle"
}
```
-   Image base64 encoded content with ROI, the pipeline uses
    ***InputNode: RawImageInputNode***
```vim
[
    {
        "image": someBase64Content,
        "roi": [int, int, int, int]
    }
    ,
    {
        "image": someBase64Content,
        "roi": [int, int, int, int]
    }
]
```
-   "image" is generated with base64 encoded image content.

-   "roi" define a region of interest; the 4 elements of the vector stand for {x, y, width, height} of the bounding box; the detection result will only occur in this region; [0, 0, 0, 0] will be regarded as the whole picture.

Here's a pipeline definition example for this type of ***InputNode***
```vim
{
    "Nde Class Name": "RawImageInputNode",
    "Node Name": "Input",
    "Thread Number": "1",
    "Is Source Node": "true"
}
```
#### An Example of Request

The following is an example of sending a request to AI Inference Service via RESTful API.
```vim
POST /run HTTP/1.1
Host: 127.0.0.1
User-Agent: Boost.Beast/306
Content-Length: 81508

{
    "pipelineConfig": "{
        "Nodes": [
            {
                "Node Class Name": "RawImageInputNode",
                "Node Name": "Input",
                "Thread Number": "1",
                "Is Source Node": "true"
            },
            {
                "Node Class Name": "CPUJpegDecoderNode",
                "Node Name": "Decoder",
                "Thread Number": "1",
                "Is Source Node": "false"
            }, 
            {
                "Node Class Name": "LLOutputNode",
                "Node Name": "Output",
                "Thread Number": "1",
                "Is Source Node": "false",
                "Configure String": "BufferType=(STRING)String"
            }
        ],
        "Links": [
            {
                "Previous Node": "Input",
                "Previous Node Port": "0",
                "Next Node": "Decoder",
                "Next Node Port": "0"
            },
            {
                "Previous Node": "Decoder",
                "Previous Node Port": "0",
                "Next Node": "Output",
                "Next Node Port": "0"
            }
        ]
                }
    ",
    "suggestedWeight": "0",
    "mediaUri": [
        "{
            "image": "{someBase64Content}",
            "roi": [
                "0",
                "0",
                "0",
                "0"
            ]
            }
        "
    ]
}                      

```
### Response

***An example of Response JSON:***
```vim
{
  "result": [
    {
      "status_code": int, 
       "description": string,
       "roi_info": [
        "roi": [int, int, int, int],
        "feature_vector": string,
        "roi_class": string,
        "roi_score": float,
        "attribute": {
            "color": string
            "color_score": float,
            "type": string,
            "type_score": float
        }
      ]
    },
    …
  ]
}
```


|     Property name    |  Value  |  Description    |    Notes |
|--------------------|--------|------------------|------------------------------|
|        result    |     array |  Contains results    | Each result item matches one input mediaUri item, they have exactly same order.|
|result.status_code|int|Processing status for AI Inference Service.||
|result.description|string|Processing status descriptor generated from AI Inference Service.|Descriptive string such as `succeeded`, `noRoiDetected`, `Read or decode input media failed`|

<center> Table 2. Properties of Response in RESTful API. </center>


The following part only exist when output node is configured as
***LLOutputNode***.

|     Property name    |  Value  |  Description    |    Notes |
|--------------------|--------|------------------|------------------------------|
|result.roi_info|array|Results for every frame processed by executor. Only exist when status_code = 0.| |
|result.roi_info.roi|array|Define the detected bounding box, elements stand for [x, y, width, height] |  |   
|result.roi_info.roi_class|string|Predicted category of the detected bounding box.|   |
|result.roi_info.roi_score|float|Predicted confidence of the detected bounding box.|Value range: [0, 1.0]|         
|result.roi_info.feature_vector|string|Base64 encoded from int8 feature vector with 512 dimensions, for the detected bounding box.| Can be empty if no feature extraction node is configured.|
|result.roi_info.attribute|JSON structure|Contains two fields related to attribute prediction of color and type for the detected bounding box.| |
|result.roi_info.attribute.color|string|Predicted color category of the detected bounding box.|Can be empty if no attribute classification node is configured.|
|result.roi_info.attribute.color_score|float|Predicted confidence for color of the detected bounding box.|Value range: [0, 1.0]|
|result.roi_info.attribute.type|string|Predicted type category of the detected bounding box.|Can be empty if no attribute classification node is configured.|
|result.roi_info.attribute.type_score|float|Predicted confidence for type of the detected bounding box.|Value range: [0, 1.0]|


### Return Values

Upon completing the user requests, AI Inference Service will return one of the following three responses under different conditions.

-   200 OK

> AI Inference service will make such reply together with matched result in JSON in case of a successful request.

-   400 Bad Request

> This response normally implies an invalid http message or JSON structure within message body. Please ensure every JSON key-value pair exists and is correct.

-   500 Pipeline Error

> This response implies the request parameter "pipelineConfig" is invalid, so the service itself is unable to construct the specific pipeline.

## gRPC API

### Overview

***Request Syntax***
```vim
{
	"pipelineConfig": string,	
	"mediaUri": [string, string, ...],	
	"suggestedWeight": unsigned,	
	"target": string,	
	"jobHandle": string,
}
```
***Response Syntax***
```vim
{
	"status": int,
	"responses": map<string, Stream_Response>,
	"message": string
}
```
***Stream_Response Syntax***
```vim
{
	"jsonMessages": string,
	"binary": bytes
}
```
### Request
| Property Name | Value | Description | Notes |
|-----------------------|--|--|--|
|pipelineConfig|string|Contains the pipeline topology that server will execute.The syntax should follow HVA pipeline framework serialized pipeline format.Can be optional if field “jobHandle” is not None.| Serialized from a JSON structure|
|mediaUri|string|This field should contain the descriptor or the actual contents in inputs to the specified pipeline. The actual format depends on the input node within pipeline parsing this value.|Supported three different input types|
|suggestedWeight|unsigned|Optional, An unsigned integer value suggesting the workload of the specified pipeline.|Default as 0.|
|target|string|Process target. Default as “run”|Options: [load_pipeline, run, unload_pipeline]|
|jobHandle|string|Optional, to reuse job handle. The job handle can be initialized with calling target: load_pipeline.| |

<center> Table 3. Properties of Request in gRPC API. </center>

#### Process Targets

-   ***target: run***

    -   Call AI Inference service in an automatic mode, the request parameter field requires at least one of {"pipelineConfig", "jobHandle"}, besides "mediaUri".

    -   If the "pipelineConfig" field is given, the pipeline manager will try to build up AI workload according to the pipeline definition or reuse the existing free workload automatically.

    -   If the "jobHandle" field is given, the pipeline manager will run the defined pipeline on the specified AI workload with jobHandle. Note that the jobHandle should be the existing handle, which can be fetched through target: load_pipeline.

-   ***target: load_pipeline***

    -   The request parameter field requires at least "pipelineConfig". AI Inference service will only build up AI workload according to the pipeline definition, and then return the jobHandle back to the client.

-   ***target: unload_pipeline***

    -   The request parameter field requires at least "jobHandle". AI Inference service will destroy the specified workload according to the parameter: jobHandle.

    -   Note that the jobHandle should be the existing handle, which can be fetched through target: load_pipeline.

### Response

***Response Syntax***
```vim
{
	"status": int,
	"responses": map<string, Stream_Response>,
	"message": string
}
```
***Stream_Response Syntax***
```vim
{
	"jsonMessages": string,
	"binary": bytes
}
```
| Property Name |  Value |  Description | Notes |
|--|--|--|--|
| status | int |Processing status for AI Inference Service. |  |
|responses|int|Describes all information returned from service. Consists of a map list of Stream_Response|It is a placeholder, not actually being used in current release.|
|message|string|Contains all information returned from service, it is a serialized JSON format.|

<center> Table 4. Properties of Response in gRPC API. </center>

#### Response: message

This section describes the response schema for the property of ***message***. Depending on the process target field, the message contents of ***Response*** will vary accordingly. See details in the following sub-sections.

##### For process target: run

This section describes the response schema for the property of ***message***, when the process target is set as "run".

***JSON syntax of Response:***
```vim
{
"result": [
	{
		"status_code": int,
		"description": string,
		"roi_info": [
			"roi": [int, int, int, int],
			"media_birdview_roi":[float, float, float, float],
			"roi_class": string,
			"roi_score": float,
			"track_id": int,
			"track_status": string,
			"fusion_roi_state": [float, float, float, float],
			"fusion_roi_size": [float, float]
			],
		},
	]
}
```
***JSON example of Response:***
```vim
"result": [
	{
		"status_code": "0",
		"description": "succeeded",
		"roi_info": [
			{
				"roi": [
				"183",
				"289",
				"120",
				"47"],
				"media_birdview_roi": [
					"47.7461815",
					"-24.1595135",
					"0",
					"6.21190643"],
				"roi_class": "car",
				"roi_score": "0.88597869873046875",
				"track_id": "1",
				"track_status": "TRACKED",
				"fusion_roi_state": [
					"35.4933739",
					"-14.8774414",
					"-1.50079763",
					"0.622255564"],
				"fusion_roi_size": [
					"2.07573128",
					"1.70347154"],
				"latency": "36"
			}
		]
	}
]
```
 |Property Name|Value|Description|Notes|
 |--|--|--|--|
 |Result|array|Contains results corresponding to input mediaUri array|Each result item match one input mediaUri item, they have exactly same order.|
 |Result.status_code|int|Processing status for AI Inference Service.| |
 |Result.description|string|Processing status descriptor generated from AI Inference Service.|Some descriptive string, such as: “succeeded”, “noRoiDetected”, “Read or decode input media failed”|
|Result.roi_info|array|Results for every frame been processed by executor. Only exist when status_code = 0.| |
|Result.roi_info.roi|array|Define the detected bounding box, coordinate stands for: x, y, width, height.| |
|Result.roi_info.roi_class|string|Predicted category of the detected bounding box.| |
|Result.roi_info.roi_score|float|Predicted confidence of the detected bounding box.|Value range: [0, 1.0]|
|Result.roi_info.track_id|int|Object tracking index.| |
|Result.roi_info.track_status|string|Describe the tracking status.|Options: [DEAD, NEW, TRACKED, LOST]|
|Result.roi_info.media_birdview_roi|array|World coordinates (in format of [x, y, xSize, ySize]) corresponding to the bounding box detected by the camera.| |
|Result.roi_info.fusion_roi_state|array|Position and velocity information (in format of [x, y, vx, vy]) of the target detected by the radar.| |
|Result.roi_info.fusion_roi_size|array|The corresponding size(in format of [xSize, ySize]) of the target detected by radar in the x and y directions.| |
|Result.latency|int|Describe the latency. The unit is ms | |

<center> Table 5. Property of message in Response in gRPC API. </center>

##### For process target: load_pipeline

This section describes the response schema for the property of ***message***, when the calling target is set as "load_pipeline".

***JSON syntax of Response:***
```vim
{
	"description": "Success",
	"request": string,
	"handle": string,
}
```
***JSON example of Response:***
```vim
{
	"description": "Success",
	"request": "load_pipeline",
	"handle": "2147483648",
}
```
##### For process target: unload_pipeline

***JSON syntax of Response:***
```vim
{
	"description": "Success",
	"request": string,
	"handle": string,
}
```
***JSON example of Response:***
```vim
{
	"description": "Success",
	"request": "unload_pipeline",
	"handle": "2147483648",
}
```
## Status Code
|Status code|Description|
|--|--|
|1|Service succeeded but no detected ROI|
|0|Service succeeded|
|-1|Service failed due to invalid media format|
## 4.0 HVA Framework Pipeline Schema

### Pipeline Configure Schema

***JSON syntax:***

-   **Json syntax:**

```vim
{
  "Nodes": [
    "HVANode#1",
    "HVANode#2",
    "HVANode#3",
    ...
  ],
  "Links": [
    "HVANodeLink#1",
    "HVANodeLink#2",
    ...
  ]
}
```


-   **JSON syntax for HVANode:**

```vim
{
  "Node Class Name": "string",
  "Node Name": "string",
  "Thread Number": "unsigned",
  "Is Source Node": "boolean",
  "Configure String": "HVAConfigStr"
}

```

-   **JSON syntax for HVANodeLink:**

```vim
{
  "Previous Node": "HVANode#NodeClassName",
  "Previous Node Port": "unsigned",
  "Next Node": "HVANode#NodeClassName",
  "Next Node Port": "unsigned"
}
```


-   **JSON syntax for HVAConfigStr:**
```vim
"Key#1=(Type)Value#1;Key#2=(Type)Val#2..."
```

### Pipeline Configure Example

This section shows an example of pipeline configuration. The pipeline consumes images from local file input, decodes jpeg, and then returns the output to the client.
```vim
{
"Nodes": [
       {
            "Node Class Name": "LocalMediaInputNode",
            "Node Name": "Input",
            "Thread Number": "1",
            "Is Source Node": "true",
            "Configure String": "MediaType=(STRING)image;DataSource=(STRING)vehicle"*
       },
       {
            "Node Class Name": "CPUJpegDecoderNode",
            "Node Name": "Decoder",
            "Thread Number": "1",
            "Is Source Node": "false"
       },
       {
            "Node Class Name": "LLOutputNode",
            "Node Name": "Output",
            "Thread Number": "1",
            "Is Source Node": "false",
            "Configure String": "BufferType=(STRING)String"
        }
],
"Links": [
        {
            "Previous Node": "Input",
            "Previous Node Port": "0",
            "Next Node": "Decoder",
            "Next Node Port": "0"
        },
  {
            "Previous Node": "Decoder",
            "Previous Node Port": "0",
            "Next Node": "Output",
            "Next Node Port": "0"
        }
]
}
```

## libradar
The `libradar` is a set of APIs to get the range, doppler, angle, clustering and tracking results for each radar frames. The library does not include any memory allocation/deallocation, creation/destroy of a thread. This library is NOT thread-safe.Check the `src/test.cpp` for usage of this library.
There are 6 APIs in the `libradar` as follows:
```
RadarErrorCode radarGetMemSize(RadarParam* rp, ulong* sz);
```
Get the buffer required for the configuration specified by `RadarParam* rp`, the size will be set in `ulong* sz`. Return `R_SUCCESS` on success, otherwise check the `RadarErrorCode` for the error code.
```
RadarErrorCode radarInitHandle(RadarHandle** h, RadarParam* rp, void* buf, ulong sz);
```
Initialize a `RadarHandle` with the radar configuration specified by `RadarParam*` and the buffer with size of `sz` specified by `buf`. Return `R_SUCCESS` on success, otherwise check the `RadarErrorCode` for the error code.
```
RadarErrorCode radarDetection(RadarHandle* h, RadarCube* c, RadarPointClouds* r);
```
Run detection on the radar frame specified by `RadarCube*` with the radar handle specified by `RadarHandle`, the output is the `RadarPointClouds`.Return `R_SUCCESS` on success, otherwise check the `RadarErrorCode` for the error code.
```
RadarErrorCode radarClustering(RadarHandle* h, RadarPointClouds* rr, ClusteringResult* cc)
```
Run clustering on the `RadarPointClouds` , the result will be stored in `ClusteringResult*`. Return `R_SUCCESS` on success, otherwise check the `RadarErrorCode` for the error code.
```
RadarErrorCode radarTracking(RadarHandle* h, ClusteringResult* cr, TrackingResult* tr);
```
Run Kalman tracking analysis for the `ClusteringResult*`, the output will be stored in `TrackingResult*`.Return `R_SUCCESS` on success, otherwise check the `RadarErrorCode` for the error code.
```
RadarErrorCode radarDestroyHandle(RadarHandle* h)
```
Destroy the `RadarHandle*`. Return `R_SUCCESS` on success, otherwise check the `RadarErrorCode` for the error code.

