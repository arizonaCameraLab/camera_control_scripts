"""
Workbench for Basler array camera capturing. 
By Minghao, 2023 Feb
I actually prefer underscore names, but the sample codes are written in camel naming. I'll use camel.
"""

import os
import warnings
import argparse
import time
from datetime import datetime
import json

import numpy as np
import cv2 as cv

from pypylon import pylon, genicam

### parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('-p', '--params', type=str, default='array_params.json',
                    help='The json file holding the array camera parameters.')
parser.add_argument('-m', '--mode', type=str, default='disp',
                    help='Script mode. Choose from disp/grab/dryrun, meaning display/grab/neither')
parser.add_argument('-n', '--amount', type=int, default=5,
                    help='Frame amount to save, 0 for manual stop. Default 5. Ignored when disp/dryrun.')
parser.add_argument('-f', '--folder', type=str, default='array_cap',
                    help='saving folder. Default \'array_cap\'. Create if not exist. Ignored when disp/dryrun.')
parser.add_argument('--window_width', type=int, default=1280,
                    help='Display window width in pixels. Positive. Default 1280')
parser.add_argument('--verbose', action='store_true', help='verbose mode, Would print more camera informations')
args = parser.parse_args()

### Load array parameters
with open(args.params, 'r') as fp:
    arrayParams = json.load(fp)

### enumerate cameras
# Get the transport layer factory.
tlFactory = pylon.TlFactory.GetInstance()

# Get all attached devices and exit application if no device is found.
diList = tlFactory.EnumerateDevices() # device info list
if len(diList) == 0:
    raise pylon.RuntimeException('No camera present.')

# retrive the serial numbers of devices
# for all accessible properties, check 
# https://docs.baslerweb.com/pylonapi/cpp/class_pylon_1_1_c_device_info
devSnList = []
for di in diList:
    if di.IsSerialNumberAvailable():
        devSnList.append(di.GetSerialNumber())
    else:
        raise pylon.RuntimeException('One {} camera\'s SN is not available.'.format(di.GetModelName()))

# validate and sort required devices
sortedDiList = ['' for _ in arrayParams.keys()]
for reqSn in arrayParams.keys():
    if not reqSn in devSnList:
        raise pylon.RuntimeException('Device with SN {} is required by array but not attached.'.format(reqSn))
    sortedDiList[arrayParams[reqSn]['index']] \
        = diList[devSnList.index(reqSn)]

### Create Instant Camera objects and adjust parameters
# these adjustable parameters are properties defined in Node maps
# check 
camList = [] # instant camera list
for di in sortedDiList:
    camList.append(pylon.InstantCamera(tlFactory.CreateDevice(di)))

for cam in camList:
    params = arrayParams[cam.GetDeviceInfo().GetSerialNumber()]
    cam.Open()
    cam.ExposureTime.SetValue(float(params['ExposureTime']))
    cam.Gain.SetValue(float(params['Gain']))
    # Need to validate offset and size, skipped here
    cam.OffsetX.SetValue(int(params['OffsetX']))
    cam.OffsetY.SetValue(int(params['OffsetY']))
    cam.Width.SetValue(int(params['Width']))
    cam.Height.SetValue(int(params['Height']))
    if params['rot180']:
        cam.ReverseX.SetValue(True)
        cam.ReverseY.SetValue(True)
    else:
        cam.ReverseX.SetValue(False)
        cam.ReverseY.SetValue(False)
    # need to set pixel format, skipped here
    if args.verbose:
        print(
            'Set camera {} (SN: {}): \n'.format(\
            params['name'], cam.GetDeviceInfo().GetSerialNumber()) \
            + 'Exposure: {}us \n'.format(cam.ExposureTime.GetValue()) \
            + 'Gain: {} \n'.format(cam.Gain.GetValue()) \
            + 'Offset X, Y: {}, {} \n'.format(cam.OffsetX.GetValue(), 
                                              cam.OffsetY.GetValue()) \
            + 'Width, height: {}, {} \n'.format(cam.Width.GetValue(), 
                                                cam.Height.GetValue()) \
            + 'Reverse X, Y: {}, {} \n'.format(cam.ReverseX.GetValue(), 
                                               cam.ReverseY.GetValue()) \
            + 'Pixel format: {} \n'.format(cam.PixelFormat.GetValue())
            )

for cam in camList:
    cam.Close()

### Archived
#    nm = cam.GetInstantCameraNodeMap()
#    nList = nm.GetNodes()
#    for n in nList:
#        print(n.GetNode().GetName())

