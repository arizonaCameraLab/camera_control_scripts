import argparse
import numpy as np
import cv2 as cv

from target_toolbox.aruco_marker import ARUCO_INNER_BIT, ARUCO_AMOUNT, ARUCO_EDGE_BIT, ARUCO_DICT_TYPE_STR, ARUCO_DICT_TYPE
from target_toolbox.aruco_marker import draw_aruco_marker, draw_aruco_desc_tile

def get_parser():
    ### compose parser
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i', '--index', type=int, choices=range(0,ARUCO_AMOUNT), 
                        metavar='[0, {})'.format(ARUCO_AMOUNT), 
                        help='ArUco marker index.')
    parser.add_argument('-l', '--length', type=int, 
                        help='ArUco marker side length in mm (including edge).')
    parser.add_argument('--dpi', type=int, default=600,
                        help='ArUco marker dpi.')
    return parser

def main(args):
    # make marker, gap tile, text tile
    aruco_marker = draw_aruco_marker(ARUCO_DICT_TYPE, args.index, args.length, args.dpi)
    side_pixels = aruco_marker.shape[1]
    gap_canvas = np.full((np.round(side_pixels/(ARUCO_INNER_BIT+2*ARUCO_EDGE_BIT)).astype(int), side_pixels, 3), 
                         255, np.uint8)
    text_canvas = draw_aruco_desc_tile(ARUCO_DICT_TYPE_STR, args.index, args.length, args.dpi)

    # concatenate final pattern
    full_pattern = np.concatenate([aruco_marker, gap_canvas, text_canvas], axis=0)
    
    # save image file
    img_name = 'ArUco-{0:s}-index{1:d}-{2:d}x{2:d}mm-dpi{3:d}.png'.format(ARUCO_DICT_TYPE_STR, args.index, args.length, args.dpi)
    assert cv.imwrite(img_name, cv.cvtColor(full_pattern, cv.COLOR_BGR2GRAY)), \
    'Fail to write image, check why.'
    
    return

if __name__ == '__main__':
    parser = get_parser()
    args, _ = parser.parse_known_args()
    main(args)
    
    