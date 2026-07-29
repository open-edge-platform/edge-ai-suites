# AI Inference Service API

This file describes the format and syntax that AI Inference Service exposes.


## RESTful API

  - **URL**:
  /run

  - **Method**:
  `POST`

  - **URL Params**:
  None

  - **Data Params**:
  Please refer the **Request Data Params** section.

  - **Success Response**:
    - HTTP Code: 200
    - Content:

      Please refer the **Response Data Params** section.

  - **Error Response**:
    - HTTP Code: 400
      This response normally implies an invalid http message or JSON structure within message body. Please ensure every JSON key-value pair are there and legal.
    &nbsp;

    OR
    &nbsp;

    - HTTP Code: 503
      This response implies the structuring service itself is not prepared or available at the moment.


## gRPC API

  - **proto**: ./source/low_latency_server/grpc_server/proto/ai_v1.proto

## Request Data Params
### Request Json Syntax 
```
{
  "pipelineConfig":  string,
  "mediaUri": [string, string, …],
  "suggestedWeight": unsigned,
  "streamNum": unsigned
}
```
### Parameter Fields
  - **pipelineConfig**: Contains the pipeline topology that server will execute. The syntax should follow HVA pipeline framework serialized pipeline format.
  ``` Example
  {
    "Nodes": [
        {
            "Node Class Name": "LocalMediaInputNode",
            "Node Name": "Input",
            "Thread Number": "1",
            "Is Source Node": "true",
            "Configure String": "some string"
        },
        {
            "Node Class Name": "OutputNode",
            "Node Name": "Output",
            "Thread Number": "1",
            "Is Source Node": "false"
        }
    ],
    "Links": [
        {
            "Previous Node": "Input",
            "Previous Node Port": "0",
            "Next Node": "Output",
            "Next Node Port": "0"
        }
    ]
  }
  ```
  - **mediaUri**: A list of input items. This field should contain the descriptor or the actual contents on inputs to pipeline specified. The actual format depends on the **InputNode** within pipeline parsing this value.
    - LocalMediaInputNode: 
    ```Example
    [
         "/path/to/media1",
         "/path/to/media2",
         "/path/to/media3",
    ]
    ```
    - RawImageInputNode:
    ```Example
    [
         {
             "image": someBase64Content,
             "roi": [int, int, int, int]
         },
         {
             "image": someBase64Content,
             "roi": [int, int, int, int]
         }
    ]
    ```
    - StorageImageInputNode/StorageVideoInputNode:
    ```Example
    [
         "173010393f5bb5286b9548e4ba46dff2d02170cb",
         "173010396a16f7ca3df4412daf87397597c7bdf3",
         "17301039a3546d2901514fa488cfb96452fdf3e5"
    ]
    ```
  - **suggestedWeight**: Optional. An unsigned integer value to suggest on the workload of the pipeline submitted.  
  - **streamNum**: Optional. An unsigned integer value to enable cross-stream inference on the workload of the pipeline submitted.  


## Response Data Params
The actual format depends on the **OutputNode** within pipeline parsing this value.

### LLOutputNode
**Low Latency Output Node**

Response Json Syntax
```
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
        "track_id": int,
        "track_status": string,
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

### LLResultSinkFileNode
**Local Output Node** save results to local output file: pipeline_results_yyyy-mm-dd-hh-mm-ss_\<timestamp\>/results.csv

Response Json Syntax
```
{
  "result": [
    { 
      "status_code": int,  
      "description": string, 
    },
    … 
  ] 
} 
```

### LLResultSinkNode
**Storage Output Node** save results to database. The database connection parameters should be configured via `environment-variable`, for example:
```
	export FeatureStorage_HBaseVehicleFeatureServerAddress="evi-hbase-hbase-master.smartedge-apps"
	export FeatureStorage_HBaseVehicleFeatureServerPort="9090"
	export FeatureStorage_RestControllerBaseUrl="evi-storage-rest.smartedge-apps"
```

Response Json Syntax
```
{
  "result": [
    { 
      "status_code": int,  
      "description": string, 
    },
    … 
  ] 
} 
```

### Parameter Fields
  - **status_code** indicates the status of service execution. Please refer the **Status Code Definition** section.
  - **description** describes the status.
  - **roi_info**
    - **roi**
    - **feature_vector** is in base64 format, the length is 512 bytes(int8).
    - **roi_class**
    - **roi_score**
    - **track_id (optional)**
    - **track_status (optional)**
    - **attribute**
      - **color**
      - **color_score**
      - **type**
      - **type_score**


## Status Code Definition

| Status Code | Description |
| ---         | ---         |
| -5          | Pipeline timeout |
| -4          | Service failed due to invalid media URI |
| -3          | Service failed due to invalid ROI |
| -2          | Service failed due to invalid image content |
| -1          | Service failed due to invalid media format |
| 0           | Service succeeded |
| 1           | Service succeeded but no detected ROI |
