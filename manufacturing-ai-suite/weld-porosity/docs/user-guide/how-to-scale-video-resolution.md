# How to Scale Video Resolution

You can scale the video resolution in the following scenarios:
-  Optimize performance and capacity based on your requirements.
-  Meet the input image requirements for Intel® Geti™ platform models.

In the **pipeline** section of the **config.json** file, use the **videoscale** element to change the resolution of the video. 

The following is a sample pipeline with image resizing using the **videoscale** element:

         "{auto_source} name=source ! decodebin ! videoscale ! video/x-raw, width=1920,height=1080 ! videoconvert ! gvaclassify inference-region=full-frame name=classification ! queue ! gvawatermark ! gvafpscounter ! gvametaconvert add-empty-results=true name=metaconvert ! appsink name=destination"

> **Note**
> For details on the **videoscale** element, see the [GStreamer API Reference](https://gstreamer.freedesktop.org/documentation/videoconvertscale/videoscale.html?gi-language=c#videoscale-page).


