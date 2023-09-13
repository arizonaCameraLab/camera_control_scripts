FILE1=$1
ssh cam1 "./trigger_capture.sh -o $FILE1 -e 4000 -n 20" &
ssh cam2 "./trigger_capture.sh -o $FILE1 -e 4000 -n 20" &
ssh cam3 "./trigger_capture.sh -o $FILE1 -e 4000 -n 20" &
ssh cam4 "./trigger_capture.sh -o $FILE1 -e 4000 -n 20" &
wait
