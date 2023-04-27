"""
Workbench for Basler array camera capturing. 
By Minghao, 2023 Feb
I actually prefer underscore names, but the sample codes are written in camel naming. I'll use camel.
"""

import os
import sys
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
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--cam_idx', type=int,
                        help='Camera index, required one.')
    parser.add_argument('-p', '--params', type=str, default='array_params.json',
                        help='The json file holding the array camera parameters.')
    parser.add_argument('-n', '--amount', type=int, default=45,
                        help='Frame amount to save, 0 for manual stop. Default 45 (about one sec).')
    parser.add_argument('--save_rgb', action='store_true',
                        help='Save converted RGB image')
#    parser.add_argument('--instant_save', action='store_true',
#                        help='Save while capturing, would probably lower fps.')
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
    # some parameters
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
    # converter to get opencv bgr format, if needed
    if args.save_rgb:
        converter = pylon.ImageFormatConverter()
        converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
    else:
        converter = None
    # open and initialize camera parameters
    cam.Open()
    setCamParams(cam, camParams, None)
    # use chunk grab mode
    enableChunk(cam)

    ### grab frames
    startTime = datetime.now()
    imgList, chunkDictList = chunkGrab(cam, args.amount, converter, camName)
    
    # save frames
    info('{} saving starts'.format(camName))
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

