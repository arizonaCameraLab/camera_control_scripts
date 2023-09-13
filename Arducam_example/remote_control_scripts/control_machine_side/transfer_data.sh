FILE1=$1


scp cam1:~/Desktop/Arducam_example/frames/${FILE1}_* ~/Downloads/cam1 &
scp cam2:~/Desktop/Arducam_example/frames/${FILE1}_* ~/Downloads/cam2 &
scp cam3:~/Desktop/Arducam_example/frames/${FILE1}_* ~/Downloads/cam3 &
scp cam4:~/Desktop/Arducam_example/frames/${FILE1}_* ~/Downloads/cam4 &
wait

ssh cam1 "rm ~/Desktop/Arducam_example/frames/$FILE1*" &
ssh cam2 "rm ~/Desktop/Arducam_example/frames/$FILE1*" &
ssh cam3 "rm ~/Desktop/Arducam_example/frames/$FILE1*" &
ssh cam4 "rm ~/Desktop/Arducam_example/frames/$FILE1*" &
wait
