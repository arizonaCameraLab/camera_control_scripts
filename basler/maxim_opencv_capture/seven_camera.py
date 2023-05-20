import pypylon
import cv2
import time

# Set up camera configuration
num_cameras = 7
camera_resolution = (3840, 2160)  # 4K resolution
camera_fps = 50 # frames per second
bandwidth_limit = 380000000  # 380 MB/s
recording_duration = 30  # seconds

# Connect to cameras
devices = pypylon.factory.find_devices()
cameras = [pypylon.factory.create_device(devices[i]) for i in range(num_cameras)]

# Set up camera parameters
for camera in cameras:
    camera.open()
    camera.properties['AcquisitionFrameRateAbs'] = camera_fps
    camera.properties['Width'] = camera_resolution[0]
    camera.properties['Height'] = camera_resolution[1]
    camera.properties['BslUSBCameraBandwidth'] = bandwidth_limit
    camera.start_grabbing()

# Save video streams from cameras
video_writers = [cv2.VideoWriter(f'camera_{i}.avi', cv2.VideoWriter_fourcc(*'XVID'), camera_fps, camera_resolution)
                 for i in range(num_cameras)]

start_time = time.time()
while (time.time() - start_time) < recording_duration:
    grab_results = [camera.retrieve_result() for camera in cameras]
    for i, result in enumerate(grab_results):
        if result.grabSucceeded():
            img = result.array
            video_writers[i].write(img)

# Clean up
for camera in cameras:
    camera.stop_grabbing()
    camera.close()
for video_writer in video_writers:
    video_writer.release()
