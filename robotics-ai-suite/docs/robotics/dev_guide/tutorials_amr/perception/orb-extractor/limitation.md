# GPU ORB Extractor Limitation

1. To use the multiple camera images feature on a single orb-extractor feature object, all input images must have the same width and height.
2. For different-sized images, create a separate orb-extractor feature object for each image. Spawn a new thread for concurrent execution.

## Troubleshooting

If a segmentation fault occurs, follow these steps:

```bash
# Confirm whether the GPU driver is loaded
lsmod | grep i915

# Add the current user to the render group
sudo usermod -a -G render <userName>
```
