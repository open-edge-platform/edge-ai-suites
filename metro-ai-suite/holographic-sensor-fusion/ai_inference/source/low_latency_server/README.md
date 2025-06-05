# Low Latency Server

## Dependencies

### dependencies within service itself

- libuv
  - v1.41.0
- spdlog
  - v1.8.2
- boost 
  - 1.75.0

### other dependencies introduced by nodes

#### image client sdk

- aws components: s3 and core
  - 1.8.55
- 

#### Jpeg Decoder

- KMB Stack
- Gstreamer
  - 1.16.0

#### Feature storage sdk

- thrift
  - v0.13.0

#### Detection and Feature Extraction

- KMB Stack

## Sample protocol 

### Sample input to trigger structuring pipeline

```json

{
    "pipelineConfig": "{\n    \"Nodes\": [\n        {\n            \"Node Class Name\": \"RawImageInputSourceNode\",\n            \"Node Name\": \"Input\",\n            \"Thread Number\": \"1\",\n            \"Is Source Node\": \"true\",\n            \"Configure String\": \"Mode=(STRING)MediaUri\"\n        },\n        {\n            \"Node Class Name\": \"JpegDecoderNode\",\n            \"Node Name\": \"Decoder\",\n            \"Thread Number\": \"1\",\n            \"Is Source Node\": \"false\"\n        },\n        {\n            \"Node Class Name\": \"DetectionNode\",\n            \"Node Name\": \"Detection\",\n            \"Thread Number\": \"1\",\n            \"Is Source Node\": \"false\",\n            \"Configure String\": \"ModelPath=(STRING)\/home\/hce-kmb-dev2\/models\/preint20210125-0605\/compiled-models\/yolo-v2-tiny-ava-0001.blob;InferReqNumber=(INT)1;Threshold=(FLOAT)0.61\"\n        },\n        {\n            \"Node Class Name\": \"FeatureExtractionNode\",\n            \"Node Name\": \"FeatureExtraction\",\n            \"Thread Number\": \"1\",\n            \"Is Source Node\": \"false\",\n            \"Configure String\": \"ModelPath=(STRING)\/home\/hce-kmb-dev2\/models\/test_reid_model_int8_U8U8.blob;InferReqNumber=(INT)2;Threshold=(FLOAT)0.1\"\n        },\n        {\n            \"Node Class Name\": \"LLResultSinkNode\",\n            \"Node Name\": \"Output\",\n            \"Thread Number\": \"1\",\n            \"Is Source Node\": \"false\",\n            \"Configure String\": \"HbaseAddr=(STRING)10.239.82.150;HbasePort=(INT)9090\"\n        }\n    ],\n    \"Links\": [\n        {\n            \"Previous Node\": \"Input\",\n            \"Previous Node Port\": \"0\",\n            \"Next Node\": \"Decoder\",\n            \"Next Node Port\": \"0\"\n        },\n        {\n            \"Previous Node\": \"Decoder\",\n            \"Previous Node Port\": \"0\",\n            \"Next Node\": \"Detection\",\n            \"Next Node Port\": \"0\"\n        },\n        {\n            \"Previous Node\": \"Detection\",\n            \"Previous Node Port\": \"0\",\n            \"Next Node\": \"FeatureExtraction\",\n            \"Next Node Port\": \"0\"\n        },\n        {\n            \"Previous Node\": \"FeatureExtraction\",\n            \"Previous Node Port\": \"0\",\n            \"Next Node\": \"Output\",\n            \"Next Node Port\": \"0\"\n        }\n    ]\n}\n",
    "suggestedWeight": "0",
    "mediaUri": [
        "17301039067beb7b0adf4a7baf1a35e279356fc3",
        "1730103912b7a65eab344e4986346cb688b51dfb",
        "1730103914c349049ab140f8bad7017d3d485eee",
        "17301039305fafaf84454bfda0ffbf7030a3791d",
        "17301039306058ec87974571990a379e7696d0fb",
        "17301039390eb8b013914c39b241b02bee6bff96",
        "173010393f5bb5286b9548e4ba46dff2d02170cb",
        "173010396a16f7ca3df4412daf87397597c7bdf3",
        "17301039a3546d2901514fa488cfb96452fdf3e5",
        "17301039a4166ee1b47446e1bded959342842293"
    ]
}

```

