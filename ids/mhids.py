#===========================================================================#
#                                                                           #
#  Copyright (C) 2006 - 2018                                                #
#  IDS Imaging Development Systems GmbH                                     #
#  Dimbacher Str. 6-8                                                       #
#  D-74182 Obersulm, Germany                                                #
#                                                                           #
#  The information in this document is subject to change without notice     #
#  and should not be construed as a commitment by IDS Imaging Development   #
#  Systems GmbH. IDS Imaging Development Systems GmbH does not assume any   #
#  responsibility for any errors that may appear in this document.          #
#                                                                           #
#  This document, or source code, is provided solely as an example          #
#  of how to utilize IDS software libraries in a sample application.        #
#  IDS Imaging Development Systems GmbH does not assume any responsibility  #
#  for the use or reliability of any portion of this document or the        #
#  described software.                                                      #
#                                                                           #
#  General permission to copy or modify, but not for profit, is hereby      #
#  granted, provided that the above copyright notice is included and        #
#  reference made to the fact that reproduction privileges were granted     #
#  by IDS Imaging Development Systems GmbH.                                 #
#                                                                           #
#  IDS Imaging Development Systems GmbH cannot assume any responsibility    #
#  for the use or misuse of any portion of this software for other than     #
#  its intended diagnostic purpose in calibrating and testing IDS           #
#  manufactured cameras and software.                                       #
#                                                                           #
#===========================================================================#

# Developer Note: I tried to let it as simple as possible.
# Therefore there are no functions asking for the newest driver software or freeing memory beforehand, etc.
# The sole purpose of this program is to show one of the simplest ways to interact with an IDS camera via the uEye API.
# (XS cameras are not supported)

# Modified by Minghao, from UArizona, 2022May02, for livestream and image capture

#---------------------------------------------------------------------------------------------------------------------------------------

#Libraries
import cv2
import sys
import ctypes
import warnings
import time
import json
from datetime import datetime
from argparse import ArgumentParser

import numpy as np
from pyueye import ueye
# need ctypes as this is just a wrapper, and all parameter types needs to be set manually
# learned from https://gist.github.com/dddomodossola/fe0099df1a91674abf88de8f56ac7350

#---------------------------------------------------------------------------------------------------------------------------------------
# Arguments
parser = ArgumentParser(description="Livestream and capture script for IDS UI-3590LE-C-HQ camera.")
# general arguments
parser.add_argument('--device', type=int, default=0,
                    help='Camera ID, 0 for first available camera, 1-254 for specific camera ID')
parser.add_argument('--mode', type=str, default='livestream',
                    help='Script mode. Choose from livestream/capture/both/dryrun')
# capture argument
parser.add_argument("--exposure", type=float, default=100,
                    help='Exposure time in ms. Actual working exposure time may be slightly different due to limited time resolution.')
parser.add_argument("--gain", type=int, default=0,
                    help='Hardware gain level, intfrom 0-100.')
parser.add_argument('--delay_per_frame', type=int, default=None, 
                    help='delay after capturing one frame to avoid duplicate capture, in ms. Default 10.')
parser.add_argument("--framerate", type=float, default=20,
                    help='NOT IMPLEMENTED.')
parser.add_argument('--aoi', type=str, default=None, 
                    help='NOT IMPLEMENTED. Area Of Interest, format as "X,Y,W,H", where X,Y are the coordinate of AOI\'s top-left corner, and W,H are the AOI\'s width and height.')
parser.add_argument('--color_mode', type=str, default='RAW10', 
                    help='NOT IMPLEMENTED.')
# saving arguments
parser.add_argument("--amount", type=int, default=1,
                    help='Frame amount to save, 0 for manual stop. Ignored when livestream.')
parser.add_argument("--prefix", type=str, default=None,
                    help='Saving file prefix. Ignored when livestream or dryrun.')
parser.add_argument('--no_preview', dest='save_preview', action='store_false',
                    help='Do not save final preview .png image.')
parser.add_argument('--write_png_frames', dest='write_png_frames', action='store_true',
                    help='Save all frames as png.')
# livestream arguments
parser.add_argument("--livestream_scale", type=float, default=None,
                    help='Scale livestream frame to fit windows.')
# parse arguments
args = parser.parse_args()

