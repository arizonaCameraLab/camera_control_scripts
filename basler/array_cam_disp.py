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

import sys
sys.path.append('/home/dbg/Desktop/camera_control_scripts/target_workbench')
import os
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
from target_toolbox.aruco_marker import ARUCO_DICT_TYPE

########################################
### Argument parsing and logging setup
########################################
def parseArguments():
    """
    Read arguments from the command line
    """
    ### compose parser
    parser = argparse.ArgumentParser(prog='Array camera display',
                 description='Display livestreams from a Basler camera array, one camera at a time',
                 epilog='Accept following keyboard inputs to the livestream window: ' + \
                        '0-6 to select camera; ' + \
                        's to save snapshot (with overlays); ' + \
                        'f to save frame (no overlays); ' + \
                        'ESC to quit.', 
                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-p', '--params', type=str, default='array_params.json',
                        help='The json file holding the array camera parameters.')
    parser.add_argument('--fps', dest='show_fps', action='store_true',
                        help='Enable livestream fps display.')
    parser.add_argument('--aruco', dest='detect_aruco', action='store_true',
                        help='Enable ArUco marker detection')
    parser.add_argument('--sine', dest='detect_aruco_sine', action='store_true',
                        help='Enable ArUco-Sine chart detection')
    parser.add_argument('--sine_params', type=str, default='aruco_sine_chart_params.json',
                        help='The json file holding the ArUco-Sine chart parameters.')
    parser.add_argument('--hist', dest='show_hist', action='store_true',
                        help='Enable pixel value histogram.')
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
    # converter to get opencv bgr/grayscale format
    converter = pylon.ImageFormatConverter()
    if args.detect_aruco_sine: # detect grayscale for better resolution analysis
        converter.OutputPixelFormat = pylon.PixelType_Mono8
    else:
        converter.OutputPixelFormat = pylon.PixelType_BGR8packed
    converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
    # open and initialize camera parameters
    for cam in camList:
        cam.Open()
        params = arrayParams[cam.GetDeviceInfo().GetSerialNumber()]
        setCamParams(cam, params, None)
    # histogram parameters
    hist_bins = None
    if args.show_hist:
        hist_bins = args.bins
    # ArUco detector parameters
    aruco_detector = None
    if args.detect_aruco or args.detect_aruco_sine:
        aruco_parameter = cv.aruco.DetectorParameters()
        aruco_dict = cv.aruco.getPredefinedDictionary(ARUCO_DICT_TYPE)
        aruco_detector = cv.aruco.ArucoDetector(aruco_dict, aruco_parameter)
    # ArUco-Sine detection parameters
    arucoSineMetas = None
    if args.detect_aruco_sine:
        sineParamsLoader = RealTimeFileLoader(args.sine_params, jsonLoadFunc)
        arucoSineMetas = sineParamsLoader.load()

    ### livestream cameras
    # the outer loop: switch between cameras
    camInd = 0
    while camInd >= 0:
        # the inner loop: grab, show, real-time configure
        camInd, arrayParams = singleCamlivestream(
            camList, arrayParamsLoader, converter,
            arrayParams, camInd,
            hist_bins, aruco_detector, 
            args.show_fps, arucoSineMetas)

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
