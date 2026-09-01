[![License](https://img.shields.io/badge/License-Apache%202.0-blue)]()
[![Metro-AI-Suite](https://img.shields.io/badge/Metro%20AI%20Suite-3%20Samples-green)]()
[![Manufacturing-AI-Suite](https://img.shields.io/badge/Manufacturing%20AI%20Suite-8%20Samples-green)]()
[![Retail-AI-Suite](https://img.shields.io/badge/Retail%20AI%20Suite-4%20Samples-green)]()

# Edge-AI-Suites

**Edge AI Suites** are collections of Intel-optimized open source AI software development kits
(SDKs), microservices, libraries, and sample applications intended to demonstrate
the applicability and efficiency of Intel hardware in industry-specific edge AI use cases.

The suites will help you develop your custom AI solutions, offering:
* Curated sample applications to use as reference for developing own edge AI solutions
* Optimized code for AI, media, and end-to-end workloads
* Benchmarks and deployment guides

## Suites and Use Cases

* [The Metro AI Suite](metro-ai-suite) accelerates the development of solutions for Edge AI video, safety and security, smart city and transportation use cases.

* [The Manufacturing AI Suite](manufacturing-ai-suite) enhances output quality and volume with automated defect detection, asset tracking, software-defined controls, and other capabilities, empowering smart factories with Vision, Time Series and Generative AI capabilities.

* [The Retail AI Suite](retail-ai-suite) accelerates hardware decisions for Retail AI workloads at the edge, featuring use cases such as self-checkout and loss prevention.

* [The Robotics AI Suite](robotics-ai-suite) provides ready to use samples leveraging AI to help solve common robotics problems such as perception, navigation, simulation, and planning.

* [The Education AI Suite](education-ai-suite) is a collection of education-focused AI applications, libraries, and benchmarking tools to help developers build solutions faster.

* [The Health And Life Sciences AI Suite](health-and-life-sciences-ai-suite) is a solution for supporting the healthcare field with AI software tools covering a wide range of monitoring and analysis features.


## Contribute

Read the [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on submitting issues and pull requests.

## Community and Support

For support, submit your bug report and feature request to [Github Issues](https://github.com/open-edge-platform/edge-ai-suites/issues).

## License

The **Edge AI Suites** project is licensed under the [APACHE 2.0](LICENSE), except for the following sample applications:

| Sample Application                                                                | License                  |
|:----------------------------------------------------------------------------------|:-------------------------|
|[Smart Intersection](metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection) | [LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE AGREEMENT](metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/LICENSE.txt) |

## Third-Party

Applications in this repository which are based on third-party content are:

| Sample Application                                              | Third-Party Application                                  |
|:----------------------------------------------------------------|:---------------------------------------------------------|
|[ACT Sample](robotics-ai-suite/pipelines/act-sample)             | [ACT](https://github.com/tonyzhaozh/act)                 |
|[ORB-SLAM3 Sample](robotics-ai-suite/pipelines/orb-slam3-sample) | [ORB-SLAM3](https://github.com/UZ-SLAMLab/ORB_SLAM3.git) |

## Intended Use

Applications developed in this repository, unless stated otherwise, are intended for reference
and demonstration purposes, not for production environments.
Certain features, such as authentication, TLS termination, and external access controls are
assumed to be covered at the infrastructure level.

For more information, refer to the
[Notes on Usage](https://docs.openedgeplatform.intel.com/dev/OEP-articles/notes-on-usage.html)
document.