#---------------------------------------------------------------------------------------------------------------------------------------
# Variables and parsed arguments
hCam = ueye.HIDS(args.device)
sInfo = ueye.SENSORINFO()
cInfo = ueye.CAMINFO()
pcImageMemory = ueye.c_mem_p()
MemID = ueye.int()
rectAOI = ueye.IS_RECT()
pitch = ueye.INT()
# Set color mode
if args.color_mode == "RAW10":
    m_nColorMode = ueye.IS_CM_SENSOR_RAW10
    nBitsPerPixel = ueye.INT(16)
    channels = ueye.INT(1)
else:
    raise RuntimeError("Bad color_mode: {}".format(args.color_mode))
bytes_per_pixel = int(nBitsPerPixel / 8)
# Parse mode
if args.mode=='livestream':
    amount = 0
    show_livestream = True
    save_frames = False
elif args.mode=='capture':
    amount = args.amount
    show_livestream = False
    save_frames= True
elif args.mode=='both':
    amount = args.amount
    show_livestream = True
    save_frames= True
elif args.mode=='dryrun':
    amount = args.amount
    show_livestream = False
    save_frames= False
else:
    raise RuntimeError("Bad mode: {}".format(args.mode))
# parse amount
if amount==0:
    amount = np.inf
# parse scale
if args.livestream_scale is None:
    ls_scale = 0.25
else:
    ls_scale = args.livestream_scale
# parse delay
if args.delay_per_frame is None:
    if show_livestream:
        delay_per_frame = 0
    else:
        delay_per_frame = 30
else:
    delay_per_frame = args.delay_per_frame

#---------------------------------------------------------------------------------------------------------------------------------------
# Startup
print("START")
print()

# Starts the driver and establishes the connection to the camera
nRet = ueye.is_InitCamera(hCam, None)
if nRet != ueye.IS_SUCCESS:
    print("is_InitCamera ERROR")

# Reads out the data hard-coded in the non-volatile camera memory and writes it to the data structure that cInfo points to
nRet = ueye.is_GetCameraInfo(hCam, cInfo)
if nRet != ueye.IS_SUCCESS:
    print("is_GetCameraInfo ERROR")

# Check camera module
nRet = ueye.is_GetSensorInfo(hCam, sInfo)
if nRet != ueye.IS_SUCCESS:
    print("is_GetSensorInfo ERROR")
if not sInfo.strSensorName.decode('utf-8')=='UI359xLE-C':
    warnings.warn("This script is specifically written for IDS UI-3590LE-C-HQ camera. Apply on other camera may introduce error.")

nRet = ueye.is_ResetToDefault(hCam)
if nRet != ueye.IS_SUCCESS:
    print("is_ResetToDefault ERROR")

# Set display mode to DIB
nRet = ueye.is_SetDisplayMode(hCam, ueye.IS_SET_DM_DIB)

# Set exposure and gain
exp_value = ctypes.c_double(args.exposure)
ueye.is_Exposure(hCam, ueye.IS_EXPOSURE_CMD_SET_EXPOSURE, exp_value, ctypes.sizeof(exp_value))
gain = ueye.INT(args.gain)
ueye.is_SetGainBoost(hCam, ueye.IS_SET_GAINBOOST_OFF)
ueye.is_SetHardwareGain(hCam, gain, gain, gain, gain)

# Can be used to set the size and position of an "area of interest"(AOI) within an image
nRet = ueye.is_AOI(hCam, ueye.IS_AOI_IMAGE_GET_AOI, rectAOI, ueye.sizeof(rectAOI))
if nRet != ueye.IS_SUCCESS:
    print("is_AOI ERROR")
width = rectAOI.s32Width
height = rectAOI.s32Height

#---------------------------------------------------------------------------------------------------------------------------------------
# Capture preparation

# Allocates an image memory for an image having its dimensions defined by width and height and its color depth defined by nBitsPerPixel
nRet = ueye.is_AllocImageMem(hCam, width, height, nBitsPerPixel, pcImageMemory, MemID)
if nRet != ueye.IS_SUCCESS:
    print("is_AllocImageMem ERROR")
else:
    # Makes the specified image memory the active memory
    nRet = ueye.is_SetImageMem(hCam, pcImageMemory, MemID)
    if nRet != ueye.IS_SUCCESS:
        print("is_SetImageMem ERROR")
    else:
        # Set the desired color mode
        nRet = ueye.is_SetColorMode(hCam, m_nColorMode)

