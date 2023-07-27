import warnings
import numpy as np
import cv2 as cv
from scipy.stats import norm as sp_norm
from .common import mm_to_pixels, center_crop_pad_to

def draw_sine_tile(lpmm, length, height, dpi, subpix_amount=101, scale_to_full=True):
    """
    Draw a sine pattern tile with certain length, height, and line pair per mm
    Args:
        lpmm (float): line pair per mm
        length, height (float): tile length and height in mm
        dpi (float): dots per inch, easier to work with printers
        subpix_amount (int): how many subpixels to integrate to form one pixel. Better to be odd.
        scale_to_full (bool): whether scaling the output to 0-255
    """
    # check subpix
    if not (subpix_amount<=1 or subpix_amount%2 == 1):
        warnings.warn('Subpixel amount is even. Recommended to be odd for certering.')
    # check size
    period = 1/lpmm
    if not length >= 10*period:
        warnings.warn('Pattern length is less than 10 periods.')
    if not height >= 2*period:
        warnings.warn('Pattern height is less than 2 periods.')
    
    # parse image size and period in pixels
    length_pix = mm_to_pixels(length, dpi)
    height_pix = mm_to_pixels(height, dpi)
    period_pix = mm_to_pixels(period, dpi)
    
    # calculate sine wave values
    x_list = np.arange(length_pix)
    # no sub-pixels
    if subpix_amount <= 1:
        y_list = np.sin(x_list/period_pix*2*np.pi)
    # with sub-pixels
    else:
        subpix_offset_list = np.linspace(0, 1, 2*subpix_amount+1)[1::2]
        subpix_weight_list = sp_norm.pdf(subpix_offset_list, 0.5, 0.5/3)
        subpix_x_array = np.stack([x_list+offset for offset in subpix_offset_list], 0)
        y_array = np.sin(subpix_x_array/period_pix*2*np.pi)
        y_list = (y_array * subpix_weight_list[:,None]).sum(0) / subpix_amount
    y_list = (y_list + 1) / 2
    
    # scale to 0-1 if needed
    if scale_to_full:
        y_list = (y_list-y_list.min())/(y_list.max()-y_list.min())
    y_list = np.clip(y_list, 0, 1)
    
    # draw the sine_wave pattern to uint8
    y_list = np.round(y_list*255.0).astype(np.uint8)
    sine_tile = np.tile(y_list, (height_pix, 1))
    
    # return
    return cv.cvtColor(sine_tile, cv.COLOR_GRAY2BGR)

def draw_sine_block(lpmm_list, length, height, dpi, subpix_amount=101, scale_to_01=True):
    sine_tile_list = []
    for lpmm in lpmm_list:
        sine_tile_list.append(draw_sine_tile(lpmm, length, height, dpi, subpix_amount, scale_to_01))
    return np.concatenate(sine_tile_list, 0)

def draw_sine_block_desc_tile(lpmm_list, length, dpi):
    # parse edge pixel length
    side_pixels = mm_to_pixels(length, dpi)

    # make description tile
    desc_str = 'Tile freqs (lp/mm): ' \
             + ', '.join(['{:.2f}'.format(x) for x in lpmm_list])
    text_canvas_height = np.round(side_pixels * 0.06).astype(int)
    text_canvas = np.full((text_canvas_height, side_pixels, 3), 
                          255, np.uint8)
    cv.putText(text_canvas, desc_str, 
               (np.round(side_pixels*0.03).astype(int), np.round(text_canvas_height*0.72).astype(int)), 
               cv.FONT_HERSHEY_SIMPLEX, side_pixels*0.0012, 
               (0,0,0), np.round(side_pixels*0.003).astype(int), cv.LINE_AA, False)
    
    return text_canvas