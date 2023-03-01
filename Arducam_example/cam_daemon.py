#!/usr/bin/env python3

# This program will run and stay running, waiting for keys
# Send "c -e <exposure> -n <count> -o <outname>" to it,
# it will capture n images, with given exposure, name it as outname_{0~n-1}.png
# Send "q" to it, the program ends

import os
import sys
import socket
import pathlib
import argparse
import numpy as np
import cv2
from utils import ArducamUtils
from mh_utils import CAM_W, CAM_H
from mh_utils import capture_frames, pixelformat, show_info, load_props, refresh_props
from datetime import datetime

if __name__ == "__main__":
    # ========== start program ==========
    # parse parameters
    parser = argparse.ArgumentParser(description='Arducam Jetson Nano MIPI Camera frame capture.')
    parser.add_argument('-d', '--device', default=0, type=int, nargs='?',
                        help='/dev/videoX default is 0')
    parser.add_argument('-f', '--pixelformat', default='Y16', type=pixelformat,
                        help="set pixelformat")
    parser.add_argument('--prop_file', default='props.json', type=str,
                        help='a json file with frame controlling properties')
    args = parser.parse_args()
    
    # assert prop_file
    propf = pathlib.Path(args.prop_file)
    assert propf.exists(), "No such file: {:s}".format(propf)
    # open camera
    cap = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
    # set pixel format, load ArducamUtils, show info
    if args.pixelformat != None:
        if not cap.set(cv2.CAP_PROP_FOURCC, args.pixelformat):
            print("Failed to set pixel format.")
    arducam_utils = ArducamUtils(args.device)
    show_info(arducam_utils)
    # turn off RGB conversion
    if arducam_utils.convert2rgb == 0:
        cap.set(cv2.CAP_PROP_CONVERT_RGB, arducam_utils.convert2rgb)
    # assert width, height
    assert cap.get(cv2.CAP_PROP_FRAME_WIDTH)==(CAM_W*4), \
            "Frame width should be 4x camera width"
    assert cap.get(cv2.CAP_PROP_FRAME_HEIGHT)==CAM_H, \
            "Frame height should be camera height"

    # ========== loop for triger ==========
    # temperal arguments parser
    tripar = argparse.ArgumentParser(description='Tigger capturing parameters')
    tripar.add_argument('-n', '--count', default=5, type=int, 
                        help='number of frames to capture, default 5')
    tripar.add_argument('-e', '--exposure', default=300, type=int, 
                        help='exposure time in milliseconds, default 300')
    tripar.add_argument('-o', '--outname', default='', type=str,
                        help='The prifix of output frames')
    # loop begins
    print("Trigger guide: 'c [-e exposure] [-n count] [-o out_name_prefix]' to capture, 'q' to quit.\n")
    while True:
        # wait for inputs
        kin = "" # stores key input
        while not( kin.startswith('c') or kin is 'q') :
            kin = input()
        
        # ending process
        if kin is 'q':
            print("Closing camera...")
            cap.release()
            sys.exit(0)

        # parse and set arguments
        triargs = tripar.parse_args(kin.split()[1:])
        prefix = triargs.outname
        props = load_props(propf)
        props['exposure'] = triargs.exposure #override exposure

        # capture
        frames, timestamps = capture_frames(cap, arducam_utils, props, triargs.count)

        # build image names
        names = []
        if prefix=='':
            name_f, date_f = props['name_f'], props['date_f']
            for frame, timestamp in zip(frames, timestamps):
                names.append( name_f.format(timestamp.strftime(date_f))+".npy" )
        else:
            for a in range(triargs.count):
                names.append( os.path.join('frames', prefix+"_{}".format(a)+".npy") )
        
        # save image
        for frame, fn in zip(frames, names):
            with open(fn, 'wb') as f:
                np.save(f, frame)
        cv2.imwrite(names[0][:-5]+'preview.png',(frames[0]/4).astype(np.uint8))
        
        # print report
        print("Finish. "
              + "{:s} ".format(socket.gethostname()) 
              + "saves {} frames ".format(triargs.count) 
              + "at {:s}. ".format(datetime.now().strftime("%Y/%m/%d %H:%M:%S.%f")[:-3])
              + "Exposure {}, ".format(triargs.exposure)
              + "prefix {}.".format(prefix)
             )

