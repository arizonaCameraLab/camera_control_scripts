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
import time
from datetime import datetime
import pathlib
import json
import copy

import numpy as np
import cv2 as cv

from pypylon import pylon, genicam

########################################
### Argument parsing and logging setup
########################################
# logging level definition: 
# critical: program terminates and no way to handle. E.g. no-catch exception, damaging if not stopped
# error: error, but the program may keep running. E.g. catched exception, ignored error input/result
# warning: not an error but not working as the user demands. E.g.: invalid input auto corrected
# info: some expected non-straightforward handling. E.g.: lazy loading, initial test grabbing
# debug: expected, as demanded, straightforward processes. Detailed processes E.g.: how many time a frame waitted, 
def parseArguments():
    """
    Read arguments from the command line
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--params', type=str, default='array_params.json',
                        help='The json file holding the array camera parameters.')
    parser.add_argument('-m', '--mode', type=str, default='disp',
                        help='Script mode. Choose from disp/grab/dryrun, meaning display/grab/neither')
    parser.add_argument('-n', '--amount', type=int, default=5,
                        help='Frame amount to save, 0 for manual stop. Default 5. Ignored when disp/dryrun.')
    parser.add_argument('-f', '--folder', type=str, default='array_cap',
                        help='saving folder. Default \'array_cap\'. Create if not exist. Ignored when disp/dryrun.')
    parser.add_argument('-w', '--window_width', type=int, default=1280,
                        help='Display window width in pixels. Positive. Default 1280. Ignored when grab/dryrun.')
    parser.add_argument('-v', '--verbose', type=int, default=2, 
                        help='Verbosity of logging: 0-critical, 1-error, 2-warning, 3-info, 4-debug')
    args = parser.parse_args()
    
    vTable = {0: logging.CRITICAL, 1: logging.ERROR, 2: logging.WARNING, 
              3: logging.INFO, 4: logging.DEBUG}
    logging.basicConfig(format='%(message)s', level=vTable[args.verbose], stream=sys.stdout)
    
    return args

########################################
### Load and refresh parameter from file
########################################
def jsonLoadFunc(plp):
    """
    This function takes in a pathlib Path of a json file and load it
    """
    if not plp.exists():
        raise RuntimeError("No such file: {:s}".format(plp))
    with open(plp, 'r') as fp:
        jo = json.load(fp) # json object
    return jo

class RealTimeFileLoader():
    """
    A class that will check the status of a certain file
    Can check if the file is changed after last load
    """
    def __init__(self, filePath, loadFunc):
        # load file path
        self.plp = pathlib.Path(filePath)
        if not self.plp.exists():
            raise RuntimeError("No such file: {:s}".format(self.plp))
            
        # load loading function
        self.loadFunc = loadFunc
        
        # initial last load time as 0
        self.lastLoadTime = 0
        
    def changedAfterLastLoad(self, tolerance=0):
        return self.plp.stat().st_ctime > self.lastLoadTime + tolerance
        
    def load(self):
        x = self.loadFunc(self.plp)
        self.lastLoadTime = time.time()
        debug('File {} loaded at {}'.format(self.lastLoadTime, self.plp))
        return x
        

########################################
### Camera configuration functions
########################################
nonStopParamList = ('ExposureTime', 'Gain')
stopParamList = ('Width', 'Height', 'OffsetX', 'OffsetY', 'rot180', 'PixelFormat')
def _checkCacheDeco(func):
    """
    Function decorator to check new value and cached value before setting a camera parameter. 
    The decorated function should take in 
        cam, camName, paramName, v, cachedV
    if v (value) and cachedV (cached value) are the same, do nothing
    else, set the value.
    The input function should take in
        cam, camName, paramName, v
    """
    def inner(cam, camName, paramName, v, cachedV):
        # check cache
        if (cachedV is not None) and (v == cachedV):
            info('Keep cam {}\'s {} {} as cached'.format(camName, paramName, v))
            return
        # set the value
        func(cam, camName, paramName, v)
        return
    return inner
    
def _breakGrabbingWhenNeeded(func):
    """
    Function decorator to break grabbing if needed when setting a camera parameter.
    This should only happen when livestreaming.
    The decorated function should take in 
        cam, camName, paramName, v
    if the parameter can't be changed while grabbing, stop grabbing, set parameter, restart grabbing
    The input function should take in
        cam, camName, paramName, v
    Note that only a list of params are supported
    """
    def inner(cam, camName, paramName, v):
        if not paramName in (nonStopParamList+stopParamList):
            error('{} is not a valid parameter to set, ignored. '.format(paramName) \
                  + 'Select from: {}'.format(nonStopParamList+stopParamList))
            return
        if not cam.IsGrabbing():
            debug('Cam {} is not grabbing, change parameter {}'.format(camName, paramName))
            func(cam, camName, paramName, v)
            return
        
        if paramName in nonStopParamList:
            debug('Cam {} is grabbing, change non-stop parameter {}'.format(camName, paramName))
            func(cam, camName, paramName, v)
        else:
            info('Break cam {}\'s grabbing to change parameter {}'.format(camName, paramName))
            cam.StopGrabbing()
            func(cam, camName, paramName, v)
            cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            warning('Assume that only in livestream mode there will be breaks. Thus using latest.' \
                    + 'Should read and keep the same strategy.')
    return inner

def _setCamNumValue(cam, camName, paramName, v):
    """
    Set a numeric parameter of a camera
    cam has to be an open instant camera
    numeric parameter is specially IFloat or IInteger here
    """
    # validate the parameter
    if not hasattr(cam, paramName):
        error('Cam {} does not have parameter {}, ignored.'.format(camName, paramName))
    
    # correct value
    tgtV = getattr(cam, paramName)
    curV = tgtV.GetValue() # current value
    minV = tgtV.GetMin()
    maxV = tgtV.GetMax()
    v = type(curV)(v)
    corV = np.clip(v, minV, maxV)
    if isinstance(tgtV, genicam.IInteger) \
       or (isinstance(tgtV, genicam.IFloat) and tgtV.HasInc()):
        incr = tgtV.GetInc()
        corV = np.round((corV - minV) / incr) * incr + minV # corrected
    corV = type(curV)(corV)
    if not v == corV:
        warning('Setting {}\'s {}, {} corrected to {}'.format(
            camName, tgtV.GetNode().Name, v, corV))
    
    # set value
    tgtV.SetValue(corV)
    debug('Set {}\'s {} to {}'.format(camName, tgtV.GetNode().Name, corV))
            
def _setCamRot(cam, camName, v):
    """
    Set image rotation of the camera
    cam has to be an open instant camera
    """
    # set value and report
    v = bool(v)
    cam.ReverseX.SetValue(v)
    cam.ReverseY.SetValue(v)
    debug('Set {}\'s rot180 to {}'.format(camName, v))
    
def _setCamPixelFormat(cam, camName, v):
    """
    Set PixelFormat of the camera
    cam has to be an open instant camera
    """
    # validate input
    vList = cam.PixelFormat.GetSymbolics()
    if not v in vList:
        error('{} does not support PixelFormat {}. Only {} available'.format(camName, v, vList) \
              + 'Keep current PixelFormat {}'.format(cam.PixelFormat.ToString()))
        return
    # set value and report
    cam.PixelFormat.FromString(v)
    debug('Set {}\'s PixelFormat to {}'.format(camName, v))

@_checkCacheDeco
@_breakGrabbingWhenNeeded
def _setCamParam(cam, camName, paramName, v):
    """
    Set a parameter of a camera
    cam has to be an open instant camera
    composed by 3 types: numeric, rotation, pixel format
    """
    # validate parameter name
    if not paramName in (nonStopParamList + stopParamList):
        error('{} is not a valid parameter to set, ignored. '.format(paramName) \
                  + 'Select from: {}'.format(nonStopParamList+stopParamList))
    if paramName == 'rot180':
        _setCamRot(cam, camName, v)
    elif paramName == 'PixelFormat':
        _setCamPixelFormat(cam, camName, v)
    else:
        _setCamNumValue(cam, camName, paramName, v)

def setCamParamBundle(cam, param, paramCache):
    """
    This function would set some concerned parameters of an instant camera.
    Supports increamental methods. If paramCache is not None, the function
    will first check the difference, then only set the changed part.
    The function will also validate the input range before set.
    The camera object has to be opened
    """
    # dummy cache if needed
    if paramCache is None:
        info('Dummy paramCache used for {}'.format(param['name']))
        paramCache = {}
        for k in param.keys():
            paramCache[k] = None
    
    # set parameters one by one
    for paramName in nonStopParamList+stopParamList:
        _setCamParam(cam, param['name'], paramName, param[paramName], paramCache[paramName])


########################################
### Main function
########################################
def main(args):
    ### prepare parameter file
    arrayParamsLoader = RealTimeFileLoader(args.params, jsonLoadFunc)
    arrayParams = arrayParamsLoader.load()

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
        setCamParamBundle(cam, params, None)

    ### livestream camera 0
    # converting to opencv bgr format
    converter = pylon.ImageFormatConverter()
    converter.OutputPixelFormat = pylon.PixelType_BGR8packed
    converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
    # start grabbing and streaming
    camera = camList[0]
    windowName = 'cam ' + arrayParams[camera.GetDeviceInfo().GetSerialNumber()]['name']
    camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
    while camera.IsGrabbing():
        grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

        if grabResult.GrabSucceeded():
            # Access the image data
            image = converter.Convert(grabResult)
            img = image.GetArray()
            # show image
            cv.namedWindow(windowName, cv.WINDOW_NORMAL)
            cv.imshow(windowName, img)
            # wait for break
            k = cv.waitKey(1)
            if k == 27:
                break
        grabResult.Release()
        
        # refresh parameters if needed
        if arrayParamsLoader.changedAfterLastLoad():
            arrayParamsCache = copy.copy(arrayParams)
            arrayParams = arrayParamsLoader.load()
            # need to validate key integrity before working on that
            for cam in camList:
                camSn = cam.GetDeviceInfo().GetSerialNumber()
                params = arrayParams[camSn]
                paramsCache = arrayParamsCache[camSn]
                setCamParamBundle(cam, params, paramsCache)
        
    # Releasing the resource    
    camera.StopGrabbing()

    cv.destroyAllWindows()

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

