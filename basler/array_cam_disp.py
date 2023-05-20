"""
Codes to display livestreams from a Basler camera array, one camera at a time
By Minghao, 2023 Mar

Camera display logic:
A json file contains all the configurations needed for a camera array, which would be loaded to the cameras before capturing. Check mhbasler/camconfig.py for details.
One camera run at a time.
The livestream and pixel value histogram can all be displayed.

Known issue:
The window sizes of the livestream and histogram are default. Need adjustment every time it appears.
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
from mhbasler.livestream import singleCamlivestream
from mhbasler.grab import enableChunk, disableChunk, chunkGrabOne, saveChunkOne

########################################
### Argument parsing and logging setup
########################################
def parseArguments():
    """
    Read arguments from the command line
    """
    ### compose parser
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-p', '--params', type=str, default='array_params.json',
                        help='The json file holding the array camera parameters.')
    parser.add_argument('--no_hist', dest='show_hist', action='store_false',
                        help='Disable pixel value histogram.')
    parser.add_argument('--bins', type=int, default=50,
                        help='Histogram bin amount.')
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
    # pick required cameras
    tlFactory = pylon.TlFactory.GetInstance() # Get the transport layer factory.
    camList = pickRequiredCameras(tlFactory, arrayParams)
    # converter to get opencv bgr format
    converter = pylon.ImageFormatConverter()
    converter.OutputPixelFormat = pylon.PixelType_BGR8packed
    converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
    # open and initialize camera parameters
    for cam in camList:
        cam.Open()
        params = arrayParams[cam.GetDeviceInfo().GetSerialNumber()]
        setCamParams(cam, params, None)

    ### livestream cameras
    # the outer loop: switch between cameras
    camInd = 0
    while camInd >= 0:
        # the inner loop: grab, show, real-time configure
        camInd, arrayParams = singleCamlivestream(
            camList, arrayParamsLoader, converter, 
            arrayParams, camInd, 
            args.show_hist, args.bins)
    
    ### cleanup
    # close cameras
    for cam in camList:
        cam.Close()


if __name__ == '__main__':
    args = parseArguments()
    main(args)

### Archived
#    nm = cam.GetInstantCameraNodeMap()
#    nList = nm.GetNodes()
#    for n in nList:
#        print(n.GetNode().GetName())

