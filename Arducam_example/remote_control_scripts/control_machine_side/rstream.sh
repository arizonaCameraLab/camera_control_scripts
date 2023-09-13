#!/bin/bash
case $1 in
	1|2|3|4)
		SRC="cam$1"
		;;
	*)
		echo "Needs to specify the index of source camera. Select from 1,2,3,4"
		exit 1
esac

ssh $SRC "cd Desktop/Arducam_example/; python3 displayer.py"
# ssh $SRC "cd Desktop/Arducam_example/; python3 displayer.py --prop_file props_backup.json"
