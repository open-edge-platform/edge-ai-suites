# USB Cameras

USB cameras are ubiquitous in computer vision use cases.

Often, you will be using a USB camera that follows the USB Video Class (UVC) standard.
Plug into any USB port and they're recognized by the Linux `uvcvideo` driver without custom kernel modules. 
They offer the simplest bring-up of any camera interface, making them ideal for quick prototyping and add-on vision.

Some USB cameras require vendor-specific drivers to take full advantage, such as RealSense.

## Supported Cameras

```{include} fragment_camera_table_usb.md
```


:::{toctree}
:hidden:

RealSense <realsense>
:::