### Sample output from structuring pipeline

```json

{
    "result": [
        {
            "status_code": "0",
            "description": "succeeded"
        },
        {
            "status_code": "0",
            "description": "succeeded"
        },
        {
            "status_code": "0",
            "description": "succeeded"
        },
        {
            "status_code": "0",
            "description": "succeeded"
        },
        {
            "status_code": "0",
            "description": "succeeded"
        },
        {
            "status_code": "0",
            "description": "succeeded"
        },
        {
            "status_code": "0",
            "description": "succeeded"
        },
        {
            "status_code": "0",
            "description": "succeeded"
        },
        {
            "status_code": "0",
            "description": "succeeded"
        },
        {
            "status_code": "0",
            "description": "succeeded"
        }
    ]
}

```

### Sample input to trigger query pipeline

```json

{
   "pipelineConfig":"{\n    \"Nodes\": [\n        {\n            \"Node Class Name\": \"RawImageInputSourceNode\",\n            \"Node Name\": \"Input\",\n            \"Thread Number\": \"1\",\n            \"Is Source Node\": \"true\",\n            \"Configure String\": \"Mode=(STRING)Raw\"\n        },\n        {\n            \"Node Class Name\": \"JpegDecoderNode\",\n            \"Node Name\": \"Decoder\",\n            \"Thread Number\": \"1\",\n            \"Is Source Node\": \"false\"\n        },\n        {\n            \"Node Class Name\": \"DetectionNode\",\n            \"Node Name\": \"Detection\",\n            \"Thread Number\": \"1\",\n            \"Is Source Node\": \"false\",\n            \"Configure String\": \"ModelPath=(STRING)\/home\/hce-kmb-dev2\/models\/preint20210125-0605\/compiled-models\/yolo-v2-tiny-ava-0001.blob;InferReqNumber=(INT)2;Threshold=(FLOAT)0.61;MaxROI=(INT)1;IOUThreshold=(FLOAT)0.5\"\n        },\n        {\n            \"Node Class Name\": \"FeatureExtractionNode\",\n            \"Node Name\": \"FeatureExtraction\",\n            \"Thread Number\": \"1\",\n            \"Is Source Node\": \"false\",\n            \"Configure String\": \"ModelPath=(STRING)\/home\/hce-kmb-dev2\/models\/test_reid_model_int8_U8U8.blob;InferReqNumber=(INT)2;Threshold=(FLOAT)0.1\"\n        },\n        {\n            \"Node Class Name\": \"LLOutputNode\",\n            \"Node Name\": \"Output\",\n            \"Thread Number\": \"1\",\n            \"Is Source Node\": \"false\"\n        }\n    ],\n    \"Links\": [\n        {\n            \"Previous Node\": \"Input\",\n            \"Previous Node Port\": \"0\",\n            \"Next Node\": \"Decoder\",\n            \"Next Node Port\": \"0\"\n        },\n        {\n            \"Previous Node\": \"Decoder\",\n            \"Previous Node Port\": \"0\",\n            \"Next Node\": \"Detection\",\n            \"Next Node Port\": \"0\"\n        },\n        {\n            \"Previous Node\": \"Detection\",\n            \"Previous Node Port\": \"0\",\n            \"Next Node\": \"FeatureExtraction\",\n            \"Next Node Port\": \"0\"\n        },\n        {\n            \"Previous Node\": \"FeatureExtraction\",\n            \"Previous Node Port\": \"0\",\n            \"Next Node\": \"Output\",\n            \"Next Node Port\": \"0\"\n        }\n    ]\n}\n",
   "suggestedWeight":"0",
   "mediaUri":[
      "{\n    \"image\": \"\\\/9j\\\/4AAQSii****SOME*MORE*CONTENT****mA3kjB4pSzdAcZ70UUCP\\\/9k=\",\n    \"roi\": [\n        \"0\",\n        \"0\",\n        \"400\",\n        \"400\"\n    ]\n}\n",
      "{\n    \"image\": \"\\\/9j\\\/4AAQSkZ****SOME*MORE*CONTENT****AQEAYAB568DvTsrRRSGf\\\/9k=\",\n    \"roi\": [\n        \"0\",\n        \"0\",\n        \"400\",\n        \"400\"\n    ]\n}\n"
   ]
}

```

