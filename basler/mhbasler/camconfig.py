"""
Codes to configure Basler camera array
By Minghao, 2023 Mar

check the notes in __init__.py for some overall ideas.

Camera configuration logic:
A json file contains all the configurations needed for a camera array.
Cameras are uniquely labeled with its serial number
That json file might change while the cameras livestreams, and that change should be applied in real time.
Minimal changes should be made to cameras. After loading, every parameter will be compared with the cached parameter. Only the changed one will be applied.

Known issue:
1. Bayer sensor pixel format may change after reversing x/y, changing offset x/y, or changing width/height. That changes automatically, and won't be reflected in cached parameters or the parameter file. A warning will be sent.
2. Some parameters can't be changed if the camera is grabbing. Stopping then restarting the grabbing would change its grabbing stragergy to latest-only. A warning will be sent.
"""

import logging
from logging import critical, error, info, warning, debug
import time
import pathlib
import json

import numpy as np

from pypylon import pylon, genicam

########################################
### File loader with change detector
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
        
def validArrayParamsSn(arrayParams, arrayParamsCache):
    """
    Return False if arrayParams uses different serial numbers 
    (SN, which is used as keys for the dictionary) 
    """
    kList = sorted(arrayParams.keys())
    kListCache = sorted(arrayParamsCache.keys())
    return kList == kListCache
    
def validArrayParamsIndex(arrayParams, arrayParamsCache):
    """
    Return False if arrayParams changes the order of cameras 
    """
    kList = arrayParams.keys()
    indList = [arrayParams[k]['index'] for k in kList]
    indListCache = [arrayParamsCache[k]['index'] for k in kList]
    return indList == indListCache
    
########################################
### Enumerate and pick cameras
########################################
def pickRequiredCameras(tlFactory, arrayParams):
    """
    This function will enumerate all cameras within available via
    the tlFactory (transport layer factory), then pick out cameras
    requested in the arrayParams (array camera parameters) in order.
    A list of Instant Camera objects will be returned.
    Note that cameras are labeled with serial number
    An error will be thrown if
        no camera found
        one camera does not gives serial number
        requested camera is not found
    """
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

    # pick needed device info and index list
    neededDiList = []
    indexList = []
    for reqSn in arrayParams.keys():
        if not reqSn in devSnList:
            raise pylon.RuntimeException('Device with SN {} is required by array but not attached.'.format(reqSn))
        neededDiList.append(diList[devSnList.index(reqSn)])
        indexList.append(arrayParams[reqSn]['index'])
        
    # sort device info list
    sortedDiList = [neededDiList[idx] for idx in np.argsort(indexList)]

    ### Create Instant Camera objects and adjust parameters
    # these adjustable parameters are properties defined in Node maps
    # use GetNodes() to find all available Nodes
    camList = [] # instant camera list
    for di in sortedDiList:
        camList.append(pylon.InstantCamera(tlFactory.CreateDevice(di)))
        
    return camList

########################################
### Camera "in-file" feature configuration
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
            warning('Stop and restart grabbing to change a parameter. ' \
                    + 'Grabbing stratergy changed to LatestImageOnly')
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
    if ('Bayer' in cam.PixelFormat.ToString()) and isinstance(tgtV, genicam.IInteger):
        warning('Bayer sensor pixel format may change after changing offset x/y, or changing width/height.')
            
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
    if 'Bayer' in cam.PixelFormat.ToString():
    	warning('Bayer sensor pixel format may change after reversing x/y.')
    
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

def setCamParams(cam, params, paramsCache):
    """
    This function would set some concerned parameters of an instant camera.
    Supports increamental methods. If paramCache is not None, the function
    will first check the difference, then only set the changed part.
    The function will also validate the input range before set.
    The camera object has to be opened
    """
    # dummy cache if needed
    if paramsCache is None:
        info('Dummy paramCache used for {}'.format(params['name']))
        paramsCache = {}
        for k in params.keys():
            paramsCache[k] = None
    
    # set parameters one by one
    for paramName in nonStopParamList+stopParamList:
        _setCamParam(cam, params['name'], paramName, params[paramName], paramsCache[paramName])
        
def configArrayIfParamChanges(camList, arrayParamsLoader, arrayParams):
    """
    Check the parameter file via arrayParamsLoader, if changed, reload
    Validate and compare newly loaded with arrayParams
    Configure camera array by setting changed parameters
    Return new arrayParams
    """
    # if not changed, simply return original parameters
    if not arrayParamsLoader.changedAfterLastLoad():
        return arrayParams
    # if changed, reload
    arrayParamsNew = arrayParamsLoader.load()
    # validate serial number integrity. If not, don't change
    if not validArrayParamsSn(arrayParamsNew, arrayParams):
        error('New array camera parameter\'s SN differs with cache. Change rejected.')
        return arrayParams
    # validate camera order
    if not validArrayParamsIndex(arrayParamsNew, arrayParams):
        warning('New array camera parameter\'s camera order differs with cache.' \
                + 'Only effective after restarting the program.')
    # config changed parameters
    for cam in camList:
        camSn = cam.GetDeviceInfo().GetSerialNumber()
        params = arrayParamsNew[camSn]
        paramsCache = arrayParams[camSn]
        setCamParams(cam, params, paramsCache) # this will only config change parameters
    debug('Lazy configured array camera parameters.')
    return arrayParamsNew
