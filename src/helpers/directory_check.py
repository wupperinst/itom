#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jul  5 11:34:54 2019

@author: dariyoushsh
"""

import os, sys, shutil
from . import color as color

def check_directory(model_run_code, repo_path):
    '''
    Check if directories named model_run_code exist in /input, /output, and /notebooks.
    If the directories don't exist, they are created.
    If the directories exist, the user is warned.
    If the directories exist and are not empty, confirmation by the user is required to 
    resume (existing files will be overwritten).
    '''
    os.chdir(repo_path)
    for loc in ['input', 'output', 'log']:
        os.chdir(repo_path)
        os.chdir(loc)
        exists = True if os.path.exists(model_run_code) else False
        if exists:
#            print('Directory: ', color.orange(loc))
#            print('Sub-directory `{}` exists.'.format(color.green(model_run_code)))
            is_dir = True if os.path.isdir(model_run_code) else False
            is_empty = True if len(os.listdir(model_run_code)) == 0 else False
            if is_dir and is_empty:
                continue
#                print('`{}` is empty'.format(model_run_code))
#                if loc == 'input':
#                    while True:
#                        answer = input(color.cyan('Do you want to continue? [Y] for Yes & [N] for No: '))
#                        if answer not in('Y', 'N'):
#                            print('Sorry, Please enter [Y] if you want to continue, otherwise, enter [N].')
#                            continue
#                        elif answer == 'N':
#                            print(color.red('Operation Aborted!'))
#                            sys.exit()
#                        else:
#                            print(color.green('Continue...'))
#                            break
            else:
                print('     Directory {}/{} is not empty.'.format(loc, model_run_code))
#                print('Directory: ', color.orange(loc))
#                print(color.orange('`{}` is not empty.'.format(model_run_code)))
#                    print(color.orange('`{}` is NOT empty!! List of the files:\n'.format(model_run_code)))
#                    print(os.listdir(model_run_code))
#                while True:
#                    answer = input(color.cyan('Do you want to continue? [Y] for Yes & [N] for No: '))
#                    if answer not in('Y', 'N'):
#                        print('Sorry, Please enter [Y] if you want to continue, otherwise, enter [N].')
#                        continue
#                    elif answer == 'N':
#                        print(color.red('Operation Aborted!'))
#                        sys.exit()
#                    else:
##                            if loc == 'log':
##                                print('Deleting old log files...')
##                                for f in os.listdir(model_run_code):
##                                    f_path = os.path.join(model_run_code, f)
##                                    try:
##                                        if os.path.isfile(f_path):
##                                            os.unlink(f_path)
##                                        # To remove sub-directories too
##                                        #elif os.path.isdir(f_path): shutil.rmtree(f_path)
##                                    except Exception as e:
##                                        print(e)
#                        print(color.green('Continue...'))
#                        break
        else:
            print('     Creating directory {}/{}.'.format(loc, model_run_code))
            os.mkdir(model_run_code)
        os.chdir(repo_path)
    os.chdir(repo_path)

