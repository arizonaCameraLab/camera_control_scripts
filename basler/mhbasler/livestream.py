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

Acknoledgement:
histogram part largely learned from 
https://github.com/nrsyed/computer-vision/blob/master/real_time_histogram/real_time_histogram.py. 
The original one is not working, though. I fixed it following 
https://www.geeksforgeeks.org/how-to-update-a-plot-on-same-figure-during-the-loop/
"""

import time
import logging
from logging import critical, error, info, warning, debug

import numpy as np
import cv2 as cv
import matplotlib.pyplot as plt

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

def initHist(bins, lw=3, alpha=0.5):
    plt.ion() # enable GUI event loop
    fig, ax = plt.subplots()
    ax.set_title('Histogram (RGB)')
    ax.set_xlabel('Bin')
    ax.set_ylabel('Frequency')
    lineR, = ax.plot(np.arange(bins), np.zeros((bins,)), c='r', lw=lw, alpha=alpha, label='Red')
    lineG, = ax.plot(np.arange(bins), np.zeros((bins,)), c='g', lw=lw, alpha=alpha, label='Green')
    lineB, = ax.plot(np.arange(bins), np.zeros((bins,)), c='b', lw=lw, alpha=alpha, label='Blue')
    ax.set_xlim(0, bins-1)
    ax.set_ylim(0, 1)
    ax.legend()
    return fig, ax, lineR, lineG, lineB
    
def dispHist(frame, bins, fig, ax, lineR, lineG, lineB):
    # calculate histogram
    numPixels = np.prod(frame.shape[:2])
    (r, g, b) = cv.split(frame)
    histogramR = cv.calcHist([r], [0], None, [bins], [0, 255]) / numPixels
    histogramG = cv.calcHist([g], [0], None, [bins], [0, 255]) / numPixels
    histogramB = cv.calcHist([b], [0], None, [bins], [0, 255]) / numPixels
    # update data value
    lineR.set_ydata(histogramR)
    lineG.set_ydata(histogramG)
    lineB.set_ydata(histogramB)
    ax.set_ylim(0, max([histogramR.max(), histogramG.max(), histogramB.max()]))
    # update value and run GUI event
    fig.canvas.draw()
    fig.canvas.flush_events()
    return
    
def singleCamlivestream(camList, arrayParamsLoader, converter, 
                        arrayParams, camInd, 
                        showHist, bins):
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
    if showHist:
        fig, ax, lineR, lineG, lineB = initHist(bins)
    
    ### Inner camera loop
    frameCount = 0
    FPS_AVG_GAP = 20
    grabTime0 = time.time_ns()
    print('Note that display fps is usually slow and unstable comparing to pure capture.')
    while cam.IsGrabbing():    
        # Access the image data, convert
        grabResult = cam.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        if grabResult.GrabSucceeded():
            img = converter.Convert(grabResult).GetArray()
        grabResult.Release()
        debug('One frame grabbed.')
        frameCount += 1
        
        # show image
        cv.namedWindow(liveWindowName, cv.WINDOW_NORMAL)
        cv.imshow(liveWindowName, img)
        debug('One frame shown.')
        # show histogram upon request
        if showHist:
            dispHist(img, bins, fig, ax, lineR, lineG, lineB)

        # refresh parameters if needed
        arrayParams = configArrayIfParamChanges(camList, arrayParamsLoader, arrayParams)

        # timing and show fps every 10 frames
        if frameCount % FPS_AVG_GAP == 0:
            grabTime1 = time.time_ns()
            print('{:d} frames grabbed, \t display fps {:.2f} '.format(frameCount, 1e9/(grabTime1-grabTime0)*FPS_AVG_GAP), end='\r')
            grabTime0 = grabTime1

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
    plt.close('all')
    print('\nLivestream ends.')
    return nextCamInd, arrayParams

