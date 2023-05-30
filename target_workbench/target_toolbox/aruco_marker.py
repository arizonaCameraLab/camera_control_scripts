import numpy as np
import cv2 as cv

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
    side_pixels = np.round(dpi / 25.4 * length).astype(int)

    # load the ArUCo dictionary
    aruco_dict = cv.aruco.getPredefinedDictionary(aruco_dict_type)

    # make marker
    aruco_marker = aruco_dict.generateImageMarker(index, side_pixels)
    aruco_marker = cv.cvtColor(aruco_marker, cv.COLOR_GRAY2BGR)
    
    return aruco_marker

def draw_aruco_desc_tile(aruco_dict_type_str, index, length, dpi):
    # parse edge pixel length
    side_pixels = np.round(dpi / 25.4 * length).astype(int)

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
               (np.round(side_pixels*0.03).astype(int), np.round(text_canvas_height*0.8).astype(int)), 
               cv.FONT_HERSHEY_SIMPLEX, side_pixels*0.0012, 
               (0,0,0), np.round(side_pixels*0.003).astype(int), cv.LINE_AA, False)
    
    return text_canvas

##############################
### marker displayers
##############################
def draw_aruco_coordinate(img, corner_list, color=(0,0,255)):
    """
    Draw ArUco marker's origin coordinate under it
    img should be a unit8 numpy array, the BGR image containing the ArUco markers
    corner_list should be a list of 1x4x2 numpy float array, returned by cv.aruco.ArucoDetector.detectMarkers()
    color should be a length-3 tuple, denoting unit8 BGR color
    """
    canvas = np.copy(img)
    for corner in corner_list:
        x, y = corner[0][0]
        bot_y = corner[0,:,1].max()    
        left_x = corner[0,:,0].min()
        width = corner[0,:,0].max() - left_x
        coor_str = '({:.1f}, {:.1f})'.format(x, y)
        cv.putText(canvas, coor_str, 
                   (np.round(left_x - width*len(coor_str)*0.06).astype(int), np.round(bot_y + width*0.38).astype(int)), 
                   cv.FONT_HERSHEY_SIMPLEX, width*0.012, 
                   (0,0,255), np.round(width*0.025).astype(int), cv.LINE_AA, False)
    return canvas