import os
import sys
import subprocess
import shutil
import argparse
import logging
from logging import critical, error, info, warning, debug
from datetime import datetime

########################################
### Argument parsing and logging setup
########################################
def parseArguments():
    """
    Read arguments from the command line
    """
    ### compose parser
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--params', type=str, default='array_params.json',
                        help='The json file holding the array camera parameters.')
    parser.add_argument('-c', '--cam_ind_list', nargs='+', type=int, required=True, 
                        help='A list of camera indices.')      
    parser.add_argument('-n', '--amount', type=int, default=45,
                        help='Frame amount to save, 0 for manual stop. '\
                            +'Default 45 (about one sec). Maximum for 7 raw 4k is about 450.')
    parser.add_argument('-m', '--save_mode', type=str, choices=['raw', 'rgb', '4bit-left'], default='raw',
                        help='Save mode. 4bit-left would move 12-bit image left 4 bits, to 16-bit.')
    parser.add_argument('-f', '--folder', type=str, default='array_cap',
                        help='saving folder. Default \'array_cap\', timestamp auto appended. Create if not exist')
    parser.add_argument('-v', '--verbose', type=int, default=1, 
                        help='Verbosity of logging: 0-critical, 1-error, 2-warning, 3-info, 4-debug')
    parser.add_argument('--dryrun', action='store_true',
                        help='generate commands recipe instead of run commands.')
    ### parse args
    args = parser.parse_args()
    ### set logging
    vTable = {0: logging.CRITICAL, 1: logging.ERROR, 2: logging.WARNING, 
              3: logging.INFO, 4: logging.DEBUG}
    logging.basicConfig(format='%(levelname)s: %(message)s', level=vTable[args.verbose], stream=sys.stdout)
    
    return args

def main(args):
    # parameters
    dateFormat = '%Y%m%d_%H%M%S.%f'
    startTime = datetime.now()
    folder_name = args.folder + '_' + startTime.strftime(dateFormat)[:-4]
    
    # make temperal command recipe
    cmd_head = 'python single_cam_cap.py'
    cmd_tail = ' '.join(['-n {}'.format(args.amount),
                         '-p {}'.format(args.params), 
                         '-m {}'.format(args.save_mode), 
                         '-v {}'.format(args.verbose)])
    cmd_list = []
    for idx in args.cam_ind_list:
        ind_str = '-c {}'.format(idx)
        subfolder = os.path.join(folder_name, 'cam_{}'.format(idx))
        folder_str = '-f {}'.format(subfolder)
        cmd_str = ' '.join([cmd_head, ind_str, folder_str, cmd_tail])
        cmd_list.append(cmd_str)
    recipe_name = 'recipe_' + startTime.strftime(dateFormat)[:-4] + '.txt'
    with open(recipe_name, 'w') as fp:
        for cmd_str in cmd_list:
            fp.write(cmd_str + '\n')
            
    # stop if dryrun
    if args.dryrun:
        return
     
    # validate folder
    if not os.path.exists(folder_name):
        os.mkdir(folder_name)
        info('Folder {} made for saving.'.format(folder_name))
        
    # parallel run the command list
    subprocess.run('parallel -a {}'.format(recipe_name), shell=True)
        
    # put recipe to folder
    shutil.move(recipe_name, os.path.join(folder_name, recipe_name))
    
if __name__ == '__main__':
    args = parseArguments()
    main(args)
