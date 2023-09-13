#!/bin/bash

SESSNAME=cam_daemon_sess

# check if the session exists. If so, kills it
tmux has-session -t $SESSNAME 2>/dev/null
if [ "$?" -eq "0" ]; then
    echo "Warning: there exists a tmux session named $SESSNAME. Restart it."
    tmux kill-session -t $SESSNAME
fi
# start new session
tmux new -d -s $SESSNAME
# clear old log file
rm ~/Desktop/Arducam_example/logs/tmp_log.txt 2>/dev/null
# pipe tmux pane to a text file
tmux pipe-pane -o -t $SESSNAME "cat | tee ~/Desktop/Arducam_example/logs/tmp_log.txt >> ~/Desktop/Arducam_example/logs/#h_cam_daemon_log_$(date '+%Y%m%d_%H%M%S').txt"
# start cam_daemon
tmux send-keys -t $SESSNAME "cd ~/Desktop/Arducam_example" ENTER
tmux send-keys -t $SESSNAME "python cam_daemon.py" ENTER
