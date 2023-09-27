The remote control script allows you to control a 16-camera array, controlled by 4 Jetson nanos, from a control machine.

## Prerequisites:
 - Each Jetson nano has the proper setup indicated in the `nano_arducam_setup.sh` script, including: 
   - required system packages installed, especially `v4l-utils libv4l-dev python3-pip ntp ntpdate`
   - required pip3 packages installed, meaning the `v4l2-fix`
   - Arducam v4l2 driver installed
   - the `Arducam_example` folder in the repo is in the `Desktop` folder
   - the scripts in the `Arducam_example/remote_control_scripts/camera_side` folder has a copy in the `~/` folder
   - the `displayer.py` and `capture.py` function properly
 - For the control machine:
   - It can ssh to all the 4 Jetson nanos, passwordlessly
   - It has configured the 4 Jetson nanos as Host cam1, cam2, cam3, cam4 within the `.ssh/config` file, and allows X11Forwarding
   - It has all the scripts in the `Arducam_example/remote_control_scripts/control_machine_side` folder
   - There are `cam1`, `cam2`, `cam3`, `cam4` folders in `~/Downloads` folder

## Test the system
On the control machine, open a terminal, go to the folder containing the scripts, run    
```
quad_stream.sh
```
You should be able to see 4 livestream windows. Enter y in the terminal to quit. Don't force quit!

## Camera daemon capture scheme explained
For continous remote capture, we adopt a daemon scheme, which means: 
 1. We first start a camera daemon on a Jetson nano, which will initialize and open the camera, and make the camera in waiting status. The camera is ready to capture a frame upon a trigger signal.
 2. When we want to capture a frame, we send a trigger signal to the daemon, and the daemon will capture one frame, save that frame, and keep the camera in waiting status.
 3. After we finish all captures, we can stop the camera daemon, which will close the camera.

With the daemon scheme, we don't need to initialize the camera every time we capture. That makes our capture fast. Also, the daemon response to the trigger fast, gives better synchronization.

## Run remote capture
 1. Make sure all Jetsons have their camera available. If another program, like `displayer.py`, is using the camera, then the daemon won't start.
 2. On the control machine, run `bash start_cam.sh`, which will start the camera daemon on all 4 Jetson Nanos.
 3. On the control machine, run `bash capture_a_frame.sh`. That script will trigger a burst shot on all 4 Jetson Nanos. `bash capture_a_frame.sh` takes one argument, which is the output file prefix. You can also manually change the `-e` argument within the script for exposure, and `-n` argument for the amount of bursts.
 4. After all captures are finished, on the control machine, run `transfer_data.sh`, which will transfer the capture frames to the control machine's `~/Downloads/camX` folder, and delete the frames on the Jetson Nanos. `transfer_data.sh` takes one argument, which is the frame file's prefix, should be the same as the one speficied in step 3.
 5. After all frames are saved, on the control machine, run `close_cam.sh`, which will stop the daemons on all 4 Jetson Nanos.