### Sample output from query pipeline

```json

{
    "result": [
        {
            "status_code": "0",
            "description": "succeeded",
            "roi_info": [
                {
                    "roi": [
                        "0",
                        "48",
                        "414",
                        "592"
                    ],
                    "feature_vector": "AANPAB0sCEgZBwEEBwAiHgIpAgUAJQAJBFFSYwFiAQcOAghIBQUEfREhFQkAAAEOQyt5AgsIEC07AQwyAAIBNzY\/YBVXCQgTUCYAAAA0BVNxBQARAAEBDwgvTS0cUQESCy0GRR8AAHcAFykGAAUhcQBccAIQA0AIAQASDRsAXAZYBCAAJiNYBnkAPQIADhQVIAABARcEAC4DBgIACAlfAi8HBDACNAUjDhIwACoFHyYASCAVCSkEAkgBBCcAdR4yMS4tAQQAExKuAAIFRwpqbh4AQE8AFBwvASsWBksBHgQKBAoAVgENKgACGgUBLwkBEAUFAgAjARQvdimqKwcibCoWixgzAS0BVgJoIAoFKiMSFGxHEQYASS5VGANAAigUEWMIDhsGAi4xLgRJAjENW2kEAkUBEQ5uCy4KDxkRMDQDAAUGAgNmNxsRAzNFVhUZSwczAABFZwAFAAoWAAAKOUt4OAg5A1MFAQAdHFMAVgQAGFMASxg5SDc9AAMGEAUACyUETgRYCZ8oXxUACQQCDVFvLXUCQgQaGAA8SiMXMAECAAEBOw0mOjJgNDA1AxspFyF8ODYiD3QsShMAASgEGwJCGCEALngERUcJVQYAAABUCDoAVhgAFAEDJB42HzYBLAseCikObgUZAwEDLCcSFwEAUBAABAUUVkJWBAJKACw="
                }
            ]
        },
        {
            "status_code": "0",
            "description": "succeeded",
            "roi_info": [
                {
                    "roi": [
                        "0",
                        "0",
                        "406",
                        "640"
                    ],
                    "feature_vector": "AANMAB8kBkUYBgIECAEgHgIjAgQAJQAHA0hSVwFbAQYOAghEBgMGdg8eFQUAAAEPPCdvAggHDyY2AQsvAAEBMjQ8WBRQCggPSiQAAAE0BVBpBQATAAEBCwgmSSkdSgAUBykEQhsAAHIAGCUEAAMeagBVaAEMAzgFAQASDhgAVgZVAiABHx1SBnEAOwEADxISHQABARkEAC0DBgIABwhZAikHBC0CLgMjERMrACYEGiMBPyMXCSYEAUEBBCoAbB0vMCsrAQQAFBKhAAIFQwpjYh0APEsAEhksASMTCEQCGAUMBAoATwMMKgACFwYBMAsBEQYFAwElARIraSegLQYhYiQXghoyAiUCVARkIQkEJBwRFmZDDwYARSdVGAM6AScXElwFDRUGAi4wJwQ\/AiwIV2AFATwBEgtjCigJDhcRKi0EAAQDAgNeLhoVAy1DUBUURwUyAAA8YAAFAAgXAAALNkdtMwcvA1AGAQAbFkcBSgMAGE8ASBM5QTQ3AAMGDgUADCQERwROC5EpWBQACQQCDk5tJm0DOQQVFAA6RB8TKQECAAEBOQ0kNidSLy4yBBopFiJuMi8kDmkmQREAASYEHQI+Ex4AJnEEPUQKVgUAAQBQCjYAVBcAEgECHxk0HioAKAwaBSgMZQcYAwEDKScQEwEAShMABQQUT0BRBANEACw="
                }
            ]
        }
    ]
}

```