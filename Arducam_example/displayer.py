#!/usr/bin/env python3

import pathlib
import argparse
import cv2
from utils import ArducamUtils
from mh_utils import CAM_W, CAM_H
from mh_utils import display, pixelformat, show_info

if __name__ == "__main__":
    # parse parameters
    parser = argparse.ArgumentParser(description='Arducam Jetson Nano MIPI Camera Displayer.')
    parser.add_argument('-d', '--device', default=0, type=int, nargs='?',
                        help='/dev/videoX default is 0')
    parser.add_argument('-f', '--pixelformat', default='Y16', type=pixelformat,
                        help="set pixelformat")
    parser.add_argument('--prop_file', default='props.json', type=str,
                        help='a json file with frame controlling properties')
    parser.add_argument('--fps', action='store_true', help="display fps")
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
    
    # begin display
    display(cap, arducam_utils, propf, args.fps)

    # release camera
    cap.release()
