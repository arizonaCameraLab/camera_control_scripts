'''
A simple Program for grabing video from basler camera and converting it to opencv img.
Tested on Basler acA1300-200uc (USB3, linux 64bit , python 3.5)

'''
from pypylon import pylon
import cv2
import sys
import time
import os


# Get the transport layer factory.
tlFactory = pylon.TlFactory.GetInstance()

# Get all attached devices and exit application if no device is found.
devices = tlFactory.EnumerateDevices()
if len(devices) == 0:
    raise pylon.RuntimeException("No camera present.")

# Create an array of instant cameras for the found devices and avoid exceeding a maximum number of devices.
cameras = pylon.InstantCameraArray(len(devices))

l = cameras.GetSize()
#print(sys.argv)
#cam_idx = int(sys.argv[1])
#assert cam_idx < l, "{} cameras attached, cam {} not found".format(l, cam_idx)

# conecting to the first available camera

camera = pylon.InstantCamera(tlFactory.CreateDevice(devices[4]))
print("Using device ", camera.GetDeviceInfo().GetModelName(), camera.GetDeviceInfo().GetSerialNumber())

# Grabing Continusely (video) with minimal delay
camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
converter = pylon.ImageFormatConverter()

# converting to opencv bgr format
converter.OutputPixelFormat = pylon.PixelType_BGR8packed
converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

# fourcc = cv2.VideoWriter_fourcc(*'XVID')
# out = cv2.VideoWriter('output1.avi', fourcc, 45.0, (3840, 2160))


img_array = []
frames = 0
max_frames = 600
start_time=time.time()
while camera.IsGrabbing():
    grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

    if grabResult.GrabSucceeded():
        # Access the image data
        image = converter.Convert(grabResult)
        img = image.GetArray()
        img_array.append(img)
        frames += 1
        if frames >= max_frames:
            camera.StopGrabbing()
            break



        #print(img.shape)
        # out.write(img)
        # cv2.namedWindow('title', cv2.WINDOW_NORMAL)
        # cv2.imshow('title', img)
        # k = cv2.waitKey(1)
        # if k == 27:
        #     break
    grabResult.Release()

end_time=time.time()

# Releasing the resource
print("Grab finished, saving images cam05")
print("Total runtime cam05: " + str(end_time-start_time) + " seconds")
print("Frames/second cam05: " + str(max_frames/(end_time-start_time)))

path = 'camera5'
if os.path.exists(path) == False:
    os.mkdir(path)

for i in range(max_frames):
    filename = '5_' + str(i) + '_savedImage.png'
    cv2.imwrite(os.path.join(path, filename), img_array[i])
