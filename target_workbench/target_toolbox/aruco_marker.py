import numpy as np
import cv2 as cv
from .common import mm_to_pixels

##############################
### constants
##############################
ARUCO_DICT_SET = {
    "DICT_4X4_50": cv.aruco.DICT_4X4_50,
    "DICT_4X4_100": cv.aruco.DICT_4X4_100,
    "DICT_4X4_250": cv.aruco.DICT_4X4_250,
    "DICT_4X4_1000": cv.aruco.DICT_4X4_1000,
    "DICT_5X5_50": cv.aruco.DICT_5X5_50,
    "DICT_5X5_100": cv.aruco.DICT_5X5_100,
    "DICT_5X5_250": cv.aruco.DICT_5X5_250,
    "DICT_5X5_1000": cv.aruco.DICT_5X5_1000,
    "DICT_6X6_50": cv.aruco.DICT_6X6_50,
    "DICT_6X6_100": cv.aruco.DICT_6X6_100,
    "DICT_6X6_250": cv.aruco.DICT_6X6_250,
    "DICT_6X6_1000": cv.aruco.DICT_6X6_1000,
    "DICT_7X7_50": cv.aruco.DICT_7X7_50,
    "DICT_7X7_100": cv.aruco.DICT_7X7_100,
    "DICT_7X7_250": cv.aruco.DICT_7X7_250,
    "DICT_7X7_1000": cv.aruco.DICT_7X7_1000,
    "DICT_ARUCO_ORIGINAL": cv.aruco.DICT_ARUCO_ORIGINAL,
#    "DICT_APRILTAG_16h5": cv.aruco.DICT_APRILTAG_16h5,
#    "DICT_APRILTAG_25h9": cv.aruco.DICT_APRILTAG_25h9,
#    "DICT_APRILTAG_36h10": cv.aruco.DICT_APRILTAG_36h10,
#    "DICT_APRILTAG_36h11": cv.aruco.DICT_APRILTAG_36h11
}

ARUCO_INNER_BIT = 5
ARUCO_AMOUNT = 100
ARUCO_EDGE_BIT = 1
ARUCO_DICT_TYPE_STR = 'DICT_{0}X{0}_{1}'.format(ARUCO_INNER_BIT, ARUCO_AMOUNT)
ARUCO_DICT_TYPE = ARUCO_DICT_SET[ARUCO_DICT_TYPE_STR]

##############################
### marker generators
##############################
def draw_aruco_marker(aruco_dict_type, index, length, dpi):
    # parse edge pixel length
    side_pixels = mm_to_pixels(length, dpi)

    # load the ArUCo dictionary
    aruco_dict = cv.aruco.getPredefinedDictionary(aruco_dict_type)

    # make marker
    aruco_marker = aruco_dict.generateImageMarker(index, side_pixels)
    aruco_marker = cv.cvtColor(aruco_marker, cv.COLOR_GRAY2BGR)
    
    return aruco_marker

def draw_aruco_desc_tile(aruco_dict_type_str, index, length, dpi):
    # parse edge pixel length
    side_pixels = mm_to_pixels(length, dpi)

    # make description tile
    desc_str = '; '.join(['ArUco',
                          aruco_dict_type_str, 
                         'Index {}'.format(index),
                         '{0:d}mmx{0:d}mm'.format(length)
                        ])
    text_canvas_height = np.round(side_pixels * 0.06).astype(int)
    text_canvas = np.full((text_canvas_height, side_pixels, 3), 
                          255, np.uint8)
    cv.putText(text_canvas, desc_str, 
               (np.round(side_pixels*0.03).astype(int), np.round(text_canvas_height*0.72).astype(int)), 
               cv.FONT_HERSHEY_SIMPLEX, side_pixels*0.0012, 
               (0,0,0), np.round(side_pixels*0.003).astype(int), cv.LINE_AA, False)
    
    return text_canvas

##############################
### marker detection and evaluation
##############################
def square_score(x, y, flip=False, uplimit=100.0, eps=1e-5):
    """
    Give a score of the "squareness" of four points
    The smaller, the more these for points form a square
    Note these points needs to be in a clockwise order. 
    If in image coordinate system (x to right, y to down), need to flip
    Mathematically, the score is defined by: 
        fitting a square to match the points giving the least square error
        the negative log of that square error
    By my vision test, above 8.5 usually means a good square
    """
    assert len(x)==4 and len(y)==4, \
    'Need four x and four y'
    if flip:
        y = -y
    
    x0 = np.mean(x)
    y0 = np.mean(y)
    u = (x[0]-y[1]-x[2]+y[3])/4
    v = (y[0]+x[1]-y[2]-x[3])/4
    
    s = (np.power(x,2).sum() + np.power(y,2).sum() - 4*(x0**2) - 4*(y0**2))/(u**2+v**2+eps) - 4
    
    if s <= 0:
        return uplimit
    else:
        return np.clip(-np.log(s), None, uplimit)

##############################
### marker displayers
##############################
def draw_aruco_coordinate(img, corner_list, color=(0,255,0)):
    """
    Draw ArUco marker's origin coordinate under it. Note that it alters the original image
    img should be a unit8 numpy array, the BGR image containing the ArUco markers
    corner_list should be a list of 1x4x2 numpy float array, returned by cv.aruco.ArucoDetector.detectMarkers()
    """
    for corner in corner_list:
        # define text location
        x, y = corner[0][0]
        bot_y = corner[0,:,1].max()    
        center_x = corner[0,:,0].mean()
        width = corner[0,:,0].max() - corner[0,:,0].min()
        
        # draw text
        coor_str = '({:.0f}, {:.0f})'.format(x, y) # its float type, but only gives integers
        cv.putText(img, coor_str, 
                   (np.round(center_x - width*len(coor_str)*0.1).astype(int), np.round(bot_y + width*0.38).astype(int)), 
                   cv.FONT_HERSHEY_SIMPLEX, width*0.012, 
                   color, np.round(width*0.025).astype(int), cv.LINE_AA, False)
    return img
    
def draw_aruco_square_score(img, corner_list, threshold=8.5):
    """
    Draw ArUco marker's square score above it. Note that it alters the original image
    img should be a unit8 numpy array, the BGR image containing the ArUco markers
    corner_list should be a list of 1x4x2 numpy float array, returned by cv.aruco.ArucoDetector.detectMarkers()
    score above threshold will be displayed green, otherwise, red
    """
    for corner in corner_list:
        # calculate score and color
        score = square_score(*corner[0].transpose(), True)
        if score >= threshold:
            color = (0,255,0)
        else:
            color = (0,0,255)
        
        # define text location
        x, y = corner[0][0]
        top_y = corner[0,:,1].min()    
        center_x = corner[0,:,0].mean()
        width = corner[0,:,0].max() - corner[0,:,0].min()
        
        # draw text
        text_str = '{:.1f}'.format(score) # its float type, but only gives integers
        cv.putText(img, text_str, 
                   (np.round(center_x - width*len(text_str)*0.12).astype(int), np.round(top_y - width*0.1).astype(int)), 
                   cv.FONT_HERSHEY_SIMPLEX, width*0.012, 
                   color, np.round(width*0.025).astype(int), cv.LINE_AA, False)
    return img
