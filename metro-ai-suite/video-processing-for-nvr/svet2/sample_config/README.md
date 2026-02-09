# SVET sample configuration files 

## How to use these configuration files?
After buiding the svet_app, you can find the "svet_app" binary under folder build.
before running svet_app, switch to root user and run "init 3" because VPPSDK uses
drm display which requies root access and there is no X server running at the same
time.

su -p
init 3

To run with one configration file under svet folder:
./build/svet_app load sample_config/basic/1dec1disp.txt

If you see error message that can't find library libgroupsock.so, you need to run
bellow command:

export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH

you'd better to add this command to your .bashrc under /root

If you run svet_app in other folders, you need to copy the 1080p.h264/h265 to that
folder or you can modify the configuraton file and replace 1080p.h264/h265 with
the full path of your test clips.

## What do the options mean in configuration file
Please refer to chapter 3 in user guide
 
## How to generate configuraton file with dozens of decoding streams?
For multiple decode and display use cases, you can use the configuration file generation
tool under svet_app/tool. 

For example, below command generate configuration file for 2x2 decode on first 1080p display
and 4x4 decode on second 4K display. The path of test clips are listed in urls.txt. 

./build/tool/ConfigGen --output=out.txt  \
        display0 --row-count=2 --column-count=2 --width=1920 --height=1080 --file=urls.txt \
        display1 --row-count=4 --column-count=4 --width=3840 --height=2160 --file=urls.txt

If urls.txt only contains the path of one clip:

$cat urls.txt
1080p.h265

It will be used for all decode input.

 
## Brief summary of each configuration file 


### Configuration files under folder basic
1dec1disp60.txt			1 decode + 1 display stream + 1 1080p@60 video layer and display
1dec1disp_nosfc.txt		1 decode + 1 display stream + 1 1080p@30 video layer and display, SFC is disabled explicitly
1dec1disp.txt		 	1 decode + 1 display stream + 1 1080p@30 video layer and display 	
1dec1pp1disp_denoise.txt        1 decode + 1 pp task(enabled denoise) + 1 display stream + 1 1080p@30 video layer and display
1dec1pp1disp.txt		1 decode + 1 pp task + 1 display stream + 1 1080p@30 video layer and display
1h2651disp.txt			1 H265 decode + 1 display stream + 1 1080p@30 video layer and display
1jpegdec1disp.txt		1 JPEG decode + 1 display stream + 1 1080p@30 video layer and display
30seconds_1dec1disp.txt		1 decode + 1 display stream + 1 1080p@30 video layer and display. The above configuraton files ends with a command stop after running 8 seconds. This one ends with a command stop after running 30 seconds. It enable the -l option in newdec that loops the input clips.
show_displays.txt		List the connected displays. User need to use the value in column  "display id" in for option "--dispid" of command newvl. If there is only one display connected, "--dispid" shall be 0. If there is two displays connected, "--dispid" can be 0 or 1 

### Configuration files under folder decode 
1dec1disp_outputsize.txt	1 decode + 1 display stream + 1 1080p@30 video layer and display. SFC is enabled to do scaling after decoding. The output size of SFC is specified by "--decW" and "--decH"

### Configuration files under folder dynamic_ctrl 
decctrl.txt			2 decode + 2 display stream + 1 1080p@30 video layer and display. After running 5 seconds, remove the first decode stream, then run for 3 seconds and stop
decnew_remove.txt		2 decode + 2 display stream + 1 1080p@30 video layer and display. After running 7 seconds, add third decode and display stream, then runs for 5 seconds. Remove first decode, runs for 3 seconds and stop. 
decnew.txt			2 decode + 2 display stream + 1 1080p@30 video layer and display. After running 5 seconds, add third decode and display stream, then runs for 8 seconds.
decremove_new.txt		2 decode + 2 display stream + 1 1080p@30 video layer and display. After running 7 seconds, remove first decode and runs for 3 seconds. Then add third decode and display stream, runs for 5 seconds and stop.
dispchctrl.txt			2 decode + 2 display stream + 1 1080p@30 video layer and display. After running 6 seconds, hide first display stream. After 3 seconds, show the first display stream. Then pause the first stream and resume after 3 seconds. Zoomin the area(200, 200, 176x128) of first display stream. Then zoom out after 3 seconds.
dispch_hideshow.txt		Hide/show display stream test 
dispch_pause_resume.txt		Pause/Resume display stream test
dispch_zoom.txt			Zoomin/Zoom out display stream test

