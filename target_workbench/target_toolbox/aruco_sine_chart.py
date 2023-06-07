import numpy as np
import cv2 as cv

from .common import mm_to_pixels, pixels_to_mm, center_crop_pad_to, remove_bezel, draw_bw_ref_tile
from .aruco_marker import ARUCO_INNER_BIT, ARUCO_AMOUNT, ARUCO_EDGE_BIT, ARUCO_DICT_TYPE_STR, ARUCO_DICT_TYPE
from .aruco_marker import draw_aruco_marker, draw_aruco_desc_tile
from .sine_chart import draw_sine_block, draw_sine_block_desc_tile

##############################
### chart generation
##############################
def generate_aruco_sine_chart_meta(aruco_idx, aruco_length, 
                                   lpmm_list, length, height,
                                   side_width, dpi=600, 
                                   aruco_dict_type=ARUCO_DICT_TYPE):
    """
    Return a special designed sine MTF chart and its meta data dict
    The chart contains one ArUco marker for location, 
        several sine wave tiles for MTF estimation, 
        and one side tile for b/w contrast
    aruco_dict_type, aruco_index, aruco_length: ArUco marker's dictionary, index, 
                                                and side length in mm
    lpmm_list, length, height: sine tiles lpmm, length, height
    side_width: side tile's width
    dpi: dots per inch, should match the printer
    """
    ### Pattern
    # ArUco marker, sine block
    aruco_marker = draw_aruco_marker(aruco_dict_type, aruco_idx, aruco_length, dpi)
    sine_block = draw_sine_block(lpmm_list, length, height, dpi)

    # description tiles, need to crop/pad to align
    aruco_desc_tile = draw_aruco_desc_tile(ARUCO_DICT_TYPE_STR, aruco_idx, aruco_length, dpi)
    sine_desc_tile = draw_sine_block_desc_tile(lpmm_list, height*len(lpmm_list), dpi)
    aruco_desc_tile = center_crop_pad_to(aruco_desc_tile, sine_block.shape[0], 1, 255)
    sine_desc_tile = center_crop_pad_to(sine_desc_tile, sine_block.shape[0], 1, 255)

    # gap around ArUco marker
    gap_pix = int(np.round(aruco_marker.shape[1]/(ARUCO_INNER_BIT+2*ARUCO_EDGE_BIT)))
    vert_gap_tile = np.full((aruco_marker.shape[1], gap_pix, 3), 255, np.uint8)
    
    # black/white side tile
    bw_tile = draw_bw_ref_tile(sine_block.shape[0]+gap_pix+aruco_marker.shape[1], 
                               mm_to_pixels(side_width, dpi))

    # other gaps
    filling_gap = np.full((gap_pix-aruco_desc_tile.shape[0]-sine_desc_tile.shape[0], 
                           sine_block.shape[0], 3), 255, np.uint8)
    right_gap = np.full((gap_pix, gap_pix+aruco_marker.shape[1], 3), 255, np.uint8)

    # tile
    top_row = np.concatenate([np.rot90(sine_block, 1), vert_gap_tile, aruco_marker], 1)
    mid_row = np.concatenate([np.concatenate([filling_gap, 
                                              sine_desc_tile, 
                                              aruco_desc_tile], 0), right_gap], 1)
    bot_row = bw_tile
    total_pattern = np.concatenate([top_row, mid_row, bot_row], 0)
    
    ### data file
    meta_dict = {}
    
    # total image height and width
    meta_dict['hw_pix'] = list(total_pattern.shape[:2]) 
    meta_dict['hw_mm'] = pixels_to_mm(np.array(total_pattern.shape[:2]), dpi).tolist()
    
    # aruco marker location and size
    meta_dict['aruco_idx'] = aruco_idx
    meta_dict['aruco_xywhr'] = [sine_block.shape[0]+gap_pix, 0, 
                                aruco_marker.shape[1], aruco_marker.shape[0],
                                0]
    meta_dict['aruco_width_mm'] = pixels_to_mm(aruco_marker.shape[1], dpi)

    # sine block location and size
    meta_dict['sine_xywhr'] = [0, sine_block.shape[1]-1, 
                               sine_block.shape[1], sine_block.shape[0], 
                               -np.pi/2]
    meta_dict['lpmm_list'] = lpmm_list

    # bw_ref chart location
    meta_dict['bw_xywhr'] = [0, sine_block.shape[0]+gap_pix, 
                             bw_tile.shape[1], bw_tile.shape[0],
                             0]
    
    ### return
    return total_pattern, meta_dict

