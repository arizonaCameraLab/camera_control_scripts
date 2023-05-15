# Display/capture of a single channel DaHeng camera
# Minghao Hu. 2022 Dec
# Example usage: 
# python mhdaheng.py -h # show help info. Note that all options can combine with each other
# python mhdaheng.py -e 15e3 -g 0 -m disp --disp_scale 0.25 # set exposure to 15ms, gain to 0dB, display 1/4 resolution livestream
# python mhdaheng.py -m cap -n 200 -f test # capture 200 frames, save in folder test
# python mhdaheng.py -m dryrun -n 200 --xywh 960,540,1920,1080 # capture the center 1/2 ROI, no display no saving. Just for fps test
# python mhdaheng.py -m both -n 0 -f test # display and save frames at the same time, manual stop

import os
import warnings
import argparse
import time
from datetime import datetime
import gxipy as gx
import numpy as np
import cv2 as cv

# add parameters
parser = argparse.ArgumentParser()
parser.add_argument('-i', '--id', type=int, default=0,
                    help='Camera id, int, 0-indexed. Default 0')
parser.add_argument('-m', '--mode', type=str, default='disp',
                    help='Script mode. Choose from disp/cap/both/dryrun, meaning display/capture/both/neither')
parser.add_argument('-e', '--exposure', type=float, default=10e3, 
                    help='Camera exposure in us, float. Default 10e3. To ensure a 22 fps, shouldn\'t exceed 40e3')
parser.add_argument('-g', '--gain', type=float, default=0.0, 
                    help='Camera gain in dB, float. Default 0.0')
parser.add_argument('--xywh', type=lambda whxy: [int(x) for x in whxy.split(',')], default='0,0,-1,-1',
                    help='Anchor x, anchor y, width, and height. For region of interest (ROI). 4 ints separated by commas. ' +\
                    'Out-of-range x,y would be set to 0.' +\
                    'Out-of-range w,h would be set to maximum allowed width, height' +\
                    'Default full image')
parser.add_argument('-n', '--amount', type=int, default=100,
                    help='Frame amount to save, 0 for manual stop. Default 0. Ignored when disp/dryrun.')
parser.add_argument('-f', '--folder', type=str, default='dhcap',
                    help='saving folder. Default \'dhcap\'. Ignored when disp/dryrun. Timestamp automatically added.')
parser.add_argument('--disp_scale', type=float, default=1.0,
                    help='Display scaling, float. Positive. Default 1')
parser.add_argument('--verbose', action='store_true', help='verbose mode, Would print more camera informations')
args = parser.parse_args()

# detect device
device_manager = gx.DeviceManager()
dev_num, dev_info_list = device_manager.update_all_device_list()
if dev_num <= 0:
    raise RuntimeError('No device detected.')
if args.id >= dev_num:
    raise RuntimeError('Request camera {}, but only {} in total'.format(args.id, dev_num))
if args.verbose:
    print('List devices and parameters')
    for a in range(dev_num):
        print('---------- Camera {} ----------'.format(a))
        for k in dev_info_list[a].keys():
            print('\t{}: {}'.format(k, dev_info_list[a][k]))
    print('')

# open device
cam = device_manager.open_device_by_sn(dev_info_list[args.id]['sn'])
print('Open camera {}'.format(args.id))

# print device parameter properties
if args.verbose:
    # exposure time
    print('Exposure time range parameters:')
    exp_range = cam.ExposureTime.get_range()
    for k in exp_range.keys():
        print('\t{}: {}'.format(k, exp_range[k]))
    print('Note that, to ensure a 22 fps capture, exposure time shouldn\'t exceed 40e3 us')
    print('')

    # gain
    print('Gain range parameters:')
    gain_range = cam.Gain.get_range()
    for k in gain_range.keys():
        print('\t{}: {}'.format(k, gain_range[k]))
    print('')
    
    # width and height
    print('Sensor width and height: {}, {}'.format(cam.SensorWidth.get(), cam.SensorHeight.get()))
    print('Max width and height: {}, {}'.format(cam.WidthMax.get(), cam.HeightMax.get()))
    print('')    

# set pixel format
print('Pixel format: {}'.format(cam.PixelFormat.get()[1]))

# set exposure and gain
cam.ExposureTime.set(args.exposure)
print('Exposure: {}'.format(cam.ExposureTime.get()))
cam.Gain.set(args.gain)
print('Gain: {}'.format(cam.Gain.get()))
    
