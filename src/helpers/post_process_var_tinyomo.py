#!/usr/bin/env python3
# -*- coding: utf-8 -*-import os , yaml, time, argparse
'''
This module provides methods to:

    - extract human-readable results from model runs using tinyomo to build the
      LP problem and gurobi to solve it. The variable optimal values are then
      stored in single .csv files.
    - extract human-readable shadow prices from model runs using tinyomo to build the
      LP problem and gurobi to solve it.

@author: mathieusa, alexanderkl
'''

import numpy as np
import pandas as pd


def extract_results(scenario_name='', output_path=''):
	'''
    This method requires a completed model run using tinyomo and gurobi which
    must have delivered the following files (saved at ouput_path):
        - {scenario_name}_variables.csv: list of non-zero variable values after optimization, e.g. x12345 | 74638.736
        - variables.txt: list of the variables as x_i and name(index), e.g. x12345 | Production(EU, steel, 2050)
        - variables_overview.txt: information relative to the index of each variable (var_name,index_length,index_sets)
    This method generates the following files (saved at output_path):
        - {scenario_name}_{variable}.csv: one file per variable, as a dataframe
          to csv with the indices in the first columns and the values in the last column.
	'''

	variables_results = pd.read_csv(os.path.join(output_path, f'{scenario_name}_variables.csv'), names=['x', 'value'], index_col=0)
	#print(variables_results)

	variables = pd.read_csv(os.path.join(output_path, 'variables.txt'), index_col=0)
	#print(variables)

	var_overview = pd.read_csv(os.path.join(output_path, 'variables_overview.txt'))

	variables_merged = variables.merge(variables_results, on='x', how='right')

	for var_index, variable in enumerate(var_overview['var_name']):
		print(f'processing var: {variable}')
		variable_subset = variables_merged.where(variables_merged['var_name'] == variable).dropna()
		variable_subset.drop(labels=['x', 'var_name', 'var_lp'], axis=1, inplace=True)
		variable_subset.rename(columns = {'value': variable}, inplace=True)
		set_names = var_overview.iloc[var_index, 2].split(';') # col 1 in var_overview is index_sets
		#variable_subset.set_index('var_index', inplace = True)
		#add empty columns
		for set_index in range(var_overview.iloc[var_index, 1]): # col 1 in var_overview is index_length
			#print(set_index)
			variable_subset[f'{set_names[set_index]}'] = np.nan
		for subset_index, _ in enumerate(variable_subset.index): # Iterate over rows
			sets = variable_subset.iloc[subset_index, 0].split(';')
			for set_index in range(len(sets)): 	# iterate over columns
				set = sets[set_index]
				variable_subset.iloc[subset_index, set_index+2]=set

		#print(variable_subset)
		#variable_subset = variable_subset.reindex([index for index in range(len(variable_subset))], axis = 0)
		variable_subset.reset_index(inplace=True)
		variable_subset.drop(labels=['index', 'var_index'], axis=1, inplace=True)
		# Reorder cols so that the variable value comes last
		cols_reordered = [c for c in variable_subset.columns[1:]]
		cols_reordered.append(variable_subset.columns[0])
		variable_subset = variable_subset[cols_reordered]
		variable_subset.to_csv(os.path.join(output_path, f'{scenario_name}_{variable}.csv'), index=False)

	return None


def extract_shadow_prices(scenario_name='', output_path='', input_path=''):
	'''
    This method requires a completed model run using tinyomo and gurobi which
    must have delivered the following files (saved at ouput_path):
        - {scenario_name}_raw_shadow_prices.csv: list of shadow prices (c.ConstrName, c.Pi)
        - constraints_detailed.txt: list of constraints with their name in tinyomo, human-readable names, and index (c.tinyomo,c.name,index)
    This method generates the following file (saved at output_path):
        - {scenario_name}_shadow_prices.csv: shadow prices for each constraint where the first columns
        contain the indices and the last two the discounted and undiscounted shadow prices.
	'''

	# Raw shadow prices with tinyomo constraint names are merged with constraints_detailed
     # to obtain human-readable constraint names.
	shadow_results = pd.read_csv(os.path.join(output_path, f'{scenario_name}_raw_shadow_prices.csv'), names=['c.tinyomo', 'shadow_price'], index_col=0)
	constraints = pd.read_csv(os.path.join(output_path, 'constraints_detailed.txt'), index_col=0)

	shadow_merged = constraints.merge(shadow_results, on='c.tinyomo', how='right')

	# Additional data from input parameters is required to calculate the undiscounted shadow prices.
	years = pd.read_csv(os.path.join(input_path, 'YEAR.csv'))
	min_year = years.min().values[0]
	regions = pd.read_csv(os.path.join(input_path, 'REGION.csv'))
	discount_rate = pd.read_csv(os.path.join(input_path, 'DiscountRate.csv'))

	# The "index" column of the shadow_merged dataframe contains the sets making up the index of the constraint, separated by ";".
	# Example: EU-27+3;ABS_terminal;2030
	# Usually the first indice is REGION and the last YEAR.

	# When the last indice is not YEAR (constraint not time dependant) we use the min year to undiscount, i.e. do not remove the discounting.
	shadow_merged['YEAR'] = shadow_merged['index'].str.split(';').str[-1]
	shadow_merged['YEAR'] = pd.to_numeric(shadow_merged['YEAR'], errors='coerce')
	shadow_merged['YEAR'].fillna(min_year, inplace=True)

	# The REGION index is used to get the discount rate by merging with the DiscountRate parameter.
	shadow_merged['REGION'] = shadow_merged['index'].str.split(';').str[0]
	shadow_merged = shadow_merged.merge(discount_rate, on='REGION', how='left')

	# Calculate the undiscounted shadow prices.
    # Formula: discounted shadow price * (1 + discount rate)^(year - min_year)
	shadow_merged['undiscounted_shadow_price'] = shadow_merged['shadow_price'].astype(float) * ((1 + shadow_merged['DiscountRate'])**(shadow_merged['YEAR'].astype(int) - 2020))

	# Save the shadow prices to a csv file.
	shadow_merged.to_csv(os.path.join(output_path, f'{scenario_name}_shadow_prices.csv'), index=True)

	return None

##########################################################

extract_results(scenario_name=config['model_run_code'], output_path=output_path)

t1 = time.time()
print('Time to extract variables:  ' + str(t1-t0) + ' seconds')

if config['solver']['shadow_prices']:
	extract_shadow_prices(scenario_name=config['model_run_code'], output_path=output_path, input_path=input_path)
	t2 = time.time()
	print('Time to extract shadow prices:  ' + str(t2-t1) + ' seconds')
