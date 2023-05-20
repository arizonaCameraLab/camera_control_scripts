"""
Codes to count the framerate of a list of captured frame with chunk data
By Minghao, 2023 May

Logic:
extract the timestamps from all chunk data json files within a folder
remove the head and tail frames
linear fit the timestamps and frame indices
return framerate and linearity
"""

import os
import sys
import json
import argparse
import logging
from logging import critical, error, info, warning, debug

import numpy as np
import matplotlib.pyplot as plt

# parse input
def parse_arguments():
    # compose parser
    parser = argparse.ArgumentParser('Framerate counter',
                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('folder', type=str,
                        help='Folder containing frames and json files')
    parser.add_argument('--head', type=int, default=2,
                        help='Amount of head frames to ignore')
    parser.add_argument('--tail', type=int, default=0,
                        help='Amount of tail frames to ignore')
    parser.add_argument('--plot', dest='plot', action='store_true',
                        help='Plot scatter and linear fitting image')
    parser.add_argument('-v', '--verbose', type=int, default=1,
                        help='Verbosity of logging: 0-critical, 1-error, 2-warning, 3-info, 4-debug')
    # parse argparse
    args = parser.parse_args()
    # set logging
    vTable = {0: logging.CRITICAL, 1: logging.ERROR, 2: logging.WARNING,
              3: logging.INFO, 4: logging.DEBUG}
    logging.basicConfig(format='%(levelname)s: %(message)s',
                        level=vTable[args.verbose], stream=sys.stdout)
    return args

# main function
def main(args):
    # list folder
    print('Scanning folder {:s}'.format(args.folder))
    filename_list = os.listdir(args.folder)
    filename_list = [fn for fn in filename_list if fn.endswith('.json')]
    filename_list = sorted(filename_list)
    print('{:d} json files found'.format(len(filename_list)))

    # drop head and tail
    if args.head > 0:
        filename_list = filename_list[args.head:]
    if args.tail > 0:
        filename_list = filename_list[:args.tail]
    print('Drop {} head, {} tail, {} json files left'.format(
        args.head, args.tail, len(filename_list)))

    # peek exposure and gain
    with open(os.path.join(args.folder, filename_list[0]), 'r') as fp:
        json_dict = json.load(fp)
    print('ExposureTime: {:.1f}us'.format(json_dict['ExposureTime']))
    print('Gain: {:.1f}dB'.format(json_dict['Gain']))

    # read timestamps
    timestamp_list = []
    for fn in filename_list:
        with open(os.path.join(args.folder, fn), 'r') as fp:
            json_dict = json.load(fp)
        timestamp_list.append(json_dict['Timestamp'])
    timestamp_list = np.array(timestamp_list)/1e9

    # linear fit
    frame_idx_list = np.arange(len(timestamp_list))
    model = np.polyfit(frame_idx_list, timestamp_list, 1)
    fps = 1/model[0]
    
    # frame gap distribution
    framegap_list = timestamp_list[1:] - timestamp_list[:-1]
    framegap_mean = framegap_list.mean()
    framegap_std = framegap_list.std()

    # print
    print('FPS: {:.2f}'.format(fps))
    print('Frame gap mean: {:.2f}ms (FPS {:.2f})'.format(framegap_mean*1e3, 1/framegap_mean))
    print('Frame gap std: {:.2e}ms, {:.2f}% of mean'.format(framegap_std*1e3, framegap_std/framegap_mean*100))
    
    # plot
    if args.plot:
        predict = np.poly1d(model)
        x_lin_reg = np.array([0, frame_idx_list[-1]])
        y_lin_reg = predict(x_lin_reg)
        plt.figure(figsize=(12, 8))
        plt.scatter(frame_idx_list, timestamp_list)
        plt.plot(x_lin_reg, y_lin_reg, c='r')
        plt.xlabel('Frame indices')
        plt.ylabel('timestamp / s')
        plt.title('Frames in {:s}, FPS {:.2f}'.format(args.folder, fps))
        plt.show()

    return 0

if __name__ == '__main__':
    args = parse_arguments()
    main(args)