##############################
### affine transform helpers
##############################
def _affine_2x3_to_3x3(H):
    Hp = np.pad(H, ((0,1),(0,0)), mode='constant', constant_values=0)
    Hp[2,2] = 1
    return Hp

def _xywhr_to_ouv(xywhr):
    """
    Transfer rectangle location's xywhr notation to ouv notation
    xywhr: length-5 list. Gives the rectangle's location in source image, by
           top-left (in local coordinate) corner x/y, 
           rectangle width/height (in local coordinate), 
           rotation (rad, clockwise)
    ouv: 3x2 array. origin - u vector - v vector
    """
    x, y, w, h, r = xywhr
    rot_mat = np.array([[np.cos(r), -np.sin(r)], 
                        [np.sin(r), np.cos(r)]], dtype=float)
    ovec = np.array([x, y], dtype=float)
    uvec = np.array(rot_mat @ np.array([[w], [0]], dtype=float)).flatten()
    vvec = np.array(rot_mat @ np.array([[0], [h]], dtype=float)).flatten()
    return np.stack([ovec, uvec, vvec], axis=0)

def _ouv_to_corners(ouv):
    """
    Transfer rectangle location's ouv notation to four corners, 
    starting from top-left corner, clockwise
    ouv: 3x2 array. origin - u vector - v vector
    corners: 4x2 array
    """
    ovec, uvec, vvec = ouv
    return np.stack([ovec, 
                     ovec + uvec,
                     ovec + uvec + vvec,
                     ovec + vvec
                    ], axis=0)

##############################
### extract tiles
##############################
def rec2rec_affine(src_xywhr, tsf_corner_list, partial=True, reverse=False):
    """
    Return an affine transformation 2x3 matrix, from source to transformed (or reversed) 
    defined by rectangle-to-rectangle correspondance
    src_xywhr: length-5 list. Gives the rectangle's location in source image, by
               top-left corner x/y, rectangle width/height, rotation (rad, clockwise)
    tsf_corner_list: 4x2 np.float32 array, gives the rectangle's corners' coordinates in transformed image
                     starting from top-left corner, clockwise
    partial: if True, estimate partial affine, which consists only rotation, scaling, translation
    """
    # build corner list
    src_corner_list = _ouv_to_corners(_xywhr_to_ouv(src_xywhr)).astype(np.float32)
    # from A to B
    if reverse:
        Acl = tsf_corner_list
        Bcl = src_corner_list
    else:
        Acl = src_corner_list
        Bcl = tsf_corner_list
    # partial or full
    if partial:
        H, _ = cv.estimateAffinePartial2D(Acl, Bcl, method=cv.LMEDS)
    else:
        H, _ = cv.estimateAffine2D(Acl, Bcl, method=cv.LMEDS)
    return H

def recout_affine_shape(xywhr, tgt_w):
    """
    Return an affine transformation matrix and a (w,h) tuple
    Which will crop a rectangle out from the original image, 
    and scale its width to tgt_w
    xywhr: length-5 list. Gives the rectangle's location in source image, by
           top-left corner x/y, rectangle width/height, rotation (rad, clockwise)
    tgt_w: target width
    """
    x, y, w, h, r = xywhr
    # translate rectangle's top-left corner to origin
    H_trans = np.array([[1, 0, -x],
                        [0, 1, -y]], dtype=float)
    # rotate rectangle's width edge to horizontal
    H_rot = np.array([[ np.cos(r), np.sin(r), 0],
                      [-np.sin(r), np.cos(r), 0]], dtype=float)
    # scale rectangle to fit target width
    s = tgt_w/w
    tgt_h = np.round(h*s).astype(int)
    H_scale = np.array([[s, 0, 0],
                        [0, s, 0]], dtype=float)
    # combine and return
    H_total = _affine_2x3_to_3x3(H_scale) @ _affine_2x3_to_3x3(H_rot) @ _affine_2x3_to_3x3(H_trans)
    H_total = np.array(H_total[:2], dtype=np.float32)
    return H_total, (tgt_w, tgt_h)
    
