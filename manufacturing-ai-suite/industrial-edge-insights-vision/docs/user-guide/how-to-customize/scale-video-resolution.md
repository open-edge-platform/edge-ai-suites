# Scale Video Resolution in Vision AI Detection Apps

You can scale the video resolution in the following scenarios:

- Optimize performance and capacity based on your requirements.
- Meet the input image requirements for Geti™ platform models.

In the **pipeline** section of the `pipeline-server-config.json` file, use the **videoscale** element to change the resolution of the video.

The following is a sample pipeline with image resizing using the **videoscale** element:

<!--hide_directive ::::{tab-set} hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **Pallet Defect Detection**
<!--hide_directive :sync: pallet-detect hide_directive-->

```text
"{auto_source} name=source ! decodebin ! videoscale ! video/x-raw, width=1920, height=1080 ! videoconvert ! gvadetect name=detection model-instance-id=inst0 ! queue ! gvawatermark ! gvafpscounter ! gvametaconvert add-empty-results=true name=metaconvert ! gvametapublish name=destination ! appsink name=appsink"
```

<!--hide_directive ::: hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
<!--hide_directive :sync: pcb-detect hide_directive-->

```text
"{auto_source} name=source ! decodebin ! videoscale ! video/x-raw, width=1920, height=1080 ! videoconvert ! gvaclassify name=classification model-instance-id=inst0 ! queue ! gvawatermark ! gvafpscounter ! gvametaconvert add-empty-results=true name=metaconvert ! gvametapublish name=destination ! appsink name=appsink"
```

<!--hide_directive
:::
::::
hide_directive-->

> **Note:**
> For details on the **videoscale** element, see the [GStreamer API Reference](https://gstreamer.freedesktop.org/documentation/videoconvertscale/videoscale.html?gi-language=c#videoscale-page).
