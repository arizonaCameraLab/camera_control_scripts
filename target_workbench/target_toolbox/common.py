import warnings
import numpy as np
import cv2 as cv

##############################
### helpers
##############################
def mm_to_pixels(x, dpi):
    return np.round(x / 25.4 * dpi).astype(int)

def pixels_to_mm(x, dpi):
    return x / dpi * 25.4

def dpi_to_pp(dpi):
    """Note that pixel pitch here is in mm"""
    return 25.4 / dpi

def pp_to_dpi(pp):
    """Note that pixel pitch here is in mm"""
    return 25.4 / pp

def center_crop_pad_to(arr, w, dim, const_value=0):
    w_ori = arr.shape[dim]
    if w>w_ori: # need to pad
        lp = (w-w_ori)//2
        rp = (w-w_ori) - (w-w_ori)//2
        pad_width = [(0,0) for a in range(arr.ndim)]
        pad_width[dim] = (lp, rp)
        pad_width = tuple(pad_width)
        return np.pad(arr, pad_width, mode='constant', constant_values=const_value)
    elif w<w_ori: # need to crop
        lc = (w_ori - w)//2
        rc = (w_ori - w) - (w_ori - w)//2
        arr = np.swapaxes(arr, 0, dim)
        arr = arr[lc:w_ori-rc]
        arr = np.swapaxes(arr, 0, dim)
        return arr
    else:
        return arr
    
def remove_bezel(arr, bezel_ratio=0.1, dims=None):
    """
    Crop out bezel pixels of an data cube
    arr: N-dim data cube
    bezel_ratio: percentage of length to remove
    dims: if None (default), apply to all dims
          if int, apply to that dim
          if list/tuple, apply to the dims contained
    """
    # validate dims
    if dims is None:
        dims = list(range(len(arr.shape)))
    elif isinstance(dims, int):
        dims = [dims]
    elif isinstance(dims, list) or isinstance(dims, tuple):
        pass
    else:
        raise RuntimeError('dims is not None, int or a list of int')
    # crop each dim
    for dim in dims:
        width = arr.shape[dim]
        bezel = np.round(width*bezel_ratio).astype(int)
        arr = np.swapaxes(arr, 0, dim)
        arr = arr[bezel:width-bezel]
        arr = np.swapaxes(arr, 0, dim)
    # return
    return arr
    
##############################
### intensity reference
##############################
def draw_bw_ref_tile(width, height):
    # width and height in pixels
    head_w = np.round(width/4).astype(int)
    y_list = np.concatenate([np.zeros(head_w, dtype=float), 
                             np.linspace(0, 1, width-2*head_w),
                             np.ones(head_w, dtype=float)
                            ])
    y_list = np.round(y_list*255.0).astype(np.uint8)
    canvas = np.tile(y_list, (height, 1))
    return cv.cvtColor(canvas, cv.COLOR_GRAY2BGR)

##############################
### drawing functions
##############################
def draw_multiline_text(img, text_list, xy, total_height, color=(0,255,0)):
    """
    Draw multiline text on image at location xy
    img should be a unit8 numpy array, BGR image
    text_list should be a list containing multiple lines. Each line is an element
    """
    N = len(text_list)
    if total_height < N:
        warnings.warn('total_height to small, skip drawing.')
        return img
    x, y = xy
    local_x = int(np.round(x))
    for a, text in enumerate(text_list):
        local_y = int(np.round(y + (a+0.8)*total_height/N))
        cv.putText(img, text, (local_x, local_y), 
                   cv.FONT_HERSHEY_SIMPLEX, total_height*0.007, 
                   color, int(np.round(total_height*0.02)), cv.LINE_AA, False)
    return img

def draw_polylines(img, pts, isClosed, color, thickness=1, lineType=cv.LINE_AA, shift=0):
    """
    OpenCV's own function is giving errors. Strange
    Reimplememt it
    """
    if thickness < 1:
        warnings.warn('Thickness less than 1, skip drawing.')
        return img
    pts_list = list(pts)
    if isClosed:
        pts_list = pts_list + [pts_list[0]]
    for pt1, pt2 in zip(pts_list[:-1], pts_list[1:]):
        img = cv.line(img, pt1, pt2, color, thickness, lineType, shift)
    return img
