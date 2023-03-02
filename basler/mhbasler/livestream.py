"""
Codes to display livestream of one camera
By Minghao, 2023 Mar

check the notes in __init__.py for some overall ideas.

Camera livestream logic:
A list of cameras are connected, but only one camera will be streaming at one time to save bandwidth.
Press number keys to switch displaying camera. Press esc to escape.
The camera configuration might change while the cameras livestreams, and that change should be applied in real time. Check camconfig.py for more information.
Two loops are applied. Outer loop switchs between cameras, only esc would break that loop. Inner loop keeps grabbing frames from one camera, esc and camera index can break that loop.
The ugly part is that real-time parameter change happens in the inner loop, thus we have to expose all camera and parameters to inner loop.

Known issue:

"""

#import os
#import sys
import logging
from logging import critical, error, info, warning, debug
#from datetime import datetime

#import numpy as np
import cv2 as cv

from pypylon import pylon, genicam

from .camconfig import configArrayIfParamChanges

########################################
### Camera livestream
########################################   
def opencvKeyWatcher(x, waitTime=1):
    """
    Return changed x if certain key is pressed
    Return original x if not pressed
    Currently only accept 0-6 and ESC (return as -1)
    """
    k = cv.waitKey(waitTime)
    if k < 0: # no input
        return x
    elif k == 27: # 27 for ESC
        return -1
    elif 48 <= k and k <= 54: # 48-57 for 0-9
        return int(k - 48)
    else:
        warning('Input not accepted. ESC to quit, and 0-6 for camera selection')
        return x
    
def singleCamlivestream(camList, arrayParamsLoader, converter, 
                        arrayParams, camInd, showHist=False):
    """
    Single camera livestream function. Including init, loop, and cleanup.
    The ugly part is that real-time parameter change happens in the inner loop, 
    thus we have to expose all camera and parameters to inner loop, 
    then return the updated arrayParams back to the outer loop.
    The nextCamInd returned to control camera switch
    """
    ### initializing
    cam = camList[camInd]
    nextCamInd = camInd
    camName = arrayParams[cam.GetDeviceInfo().GetSerialNumber()]['name']
    liveWindowName = 'cam{} '.format(camInd) + camName
    histWindowName = liveWindowName + ' histogram'
    cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
    
    ### Inner camera loop
    while cam.IsGrabbing():
        # Access the image data, convert
        grabResult = cam.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        if grabResult.GrabSucceeded():
            img = converter.Convert(grabResult).GetArray()
        grabResult.Release()
        debug('One frame grabbed.')
        
        # show image
        cv.namedWindow(liveWindowName, cv.WINDOW_NORMAL)
        cv.imshow(liveWindowName, img)
        debug('One frame shown.')
        # show histogram upon request
        if showHist:
            pass

        # refresh parameters if needed
        arrayParams = configArrayIfParamChanges(camList, arrayParamsLoader, arrayParams)

        # wait for keyboard input, change if needed
        nextCamInd = opencvKeyWatcher(nextCamInd)
        if nextCamInd == camInd: # no change, keep running
            continue
        else: # changed, break
            debug('Break from inner livestream loop, nextCamInd {}'.format(nextCamInd))
            break
            
    ### cleanup
    cam.StopGrabbing()
    cv.destroyAllWindows()
    return nextCamInd, arrayParams