def extract_sine_and_bw_tiles(img, aruco_corner_list, meta_dict, 
                              sine_oversample=16, bw_oversample=4,
                              partial=True, interp_flag=cv.INTER_CUBIC):
    """
    Extract sine tiles and bw tile from a ArUco-Sine chart in a frame based on detected ArUco marker
    
    Inputs
    img: HxWx3 or HxW uint8 or np.float32 image containing the ArUco-Sine chart
    aruco_corner_list: 4x2 np.float32 array, starting from origin, clockwise
                       easily generated from cv.aruco.ArucoDetector.detectMarkers() result
    meta_dict: meta data dictionary discribing the property of the board
    sine_oversample: sine tiles' oversample ratio comparing to Myquist frequency of targeting tile
    bw_oversample: bw tile's oversample ratio comparing to input image
    partial: if True, estimate partial affine, which consists only rotation, scaling, translation.
             Should keep True if the chart is fronto-parallel to the camera
    interp_flag: interpolation flag defined by OpenCV
    
    Return values
    tile_list: a list of extracted tiles, last is bw tile, rest are sine tiles
    pp_list: a list of pixel pitch in mm for these tiles
    lpmm_list: the lpmm of the sine tiles
    """
    # source image geometry
    src_pp = meta_dict['aruco_width_mm'] / meta_dict['aruco_xywhr'][2] # source pixel pitch in mm
    # prepare to split sine block to sine tile
    N_tile = len(meta_dict['lpmm_list'])
    sine_block_ouv = _xywhr_to_ouv(meta_dict['sine_xywhr']) # origin-uvector-vvector
    tile_w = meta_dict['sine_xywhr'][2]
    tile_h = meta_dict['sine_xywhr'][3]/N_tile
    tile_r = meta_dict['sine_xywhr'][4]
    
    # affine matrix from transformed image to source image
    H_tsf2src = rec2rec_affine(meta_dict['aruco_xywhr'], aruco_corner_list, 
                               partial=partial, reverse=True)
    s_src2tsf = 1 / np.sqrt(np.linalg.det(H_tsf2src[:2,:2])) # scale
    
    # sine tiles' affine transformation parameter
    tile_xywhr_tgtw_list = []
    pp_list = [] # pixel pitch in mm
    for a, lpmm in enumerate(meta_dict['lpmm_list']):
        tile_xy = sine_block_ouv[0] + a / N_tile * sine_block_ouv[2]
        tgt_w = meta_dict['sine_xywhr'][2] * src_pp * lpmm * 2 * sine_oversample
        tgt_w = np.round(tgt_w).astype(int)
        pp = meta_dict['sine_xywhr'][2] * src_pp / tgt_w
        tile_xywhr_tgtw_list.append([[*tile_xy, tile_w, tile_h, tile_r],
                                      tgt_w])
        pp_list.append(pp)
    
    # bw tile's affine transformation parameter
    bw_tgt_w = np.round(s_src2tsf * bw_oversample * meta_dict['bw_xywhr'][2]).astype(int)
    tile_xywhr_tgtw_list.append([meta_dict['bw_xywhr'], bw_tgt_w])
    pp_list.append(meta_dict['bw_xywhr'][2] * src_pp / bw_tgt_w)
        
    # extract tiles by affine warpping
    tile_list = []
    for xywhr, tgt_w in tile_xywhr_tgtw_list:
        H_src2tgt, tgt_wh = recout_affine_shape(xywhr, tgt_w)
        H_total = _affine_2x3_to_3x3(H_src2tgt) @ _affine_2x3_to_3x3(H_tsf2src)
        H_total = np.array(H_total, dtype=np.float32)[:2]
        roi_img = cv.warpAffine(img, H_total, tgt_wh, flags=interp_flag)
        tile_list.append(roi_img)
        
    # return
    return tile_list, pp_list, meta_dict['lpmm_list']