# parse and set ROI
x, y, w, h = args.xywh
if x < 0 or x >= cam.WidthMax.get():
    print('x out of range, set to 0')
    x = 0
if y < 0 or y >= cam.HeightMax.get():
    print('y out of range, set to 0')
    y = 0
if w <= 0 or x+w > cam.WidthMax.get():
    print('w or x+w out of range, adjusted to max')
    w = cam.WidthMax.get() - x
if h <= 0 or y+h > cam.HeightMax.get():
    print('h or y+h out of range, adjusted to max')
    h = cam.HeightMax.get() - y
cam.OffsetX.set(x)
cam.OffsetY.set(y)
cam.Width.set(w)
cam.Height.set(h)
print('Offset xy: {}, {}.'.format(cam.OffsetX.get(), cam.OffsetY.get()))
print('Image width and height: {}, {}.'.format(cam.Width.get(), cam.Height.get()))

# set mode
if args.mode=='disp':
    amount = 0
    show_stream = True
    save_frames = False
elif args.mode=='cap':
    amount = args.amount
    show_stream = False
    save_frames = True
elif args.mode=='both':
    amount = args.amount
    show_stream = True
    save_frames = True
elif args.mode=='dryrun':
    amount = args.amount
    show_stream = False
    save_frames = False
else:
    raise RuntimeError("Bad mode: {}. Only support disp/cap/both/dryrun".format(args.mode))
print('Running in {} mode'.format(args.mode))

# set amount
if amount <= 0:
    if save_frames:
        print('Warning: using manual stop while saving frames. May lead to memory explode.')
    amount = np.inf
    print('Stop manually. Hit \'q\' within the display window to stop.')
else:
    print('Stop automatically after {} frames are streamed.'.format(amount))

# parse and set scaling
if show_stream:
    disp_scale = args.disp_scale
    if disp_scale <= 0:
        print('disp_scale out of range, set to 1')
        disp_scale = 1.0
    print('Display scale {}'.format(disp_scale))
    
# record date time, make folder
if save_frames:
    folder_name = args.folder
    datetime = time.strftime('_%Y-%m-%d_%H-%M-%S', time.localtime())
    folder_name += datetime
    os.system('mkdir '+folder_name)
    print('Save frames to folder {}'.format(folder_name))

# prepare display window
window_name = 'DaHeng cam: {} mode'.format(args.mode)
cv.namedWindow(window_name)

# stream and display/save
frame_count = 0
frame_list = []
cam.stream_on()
start_time = time.time()
if args.verbose:
    loop_end_time = time.time()
while True:
    # capture a frame
    raw_img = cam.data_stream[0].get_image()
    np_img = raw_img.get_numpy_array()
    if np_img is None:
        continue

    if show_stream:
        # scale the image
        if disp_scale < 1:
            canvas = cv.resize(np_img, (0, 0), None,
                               disp_scale, disp_scale, cv.INTER_AREA)
        elif disp_scale > 1:
            canvas = cv.resize(np_img, (0, 0), None,
                               disp_scale, disp_scale, cv.INTER_LINEAR)
        else:
            canvas = np_img
        # display
        cv.namedWindow(window_name)
        cv.imshow(window_name, canvas)
    
    if save_frames:
        frame_list.append(np_img)
    
    # add frame count
    frame_count += 1

    # verbose output
    if args.verbose:
        tmp_time = time.time()
        loop_time = tmp_time - loop_end_time
        loop_end_time = tmp_time
        print('Frame {:d} captured, temporal framerate {:.2f}'.format(frame_count, 1/loop_time))
        

    # Press q if you want to end the loop
    if amount == np.inf and cv.waitKey(1) & 0xFF == ord('q'):
        break
    # If enough frames are collected, end the loop
    if frame_count >= amount:
        break

end_time = time.time()
cv.destroyAllWindows()
cam.stream_off()

# calculate frame rate
elapsed_time = end_time - start_time
real_fps = frame_count / elapsed_time
print('Total fps: {:.2f}'.format(real_fps))

# close device
cam.close_device()
print('Camera closed')

# save frames, if needed
if save_frames:
    N = len(frame_list)
    assert N > 0, 'No frame captured!'
    print('Saving {:d} frames...'.format(N))
    zfill_num = np.ceil(np.log10(N)).astype(int)
    for a, img in enumerate(frame_list):
        frame_path = os.path.join(folder_name, str(a).zfill(zfill_num)+'.png')
        if args.verbose:
            print('Saving frame {}'.format(frame_path))
        cv.imwrite(frame_path, img)
        
# exit
exit(0)
