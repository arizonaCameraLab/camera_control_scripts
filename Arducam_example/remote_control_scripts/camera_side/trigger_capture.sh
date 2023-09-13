#!/bin/bash

SESSNAME=cam_daemon_sess
LOGFILE=~/Desktop/Arducam_example/logs/tmp_log.txt

# parse input parameters
exposure=300
count=5
outname=""
while getopts ":e:n:o:h" opt; do
    case $opt in
        e) 
            exposure="$OPTARG"
            ;;
        n) 
            count="$OPTARG"
            ;;
        o) 
            outname="$OPTARG"
            ;;
        h) 
            echo "Trigger the running cam_daemon to capture a set of frames"
            echo "Usage: ./trigger_capture.sh [-e exposure] [-n count] [-o out_name_prefix]"
            echo "  exposure: integer 1-65535, default 300"
            echo "  count: positive integer, default 5"
            echo "  out_name_prefix: string, default None, using timestamp as file name"
            echo "Captured frames are stored in ~/Desktop/Arducam_example/frames"
            exit 0
            ;;
        \?) 
            echo "Invalid option -$OPTARG" >&2
            exit 1
            ;;
        :)
            echo "Option -$OPTARG requires an argument." >&2
            exit 1
            ;;
  esac
done

# capture images
if [[ $outname = "" ]]
then
    tmux send-keys -t $SESSNAME "c -e $exposure -n $count" ENTER
else
    tmux send-keys -t $SESSNAME "c -e $exposure -n $count -o $outname" ENTER
fi

# wait for finish
while ! [[ $(tail -n 1 $LOGFILE) = Finish.* ]]
do
    sleep 0.1
done

# exit
exit 0
