#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  8 15:34:46 2020

@author: dariyoush
"""
import pandas as pd
import os
from pathlib import Path
from . import color as color

def InOut_union(input_path, sets):
    '''
    Returns the indexes of technologies that do not exist in neither InputActivityRatio
    nor in OutputActivityRatio
    
    Arguments
    ---------
        input_path: String
        sets: Dict
    
    Return
    ------
        List
        
    '''
    files = ['InputActivityRatio', 'OutputActivityRatio']
    InOut = {}
    # Read abovementioned files as a DataFrame and add them to a dict.
    for file in files:
        df = pd.read_csv(os.path.join(input_path, file + '.csv'))
        InOut[file] = df
    # Take the union of two list
    both = list(set().union(InOut['InputActivityRatio'].TECHNOLOGY, InOut['OutputActivityRatio'].TECHNOLOGY))
    # Check the values to see whether they exist in TECHNOLOGY set or not
    exist = sets['TECHNOLOGY'].TECHNOLOGY.apply(lambda x: x in both)  
    # Return a list correspondig to the indecies of technologies that don't exist      
    return exist[exist == False].index
    
def transport_parameters_check(input_path):
    '''
    Check the two “TransportCapacity.csv” and “TransportRoute.csv” parameters as follows:
    
    Note
    ----
        Each transport link in TransportCapacity (even if capacity is zero) should
        also appear in TransportRoute with value = 1. If that’s not the case, output to the screen.
        If there is a transport link in one file but not in the other, output the info to the screen.
        In both parameters, if both LOCATIONs are the same, the TransportMode should be “ONSITE”.
        Output to screen if such cases occur.

    Arguments
    ---------
        input_path: String
    
    Return
    ------
        None
    
    '''
    files = ['TransportCapacity', 'TransportRoute']
    cap_rot = {}
    # Read abovementioned files as a DataFrame and add them to a dict.
    for file in files:
        df = pd.read_csv(os.path.join(input_path, file + '.csv'))
        cap_rot[file] = df
    cap = cap_rot['TransportCapacity']
    rout = cap_rot['TransportRoute']
    # Check if a DataFrame exist
    trans_link = pd.merge(cap, rout, indicator=True, how='outer')
    # Check if a row exist only if in TransportCapacity
    only_capacity = trans_link[trans_link['_merge'] == 'left_only']
    if len(only_capacity) >= 1:
        print(color.red('The following rows from `TransportCapacity` do not exist in `TransportRoute`'))
        print(only_capacity)
    if (cap['LOCATION'] == cap['LOCATION.1']).any() or (rout['LOCATION'] == rout['LOCATION.1']).any():
        cap_onsite = cap[(cap['LOCATION'] == cap['LOCATION.1']) & (cap['TRANSPORTMODE'] != 'ONSITE')]
        rout_onsite = rout[(rout['LOCATION'] == rout['LOCATION.1']) & (rout['TRANSPORTMODE'] != 'ONSITE')]
        if not cap_onsite.empty:
            print(color.orange('\nProblem with ONSITE TransportMode in Capacity:\n'))
            print(cap_onsite)
        if not rout_onsite.empty:
            print(color.orange('\nProblem with ONSITE TransportMode in Route:\n'))
            print(rout_onsite)
        
def check_input_data(input_path, param_set_index, config):
    '''
    Check the `parameters set index` and list the indexes of descripancies.
    
    Arguments
    ---------
        input_path: String
        param_set_index: List
            list of sets in input_path which their name are all in capital
        config: Dict
        
    Return
    ------
        None  
    
    '''
    avoid_files = ['INFO.csv', '.DS_Store']
    # Check the config file and to see whether proc_list and prod_list are defined,
    # if yes, assign proc and prod to True and False if not.
    proc = True if len(config['processes']['proc_list']) > 1 else False
    prod = True if len(config['products']['prod_list']) > 1 else False
    sets = {}
    mismatch = {}
    dupi = {}
    dup = {}
    # Read all sets in the directory and put them in a dict names `sets`
    for el in param_set_index:
        set_df = pd.read_csv(os.path.join(input_path, el + '.csv'))
        if set_df.duplicated().any():
            print(color.red('Duplicate value detected in set: '), el)
            print(set_df[set_df.duplicated() == True])
            print(color.green('The duplicate value/s droped.'))
            # Only take the unique values
            set_df = set_df.drop_duplicates()
        sets[el] = set_df
    # The following for loop checks if the data has descripancy or not
    for file in os.listdir(input_path):
        # only check the `.csv` files and exclude `sets` 
        if file.endswith('.csv') and file.split('.')[0] not in param_set_index and file not in avoid_files:
            # Read the `.csv` file as a pandas DataFrame
            df = pd.read_csv(os.path.join(input_path, file))
            # Select the columns except the last one
            df_cols = df.columns[:-1]
            # This `if` checks if proc/prod_list.csv exist and ignore them if they do
            if proc or prod:
                if file == 'proc_list.csv' or file == 'prod_list.csv':
                    print(file, color.orange(' ignored'))
                    continue
#            print('checking...', color.cyan(file))
            # This foor loop runs over every parameter index
            for col in df_cols:
                # check if the DataFrame has two or more columns of same categoty
                # e.g.: `LOCATION` and `LOCATION.1`
                if '.' in col:
                    col = col.split('.')[0]
                # If values match it prints a verification
                if df[col].isin(sets[col][col]).all():
                    pass
                    #print(col, color.green('looks good'))
                # if values don't match it prints a warning and shows the position
                # of the descripancy (i.e. shows the index)
                
                # Runs if there are duplicate rows with same value in parameter name 
                elif df.duplicated().any():
                    print(color.red('Duplicate rows with same value in `{}` detected!'.format(file)))
                    print(df[df.duplicated()])
                    dupi[file] = df[df.duplicated()]
                    df = df.drop_duplicates()
                    print(color.green('Duplicate rows have been removed.'))
                
                # Runs if there are duplicate rows with DIFFERENT value in parameter name
                elif df.duplicated(subset=df_cols).any():
                    print(color.red('Duplicate rows with different values in \
                                    `{}` detected BUT NOT REMOVED!'.format(file)))
                    print(df[df.duplicated(subset=df_cols)])
                    dup[file] = df[df.duplicated(subset=df_cols, keep=False)]
                
                else:
                    discrep = df[col].isin(sets[col][col])
                    print(color.red('There is a discrepancy in'), file,
                          color.red('in column'), col, color.red('in the\
                          following index/es.'))
                    print(discrep[discrep == False])
                    mismatch[file] = df[col].loc[discrep[discrep == False].index]
    if len (mismatch) == 0:
        pass
#        print(color.green('\nNo Descrepancy Found In DataFrames :)'))
    else:
        print(color.red('Following Values Do Not Match:\n'))
        for key, val in mismatch.items():
            print(color.orange(key))
            print(mismatch[key])
#            print(os.path.abspath(os.path.join(input_path, os.pardir), config['model_run_code'], key)))
            print(os.path.join(Path(input_path).parent.parent, 'log', config['model_run_code'], key))
            mismatch[key].to_csv(os.path.join(Path(input_path).parent.parent, 'log', config['model_run_code'], key), sep='\t')
        
    InOut_desc = InOut_union(input_path, sets)
    if not InOut_desc.empty:
        print(color.red('\nThe following technologies do not exist in neither InputActivityRatio nor in OutputActivityRatio:'))
        print(sets['TECHNOLOGY'].loc[InOut_desc, 'TECHNOLOGY'])
    
    if len(dupi) > 0:
        print(color.red('\nFollowing Duplicate Rows With `Same Parameter` Values Have Been Droped:\n'))
        for key, val in dupi.items():
            print(color.orange(key))
            print(dupi[key])
    if len(dup) > 0:
        print(color.red('\nDupicate Rows in `Parameter Name Column` That Have Different Values:\n'))
        for key, val in dup.items():
            print(color.orange(key))
            print(dup[key])

    transport_parameters_check(input_path)
