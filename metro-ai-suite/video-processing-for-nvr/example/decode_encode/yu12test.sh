echo "Showing nv12 image and yu12 image"
ffmpeg -f rawvideo -pix_fmt yuv420p -s 720x480 -i out_720x480_yu12.yuv -frames:v 1 yu12.png
ffplay -f rawvideo -pixel_format nv12 -video_size 720x480 out_720x480_nv12.yuv
ffplay yu12.png

