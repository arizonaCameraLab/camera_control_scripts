# Basler cameras Python script for config/livestream/capture

## Environment setup
The script has been tested on Jetson AGX Orin Developer Kit with JetPack 5.0.1 (nvidia-l4t-core	34.1.1) and an Intel x86-64 laptop with Ubuntu 22.04.   
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
pip install pypylon opencv-python
```
Note that for the laptop mentioned before, `matplotlib` has to be installed via `pip`. Otherwise, there will be errors during display. 
I guess `opencv-python` installed via `pip` expects a certain version version of `pyqt5`, and if you install `matplotlib` via `conda`, 
the `pyqt5` version would be different and won't work good.

## Usage
Activate basler conda environment, and run `python basler_array.py -h`. 
That should give you a brief helping information.

The script retrieves camera configurations from a json file. It uses serial number (SN) as the camera key. 
Make sure that the SN in the config file matches the physical cameras you want to control. 

The script supports real time parameter update during livestream. You can alter and save the config json file during livestream.

## Some experimental notes
2023Mar10: 7x100 12-bit raw frames would occupy 6.8GB. The RAM can hold it.
