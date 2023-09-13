#!/bin/bash

SESSNAME=cam_daemon_sess

# check if the session exists. If not, do nothing
tmux has-session -t $SESSNAME 2>/dev/null
if ! [ "$?" -eq "0" ]; then
    exit 0
fi
# If so, close camera daemon and kill session
tmux send-keys -t $SESSNAME q ENTER
tmux kill-session -t $SESSNAME
