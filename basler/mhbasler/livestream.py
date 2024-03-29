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

import sys
sys.path.append('/home/dbg/Desktop/camera_control_scripts/target_workbench')
import time
from datetime import datetime
import logging
from logging import critical, error, info, warning, debug

import numpy as np
import cv2 as cv
import matplotlib.pyplot as plt

from pypylon import pylon, genicam

from .camconfig import configArrayIfParamChanges
from target_toolbox.aruco_marker import draw_aruco_square_score, draw_aruco_coordinate
from target_toolbox.aruco_sine_chart import extract_sine_and_bw_tiles, estimate_comm_diff_from_bw_tile, \
                                            estimate_mtf_from_sine_tile, find_sine_corner_list, \
                                            draw_sine_block_outline_and_mtf

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
    elif k == 102: # 102 for f, frame grab
        return 'f'
    elif k == 115: # 115 for s, snap shot
        return 's'
    else:
        warning('Input not accepted. ESC to quit, 0-6 for camera selection, s for snapshot, f for frame grab')
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
                        histBins=None,
                        arucoDetector=None,
                        showFps=False, 
                        arucoSineMetas=None
                       ):
    """
    Single camera livestream function. Including init, loop, and cleanup.
    The ugly part is that real-time parameter change happens in the inner loop,
        thus we have to expose all camera and parameters to inner loop,
        then return the updated arrayParams back to the outer loop.
    The nextCamInd returned to control camera switch
        histBins denotes the numbers of bins when showing histogram.
    If None, no hisograms will be shown
        arucoDetector detects the Aruco markers and labels it on the image.
    If None, not going to detect ArUco markers
    If showFps, image count and fps would not only printed in terminal,
        but also displayed at the frames top-left corner
    If arucoSineMetas is not None, the program would try to find ArUco-Sine chart,
        and calculate the MTF if we found any fronto-parallel. Note that
        that should be dict of meta dicts, the key being ArUco index
    """
    ### initializing
    # camera
    cam = camList[camInd]
    nextCamInd = camInd
    camName = arrayParams[cam.GetDeviceInfo().GetSerialNumber()]['name']
    liveWindowName = 'cam{} '.format(camInd) + camName
    cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
    # histogram window
    if histBins is not None:
        histWindowName = liveWindowName + ' histogram'
        fig, ax, lineR, lineG, lineB = initHist(histBins)
    # arucoSineMetas
    if arucoSineMetas is not None:
        assert arucoDetector is not None, 'ArUco-Sine charts needs a arucoDetector'
        arucoSineIdxList = list(arucoSineMetas.keys())
        #print(arucoSineIdxList)
    # other args
    dateFormat = '%Y%m%d_%H%M%S.%f'

    ### Inner camera loop
    frameCount = 0
    fps = 0
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

        # timing and show fps every 10 frames
        if frameCount % FPS_AVG_GAP == 0:
            grabTime1 = time.time_ns()
            fps = 1e9/(grabTime1-grabTime0)*FPS_AVG_GAP
            print('{:d} frames grabbed, \t display fps {:.2f} '.format(frameCount, fps), end='\r')
            grabTime0 = grabTime1

        ### add overlays to image
        dispImg = np.copy(img)
        if len(dispImg.shape) == 2: # if grayscale, to RGB for better text drawing
            dispImg = cv.cvtColor(dispImg, cv.COLOR_GRAY2BGR)
            
        # fps
        if showFps:
            h, w, _ = dispImg.shape
            fpsStr = 'Frame {:d}, fps {:.2f}'.format(frameCount, fps)
            cv.putText(dispImg, fpsStr,
                (np.round(w*0.01).astype(int), np.round(w*0.03).astype(int)),
                cv.FONT_HERSHEY_SIMPLEX, w*0.0008,
                (0,255,0), np.round(w*0.0012).astype(int), cv.LINE_AA, False)
        
        # ArUco markers
        if arucoDetector is not None:
            cornerList, idList, rejectedImgPoints = arucoDetector.detectMarkers(img)
            if len(cornerList) > 0:
                cv.aruco.drawDetectedMarkers(dispImg, cornerList, idList, (255,0,0))
                draw_aruco_square_score(dispImg, cornerList)
                draw_aruco_coordinate(dispImg, cornerList)
        
        # ArUco-Sine charts, note that img is aready grayscale
        if arucoSineMetas is not None and len(cornerList) > 0:
            # loop each marker found
            for arucoCorner, arucoIdx in zip(cornerList, idList):
                # see if the corner is in meta dict
                if not (str(arucoIdx[0]) in arucoSineIdxList):
                    continue
                arucoCorner = np.array(arucoCorner, dtype=np.float32).reshape(4,2)
                metaDict = arucoSineMetas[str(arucoIdx[0])]
                # extract tiles
                tileList, ppList, lpmmList = \
                extract_sine_and_bw_tiles(img, arucoCorner, metaDict)
                # calculate black/white contrast
                bwTile = tileList[-1].astype(float)/255.0
                commMode, diffMode = estimate_comm_diff_from_bw_tile(bwTile)
                # calculate spectrum and MTF
                mtfList = []
                for tile, lpmm, pp in zip(tileList[:-1], lpmmList, ppList):
                    mtf = estimate_mtf_from_sine_tile(tile.astype(float)/255.0, lpmm, pp, 
                                                      commMode, diffMode, bezel_ratio=0.15)
                    mtfList.append(mtf)
                # find and draw sine block outline
                sineCorner = find_sine_corner_list(arucoCorner, metaDict)
                dispImg = draw_sine_block_outline_and_mtf(dispImg, sineCorner, lpmmList, mtfList)
            

        # show image
        cv.namedWindow(liveWindowName, cv.WINDOW_NORMAL)
        cv.imshow(liveWindowName, dispImg)
        debug('One frame shown.')

        # show histogram upon request
        if histBins is not None:
            dispHist(img, histBins, fig, ax, lineR, lineG, lineB)

        # refresh parameters if needed
        arrayParams = configArrayIfParamChanges(camList, arrayParamsLoader, arrayParams)

        # wait for keyboard input, change if needed
        nextCamInd = opencvKeyWatcher(nextCamInd)
        if isinstance(nextCamInd, int):
            if nextCamInd == camInd: # no change, keep running
                continue
            else: # changed, break(-1)
                debug('Break from inner livestream loop, nextCamInd {}'.format(nextCamInd))
                break
        elif isinstance(nextCamInd, str):
            # timestamp
            timestamp = datetime.now().strftime(dateFormat)[:-4]
            if nextCamInd == 's':
                # snapshot
                imgFn = 'cam{:d}_snapshot_{:s}.png'.format(camInd, timestamp)
                if not cv.imwrite(imgFn, dispImg):
                    error('Cannot save image {:s}. Check problem.'.format(imgFn))
                else:
                    print('\nSnapshot saved to {:s}'.format(imgFn))
            elif nextCamInd == 'f':
                # frame grab
                imgFn = 'cam{:d}_frame_{:s}.png'.format(camInd, timestamp)
                if not cv.imwrite(imgFn, img):
                    error('Cannot save image {:s}. Check problem.'.format(imgFn))
                else:
                    print('\nFrame saved to {:s}'.format(imgFn))
        # no state-changing key captured
        warning('Unexpected keyboard input gives {}, continue display'.format(nextCamInd))
        nextCamInd = camInd

    ### cleanup
    cam.StopGrabbing()
    cv.destroyAllWindows()
    plt.close('all')
    print('\nLivestream ends.')
    return nextCamInd, arrayParams
