# increase usb buffer size
sudo sh -c 'echo 20000 > /sys/module/usbcore/parameters/usbfs_memory_mb'
# increase maximum amount of files opened at the same time
ulimit -n 8192 