##############################
### estimate mtf
##############################
def estimate_comm_diff_from_bw_tile(bw_tile, bezel_ratio=0.1):
    """
    bw_tile should be a MxN 0-1 float array
    Along width, left 1/4 is pure black, right 1/4 is pure white,
    middle 1/2 is gradient, black to white
    """
    # split pure color blocks
    sub_width = bw_tile.shape[1]//4
    b_block = bw_tile[:, :sub_width]
    w_block = bw_tile[:, -sub_width:]
    b_block = remove_bezel(b_block, bezel_ratio)
    w_block = remove_bezel(w_block, bezel_ratio)
    # calculate 
    b_value = b_block.mean()
    w_value = w_block.mean()
    comm_mode = (b_value + w_value) / 2
    diff_mode = (w_value - b_value) / 2
    # return
    return comm_mode, diff_mode

def estimate_mtf_from_sine_tile(sine_tile, lpmm, pp, 
                                comm_mode=0.5, diff_mode=0.5, 
                                freq_diff_ratio=0.15, bezel_ratio=0.1
                               ):
    """
    sine_tile:       a MxN 0-1 float array, sine wave along horizontal direction
    lpmm:            spatial frequency of that sine wave in lp/mm
    pp:              pixel pitch of input tile in mm
    comm/diff_mode:  common/differential mode estimated from bw tile, 
                     eliminates error from illumination/exposure/etc
    freq_diff_ratio: the ratio of difference tolerance, defines the integration window
                     0.15 is about 9 degrees rotation
    bezel_ratio:     bezel width ratio to remove
                     allows slightly tilting/distortion
    """
    # preprocess and parse parameter
    tile = remove_bezel(sine_tile, bezel_ratio) # remove bezel
    tile = (tile - comm_mode) / diff_mode # make zero-mean, normalize scale
    tile_h, tile_w = tile.shape[:2]
    lpmm_whw = lpmm * freq_diff_ratio
    
    # fft to spectrum
    spec = np.fft.fftshift(np.fft.rfftn(tile), 0)
    spec = spec/spec.size # normalize power
    fx = np.fft.rfftfreq(tile_w, pp)
    fy = np.fft.fftshift(np.fft.fftfreq(tile_h, pp))
    
    # calculate MTF by power within the window
    fx_inline_idx = np.argwhere(np.abs(fx-lpmm)<=lpmm_whw).reshape(1,-1)
    fy_inline_idx = np.argwhere(np.abs(fy)<=lpmm_whw).reshape(-1,1)
    p_spec = np.power(np.abs(spec[fy_inline_idx, fx_inline_idx]), 2).sum()
    mtf = np.sqrt(p_spec) # MTF is amplitude ratio, square root of power ratio
    
    return mtf

# def estimate_mtf_from_sine_tile(sine_tile, lpmm, pp, 
#                                 comm_mode=0.5, diff_mode=0.5, 
#                                 freq_diff_ratio=0.15, bezel_ratio=0.1
#                                ):
#     """
#     sine_tile:       a MxN 0-1 float array, sine wave along horizontal direction
#     lpmm:            spatial frequency of that sine wave in lp/mm
#     pp:              pixel pitch of input tile in mm
#     comm/diff_mode:  common/differential mode estimated from bw tile, 
#                      eliminates error from illumination/exposure/etc
#     freq_diff_ratio: the freq peak value error tolarence
#     bezel_ratio:     bezel width ratio to remove
#                      allows slightly tilting/distortion
#     """
#     # preprocess and parse parameter
#     tile = remove_bezel(sine_tile, bezel_ratio) # remove bezel
#     tile = (tile - comm_mode) / diff_mode # make zero-mean, normalize scale
#     tile_h, tile_w = tile.shape[:2]
#     freq_diff = lpmm * freq_diff_ratio
    
#     # fft to spectrum
#     spec = np.fft.fftshift(np.fft.rfftn(tile), 0)
#     spec = spec/spec.size # make total power 1
    
#     # find peak power spec
#     p_spec = np.power(np.abs(spec), 2) # amplitude to power
#     ind = np.unravel_index(np.argmax(p_spec, axis=None), p_spec.shape)
    
#     # assert that peak power spec is close to where it should be
#     fx = np.fft.rfftfreq(tile_w, pp)[ind[1]]
#     fy = np.fft.fftshift(np.fft.fftfreq(tile_h, pp))[ind[0]]
    
#     # return ntf
#     if np.sqrt((fx-lpmm)**2 + fy**2) > freq_diff:
#         return None
#     else:
#         return np.sqrt(p_spec[ind]) # MTF is amplitude ratio, square root of power ratio