# Activates the camera's live video mode (free run mode)
nRet = ueye.is_CaptureVideo(hCam, ueye.IS_DONT_WAIT)
if nRet != ueye.IS_SUCCESS:
    print("is_CaptureVideo ERROR")

# Enables the queue mode for existing image memory sequences
nRet = ueye.is_InquireImageMem(hCam, pcImageMemory, MemID, width, height, nBitsPerPixel, pitch)
if nRet != ueye.IS_SUCCESS:
    print("is_InquireImageMem ERROR")
else:
    print("Press q to leave the programm")

# prepare saving file name
suffix = datetime.now().strftime("%Y%m%d-%H%M%S.%f")
if args.prefix is None:
    save_name = suffix
else:
    save_name = '_'.join([args.prefix, suffix])

# prepare saving list
if save_frames:
    frame_list = []

# Prepare some sensor and capture informations
report_dict = {}
report_dict['camera model'] = sInfo.strSensorName.decode('utf-8')
report_dict['camera serial No.'] = cInfo.SerNo.decode('utf-8')
report_dict['frame wh'] = (int(width), int(height))
report_dict['color_mode'] = args.color_mode
if save_frames:
    report_dict['clip name'] = save_name+'.raw'
else:
    report_dict['clip name'] = None
# SHOULD ADD frame rate and aoi

# Prints out some information about the camera and the sensor
for k in report_dict.keys():
    print("{}: {}".format(k, report_dict[k]))
print()

#---------------------------------------------------------------------------------------------------------------------------------------

# Continuous capture and display loop
frame_count = 0
start_time = time.time()
while(nRet == ueye.IS_SUCCESS):
    # print(frame_count)
    # In order to capture an image we need to...
    # ...extract the data of our image memory
    array = ueye.get_data(pcImageMemory, width, height, nBitsPerPixel, pitch, copy=save_frames)
    # ...reshape it in an numpy array...
    frame = np.reshape(array, (height.value, width.value, bytes_per_pixel))
    
    # In order to display the image in an OpenCV window we need to...
    if show_livestream:
        # ...scale it to proper value range...
        if args.color_mode=='RAW10':
            frame = frame.astype(np.uint16)
            frame = frame[:,:,1]*256 + frame[:,:,0]
            frame = frame.astype(np.float32)/1023.0
        # ...resize the image by a quater...
        frame = cv2.resize(frame, (0,0), fx=ls_scale, fy=ls_scale)
        #...and finally display it
        cv2.imshow("mhids_livestream_window", frame)
    
    # To save frame...
    if save_frames:
        frame_list.append(frame)
    
    # accumulate frame count
    frame_count += 1
    print(frame_count)
    
    # Press q if you want to end the loop
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    # If enough frames are collected, end the loop
    if frame_count >= amount:
        break
        
    # delay some time to avoid duplicate capture
    time.sleep(delay_per_frame/1000)

#---------------------------------------------------------------------------------------------------------------------------------------
# Post process

# Add some other information
end_time = time.time()
elapsed_time = end_time - start_time
real_fps = frame_count / elapsed_time
report_dict['amount'] = frame_count
report_dict['real_fps'] = real_fps

# Releases an image memory that was allocated using is_AllocImageMem() and removes it from the driver management
ueye.is_FreeImageMem(hCam, pcImageMemory, MemID)

# Disables the hCam camera handle and releases the data structures and memory areas taken up by the uEye camera
ueye.is_ExitCamera(hCam)

# Destroys the OpenCv windows
cv2.destroyAllWindows()

# Prints out some information about the camera and the sensor
for k in report_dict.keys():
    print("{}: {}".format(k, report_dict[k]))
print()

# Save frames, preview, and meta data
print("Saving...")
if save_frames:
    with open(save_name+'.raw', 'wb') as fio:
        for a, frame in enumerate(frame_list):
            if args.color_mode=="RAW10":
                frame = frame.astype(np.uint16)
                frame = frame[..., 1]*256 + frame[..., 0]
            if args.write_png_frames:
                cv2.imwrite(save_name+'_{:03d}.png'.format(a), (frame//4).astype(np.uint8))
            fio.write(frame.tobytes())
    if args.save_preview:
        if args.color_mode=="RAW10":
            frame = (frame//4).astype(np.uint8)
        cv2.imwrite(save_name+'.png', frame)
with open(save_name+'.json', 'w') as fp:
    json.dump(report_dict, fp, indent=4)

print("END")
