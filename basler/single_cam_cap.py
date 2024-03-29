"""
Codes to capture frames from one Basler camera
By Minghao, 2023 Mar

Camera capture logic:
A json file contains all the configurations needed for a camera array, which would be loaded to the cameras before capturing. Check mhbasler/camconfig.py for details.
The images and chunk data are saved at the same time.

Known issue:

"""

import os
import sys
import time
import argparse
import logging
from logging import critical, error, info, warning, debug
from datetime import datetime

import numpy as np
import cv2 as cv

from pypylon import pylon, genicam

from mhbasler.camconfig import jsonLoadFunc, RealTimeFileLoader
from mhbasler.camconfig import pickRequiredCameras, setCamParams
from mhbasler.grab import enableChunk, disableChunk, chunkGrab, saveChunkOne

########################################
### Argument parsing and logging setup
########################################
def parseArguments():
    """
    Read arguments from the command line
    """
    ### compose parser
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--cam_idx', type=int,
                        help='Camera index, required one.')
    parser.add_argument('-p', '--params', type=str, default='array_params.json',
                        help='The json file holding the array camera parameters.')
    parser.add_argument('-n', '--amount', type=int, default=45,
                        help='Frame amount to save, 0 for manual stop. ')
    parser.add_argument('-m', '--save_mode', type=str, choices=['raw', 'rgb', '4bit-left'], default='raw',
                        help='Save mode. 4bit-left would move 12-bit image left 4 bits, to 16-bit.')
#    parser.add_argument('--instant_save', action='store_true',
#                        help='Save while capturing, would probably lower fps.')
    parser.add_argument('--start_ns', type=int, default=0,
                        help='Capture starting Unix time in ns. Default 0 (instant start)')
    parser.add_argument('-f', '--folder', type=str, default=None,
                        help='saving folder. Default \'<camName>_<time>\'. Create if not exist')
    parser.add_argument('-v', '--verbose', type=int, default=1, 
                        help='Verbosity of logging: 0-critical, 1-error, 2-warning, 3-info, 4-debug')
    ### parse args
    args = parser.parse_args()
    ### set logging
    vTable = {0: logging.CRITICAL, 1: logging.ERROR, 2: logging.WARNING, 
              3: logging.INFO, 4: logging.DEBUG}
    logging.basicConfig(format='%(levelname)s: %(message)s', level=vTable[args.verbose], stream=sys.stdout)
    
    return args

########################################
### Main function
########################################
def main(args):
    ### Initialize
    # parse some parameters
    dateFormat = '%Y%m%d_%H%M%S.%f'
        
    # prepare parameter file
    arrayParamsLoader = RealTimeFileLoader(args.params, jsonLoadFunc)
    arrayParams = arrayParamsLoader.load()
    # pick the parameter of the camera needed. 
    # Note that only the first camera with correct index will be picked
    for sn in arrayParams.keys():
        if arrayParams[sn]['index'] == args.cam_idx:
            camParams = arrayParams[sn]
            info('Camera index {}, name {}, SN {}, is picked.'.format(camParams['index'], camParams['name'], sn))
            break
    assert ('camParams' in locals()), 'Camera with index {} not found'.format(args.cam_idx)
    singleCamArrayParams = {sn: camParams}
    camName = camParams['name']
    
    # pick required cameras
    tlFactory = pylon.TlFactory.GetInstance() # Get the transport layer factory.
    camList = pickRequiredCameras(tlFactory, singleCamArrayParams)
    cam = camList[0]
    
    # convert and scale parameters
    if args.save_mode == 'raw':
        converter = None
        leftShift = 0
    elif args.save_mode == 'rgb':
        converter = pylon.ImageFormatConverter()
        converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
        leftShift = 0
    elif args.save_mode == '4bit-left':
        converter = None
        leftShift = 4
    else:
        raise RuntimeError('save mode \'{}\' is not supported.'.format(args.save_mode))
        
    # open and initialize camera parameters
    cam.Open()
    setCamParams(cam, camParams, None)
    # use chunk grab mode
    enableChunk(cam)

    ### wait until the start time
    print('{} waiting'.format(camName))
    while time.time_ns() < args.start_ns:
        pass

    ### grab frames
    print('{} capturing starts'.format(camName))
    startTime = datetime.now()
    imgList, chunkDictList = chunkGrab(cam, args.amount, converter, leftShift, camName)
    
    # save frames
    print('{} saving starts'.format(camName))
    if args.folder is None:
        folderName = camName
    else:
        folderName = args.folder
    folderName = folderName + '_' + startTime.strftime(dateFormat)[:-4]
    for (idx, img), chunkDict in zip(enumerate(imgList), chunkDictList):
        saveChunkOne(img, chunkDict, folderName, '{:05d}'.format(idx))
    
    ### cleanup
    disableChunk(cam)
    cam.Close()


if __name__ == '__main__':
    args = parseArguments()
    main(args)

### Archived
#    nm = cam.GetInstantCameraNodeMap()
#    nList = nm.GetNodes()
#    for n in nList:
#        print(n.GetNode().GetName())