### Configuration files under folder error_handle 
inputfilenotfound.txt		Error handling test for wrong path of input clip
wrongdeccodec.txt		Error handling test for setting wrong codec

### Configuration files under folder multiview 
16_16_16dec_3disp4k.txt		3 4K@30 displays. Each display runs workload 16 decode + 16 display stream and 1 4k@30 videolayer
16_16dec_2disp4k.txt		2 4K@30 displays. Each display runs workload 16 decode + 16 display stream and 1 4k@30 videolayer
16_4dec_2disp4k.txt		16 decode + 16 display stream + 1 4k@30 videolayer on first 4k@30 display, 4 decode + 4 display stream + 1 4k@30 videolayer on second 4k@30 display
16dec_4kdisp.txt		16 decode + 16 display stream + 1 4k@30 videolayer on 4K@30 display
2dec1disp_h265.txt		2 h265 decode + 2 display stream + 1 1080p@30 video layer on 1080p@30 display
2dec1disp.txt			2 h264 decode + 2 display stream + 1 1080p@30 video layer on 1080p@30 display
2dec_2disp.txt			1 1080p@60 display + 1 4K@30 display. Each display runs workload 1 decode + 1 display stream + 1 1080p@30 video layer
2dec2pp1disp.txt		2 decode + 2 pp + 2 display stream + 1 1080p@30 video layer on 1080p@30 display
3dec1disp.txt			3 decode + 3 display stream + 1 1080p@30 video layer on 1080p@30 display
4_4dec_2disp4k.txt		2 4K@30 displays. Each display runs workload 4 decode + 4 display stream + 1 4k@30 videolayer on 4K@30 display
4dec1disp4k.txt			4 decode + 4 display stream + 1 4k@30 videolayer on 4K@30 display
4dec1disp.txt			4 decode + 4 display stream + 1 1080p@30 videolayer on 1080p@60 display
4dec_2disp.txt			2 decode + 2 display stream + 1 1080p@30 videolayer on 1080p@30 display. And 2 decode + 2 display stream + 1 4k@30 videolayer on 4k@30 display. 
4dec4pp1disp.txt		4 decode + 4 pp + 4 display stream + 1 1080p@30 videolayer on 1080p@30 display
6_4dec_2disp4k.txta		4 decode + 4 display stream + 1 4k@30 videolayer on 4K@30 display. And 2 decode + 2 display stream + 1 4k@30 videolayer on 4K@30 display
8dec_2disp.txt			2 4k displays. Each display runs workload  4 decode + 4 display stream + 1 4k@30 videolayer

### Configuration files under folder rtsp 
1rtsp1disp_h265.txt		1 h265 rtsp decode + 1 display stream + 1 1080p@30 video layer on 1080p@30 display
1rtsp1disp_save.txt 		1 h265 rtsp decode + 1 display stream + 1 1080p@30 video layer on 1080p@30 display. The input rtsp stream is saved to local file.
1rtsp1disp.txt			1 h265 rtsp decode + 1 display stream + 1 1080p@30 video layer on 1080p@30 display
2rtsp1disp.txt			2 h265 rtsp decode + 2 display stream + 1 1080p@30 video layer on 1080p@30 display
12rtspdec_4kdisp.txt		12 h264 rtsp decode + 12 display stream + 1 4Kp@30 video layer on 3840x2160@30 display
4rtsp_1disp_1hour.txt		4 h264 rtsp decode + 4 display stream + 1 1080p@30 video layer on 1080p@60 display. Run for 1 hour before stop.
4rtsp_1disp_h265.txt		4 h265 rtsp decode + 4 display stream + 1 1080p@30 video layer on 1080p@60 display.
8dec_4kdisp.txt			8 h264 rtsp decode + 8 display stream + 1 4Kp@30 video layer on 3840x2160@30 display

