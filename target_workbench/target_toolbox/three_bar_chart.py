"""
Functions to generate a three-bar resolution target similar to 1951 USAF resolution test chart
minghao, Jan 2021
"""

import numpy as np
import cv2 as cv
from .common import dpi_to_pp, center_crop_pad_to
# from PIL import Image, ImageFont, ImageDraw
# from skimage.color import rgb2gray

def three_line_square(lw, sf):
    """
    Generate a 5Nx5N numpy bool matrix with 3 horizontal lines, black background
    lw: line width, in mm. A float
    sf: scale factor, pixels per mm. A float
    """
    pix_lw = np.round(float(lw)*float(sf)).astype(int)
    P = np.zeros((5*pix_lw, 5*pix_lw), dtype=bool)
    for a in range(0,5,2):
        P[a*pix_lw:(a+1)*pix_lw] = True
    
    return P

# def number_square(w, num):
#     """
#     Generate a square pattern with a number at the top-left corner, black background.
#     The returning value is a w-by-w boolean numpy array
#     w: pattern width, integer
#     num: number to write, usually integer
#     """
#     num_size = w//2
#     img = Image.new('RGB', (w, w))
#     img_draw = ImageDraw.Draw(img)
#     text_font = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeSerif.ttf', num_size)
#     img_draw.text((0,w//6), "{}".format(num), (255, 255, 255), font=text_font)
#     img = rgb2gray(np.asarray(img))
#     img = img>0.5
#     return img

def text_square(w, text):
    """
    Generate a square pattern with a text at the top-left corner, black background.
    The returning value is a w-by-w boolean numpy array
    w: pattern width, integer
    num: number to write, usually integer
    """
    num_size = w//2
    img = np.zeros((w, w, 3), dtype=np.uint8)
    cv.putText(img, text, 
               (np.round(w*0.01).astype(int), np.round(w*0.7).astype(int)), 
               cv.FONT_HERSHEY_SIMPLEX, w*0.018, 
               (255,255,255), np.round(w*0.015).astype(int), cv.LINE_AA, False)
    img = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    img = img>0.5
    return img

def resolution_element(lw, sf):
    """
    Generate a resolution element with 
     - 3 vertical lines
     - 3 horizontal lines
     - a number denotes the line width in mm
    tiled horizontally. 
    The returning value is a 5N-by-17N boolean numpy array
    """
    hlines = three_line_square(lw, sf)
    vlines = np.transpose(hlines)
    w = hlines.shape[0]
    text = '{:d}'.format(lw) if isinstance(lw, int) else '{:.1f}'.format(lw)
    num = text_square(w, text)
    gap = np.zeros((w, w//5), dtype=hlines.dtype)
    return np.concatenate([vlines, gap, hlines, gap, num], axis=1)

def tile_resolution_elements(P_list):
    """
    Tile a list of resolution elements vertically.
    P_list: a list of resolution elements, size decreasing. (P for pattern)
    """
    final_w = P_list[0].shape[1]
    P_pad_list = P_list[:1]
    for P in P_list[1:]:
        h = P.shape[0]
        gap = np.zeros((2*h//5, final_w), dtype=P.dtype)
        P_pad = np.pad(P, ((0,0),(0,final_w-P.shape[1])))
        P_pad_list.append(gap)
        P_pad_list.append(P_pad)
    return np.concatenate(P_pad_list, 0)

def pad_to_square(P, center=False):
    # zero-padding a 2D array to square shape
    h, w = P.shape
    tgt_w = max(h, w)
    if center:
        tp = (tgt_w-h)//2
        lp = (tgt_w-w)//2
    else:
        tp = 0
        lp = 0
    bp = tgt_w-h-tp
    rp = tgt_w-w-lp
    return np.pad(P, ((tp,bp), (lp,rp)))

def add_frame(P, fw):
    # add zero-frame to a 2D array
    return np.pad(P, ((fw,fw), (fw,fw)))
    
def three_bar_target(lw_list, mid_num, dpi, *, 
                     center=False, tightness=0):
    """
    Return a three_bar target pattern, white background
    lw_list: line width list, mm, a list of floats
    mid_num: where to break the series
    dpi: dots per inch, depends on the printer
    tightness: make two rows closer, mm
    """
    sf = 1/dpi_to_pp(dpi) # scale factor, pixels per mm. A float
    P_list = [resolution_element(lw, sf) for lw in lw_list] # pattern list
    PL1 = P_list[:mid_num]
    PL2 = P_list[mid_num:]
    PT1 = tile_resolution_elements(PL1)
    PT2 = np.rot90(tile_resolution_elements(PL2), 2)
    h, w = PT2.shape
    tightness_pix = np.round(tightness*sf).astype(int)
    PT = PT1[:, :PT1.shape[1]-tightness_pix] # pattern tiled
    PT[-h:,-w:] = np.logical_or(PT[-h:,-w:], PT2)
    PT = pad_to_square(PT, center)
    PT = add_frame(PT, int(lw_list[0]*sf))
    PT = np.logical_not(PT).astype(np.uint8)*255
    return PT