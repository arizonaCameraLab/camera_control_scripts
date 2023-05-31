# Basler cameras Python script for config/livestream/capture

## Environment setup
The script has been tested on a Jetson AGX Orin Developer Kit with JetPack 5.0.1 (nvidia-l4t-core	34.1.1), an Intel x86-64 laptop with Ubuntu 22.04, and an Intel x86-64 desktop with USB expansion cards and Ubuntu 22.04.   
The array camera tested consists 1 Basler daa3840-45uc and 6 Basler daa3840-45um.

### Install Miniconda for package management
Follow [conda's document](https://docs.conda.io/en/latest/miniconda.html).

### Install Basler Pylon SDK
Follow [Pylon instruction](https://www.baslerweb.com/en/products/basler-pylon-camera-software-suite/)
and check [Pypylon GitHub repo](https://github.com/basler/pypylon).

### Create Basler conda environment
```
conda create -n basler python pip numpy scipy pillow h5py matplotlib
conda activate basler
conda install parallel -c conda-forge
pip install pypylon opencv-python
```
Note that for the laptop/desktop mentioned before, `matplotlib` has to be installed via `pip`. Otherwise, there will be errors during display.
I guess `opencv-python` installed via `pip` expects a certain version version of `pyqt5`, and if you install `matplotlib` via `conda`,
the `pyqt5` version would be different and won't work good.

For the desktop, a warning `ignoring XDG_SESSION_TYPE=wayland on Gnome. Use QT_QPA_PLATFORM=wayland to run on Wayland anyway` would popup when running display. That won't affect the functionality, but I didn't find a way to get rid of it.

## Usage
Increase USB buffer memory size. We chose 20G for safety (shouldn't need that much). Use code   
```
./init_env.sh
```   
For `ulimit` command, I also noticed `-p` for pipe size, and `-s` for stack size. Don't know whether these would help.   
It's also possible to make them in `/etc/rc.local`, which would run after booting.

Activate basler conda environment, and run `python array_cam_disp.py -h` or `python array_cam_cap.py -h`.
That should give you a brief helping information.

Both scripts retrieve camera configurations from a json file. It uses serial number (SN) as the camera key.
Make sure that the SN in the config file matches the physical cameras you want to control.

The array_cam_disp.py script supports real time parameter update during livestream. You can alter and save the config json file during livestream.

The `array_cam_cap.py` script can run multiple cameras simultaneously with GNU parallel. Run all 7 cameras only when on the desktop, where the USB expansion cards gives sufficient bandwidth. Otherwise, the cameras would jam.

When all frames are captured, it's better to scp/sftp to put them to lab desktop / UA HPC. Tried to compress the frames, but the compression ratio is not that good through. Directly transfer usually takes less time.

## TODO
Implement take-one-save-one strategy. Maxim has roughly tested it, got about 33 fps.   
Make a quick framerate examine script.    
Explore the reason why one-script function failed. Maxim tried to run multiple cameras within one Python script, but when the amount of cameras exceed 4, the program failed. Neither an InstantCameraArray nor a list of running cameras worked. Minghao's guess is the there's some resource limit upon one process. Maybe altering the Linux setting would help.

## Some experimental notes
2023Mar10: 7x100 12-bit raw frames would occupy 6.8GB. The RAM can hold it.   
2023Apr27: 7x450 12-bit raw frames nearly fill the 64GB memory of our desktop.   
2023May18: now switch to 8-bit. I think read and shot noise is stronger than quantization noise. With that, we can hold more frames.   
