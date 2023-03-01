# Some helper functions for Nvidia Jetson Nano + Arducam 1MP Quadrascopic Camera Bundle Kit
# By Minghao, May 11, 2021

import os
import time
from datetime import datetime
import json
import argparse
import cv2
import numpy as np
from utils import ArducamUtils

#####################
### Minghao Coded ###
#####################

# Camera sensor parameters
CAM_W = 1280
CAM_H = 800

# Camera control properties
# exposure, gain, frame_rate, as their name suggests
# aois controls the areas shown from each micro-cam, in form [x1, x2, y1, y2]
# cell_w, cell_h controls the window size for each micro-cam, in pixels
# tile controls window tilling, 0-3 means micro-camera, -1 means blank
PROPS_DEFAULT = {
    "exposure": 500,
    "gain": 1,
    "frame_rate": 30,
    "aois": [
        [0, CAM_W, 0, CAM_H],
        [0, CAM_W, 0, CAM_H],
        [0, CAM_W, 0, CAM_H],
        [0, CAM_W, 0, CAM_H]
    ],
    "cell_w": CAM_W,
    "cell_h": CAM_H,
    "tile": [
        [0, 1, 2, 3]
    ]    
}

def load_props(propf):
    # load parameter properties
    with open(propf, 'r') as pf:
        props = json.load(pf)
    # load default values
    for k in PROPS_DEFAULT.keys():
        if not k in props:
            props[k] = PROPS_DEFAULT[k]
    return props 

def refresh_props(props):
    # refresh v4l2 level properties
    for k in ['exposure', 'gain', 'frame_rate']:
        os.system("v4l2-ctl -c {}={}".format(k, props[k]))
    return

def frame_to_mcam_frames(frame, aois, rot_marks):
    # frame should to be a 5120x800 grayscale image, 4 tiled as a row
    # aois are 4 lists, each list contain [x0, x1, y0, y1]
    # rot_marks are 4 booleans, True means rotate 180 degrees

    # some assertion
    assert len(frame.shape)==2, \
        "Frame needs to be grayscale! Now its shape: {}".format(frame.shape)
    # crop out single micro-camera frame and its aoi
    mcam_frames = []
    for a in range(4):
        crop = frame[:CAM_H,a*CAM_W:(a+1)*CAM_W]
        x0, x1, y0, y1 = aois[a]
        crop = crop[y0:y1, x0:x1]
        if rot_marks[a]:
            crop = np.fliplr(np.flipud(crop))
        mcam_frames.append(crop)
    return mcam_frames

def scale_and_tile_mcam_frames(mcam_frames, cell_w, cell_h, tile_mat):
    # mcam_frames should to be a list of 4 grayscale images
    # tile_mat should be a 2D numpy array, containing ints <4
    
    # some assertion
    assert len(tile_mat.shape)==2, \
        "Tile matrix should be a 2-dimension array"
    assert np.all(tile_mat.flatten()<4), \
        "Tile matrix should contain camera indices, less than 4"

    # rescale and place each frame
    patches = np.zeros((4, cell_h, cell_w), dtype=mcam_frames[0].dtype)
    for a in range(4):
        mcam_f = mcam_frames[a]
        mh, mw = mcam_f.shape
        # scale mcam frame
        scale = min(cell_h/mh, cell_w/mw)
        if scale>1:
            mcam_f = cv2.resize(mcam_f, (0,0), None, 
                    scale, scale, cv2.INTER_AREA)
        else:
            mcam_f = cv2.resize(mcam_f, (0,0), None, 
                    scale, scale, cv2.INTER_LINEAR)
        mh, mw = mcam_f.shape
        # place the scaled frame in patch with offset
        h_off, w_off = (cell_h-mh)//2, (cell_w-mw)//2
        patches[a, h_off:h_off+mh, w_off:w_off+mw] = mcam_f

    # tile patches
    m, n = tile_mat.shape
    canvas = np.zeros((m*n, cell_h, cell_w), dtype=patches.dtype)
    for a, cind in enumerate(tile_mat.flatten()):
        if cind>=0: # camera index, negative means "leave blank"
            canvas[a] = patches[cind]
    canvas = canvas.reshape(m,n,cell_h,cell_w)
    canvas = np.transpose(canvas, (0,2,1,3))
    canvas = canvas.reshape(m*cell_h, n*cell_w)
    return canvas

