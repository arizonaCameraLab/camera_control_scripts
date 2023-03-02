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
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--params', type=str, default='array_params.json',
                        help='The json file holding the array camera parameters.')
    parser.add_argument('-m', '--mode', type=str, default='disp',
                        help='Script mode. Choose from disp/grab, meaning display/grab')
    parser.add_argument('-n', '--amount', type=int, default=5,
                        help='Frame amount to save, 0 for manual stop. Default 5. Ignored when disp.')
    parser.add_argument('-f', '--folder', type=str, default='array_cap',
                        help='saving folder. Default \'array_cap\'. Create if not exist. Ignored when disp.')
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
    # if grabbing, use chunk
    if args.mode == 'grab':
        for cam in camList:
            enableChunk(cam)

    ### livestream cameras
    if args.mode == 'disp': 
        # the outer loop: switch between cameras
        camInd = 0
        while camInd >= 0:
            # the inner loop: grab, show, real-time configure
            camInd, arrayParams = singleCamlivestream(
                camList, arrayParamsLoader, converter, arrayParams, camInd, showHist=False)
    
    ### grabbing frames
    elif args.mode == 'grab':
        # grabbing loop
        print('Capture starts...')
        startTime = datetime.now()
        loopList = []
        for loopNum in range(args.amount):
            frameList = []
            for camInd, cam in enumerate(camList):
                camName = arrayParams[cam.GetDeviceInfo().GetSerialNumber()]['name']
                img, chunkDict = chunkGrabOne(cam, converter, camName)
                saveName = '{}_{}_{}'.format(loopNum, camInd, camName)
                frameList.append([img, chunkDict, saveName])
            loopList.append(frameList)
            
        # saving loop
        print('Saving starts...')
        folderName = args.folder + '_' + startTime.strftime(dateFormat)[:-4]
        for frameList in loopList:
            for img, chunkDict, saveName in frameList:
                saveChunkOne(img, chunkDict, folderName, saveName)
    
    #### bad mode
    else:
        error('Bad mode {}. Only {} modes are accepted'.format(args.mode, ('disp', 'grab')))
    
    ### cleanup
    # if grabbing, use chunk
    if args.mode == 'grab':
        for cam in camList:
            disableChunk(cam)
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

