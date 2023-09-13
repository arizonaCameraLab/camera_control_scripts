#!/bin/bash
SESSNAME=cam_stream_

# open tmux sessions and start remote streaming
for i in {1..4}; do
    tmux new -d -s "$SESSNAME$i"
    tmux send-keys -t "$SESSNAME$i" "ssh cam$i 'cd Desktop/Arducam_example/; python3 displayer.py --prop_file props.json'" ENTER
done

# wait for shutdown command
while :
do
	read -p "Stop streaming? (y/n) " VAL_CHAR
	if [[ $VAL_CHAR =~ ^[Yy]$ ]]
	then
    		break
	fi
done

# kill remote streaming sessions
for i in {1..4}; do
    tmux kill-session -t "$SESSNAME$i"
done
