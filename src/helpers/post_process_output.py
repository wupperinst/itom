#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This module provides methods to:

    - clean up some production and transport results, calculate some preliminary analyses
    - compress the output by removing zero values

@author: mathieusa
"""

import os, sys, csv, yaml, time, shutil, glob
import argparse

import numpy as np
import pandas as pd

def _get_output_files(output_path='', config={}):
    '''
    '''
    model_run_code = config['model_run_code']
    
    # Output files
    csv_file_to_ignore = [model_run_code + '_variables.csv',
                          model_run_code + '_raw_shadow_prices.csv',
                          model_run_code + '_shadow_prices.csv']
    output_files = [f for f in os.listdir(output_path) if (os.path.isfile(os.path.join(output_path, f))) and (f.endswith('.csv')) and (f not in csv_file_to_ignore)]
    
    # Variables
    var = {}
    for f in output_files:
        if f.startswith(model_run_code + '_'):
            var[f] = f[len(model_run_code)+1:-4] # Removes 'code_' and .csv from file name
        else:
            var[f] = f[:-4] # Removes '.csv' from file name

    return output_files, var


def process_output(module_path='', input_path='', output_path='', config={}, output_files=[], var={}):
    '''
    Clean up outputs and run some first analyses.
    '''

    t0 = time.time()
    ###############################################################################
    # PREPARE

    model_run_code = config['model_run_code']

    # Sets
    sets = ['REGION','LOCATION', 'YEAR', 'TECHNOLOGY', 'TRANSPORTMODE', 'PRODUCT']
    yrs = (pd.read_csv(os.path.join(input_path, "YEAR.csv"))).YEAR.tolist()
    tech = (pd.read_csv(os.path.join(input_path, "TECHNOLOGY.csv"))).TECHNOLOGY.tolist()
    trans = (pd.read_csv(os.path.join(input_path, "TRANSPORTMODE.csv"))).TRANSPORTMODE.tolist()
    prod = (pd.read_csv(os.path.join(input_path, "PRODUCT.csv"))).PRODUCT.tolist()
    region = (pd.read_csv(os.path.join(input_path, "REGION.csv"))).REGION.tolist()
    loc = (pd.read_csv(os.path.join(input_path, "LOCATION.csv"))).LOCATION.tolist()
    # Variables
    var_units = pd.read_csv(os.path.join(module_path, 'configs', config['output']['units']))
    #
    time_step = yrs[1]-yrs[0]

    ###############################################################################
    # POST-PROCESS

    ### CAPACITY UTILIZATION

    ## LOCATION LEVEL

    # Get production
    var_name = 'LocalProductionByTechnology'
    f = model_run_code + '_' + var_name + '.csv'

    var_res = pd.read_csv(os.path.join(output_path, f), encoding = "ISO-8859-1")
    var_res[var[f]] = var_res[var[f]] / time_step
    prod = var_res.copy(deep=True)

    # Get installed capacity
    var_name = 'LocalTotalCapacity'
    f = model_run_code + '_' + var_name + '.csv'

    var_res = pd.read_csv(os.path.join(output_path, f), encoding = "ISO-8859-1")
    cap = var_res.copy(deep=True)

    # Calculate utilisation capacity
    cap_util = prod.merge(cap, on=['LOCATION', 'YEAR', 'TECHNOLOGY'])
    cap_util['LocalCapacityUtilization'] = cap_util['LocalProductionByTechnology'] / cap_util['LocalTotalCapacity']
    cap_util.dropna(axis=0, inplace=True)
    nz_var_res = cap_util['LocalCapacityUtilization'].to_numpy().nonzero()
    var_res = cap_util.iloc[nz_var_res].sort_values(by=['LOCATION','YEAR'], axis=0, ascending=True, inplace=False)
    var_res.to_csv(os.path.join(output_path,config['model_run_code']+'_capacity_utilization_at_location.csv'),index=False)

    ## REGION LEVEL

    # Remove "terminal" and "pipeline transfert" technology from production and installed capacity data
    #prod = prod[~prod['TECHNOLOGY'].str.contains('terminal')]
    prod = prod[~prod['TECHNOLOGY'].str.contains('transfert')]
    #cap = cap[~cap['TECHNOLOGY'].str.contains('terminal')]
    cap = cap[~cap['TECHNOLOGY'].str.contains('transfert')]

    # Prepare utilisation capacity df
    cap_util = prod.merge(cap, on=['LOCATION', 'YEAR', 'TECHNOLOGY'])

    # Get geo information and include it into production figures
    geo = pd.read_csv(os.path.join(input_path,'Geography.csv'))
    cap_util_xtd = cap_util.merge(geo,how='inner',on='LOCATION')
    cap_util_xtd.drop(labels=['Geography'], axis=1, inplace=True)

    # Calculate utilisation capacity per region
    cols = ['REGION', 'TECHNOLOGY', 'PRODUCT', 'YEAR']
    grouped_df = cap_util_xtd.groupby(cols)
    df_agg = grouped_df.agg({'LocalProductionByTechnology':np.sum, 'LocalTotalCapacity':np.sum})

    # Finalise the results
    var_res = df_agg.reset_index()
    var_res['LocalCapacityUtilization'] = var_res['LocalProductionByTechnology'] / var_res['LocalTotalCapacity']
    var_res.dropna(axis=0, inplace=True)
    nz_var_res = var_res['LocalCapacityUtilization'].to_numpy().nonzero()
    var_res = var_res.iloc[nz_var_res].sort_values(by=['REGION','YEAR'], axis=0, ascending=True, inplace=False)
    var_res.to_csv(os.path.join(output_path,config['model_run_code']+'_capacity_utilization_at_region.csv'),index=False)

    ### TRANSPORT

    ## PIPELINE TRANSPORT

    # Get transport results
    columns = ['from_LOCATION','to_LOCATION', 'PRODUCT','TRANSPORTMODE','YEAR','VARIABLE', 'VALUE', 'UNIT']
    trans_res = pd.DataFrame(columns=columns)
    f = config['model_run_code'] + '_' + 'Transport.csv'
    df = pd.read_csv(os.path.join(output_path, f))
    df['VARIABLE'] = var[f]
    df.rename(columns={var[f]:'VALUE'}, inplace=True)
    df.rename(columns={'LOCATION':'from_LOCATION', 'LOCATION.1':'to_LOCATION'}, inplace=True)
    df['UNIT'] = var_units.loc[var_units['VARIABLE']==var[f], 'UNIT'].iloc[0]
    trans_res = pd.concat([trans_res, df], axis='index', sort=False)

    # Extract pipelines
    nz_trans_res = trans_res['VALUE'].to_numpy().nonzero()
    var_res = trans_res.iloc[nz_trans_res].sort_values(by=['from_LOCATION','YEAR'], axis=0, ascending=True, inplace=False)
    var_res.VALUE = var_res.VALUE / time_step
    var_res = var_res[var_res['TRANSPORTMODE'].str.contains('PIPELINE')]
    var_res = var_res[var_res.VALUE > 0.1].sort_values(by=['from_LOCATION','YEAR'], axis=0, ascending=True, inplace=False)
    var_res.to_csv(os.path.join(output_path,config['model_run_code']+'_pipeline_transport.csv'),index=False)

    ## IMPORT through port terminal

    # Get production figures
    cols = ['LOCATION', 'YEAR', 'TECHNOLOGY', 'PRODUCT', 'VARIABLE', 'VALUE', 'UNIT']
    prod = pd.DataFrame(columns=columns)
    var_name = 'LocalProductionByTechnology'
    f = model_run_code + '_' + var_name + '.csv'
    df = pd.read_csv(os.path.join(output_path, f), encoding = "ISO-8859-1")
    df['VARIABLE'] = var[f]
    df.rename(columns={var[f]:'VALUE'}, inplace=True)
    df['UNIT'] = var_units.loc[var_units['VARIABLE']==var[f], 'UNIT'].iloc[0]
    prod = pd.concat([prod, df], axis='index', sort=False)
    prod.VALUE = prod.VALUE / time_step

    # Keep only production from "terminal technologies"
    prod_terminal = prod[prod['TECHNOLOGY'].str.contains('terminal')]

    # Get geo information and include it into production figures
    geo = pd.read_csv(os.path.join(input_path,'Geography.csv'))
    prod_terminal_xtd = prod_terminal.merge(geo,how='inner',on='LOCATION')
    prod_terminal_xtd.drop(labels=['Geography'], axis=1, inplace=True)

    # Calculate total production from terminals per region
    cols = ['REGION', 'TECHNOLOGY', 'YEAR']
    grouped_df = prod_terminal_xtd.groupby(cols)
    df_agg = grouped_df.agg({'VALUE':np.sum})

    # Finalise the results
    var_res = df_agg.reset_index()
    #nz_var_res = var_res['VALUE'].to_numpy().nonzero()
    #var_res = var_res.iloc[nz_var_res].sort_values(by=['REGION','YEAR'], axis=0, ascending=True, inplace=False)
    var_res = var_res[var_res.VALUE > 0.1].sort_values(by=['REGION','YEAR'], axis=0, ascending=True, inplace=False)
    var_res.to_csv(os.path.join(output_path,config['model_run_code']+'_import_from_terminals.csv'),index=False)

    ## EXPORT through port terminal

    # Get use figures
    cols = ['LOCATION', 'YEAR', 'TECHNOLOGY', 'PRODUCT', 'VARIABLE', 'VALUE', 'UNIT']
    use = pd.DataFrame(columns=columns)
    var_name = 'LocalUseByTechnology'
    f = model_run_code + '_' + var_name + '.csv'
    df = pd.read_csv(os.path.join(output_path, f), encoding = "ISO-8859-1")
    df['VARIABLE'] = var[f]
    df.rename(columns={var[f]:'VALUE'}, inplace=True)
    df['UNIT'] = var_units.loc[var_units['VARIABLE']==var[f], 'UNIT'].iloc[0]
    use = pd.concat([use, df], axis='index', sort=False)
    use.VALUE = use.VALUE / time_step

    # Keep only production from "terminal technologies"
    use_terminal = use[use['TECHNOLOGY'].str.contains('terminal')]

    # Get geo information and include it into production figures
    geo = pd.read_csv(os.path.join(input_path,'Geography.csv'))
    use_terminal_xtd = use_terminal.merge(geo,how='inner',on='LOCATION')
    use_terminal_xtd.drop(labels=['Geography'], axis=1, inplace=True)

    # Calculate total production from terminals per region
    cols = ['REGION', 'TECHNOLOGY', 'YEAR']
    grouped_df = use_terminal_xtd.groupby(cols)
    df_agg = grouped_df.agg({'VALUE':np.sum})

    # Finalise the results
    var_res = df_agg.reset_index()
    nz_var_res = var_res['VALUE'].to_numpy().nonzero()
    var_res = var_res.iloc[nz_var_res].sort_values(by=['REGION','YEAR'], axis=0, ascending=True, inplace=False)
    var_res.to_csv(os.path.join(output_path,config['model_run_code']+'_export_from_terminals.csv'),index=False)

    t1 = time.time()
    print('Time to post-process raw output:  ' + str(t1-t0) + ' seconds')

###############################################################################
# COMPRESS
def compress_output(output_path='', config={}, output_files=[], var={}):
    '''
    Reduce output size by eliminating zero values.
    '''

    t0 = time.time()
    for f in output_files:
        var_res = pd.read_csv(os.path.join(output_path, f), encoding = "ISO-8859-1")
        nz_var_res = var_res[var[f]].to_numpy().nonzero()
        var_res = var_res.iloc[nz_var_res]
        var_res.to_csv(os.path.join(output_path, f),index=False)

    t1 = time.time()
    print('Time to compress raw output:  ' + str(t1-t0) + ' seconds')
