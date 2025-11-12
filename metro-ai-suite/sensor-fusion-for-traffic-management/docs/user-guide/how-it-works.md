
# How It Works

This reference implementation enables the development of a high-performance, Intel-based® Intelligent Traffic Solution. The end-to-end pipeline of this software reference implementation includes the following major workloads, as shown in the following figure:

- Dataset loading and data format conversion
- Lidar signal processing
- Video analytics
- Data fusion
- Visualization


Each pipeline is deployed on a single Intel® SoC processor, providing the necessary heterogeneous compute capabilities from Intel Core™ processors and integrated GPU. The implementation includes video analytics optimized by the Intel® Distribution of OpenVINO™ Toolkit, radar/lidar signal processing accelerated by Intel® oneAPI, data fusion, and visualization. Key performance indicators, such as throughput and processing latency, significantly surpass current market standards. To maximize performance on Intel® processors, we optimized this SW RI using Intel software toolkits and open-source libraries.

![Case-C+L](./_images/Case-C+L.png)
<center>Use case: C+L Pipeline</center>

Following are the four demo configurations. Please refer to the [Get Started Guide](./Get-Started-Guide.md) for more instructions on deploying services on bare metal.

## Demo for 2C+1L

![Demo-2C1L](./_images/Demo-2C1L.png)
<center>Use case #1: 2C+1L running on Intel® Core™ Ultra 7 265H </center>

## Demo for 4C+2L

![Demo-4C2L](./_images/Demo-4C2L.png)
<center>Use case #2: 4C+2L running on Intel® Core™ Ultra 7 265H </center>

## Demo for 12C+2L

![Demo-12C2L](./_images/Demo-12C2L.png)
<center>Use case #3: 12C+2L running on Intel® Core™ i7-13700 and Intel® B580 Graphics </center>

## Demo for 8C+4L

![Demo-8C4L](./_images/Demo-8C4L.png)

<center>Use case #4: 8C+4L running on Intel® Core™ i7-13700 and Intel® B580 Graphics </center>









