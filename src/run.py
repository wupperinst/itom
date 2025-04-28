#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script controls:
    - preparing input data from an Excel file
    - building an LP problem with this input data
    - sending the problem to a solver
    - recovering the results from the solver

This script should be called with:
        python3 run.py SCENARIO_NAME
If a SCENARIO_NAME_config file exists in the configs/ folder, it will beused,
otherwise the default configuration file will be used.

@author: mathieusa
"""

import os, yaml, logging, csv, timegc, sys, shutil, glob
import argparse

import pandas as pd
from pyomo.opt import SolverFactory, SolverStatus, TerminationCondition
from pyomo.environ import value

from helpers.directory_check import check_directory
from helpers.data2csv import xlsx2csv
from helpers.debug_util import debug_infeas
from helpers.build_input_data import get_raw_input_data, build_sets, build_params, _build_transport_params
from helpers.input_data_check import check_input_data

from itom import abstract_itom, concrete_itom
from itom_hub import abstract_itom_hub
from itom_retrofit import abstract_itom_retrofit, abstract_itom_hub_retrofit
from itom_impurities import abstract_itom_hub_retrofit_impurities

import gurobipy as gp
from gurobipy import GRB

from itom_hub_tinyomo import itom_hub_tinyomo
from itom_retrofit_tinyomo import itom_hub_retrofit_tinyomo
from itom_impurities_tinyomo import itom_hub_retrofit_impurities_tinyomo

t0 = time.time()
###############################################################################
# ARGUMENTS

parser = argparse.ArgumentParser(description='Prepare input data for edm-I.')
parser.add_argument('-s', '--scenario', dest='scenario', type=str, help='scenario names')
args = parser.parse_args()

###############################################################################
# CONFIG

# Generate path to root of repo
if os.getcwd().endswith('itom'):
    repo_path = os.path.abspath(os.getcwd())
elif os.getcwd().endswith('itom/src'):
    repo_path = os.path.abspath(os.pardir)
else:
    print('Config path could not be defined. Check your working directory.')
# Generate path to configs folder
config_path = os.path.join(repo_path, 'configs')

# Get config information
print('Get configuration...')
try:
    with open(os.path.join(config_path, args.scenario + '_' + 'config.yaml'), 'r') as stream:
        try:
            config = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print('Problem with your model-run specific yaml config file in the configs directory.')
            print(exc)
except:
    with open(os.path.join(config_path, 'default_config.yaml'), 'r') as stream:
        config = yaml.safe_load(stream)
        config['model_run_code'] = args.scenario

stream.close()

###############################################################################
# SETUP

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

# Check the directory structure
print('Check directory structure...')
check_directory(config['model_run_code'], repo_path)

# Generate paths to other folders
input_path = os.path.join(repo_path, 'input', config['model_run_code'])
output_path = os.path.join(repo_path, 'output', config['model_run_code'])

# Optimisation solver
opt = SolverFactory(config['solver']['name'])

###############################################################################
# INPUT DATA
print('Build input datasets...')

# NOTE:
# Sheets from the Excel file are exported TWICE to csv!
# This is because the LOCATION and LocalResidualCapacity_prelim data are needed
# to build the other input data.

# Get SETS and PARAMETERS from Excel file
print('Get input data from Excel...')
input_xlsx = os.path.join(os.pardir, input_path, config['model_run_code'] + '_input.xlsx')
csv_path = input_path
xlsx2csv(input_xlsx, csv_path)

print('Build transport links...')
# Build TransportRoute and TransportCapacity parameters
years = pd.read_csv(os.path.join(input_path, 'YEAR.csv'))
config['years'] = years['YEAR'].values.tolist()
df_tr_route, df_tr_cap = _build_transport_params(config, input_path)
df_tr_route.to_csv(os.path.join(input_path, 'TransportRoute.csv'), index=False)
df_tr_cap.to_csv(os.path.join(input_path, 'TransportCapacity.csv'), index=False)

# Get SETS and PARAMETERS from Excel file (again)
input_xlsx = os.path.join(os.pardir, input_path, config['model_run_code'] + '_input.xlsx')
csv_path = input_path
xlsx2csv(input_xlsx, csv_path)

# Check input data for consistency
print('Check consistency of input data...')
#list of sets
param_set_index= ['REGION', 'TECHNOLOGY', 'PRODUCT', 'MODE_OF_OPERATION',
                  'TRANSPORTMODE', 'YEAR', 'EMISSION', 'LOCATION']
check_input_data(input_path, param_set_index, config)

t1 = time.time()
print('Time to build input data:  ' + str(int(t1-t0)) + ' seconds')

###############################################################################
# MODEL RUN

# Using pyomo
if config['framework']['tinyomo'] == False:

    print('\nBuilding LP problem with PYOMO')

    # Configuration for abstract model
    if not config['processes']['retrofit'] and not config['transport']['hub']:
        print('Building abstract model: NO retrofit, NO transport hub')
        am = abstract_itom(InputPath=input_path) # Create an abstract model
    elif not config['processes']['retrofit'] and config['transport']['hub']:
        print('Building abstract model: NO retrofit, WITH transport hub')
        am = abstract_itom_hub(InputPath=input_path) # Create an abstract model
    elif config['processes']['retrofit'] and not config['transport']['hub']:
        print('Building abstract model: WITH retrofit, NO transport hub')
        am = abstract_itom_retrofit(InputPath=input_path) # Create an abstract model
    else:
        print('Building abstract model: WITH retrofit, WITH transport hub, WITH impurities')
        am = abstract_itom_hub_retrofit_impurities(InputPath=input_path) # Create an abstract model

    am.load_data() # Load input data from csv files
    t1 = time.time()
    print('\n\nTime to build abstract model:  ' + str(t1-t0) + ' seconds')

    # Build a concrete model
    cm = concrete_itom(am,
                        OutputPath=output_path,
                        OutputCode=config['model_run_code'],
                        Solver=config['solver']['name'])
    t2 = time.time()
    print('Time to build concrete model:  ' + str(t2-t1) + ' seconds')

    # For debugging
    if (config['framework']['keep_LP'] or config['framework']['keep_MPS']) and config['solver']['name']=='gurobi':
        print('DEBUGGING: export LP files')
        cm.export_lp_problem()
        model = gp.read(os.path.join(output_path,'problem.lp'))
        if config['framework']['keep_MPS'] and opt=='gurobi':
            model.write(os.path.join(output_path, config['model_run_code'] + '_'+ 'model.mps'))

    if config['framework']['keep_files']:
        cm.solve_model(keeplog=True, keepfiles=True)
    else:
        cm.solve_model(keeplog=True) # Optimisation

    t3 = time.time()
    print('Time to solve model:  ' + str(t3-t2) + ' seconds')

    cm.export_results() # Export results summary
    cm.export_all_var() # Export all variables to csv files
    t4 = time.time()
    print('Time to export results:  ' + str(t4-t3) + ' seconds')

    t5 = time.time()
    print('\nTotal server time:  ' + str(t5-t0) + ' seconds\n')
    print('\n\n##############################################\n\n')


# Using tinyomo
elif (config['framework']['tinyomo'] == True or config['framework']['like_pyomo'] == True) and config['solver']['name']=='gurobi':

    #### BUILD LP PROBLEM

    # Configuration for model
    print('\nBuilding LP problem with TINYOMO')
    if not config['processes']['retrofit'] and not config['transport']['hub']:
        print('Building model: NO retrofit, NO transport hub')
        m = itom_tinyomo(InputPath=input_path, OutputPath=output_path, config=config) # Build LP file
    elif not config['processes']['retrofit'] and config['transport']['hub']:
        print('Building abstract model: NO retrofit, WITH transport hub')
        m = itom_hub_tinyomo(InputPath=input_path, OutputPath=output_path, config=config) # Build LP file
    elif config['processes']['retrofit'] and not config['transport']['hub']:
        print('Building abstract model: WITH retrofit, NO transport hub')
        m = itom_retrofit_tinyomo(InputPath=input_path, OutputPath=output_path, config=config) # Build LP file
    else:
        print('Building abstract model: WITH retrofit, WITH transport hub, WITH impurities')
        m = itom_hub_retrofit_impurities_tinyomo(InputPath=input_path, OutputPath=output_path, config=config) # Build LP file


    if config['framework']['tinyomo']:
        m.build_lp() # Build LP file
    if config['framework']['like_pyomo']:
        print('\nWriting LP file like pyomo')
        m.build_lp_likepyomo() # For debugging

    t1 = time.time()
    print('\nTime to build model and write as LP file:  ' + str(t1-t0) + ' seconds\n')

    gc.collect()

    #### MODEL RUN

    # Read LP model
    if config['framework']['tinyomo'] and not config['framework']['like_pyomo']:
        model = gp.read(os.path.join(output_path,'problem.lp'))
    if config['framework']['like_pyomo']:
        model = gp.read(os.path.join(output_path,'problem_likepyomo.lp'))

    t2 = time.time()
    print('Time to read LP problem:  ' + str(t2-t1) + ' seconds')

    # Set model parameters
    # Gurobi parameters
    model.Params.OptimalityTol = float(config['solver']['optTol'])
    model.Params.FeasibilityTol = float(config['solver']['feasTol'])
    model.Params.DualReductions = int(config['solver']['dual_reductions'])
    model.Params.Method = int(config['solver']['method'])
    model.Params.Crossover = int(config['solver']['crossover'])
    model.Params.Presolve = int(config['solver']['presolve'])
    model.Params.Aggregate = int(config['solver']['aggregate'])
    model.Params.SolutionTarget = int(config['solver']['solution_target'])
    model.Params.BarHomogeneous = int(config['solver']['bar_homogeneous'])
    model.Params.PreDual = int(config['solver']['pre_dual'])
    model.Params.ScaleFlag = int(config['solver']['scale_flag'])
    model.Params.Threads = int(config['solver']['threads'])
    model.Params.Seed = int(config['solver']['seed'])
    if config['solver']['bar_dense_thresh'] > 0:
        model.Params.GURO_PAR_BarDenseThresh = int(config['solver']['bar_dense_thresh'])

    # Gurobi log
    log_file = config['model_run_code'] + '_'+ 'gurobi.log'
    model.Params.LogFile = log_file

    # Export LP problem in a format that can be used by Gurobi Support
    if config['framework']['keep_MPS']:
        model.write(os.path.join(output_path, config['model_run_code'] + '_'+ 'model.mps'))
        t3 = time.time()
        print('Time to write LP problem in mps format:  ' + str(t3-t2) + ' seconds')

    t3 = time.time()
    # Solve model
    model.optimize()
    t4 = time.time()
    print('Time to optimize model:  ' + str(t4-t3) + ' seconds')

    # Keep .lp and other other intermediary files if so configured
    if not config['framework']['keep_LP']:
        for file in glob.glob(os.path.join(output_path, '*.lp')):
            file_to_remove = pathlib.Path(file)
            file_to_remove.unlink()
    if not config['framework']['keep_files']:
        for file in glob.glob(os.path.join(output_path, '*.txt')):
            if not (file.endswith('variables.txt') or file.endswith('variables_overview.txt') or file.endswith('constraints_detailed.txt')):
                file_to_remove = pathlib.Path(file)
                file_to_remove.unlink()
                
    # Post-processing of optimization results

    if model.status == GRB.INF_OR_UNBD:
        # Turn presolve off to determine whether model is infeasible
        # or unbounded
        model.setParam(GRB.Param.Presolve, 0)
        model.optimize()

    if model.status == GRB.OPTIMAL:
        print('Optimal objective: %g' % model.objVal)
        print('')
        print('Model quality:')
        model.printQuality()
        model.write(os.path.join(output_path, config['model_run_code'] + '_' + 'model.sol'))
        print('Solutions written to model.sol')

        # Export variables to csv
        varInfo = [(v.varName, v.X) for v in model.getVars() if v.X > 0]
        # Write to csv
        with open(os.path.join(output_path, config['model_run_code'] + '_' + 'variables' + '.csv'), 'w') as file:
            wr = csv.writer(file, quoting=csv.QUOTE_ALL)
            wr.writerows(varInfo)

        if config['solver']['shadow_prices']:
            # Export dual values (shadow prices)
            consInfo = [(c.ConstrName, c.Pi) for c in model.getConstrs()]
            # Write to csv
            with open(os.path.join(output_path, config['model_run_code'] + '_' + 'raw_shadow_prices' + '.csv'), 'w') as file:
                wr = csv.writer(file, quoting=csv.QUOTE_ALL)
                wr.writerows(consInfo)


    elif model.status != GRB.OPTIMAL:
        print('Optimization was stopped with status %d' % model.status)

    	# Model is infeasible - compute an Irreducible Inconsistent Subsystem (IIS)
        print('')
        #print('Model is infeasible')
        model.computeIIS()
        model.write(os.path.join(output_path, config['model_run_code'] + '_' + 'model.ilp'))
        print('IIS written to file model.ilp')

        # Relax the bounds and try to make the model feasible
        print('\nRelaxing the bounds')
        orignumvars = model.NumVars
        # Relaxing only variable bounds
        #model.feasRelaxS(0, False, True, False)
        # Relaxing variable bounds and constraint bounds
        model.feasRelaxS(0, False, True, True)

        model.optimize()

        status = model.Status
        if status in (GRB.INF_OR_UNBD, GRB.INFEASIBLE, GRB.UNBOUNDED):
            print('The relaxed model cannot be solved \
                because it is infeasible or unbounded')
            sys.exit(1)
        if status != GRB.OPTIMAL:
            print('Optimization was stopped with status %d' % status)
            sys.exit(1)

        # print the values of the artificial variables of the relaxation
        print('\nSlack values:')
        slacks = model.getVars()[orignumvars:]
        for sv in slacks:
            if sv.X > 1e-9:
                print('%s = %g' % (sv.VarName, sv.X))

    t5 = time.time()
    print('\nTotal elapsed time:  ' + str(t5-t0) + ' seconds\n')
    print('\n##############################################\n')

else:
    print('Config unsupported.')
