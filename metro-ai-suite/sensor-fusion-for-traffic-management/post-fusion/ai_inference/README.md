# EVI AI Inference Service

## Overview

AI Inference Service is a streaming media analytics microservice, it provides RESTful APIs to users to support different media processing pipelines. Based on HVA framework, pipeline topology JSON files are used to create complex media analytics pipelines through user requests. HVA pipeline framework, named from heterogeneous video analytic pipeline framework, is a lightweight library that helps developers from building, managing, and controlling an service/application that executes in a manner of pipelines. The main functions includes: media decoding, object detection, vehicle attribute recognition, feature extraction, multi-objects tracking, etc..

Figure below depicts AI service architecture
[![AI-service-architecture](../../../docs/images/AI-service-architecture-standalone.png)](../../../docs/images/AI-service-architecture-standalone.png)

## Target System Requirements
* Debian 12.0.0
* supported hardware: Intel® Xeon® Processor, Intel® Core™ processor and Intel® Arc™ Graphics

## Running EVI AI Inference Service with Docker

### Pulling the docker images

``` shell.bash
docker pull intel/ai-inference-cpu:evi-2.0.0
```

### Starting the EVI AI Inference Service

#### For evi-2.0.0 release

``` shell.bash
docker run -tid -p 50051:50051 intel/ai-inference-cpu:evi-2.0.0 "/opt/run_service.sh"
```

#### For evi-3.0.0 release (Coming soon)

``` shell.bash
docker run -tid -p 50051:50051 intel/ai-inference-cpu:evi-3.0.0 "/opt/run_service.sh"
```

### Testing the service

Create a json file as restful api parameter

``` shell.bash
vi params.json
```

Edit the json file with content like [params.json](../../../docs/images/cpuLocalImageTest.json) for evi-2.0.0 or [params.json](../../../docs/images/cpuLocalImageTestNew.json) for later evi release.

Run the curl command to send inference request to EVI inference servcie

``` shell.bash
curl -X POST http://127.0.0.1:50051/run  --user-agent "User-Agent: Boost.Beast/306" --header "Content-Type: application/json" -d @params.json
```

EVI Inference Service is working if you get response below:

``` json
{
    "result": [
        {
            "status_code": "0",
            "description": "succeeded",
            "roi_info": [
                {
                    "roi": [
                        "801",
                        "170",
                        "407",
                        "520"
                    ],
                    "feature_vector": "\/vUFC\/rz2e34CvYSAAAAEfD+CAkyHQPq8APy\/wnhDwIM+fwKHOv56egAAeX9xwQJAwYQ+QHyEff3\/d4CARAHDhn\/8RwAExT07vcP6BvlDAIS5QkE\/gUK9CYN8Qch8t3f5\/oD\/B39+gAB\/esi5un45u72+Nnl5An\/Bwf1HfQL7AAC9PPpBOgbLOAQ\/+b1\/gQOCvv4B\/YnDxDw+Bfaz\/sK8e\/1D\/UQ9wrSF+n8Gt4XDAfMCfULGyMHAPL+CAkC+94p2\/TpA\/4aFhAT9N0j8f7+5vcICRv++ffrJf776xHl8+76FgYLGxgM8QMT4vwY5\/QCBw8B\/AjyJ+z9CfUGDfAKC\/7n\/uwPA\/3y+gQC+e7l\/Aga\/uMA9AjvEvQSDwTiRfr0E\/3VFP\/+Dw4IAALdDgkz8+McBwT69gID\/BL4E+sV+AUZ8QYLCALr2\/r16gEC+Of84\/4o9BHkFfsBB\/z3BwPlCAkL+QIB+BAFBB4BL9jqFAb+Ae8I\/Qrb9P4P8QD74\/oSBf4d\/vYKAR0A8hUEDwkUCP\/xBPgUCO31\/SMIAfP59hYN\/AEA6PsE3RUXDAbx4vL+BP\/8Jwnt+Pb37vnvFv8OBvjr+fj9\/vAH\/wHoEiEHEfkcAvzr\/vcMBQrn\/wT9BhAQICoVHBAIAuTvB9QEBxgE5RT5CwAF0g0GC+UM\/vT4Kx0=",
                    "roi_class": "vehicle",
                    "roi_score": "0.99949359893798828",
                    "attribute": {
                        "color": "white",
                        "color_score": "0.999999642",
                        "type": "car",
                        "type_score": "0.998976469"
                    }
                },
                {
                    "roi": [
                        "124",
                        "0",
                        "370",
                        "392"
                    ],
                    "feature_vector": "HgwIFeoE5OYZEPLn\/A3\/Awj3AwL9GQMGDPf\/\/wvm+\/wY8gsAAfYN8ff8B9X+q\/sOCxAF\/RffBOrx+uT4FAjwCREABRbmDf4B\/vUcDREoDAfpBvUR\/v0M4BML7Nv38Bfx\/gAH4hAADgDmB\/wp9wYA6gsG+fvS5hz6DxP7E+sK9APy9vnuCeMhI\/ISAej6I\/82++7zGQ71Bgj+CwPiygT+DAr\/KwL5\/AjzJQQY+dgm\/wfr5A\/w8ir7AwcE\/Afs+Q0J9P\/5BvodCysE\/A0U6vz37gMHHP\/++vIHDPsV\/vnt5ez\/7vgG+fEBDjH83+gz5Nbu8x3zI+EGA\/0CBSUaDfX4B\/r55gkCEuHw3\/P\/+ernC\/jW5+UL\/\/YX+AwsBBIsBwr1\/xrsCAIaDQgNEw8N8AMd7vcDFOL59vgG2xQNBvAL+\/4P7gbi\/xL6IQn6CQrw5\/MYDAsJ+ArqGf0MCRL2+wzsGAIE7RP0ChsAGRoCBObvAAEDBvbtD+L69wwG\/OftAAP4CQwUAQMD+hH\/9fUSGgUD4wf7\/hAJCAEO+RIV8+QD9x4F7ur5C\/8G7xcfDgoP+PsNAwrhHf4WCPL8Df7x7gft+e\/zAAv19+n37w\/2\/QbjEuMqAgYTCwERFQo67hb9Bx7\/JhL54wwUJxDpAfL2+BcD+RYXCAL85Cr78hn7BRT4BwU=",
                    "roi_class": "vehicle",
                    "roi_score": "0.98814117908477783",
                    "attribute": {
                        "color": "white",
                        "color_score": "0.999962687",
                        "type": "van",
                        "type_score": "0.993178844"
                    }
                }
            ]
        }
    ]
}
```

## EVI AI Inference Service APIs

See details in file [InferenceServiceAPIDesign.md](InferenceServiceAPIDesign.md).
