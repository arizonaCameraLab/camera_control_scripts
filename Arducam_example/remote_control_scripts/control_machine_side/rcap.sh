#!/bin/bash

# select proper camera source
case $1 in
	1|2|3|4)
		SRC="cam$1"
		;;
	*)
		echo "Needs to specify the index of source camera. Select from 1,2,3,4"
		exit 1
esac

# capture a png frame
fname="~/Videos/tmp.png"
#ssh $SRC "gst-launch-1.0 v4l2src num-buffers=1 ! pngenc ! filesink location=$fname"
ssh $SRC "cd Desktop/Arducam_example/; python3 capture.py"
#scp $SRC:$fname ./

exit 0