def capture_frames(cap, arducam_utils, props, frame_count=1, *, 
                   quiet=True):
    # Capture some frames

    # start the camera
    ret, frame = cap.read() #activation (NEEDED! Remove it then refresh_props won't work)
    refresh_props(props) #load parameters
    for _ in range(5):
        ret, frame = cap.read() #wait for the new parameters to take effect
    # A waiting-for-trigger program should work better
    # capture frames
    frames = []
    timestamps = []
    start_time = datetime.now()
    start = time.time()
    for a in range(frame_count):
        # record capturing time
        timestamps.append(datetime.now())
        # capture a frame
        ret, frame = cap.read()
        assert ret, "Unsucessful capture?"
        # some convertion
        if arducam_utils.convert2rgb == 0:
            w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            frame = frame.reshape(int(h), int(w))
        #frame = arducam_utils.convert(frame) #this convert 10-bit to 8-bit
        # store frame
        frames.append(frame)

    # ending information
    end_time = datetime.now()
    elapsed_time = end_time - start_time
    avgtime = elapsed_time.total_seconds() / frame_count
    if not quiet:
        print ("Average time between frames: " + str(avgtime))
        print ("Average FPS: " + str(1/avgtime))
    return frames, timestamps


##########################################
### Adapted from Arducam's example code ##
##########################################

def display(cap, arducam_utils, propf, 
        fps=False, prop_refresh_time=0.2):
    
    # initialize
    counter = 0
    frame_count = 0
    check_time = 0
    start_time = datetime.now()
    start = time.time()

    # start streaming
    ret, frame = cap.read() #activation (NEEDED?)
    while True:

        # check if property update is needed
        if time.time()-check_time > prop_refresh_time:
            if propf.stat().st_ctime > check_time:
                props = load_props(propf)
                refresh_props(props)
                # print("Updates properties!")
            check_time = time.time() #may not really safe?
        
        # capture a frame
        ret, frame = cap.read()
        counter += 1
        frame_count += 1

        # some convertion
        if arducam_utils.convert2rgb == 0:
            w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            frame = frame.reshape(int(h), int(w))
        frame = arducam_utils.convert(frame)
        # crop, resize, rotate, tile
        mcam_frames = frame_to_mcam_frames(frame, props['aois'], props['rots'])
        canvas = scale_and_tile_mcam_frames(mcam_frames, 
                props['cell_w'], props['cell_h'], 
                np.array(props['tile']))
        
        # display
        cv2.namedWindow("Arducam", cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Arducam', 1280, 800)
        cv2.imshow("Arducam", canvas)
        ret = cv2.waitKey(1)
        
        # press 'q' to exit.
        if ret == ord('q'):
            break
        # show fps if needed
        if fps and time.time() - start >= 1:
            print("fps: {}".format(frame_count),end='\r')
            start = time.time()
            frame_count = 0 

    # ending information
    end_time = datetime.now()
    elapsed_time = end_time - start_time
    avgtime = elapsed_time.total_seconds() / counter
    print ("Average time between frames: " + str(avgtime))
    print ("Average FPS: " + str(1/avgtime))

##############################
### Arducam's example code ###
##############################

def fourcc(a, b, c, d):
    return ord(a) | (ord(b) << 8) | (ord(c) << 16) | (ord(d) << 24)

def pixelformat(string):
    if len(string) != 3 and len(string) != 4:
        msg = "{} is not a pixel format".format(string)
        raise argparse.ArgumentTypeError(msg)
    if len(string) == 3:
        return fourcc(string[0], string[1], string[2], ' ')
    else:
        return fourcc(string[0], string[1], string[2], string[3])

def show_info(arducam_utils):
    _, firmware_version = arducam_utils.read_dev(ArducamUtils.FIRMWARE_VERSION_REG)
    _, sensor_id = arducam_utils.read_dev(ArducamUtils.FIRMWARE_SENSOR_ID_REG)
    _, serial_number = arducam_utils.read_dev(ArducamUtils.SERIAL_NUMBER_REG)
    print("Firmware Version: {}".format(firmware_version))
    print("Sensor ID: 0x{:04X}".format(sensor_id))
    print("Serial Number: 0x{:08X}".format(serial_number))
