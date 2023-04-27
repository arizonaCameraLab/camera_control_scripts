"""
Codes to grab frames from a Basler camera array
By Minghao, 2023 Mar

check the notes in __init__.py for some overall ideas.

Grabbing logic:
Grab frame from these cameras one by one to save bandwidth.
Grab several rounds if needed.
Don't expect all cameras are with same size
Use chunk grabbing to save meta parameters
"""

import os
import sys
import logging
from logging import critical, error, info, warning, debug
from datetime import datetime
import json

import numpy as np
import cv2 as cv

from pypylon import pylon, genicam

########################################
### Camera chunk feature configuration
########################################
chunkNameList = ('ExposureTime', 'Gain', 'Timestamp')

def enableChunk(camera, chunkFeatureList=chunkNameList):
    if not genicam.IsWritable(camera.ChunkModeActive):
        raise pylon.RuntimeException('Camera {} does not support chunk features'.format( \
            camera.GetDeviceInfo().GetModelName()))
    camera.ChunkModeActive = True
    
    supportedFeatureList = camera.ChunkSelector.Symbolics
    for cf in chunkFeatureList:
        if not cf in supportedFeatureList:
            error('Camera {} does not support chunk feature {}, ignored.'.format(\
                cf, camera.GetDeviceInfo().GetModelName()))
            continue
        camera.ChunkSelector = cf
        camera.ChunkEnable = True
        debug('Camera SN {} enabled {} chunk feature'.format(\
            camera.GetDeviceInfo().GetSerialNumber(), cf))
    return
    
def disableChunk(camera):
    if not genicam.IsWritable(camera.ChunkModeActive):
        raise pylon.RuntimeException('Camera {} does not support chunk features'.format( \
            camera.GetDeviceInfo().GetModelName()))
    camera.ChunkModeActive = False
    debug('Camera SN {} disabled chunk feature'.format(\
        camera.GetDeviceInfo().GetSerialNumber()))
    return

########################################
### chunk grabbing
########################################
def chunkGrabOne(cam, converter, camName, chunkFeatureList=chunkNameList, save_raw=False):
    """
    Grab one image from cam with already made configurations
    Return converted image, and a json file containing chunk data
    """
    grabResult = cam.GrabOne(500)
    if save_raw:
        img = grabResult.GetArray()
    else:
        img = converter.Convert(grabResult).GetArray()
    chunkFeatureDict = {}
    for cf in chunkFeatureList:
        if not (hasattr(grabResult, 'Chunk'+cf) \
                and genicam.IsAvailable(getattr(grabResult, 'Chunk'+cf))):
            error('Cam {} does not transfer {} chunk feature, ignored.'.format(camName, cf))
        chunkFeatureDict[cf] = getattr(grabResult, "Chunk"+cf).Value
    return img, chunkFeatureDict

def chunkGrab(cam, amount, converter, leftShift, camName, chunkFeatureList=chunkNameList):
    """
    Grab a sequence of images from cam with already configured
    Return converted image, and a json file containing chunk data
    """
    
    imgList = []
    chunkList = []
    counter = 0
    cam.StartGrabbingMax(amount)
    info('{} capture starts'.format(camName))
    while cam.IsGrabbing():
        grabResult = cam.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        if converter is None:
            img = grabResult.GetArray()
        else:
            img = converter.Convert(grabResult).GetArray()
        if leftShift > 0:
            img = np.left_shift(img, leftShift)
        chunkFeatureDict = {}
        for cf in chunkFeatureList:
            if not (hasattr(grabResult, 'Chunk'+cf) \
                    and genicam.IsAvailable(getattr(grabResult, 'Chunk'+cf))):
                error('Cam {} does not transfer {} chunk feature, ignored.'.format(camName, cf))
            chunkFeatureDict[cf] = getattr(grabResult, "Chunk"+cf).Value
        imgList.append(img)
        chunkList.append(chunkFeatureDict)
        debug('{} frame {} captured'.format(camName, counter))
        counter += 1
    info('{} capture ends'.format(camName))
    return imgList, chunkList

def saveChunkOne(img, chunkDict, folder, name):
    """
    Save one image with its chunk feature dictionary
    """
    # validate folder
    if not os.path.exists(folder):
        os.mkdir(folder)
        info('Folder {} made for saving.'.format(folder))
    # save image as png
    imgName = os.path.join(folder, name+'.png')
    if not cv.imwrite(imgName, img):
        error('Can not save image to {}.'.format(imgName))
    debug('{} saved.'.format(imgName))
    # save chunk data as json
    jsonName = os.path.join(folder, name+'.json')
    with open(jsonName, 'w') as fp:
        json.dump(chunkDict, fp)
    debug('{} saved.'.format(jsonName))
    return 
