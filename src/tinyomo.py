#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
This file defines classes replacing the Set, Param, Var, Constraint, and Objective Pyomo objects and necessary methods
to use them to build an LP problem.
The tinyomo ("tiny pyomo") module uses much less memory compared to Pyomo, which is critical with large problems.

@author: mathieusa
'''

__all__ = ('Sets', 'Set', 'Params', 'Param', 'Vars', 'Var', 'Constraints', 'Constraint', 'Objective', 'NonNegativeReals', 'Reals')

#from __future__ import division
import os, math
from time import time
import pandas as pd
import numpy as np
from functools import reduce

###############################################################################

# Private functions doing the heavy lifting

def _prepare_df_structure(set_structure, exchange=False):
	'''
	Take in a list of set names and a dictionary of set dataframes to build a
	dataframe correctly indexed (with all possible index combinations) for a
	given parameter. The VALUE colummn of the parameter dataframe is not provided,
	it will be dealt with in the get_Parameter functions().

	Parameters
	----------
	set_structure :     tuple
						Tuple of Set objects that should index the
						parameter for which a dataframe is to be prepared. These
						set names will be the dataframe's column names.
	exchange:           bool
						Should be True if the parameter for which a dataframe is
						to be prepared is one of the "exchange parameters" that
						is indexed by the set REGION twice (i.e. has two columns
						named REGION).
						False by default.
	Returns
	-------
	df :        pandas DataFrame
				Correctly indexed parameter dataframe, only missing the VALUE column.
	'''
	# The following is a not-so-pretty way to mostly reuse the _prepare_param_df()
	# function from osemosys_preparation_func without having to change most of the
	# code (yes, duplicate code...)
#    param_set_index :   list
#                        List of set names (as strings) that should index the
#                        parameter for which a dataframe is to be prepared. These
#                        set names will be the dataframe's column names.
#    sets:               dict
#                        The keys are the names of the sets in OSeMOSYS.
#                        The values are the sets' dataframes generated in the
#                        get_SET() functions.

	param_set_index = [s.name for s in set_structure]
	sets = {s.name:s.data for s in set_structure}

	# For some Exchange parameters, two columns have the same name. They need
	# to be renamed to avoid problems.
	if exchange and (param_set_index[0]!='LOCATION_1' or param_set_index[1]!='LOCATION_2'):
		regions_to_from = ['LOCATION_1', 'LOCATION_2']
		regions_to_from.extend(param_set_index[2:])
		param_set_index = regions_to_from
		sets['LOCATION_1'] = sets['LOCATION']
		sets['LOCATION_2'] = sets['LOCATION']

	# For multiregional modelling, interregional cost parameters have two columns with the same name.
	if len(param_set_index)>=2 and (param_set_index[0]=='REGION') and (param_set_index[1]=='REGION'):
		regions_to_from = ['REGION_1', 'REGION_2']
		regions_to_from.extend(param_set_index[2:])
		param_set_index = regions_to_from
		sets['REGION_1'] = sets['REGION']
		sets['REGION_2'] = sets['REGION']

	# For some Retrofit parameters, two columns have the same name. They need
	# to be renamed to avoid problems.
	if len(param_set_index)>=2 and (param_set_index[0]=='TECHNOLOGY') and (param_set_index[1]=='TECHNOLOGY'):
		tech_current_retrofit = ['TECHNOLOGY_1', 'TECHNOLOGY_2']
		param_set_index = tech_current_retrofit
		sets['TECHNOLOGY_1'] = sets['TECHNOLOGY']
		sets['TECHNOLOGY_2'] = sets['TECHNOLOGY']

	# For some Impurity parameters, two columns have the same name. They need
	# to be renamed to avoid problems.
	if len(param_set_index)>=2 and (param_set_index[0]=='PRODUCT') and (param_set_index[1]=='PRODUCT'):
		tech_current_retrofit = ['PRODUCT_1', 'PRODUCT_2']
		param_set_index = tech_current_retrofit
		sets['PRODUCT_1'] = sets['PRODUCT']
		sets['PRODUCT_2'] = sets['PRODUCT']

	# Empty parameter df with necessary columns (except 'VALUE')
	df_param = pd.DataFrame(columns=param_set_index)

	if len(param_set_index) == 1:
		df_param = sets[param_set_index[0]].rename({'VALUE':param_set_index[0]}, axis='columns')
	else:
		# First set-index in first column (usually 'REGION')
		set_name = param_set_index[0]
		# The index should be repeated product(length all other sets) times
		repeat_length = reduce(lambda x, y: x*y, [len(sets[s]) for s in param_set_index[1:]])
		df_param.loc[:,set_name] = np.repeat(sets[set_name]['VALUE'], repeat_length).values

		# Second to second-to-last indices
		for set_name in param_set_index[1:-1]:
			# Find the position of the set in the list of set-indices
			set_pos = param_set_index.index(set_name)
			# The index should be repeated product(length of sets listed AFTER this set in param_set_index) times
			repeat_length = reduce(lambda x, y: x*y, [len(sets[s]) for s in param_set_index[set_pos+1:]])
			# The tile should measure product(length of sets listed BEFORE this set in param_set_index)
			tile_length = reduce(lambda x, y: x*y, [len(sets[s]) for s in param_set_index[0:set_pos]])
			# Fill the dataframe
			df_param.loc[:,set_name] = np.tile(np.repeat(sets[set_name]['VALUE'], repeat_length), tile_length)

		# Last index
		set_name = param_set_index[-1]
		# The index tile should measure product(length all other sets) times
		tile_length = reduce(lambda x, y: x*y, [len(sets[s]) for s in param_set_index[:-1]])
		df_param.loc[:,set_name] = np.tile(sets[set_name]['VALUE'], tile_length)

	return df_param

###############################################################################

# OSeMOSYS Sets

class Sets(object):
	'''
	Class containing info on all Set objects.

	Constructor arguments:
		InputPath: string
			Path to folder containing the csv input files for the Sets.

	Public class attributes:
		input_path: string
			Path to folder containing the csv input files for the Sets.
		all: list
			Names of Set instantiated in the model.
		all_sets: list
			All Set objects instantiated in the model.
	 '''
	def __init__(self, InputPath=None):

		try:
			if InputPath==None:
				raise SyntaxError
		except SyntaxError:
				print('Cannot create a Set without a path to input data.')

		self.input_path = InputPath
		self.all = []
		self.all_sets = {}

class Set(object):
	'''
	Class replacing Pyomo's Set class.

	Constructor arguments:
		SetName: string
			Name of the Set, which should also be the name of the csv file containing the data.
		SetsGroup: Sets object
			Instance of the Sets class.

	Public class attributes:
		type: string
			Registers that the object is a Set.
		name: string
			The name of the Set.
		data: pandas DataFrame
			Data from the input csv file.

	Public class method:
		get_index(self, val)
			Returns the index integer of the set for the value passed as argument.
	'''
	def __init__(self, SetName='', SetsGroup=None):

		# Verify that we got all we need to try and build a Set.
		try:
			if SetName=='' or not isinstance(SetName, str):
				raise NameError
		except NameError:
				print('Cannot create a Set without a proper name (non-empty string).')

		# Update and get info from SetsGroup object
		if not SetsGroup == None:
			SetsGroup.all.append(SetName)
			InputPath = SetsGroup.input_path

		# Try to build a Set's dataframe
		self.type = 'Set'
		self.name = SetName

		# For LOCATION_1 and LOCATION_2 get the set values from LOCATION
		if self.name=='LOCATION_1' or self.name=='LOCATION_2':
			SetName = 'LOCATION'
		# For REGION_1 and REGION_2 get the set values from REGION
		if self.name=='REGION_1' or self.name=='REGION_2':
			SetName = 'REGION'
		# For TECHNOLOGY_1 and TECHNOLOGY_2 get the set values from TECHNOLOGY
		if self.name=='TECHNOLOGY_1' or self.name=='TECHNOLOGY_2':
			SetName = 'TECHNOLOGY'
		# For PRODUCT_1 and PRODUCT_2 get the set values from PRODUCT
		if self.name=='PRODUCT_1' or self.name=='PRODUCT_2':
			SetName = 'PRODUCT'

		try:
			self.data = pd.read_csv(os.path.join(InputPath, SetName + '.csv'))
			self.data.drop_duplicates(inplace=True) # Make sure the csv input file does not introduce duplicates
			self.data.reset_index(drop=True, inplace=True) # If duplicates were removed, need to reset the index for it to be continuous
			# Make sure that the last column (with the data) is 'VALUE'
			self.data.rename(columns={self.data.columns[-1:][0]:'VALUE'}, inplace=True)
			# Save the dataframe as dict for faster lookups in get_set_index() method of Constraint Class
			self.datadict = self.data.to_dict('index')
			# Update SetsGroup
			SetsGroup.all_sets[self.name] = self
			#SetsGroup.all_sets.append(self)

			# Length of set (to avoid calculating it for each constraint)
			self.len = len(self.data)

			# Save the position of each set item in the set dataframe in a dict.
			# This is used in Param.get_value() and Var.get_index_label() and
			# speeds up the code.
			self.pos = {s:self.data.loc[self.data['VALUE']==s].index[0] for s in self.data['VALUE']}
#            # Swap VALUE and index to be able to faster access the position of
#            # a given set value. This is used in Param.get_value() and Var.get_index_label()
#            self.pos = self.data.copy(deep=True)
#            self.pos.loc[:,'pos'] = self.pos.index
#            self.pos.set_index('VALUE', inplace=True)

		except:
			print('Could not get the data to create Set ' + SetName + '.')


	# Methods
	def get_index(self, val):
		'''
		Returns the index integer of the set for the value passed as argument.

		Arguments:
			val: int
		'''
		return self.data.loc[self.data['VALUE']==val].index[0]

###############################################################################

# OSeMOSYS Parameters

class Params(object):
	'''
	Class containing info on all Param objects.

	Constructor arguments:
		InputPath: string
			Path to folder containing the csv input files for the Params.

	Public class attributes:
		input_path: string
			Path to folder containing the csv input files for the Sets.
		all: list
			Names of Param instantiated in the model.
	 '''
	def __init__(self, InputPath=None, SetsGroup=None):

		try:
			if InputPath==None:
				raise SyntaxError
		except SyntaxError:
				print('Cannot create a Param without a path to input data.')

		self.input_path = InputPath
		self.all = []
		self.sets_group = SetsGroup

class Param(object):
	'''
	Class replacing Pyomo's Param class.

	Constructor arguments:
		*arg: Set objects
			Arbitrary number of Set object instances defining the index of the parameter.
		default: float
			Value to be used if no input data is provided.
		exchange: boolean
			True if building an Exchange parameter, i.e. a parameter that have
			two columns with the same name ('REGION').
		ParamName: string
			Name of the Param, which should also be the name of the csv file containing the data.
		ParamsGroup: Params object
			Instance of the Params class.

	Public class attributes:
		type: string
			Registers that the object is a Param.
		name: string
			The name of the Param.
		sets: list
			The sets indexing the parameter.
		data: pandas DataFrame
			Data from the input csv file.

	Public class method:
		get_value(self, *arg)
			Returns the value in the 'VALUE' column for the row defined by the
			values in all the other columns given in *arg.
	'''
	def __init__(self, *arg, default=0, exchange=False, ParamName='', ParamsGroup=None):

		# Verify that we got all we need to try and build a Param.
		try:
			if ParamName=='' or not isinstance(ParamName, str):
				raise NameError
		except NameError:
				print('Cannot create a Param without a proper name (non-empty string).')

		# Update and get info from ParamsGroup object
		if not ParamsGroup == None:
			ParamsGroup.all.append(ParamName)
			InputPath = ParamsGroup.input_path

		# Update Param's attributes
		self.type = 'Param'
		self.name = ParamName
		self.default = default
		self.sets = [a for a in arg]
		if exchange:
			# The first two sets are LOCATION.
			# Need to differentiate between LOCATION_1 and LOCATION_2
			self.sets[0] = ParamsGroup.sets_group.all_sets['LOCATION_1']
			self.sets[1] = ParamsGroup.sets_group.all_sets['LOCATION_2']
		self.set_len = {s.name:len(s.data) for s in self.sets}

		# Try to build a Param's dataframe
		## 1) Build the dataframe structure indexed by the Sets passed as *arg
		## 2) Merge the input data into that structure
		## 3) Drop the NaNs (while keeping the index), the NaNs will be replaced with default values at get_value()
		## old: 3) Fill the NaNs with the default value for the parameter
		df_structure = _prepare_df_structure(arg, exchange=exchange)
		try:
			self.data = pd.read_csv(os.path.join(InputPath, ParamName + '.csv'))
			self.data.drop_duplicates(inplace=True) # Make sure the csv input file does not introduce duplicates
			if exchange: # if Exchange Param, the first two columns are LOCATION and LOCATION.1 after read_csv
				self.data.rename(columns={self.data.columns[0]:'LOCATION_1', self.data.columns[1]:'LOCATION_2'}, inplace=True)
			if self.data.columns[1]=='REGION.1': # if TransportCostInterReg Param, the first two columns are REGION and REGION.1 after read_csv
				self.data.rename(columns={self.data.columns[0]:'REGION_1', self.data.columns[1]:'REGION_2'}, inplace=True)
			if self.data.columns[1]=='TECHNOLOGY.1': # if retrofit Param, the first two columns are TECHNOLOGY and TECHNOLOGY.1 after read_csv
				self.data.rename(columns={self.data.columns[0]:'TECHNOLOGY_1', self.data.columns[1]:'TECHNOLOGY_2'}, inplace=True)
			if self.data.columns[1]=='PRODUCT.1': # if retrofit Param, the first two columns are PRODUCT and PRODUCT.1 after read_csv
				self.data.rename(columns={self.data.columns[0]:'PRODUCT_1', self.data.columns[1]:'PRODUCT_2'}, inplace=True)

			self.data = df_structure.merge(self.data, how='left')
			#self.data.fillna(default, inplace=True)
			self.data.dropna(inplace=True)
			# Make sure that the last column (with the data) is 'VALUE'
			self.data.rename(columns={self.data.columns[-1:][0]:'VALUE'}, inplace=True)

			# Reshape the data from a dataframe to a dictionary:
			# look-ups are much faster for dict types, which we need because of the many get_value() calls
			cols = [c for c in self.data.columns[:-1]]
			self.data.drop_duplicates(subset=cols, keep='first', inplace=True) # Drop possible duplicates based on the columns for the multiindex
			self.data = self.data.set_index(cols) # Set all columns but VALUE as the multiindex
			self.data = self.data.to_dict('index') # Convert the DataFrame to a dictionary with orient='index'

		except:
			print('Could not get correct input data to create Param ' + ParamName + '.'
				  + ' Using default values.')
			#self.data = df_structure
			#self.data.loc[:, 'VALUE'] = default
			self.data = {}

	# Methods
	def get_value(self, *arg):
		'''
		Returns the value in the 'VALUE' column for the row defined by the
		values in all the other columns given in *arg.

		Arguments:
			*arg: Set objects
				Arbitrary number of Set object instances defining the index of the parameter.
		'''
		if len(arg)==1:
			try:
				return self.data[arg[0]]['VALUE']
			except KeyError:
				return self.default
		else:
			try:
				return self.data[arg]['VALUE']
			except KeyError:
				return self.default

	def get_value_v1(self, *arg):
		'''
		Returns the value in the 'VALUE' column for the row defined by the
		values in all the other columns given in *arg.

		Arguments:
			*arg: Set objects
				Arbitrary number of Set object instances defining the index of the parameter.
		'''
#        set_len = {s.name:len(s.data) for s in self.sets}
		set_len = self.set_len
		# This list comprehension was taking too long according to the profiler,
		# therefore we introduced the .pos (as "position") attribute to the Set object.
#        set_pos = [self.sets[i].data.index[self.sets[i].data['VALUE']==arg[i]][0] for i in range(0, len(arg))]
		set_pos = {self.sets[i].name:self.sets[i].pos[arg[i]] for i in range(0, len(arg))}
#        set_pos = [self.sets[i].pos.loc[arg[i], 'pos'] for i in range(0, len(arg))]
#        set_pos = dict(zip([s.name for s in self.sets], set_pos))

		index_label = 0
		if len(self.sets) == 1:
			index_label = set_pos[self.sets[0].name]
		else:
			for i in range(0, len(self.sets)-1):
				index_label += set_pos[self.sets[i].name] * reduce(lambda x, y: x*y, [set_len[s.name] for s in self.sets[i+1:]])
			index_label += set_pos[self.sets[len(self.sets)-1].name]

		return self.data.loc[index_label , 'VALUE']


# Previous code using the pandas method .query. Profiling showed that much time
# was spent in it especially because it calls eval to evaluate the string passed
# to the query. The code above is more efficient.
#        set_index = [a for a in arg]
#        if isinstance(set_index[0], int) or isinstance(set_index[0], np.int64):
#            query = self.set_columns[0] + '==' + str(set_index[0])
#        elif isinstance(set_index[0], str):
#            query = self.set_columns[0] + '==' + '"' + set_index[0] + '"'
#
#        for col in range(1,len(self.set_columns[1:])+1):
#            if isinstance(set_index[col], int) or isinstance(set_index[col], np.int64):
#                query = self.set_columns[col] + '==' + str(set_index[col])
#            elif isinstance(set_index[col], str):
#                query = self.set_columns[col] + '==' + '"' + set_index[col] + '"'
#
#        return self.data.query(query)['VALUE'].iloc[0]

# Previous code using a deep copy of a dataframe. Profiling showed that much time
# was spent in deep copy (especially because it is a recursive function).
# The code above is more efficient.
#
#        set_index = [a for a in arg]
#        df = self.data.copy(deep=True)
#        for col in self.set_columns:
#            df = df.loc[df[col]==set_index[self.set_columns.index(col)], :]
#        return df['VALUE'].iloc[0]

###############################################################################

# OSeMOSYS Variables

class NonNegativeReals(object):
	'''
	Class defining bounds for variables in the domian [0, +inf[
	'''
	def __init__(self):
		self.lower = "0"
		self.upper = "+inf"


class Reals(object):
	'''
	Class defining bounds for variables in the domian [-inf, +inf[
	'''
	def __init__(self):
		self.lower = "-inf"
		self.upper = "+inf"


class Vars(object):
	'''
	Class containing info on all Var objects.

	Constructor arguments:
		OutputPath [optional]: string
			Path to folder where the modelling results (variable values) should
			be written as csv files. Also where the LP bounds file will be written.

	Public class attributes:
		output_path: string
			Path to folder containing the csv output files for the Vars.
		all: list
			Names of Var instantiated in the model.
		all_vars: list
			All Var object instantiated in the model.
		relevant_vars: set
			Set of variable indices actually used in constraints (i.e. relevant variables).
	 '''
	def __init__(self, OutputPath=None, SetsGroup=None):

		try:
			if OutputPath==None:
				raise SyntaxError
		except SyntaxError:
				print('Cannot save modelling results without a path to output data.')

		self.output_path = OutputPath
		self.all = []
		self.all_vars = []
		self.relevant_vars = set()
		self.sets_group = SetsGroup

class Var(object):
	'''
	Class replacing Pyomo's Var class.

	Constructor arguments:
		*arg: Set objects
			Arbitrary number of Set object instances defining the index of the variable.
		domain: NonNegativeReals object
			Defines the bounds of the variable.
		initialize: float
			Not used.
		exchange: boolean
			True if building an Exchange variable, i.e. a variable that have
			two columns with the same name ('REGION').
		VarName: string
			Name of the Var, which will also be the name of the csv file
			containing the output data.
		VarsGroup: Vars object
			Instance of the Vars class.
		SetsGroup: Sets object
			Instance of the Sets class.

	Public class attributes:
		type: string
			Registers that the object is a Var.
		name: string
			The name of the Var.
		sets: list
			The sets indexing the variable.
		lower: float or -np.inf
			Lower bound of the variable.
		upper: float or np.inf
			Upper bound of the variable.
		positions: dict
			'pos': integer label associated with this variable.
			'index_start': start of integer index range indexing this variable.
			'index_end': end of integer index range indexing this variable.

	Public class method:
		get_index_label(self, *arg)
			Returns the index integer label of the variable for the set indices given in *arg.
	'''
	def __init__(self, *arg, domain=None, initialize=0.0, exchange=False, VarName='', VarsGroup=None):

		# Verify that we got all we need to define a Var.
		try:
			if VarName=='' or not isinstance(VarName, str):
				raise NameError
		except NameError:
				print('Cannot create a Var without a proper name (non-empty string).')

		# Update Var's attributes
		self.type = 'Var'
		self.name = VarName
		self.sets = [a for a in arg]
		if exchange:
			# The first two sets are LOCATION.
			# Need to differentiate between LOCATION_1 and LOCATION_2
			self.sets[0] = VarsGroup.sets_group.all_sets['LOCATION_1']
			self.sets[1] = VarsGroup.sets_group.all_sets['LOCATION_2']
		self.set_len = {s.name:len(s.data) for s in self.sets}
		self.exchange = exchange
		# Get the variable's bounds
		domain = domain()
		self.lower = domain.lower
		self.upper = domain.upper
		# Get the range of indices that the variable spans.
		# We only store the first and last index to spare memory.
		if not VarsGroup == None:
			# If it's the first Var being instantiated
			if VarsGroup.all_vars == []:
				prev_max_index = 0
				len_var_index = reduce(lambda x, y: x*y, [len(a.data) for a in arg])
				self.positions = {'pos': 1,
								  'index_start': prev_max_index + 1,
								  'index_end': prev_max_index + len_var_index}
			# If there are other Var already instantiated
			else:
				prev_max_index = max([var.positions['index_end'] for var in VarsGroup.all_vars])
				# AK: needed to fix an error with var ModelPeriodCost that has no sets
				if arg:
					len_var_index = reduce(lambda x, y: x*y, [len(a.data) for a in arg])
					self.positions = {'pos': len(VarsGroup.all) + 1,
								  	'index_start': prev_max_index + 1,
								  	'index_end': prev_max_index + len_var_index}
				else:
					len_var_index = 0
					self.positions = {'pos': len(VarsGroup.all) + 1,
									  'index_start': prev_max_index + 1,
									  'index_end': prev_max_index + len_var_index}


			# Update and get info from VarsGroup object
			VarsGroup.all.append(VarName)
			VarsGroup.all_vars.append(self)

	# Methods
	def get_index_label(self, *arg):
		'''
		Returns the index integer label of the variable for the set indices given in *arg.

		Arguments:
			*arg: Set objects
				Arbitrary number of Set object instances defining the index of the variable.
		'''
#        set_len = {s.name:len(s.data) for s in self.sets}
		set_len = self.set_len
		# This list comprehension was taking too long according to the profiler,
		# therefore we introduced the .pos attribute to the Set object.
#        set_pos = [self.sets[i].data.index[self.sets[i].data['VALUE']==arg[i]][0] for i in range(0, len(arg))]
		set_pos = {self.sets[i].name:self.sets[i].pos[arg[i]] for i in range(0, len(arg))}
#        set_pos = [self.sets[i].pos.loc[arg[i], 'pos'] for i in range(0, len(arg))]
#        set_pos = dict(zip([s.name for s in self.sets], set_pos))

		index_label = 0
		if len(self.sets) == 1:
			index_label = set_pos[self.sets[0].name]
		else:
			for i in range(0, len(self.sets)-1):
				index_label += set_pos[self.sets[i].name] * reduce(lambda x, y: x*y, [set_len[s.name] for s in self.sets[i+1:]])
			index_label += set_pos[self.sets[len(self.sets)-1].name]

		return index_label + self.positions['index_start']

# Previous code using numpy.split. Profiling showed that much time was spent in
# numpy.array. The code above is more efficient.
#
#        set_len = {s.name:len(s.data) for s in self.sets}
#        set_pos = [self.sets[i].data.index[self.sets[i].data['VALUE']==arg[i]][0] for i in range(0, len(arg))]
##        set_pos = [self.sets[arg.index(a)].data.index[self.sets[arg.index(a)].data['VALUE']==a][0] for a in arg]
#        set_pos = dict(zip([s.name for s in self.sets], set_pos))
#
#        var_range = np.array(range(self.positions['index_start'], self.positions['index_end']+1))
#
#        for s in self.sets:
#            var_range = np.split(var_range, set_len[s.name])[set_pos[s.name]]
#
#        return var_range[0]

###############################################################################

# OSeMOSYS Constraints

class Constraints(object):
	'''
	Class containing info on all Constraint objects.

	Constructor arguments:
		OutputPath [optional]: string
			Path to folder where the LP constraint file will be written.

	Public class attributes:
		output_path: string
			Path to folder containing the constraints written for the LP.
		all: list
			Names of Constraint instantiated in the model.
		all_cons: list
			All Constraint objects instantiated in the model.
	 '''
	def __init__(self, OutputPath=None, SetsGroup=None):

		try:
			if OutputPath==None:
				raise SyntaxError
		except SyntaxError:
				print('Cannot save modelling results without a path to output data.')

		self.output_path = OutputPath
		self.all = []
		self.all_cons = []
		self.sets_group = SetsGroup

class Constraint(object):
	'''
	Class replacing Pyomo's Constraint class.

	Constructor arguments:
		*arg: Set objects
			Arbitrary number of Set object instances defining the index of the constraint.
		rule: function
			A special function returning the lhs, sense and rhs of the constraint.
		ConsGroup: Constraints object
			Instance of the Constraints class.
		ConsName: string
			Name of the Constraint.

	Public class attributes:
		type: string
			Registers that the object is a Constraint.
		name: string
			The name of the Constraint.
		sets: list
			The sets indexing the constraint.
		rule: function
			Function defining the constraint's coefficient matrix.
		positions: dict
			'pos': integer label associated with this constraint.
			'index_start': start of integer index range indexing this constraint.
			'index_end': end of integer index range indexing this constraint.

	Public class methods:
		get_set_index(self)
			This is a generator function that yields (one by one as a generator)
			in order the lists of sets indexing the constraint.
	'''
	def __init__(self, *arg, rule=None, ConsName='', ConsGroup=None, exchange=False):

		# Verify that we got all we need to define a Constraint.
		try:
			if ConsName=='' or not isinstance(ConsName, str):
				raise NameError
		except NameError:
				#print('Cannot create a Constraint without a proper name (non-empty string).')
				self.name = rule.__name__[:-5] # Remove '_rule' from the rule function name

		# Update Constraint's attributes
		self.type = 'Constraint'
		self.name = ConsName
		self.sets = [a for a in arg]
		if exchange:
			# The first two sets are LOCATION.
			# Need to differentiate between LOCATION_1 and LOCATION_2
			self.sets[0] = ConsGroup.sets_group.all_sets['LOCATION_1']
			self.sets[1] = ConsGroup.sets_group.all_sets['LOCATION_2']
		self.rule = rule
		# Calculate the following data once in __init__ and then use it multiple
		# times in get_set_index()
		# product(length of sets listed AFTER this set in param_set_index)
		self.stacked_index = [reduce(lambda x, y: x*y, [len(s.data) for s in self.sets[set_pos+1:]]) for set_pos in range(0, len(self.sets)-1)]
		# Get the range of indices that the constraint spans.
		# We only store the first and last index to spare memory.
		if not ConsGroup == None:
			# If it's the first Cons being instantiated
			if ConsGroup.all_cons == []:
				prev_max_index = 0
				len_var_index = reduce(lambda x, y: x*y, [len(a.data) for a in arg])
				self.positions = {'pos': 1,
								  'index_start': prev_max_index + 1,
								  'index_end': prev_max_index + len_var_index}
			# If there are other Constraint already instantiated
			else:
				prev_max_index = max([cons.positions['index_end'] for cons in ConsGroup.all_cons])
				# AK: needed to fix an error with var ModelPeriodCost that has no sets
				if arg:
					len_var_index = reduce(lambda x, y: x*y, [len(a.data) for a in arg])
					self.positions = {'pos': len(ConsGroup.all) + 1,
								  	'index_start': prev_max_index + 1,
								  	'index_end': prev_max_index + len_var_index}
				else:
					len_var_index = 0
					self.positions = {'pos': len(ConsGroup.all) + 1,
									  'index_start': prev_max_index + 1,
									  'index_end': prev_max_index + len_var_index}

			# Update and get info from ConsGroup object
			ConsGroup.all.append(ConsName)
			ConsGroup.all_cons.append(self)

	# Methods
	def get_set_index(self):
		'''
		This is a generator function that yields (one by one as a generator)
		in order the lists of sets indexing the constraint.
		'''
		len_sets = [s.len for s in self.sets]
		nb_sets = len(len_sets)
		cum_len_sets = [math.prod(len_sets[i:]) for i in range(0,len(len_sets))]

		index_label = 0
		index_label_end = self.positions['index_end'] - self.positions['index_start']
		while index_label <= index_label_end:
			set_index = [(index_label//cum_len_sets[i+1])%len_sets[i]
				if i<nb_sets-1 else index_label%len_sets[i]
				for i in range(0,nb_sets)]
			set_index_labels = [self.sets[i].datadict[set_index[i]]['VALUE'] for i in range(0,nb_sets)]
			yield(set_index_labels)
			index_label += 1

	def get_set_index_v3(self):
		'''
		This is a generator function that yields (one by one as a generator)
		in order the lists of sets indexing the constraint.
		'''
		df_set_index = _prepare_df_structure(self.sets)
		index_labels = df_set_index.index
		df_set_index = df_set_index.to_dict('index')

		set_names = [s.name for s in self.sets]

		for index_label in index_labels:
			yield([df_set_index[index_label][set_name] for set_name in set_names])

	def get_set_index_v2(self):
		'''
		This is a generator function that yields (one by one as a generator)
		in order the lists of sets indexing the constraint.
		'''
		index_label = 0
		index_label_end = self.positions['index_end'] - self.positions['index_start']
		while index_label <= index_label_end:
#        for index_label in range(0, self.positions['index_end'] - self.positions['index_start'] + 1):

			if len(self.sets) == 1:
				set_index = self.sets[0].data.loc[index_label, 'VALUE']
				yield([set_index])

			else:
				remaining_index_label = index_label
				index_pos = []
				set_index = []
				# Calculate the position of the first until second-to-last index set value in the Set dataframe.
				# Get the corresponding index set value.
				for set_pos in range(0, len(self.sets)-1): # set_pos is the position of the set in the list of set-indices
#                    stacked_index = reduce(lambda x, y: x*y, [len(s.data) for s in self.sets[set_pos+1:]]) # product(length of sets listed AFTER this set in param_set_index)
					index_pos.append(remaining_index_label // self.stacked_index[set_pos])
					set_index.append(self.sets[set_pos].data.loc[index_pos[set_pos], 'VALUE'])
					remaining_index_label = remaining_index_label - (index_pos[set_pos] * self.stacked_index[set_pos])

				# Calculate the position of the last index set value in the Set dataframe.
				# Get the corresponding index set value.
				set_pos = len(self.sets) - 1
				index_pos.append(remaining_index_label)
				set_index.append(self.sets[set_pos].data.loc[index_pos[set_pos], 'VALUE'])

				yield(set_index)

			index_label += 1

	def get_set_index_v1(self):
		'''
		This is a generator function that yields (one by one as a generator)
		in order the lists of sets indexing the constraint.
		'''
		df_set_index = _prepare_df_structure(self.sets)
		for index_label in df_set_index.index:
			yield(df_set_index.loc[index_label,:].tolist())

###############################################################################

# OSeMOSYS Objective

class Objective(object):
	'''
	Class replacing Pyomo's Objective class.

	Constructor arguments:
		rule: function
			Function defining the constraint's coefficient matrix.
		ObjName: string
			Name describing the objective.

	Public class attributes:
		type: string
			Registers that the object is an Objective.
		name: string
			The name of the Constraint.
		sets: list
			The sets indexing the constraint.
		rule: function
			Function defining the constraint's coefficient matrix.
		positions: dict
			'pos': integer label associated with this constraint.
			'index_start': start of integer index range indexing this constraint.
			'index_end': end of integer index range indexing this constraint.
	'''
	def __init__(self, rule=None, ObjName=''):

		# Verify that we got all we need to define a Var.
		try:
			if ObjName=='' or not isinstance(ObjName, str):
				raise NameError
		except NameError:
				print('Cannot create an Objective without a proper name (non-empty string).')

		# Update Constraint's attributes
		self.type = 'Objective'
		self.name = ObjName
		self.rule = rule

###############################################################################

# LP problem

def write_objective(Obj, output_path):
	'''
	Writes the objective function of the model.

	Arguments:
		Obj: Objective object
			Instance of the Objective class
	'''
	print('Writing objective of the LP problem...')
	objective_filename = os.path.join(output_path, "objective.txt")
	objective_file = open(objective_filename,"w")
	objective_file.write("\\* ITOM_tinyomo *\\")
	objective_file.write("\n\n")
	objective_file.write("min\nOBJ:\n")

	# rule
	obj_data = Obj.rule()

	for pair in obj_data:
		coeff = pair[0]
		var_index = pair[1]
		# var_index is either a single variable index label or a list of
		# variable index labels (returned by .get_index_label)
		if isinstance(var_index, list):
			# coeff is either a single number or a list of numbers
			# (the same length as the var_index list)
			if isinstance (coeff, list):
				for i in range(0,len(coeff)):
					objective_file.write("{}{} x{}\n".format("+" if coeff[i] >= 0
															 else "",
															 coeff[i],
															 var_index[i]))
			else:
				for single_var_index in var_index:
					objective_file.write("{}{} x{}\n".format("+" if coeff >= 0
															 else "",
															 coeff,
															 single_var_index))
		else:
			# When var_index is a single index label, coeff should also be a
			# single number
			objective_file.write("{}{} x{}\n".format("+" if coeff >= 0
													  else "",
													  coeff,
													  var_index))
	objective_file.close()

	return None

def write_constraints(ConsGroup, VarsGroup, SingleCons=None, shadow=False):
	'''
	Writes the constraints of the model.

	Arguments:
		ConsGroup: Constraints object
			Instance of the Constraints class
		VarsGroup: Variables object
			Instance of the Variables class
		SingleCons [optional]: Constraint Object
			Instance of a single Constraint object.
			Can be used for testing/debugging to write out only one constraint.
	'''
	print('Writing constraints of the LP problem...')
	constraints_filename = os.path.join(ConsGroup.output_path, "constraints.txt")
	constraints_file = open(constraints_filename,"w")
	constraints_file.write("\ns.t.\n\n")

	# For retrieving shadow prices
	if shadow:
		shadow_filename = os.path.join(ConsGroup.output_path, "constraints_detailed.txt")
		shadow_file = open(shadow_filename,"w")
		shadow_file.write("c.tinyomo,c.name,index\n")

	# For testing/debugging purposes
	if not SingleCons is None:
		constraints = [SingleCons]
	else:
		constraints = ConsGroup.all_cons

	for c in constraints:

		tc0 = time()
#        set_index_gen = (c.get_set_index(p) for p in range(c.positions['index_start'], c.positions['index_end']+1))
		set_index_gen = c.get_set_index()
		for position in range(c.positions['index_start'], c.positions['index_end']+1):

			# Get the list of set values making the index of the constraint at that position.
			set_index = next(set_index_gen)

			# rule
			cons_data = c.rule(*set_index)

			# If the constraint rule returns None, skip the constraint.
			if not cons_data is None:

				constraints_file.write("c_{}_c{}_:\n".format("e" if cons_data['sense'] == "==" else ("u" if cons_data['sense'] == "<=" else "l"),
															position))

				# For retrieving shadow prices
				if shadow:
					shadow_file.write("c_{}_c{}_,{},{}\n".format("e" if cons_data['sense'] == "==" else ("u" if cons_data['sense'] == "<=" else "l"),
										position, c.name, ';'.join([str(s) for s in set_index])))


				for pair in cons_data['lhs']:
					coeff = pair[0]
					var_index = pair[1]
					# var_index is either a single variable index label or a list of
					# variable index labels (returned by .get_index_label)
					if isinstance(var_index, list):
						# coeff is either a single number or a list of numbers
						# (the same length as the var_index list)
						# Add the variable indices to the set of relevant variables
						VarsGroup.relevant_vars.update(var_index)
						if isinstance (coeff, list):
							for i in range(0,len(coeff)):
								constraints_file.write("{}{} x{}\n".format("+" if coeff[i] >= 0
																		   else "",
																		   coeff[i],
																		   var_index[i]))
						else:
							# If coeff is a single number, use the same coeff for each variable.
							for single_var_index in var_index:
								constraints_file.write("{}{} x{}\n".format("+" if coeff >= 0
																		   else "",
																		   coeff,
																		   single_var_index))
					else:
						# When var_index is a single index label, coeff should also be a
						# single number
						# Add the variable indices to the set of relevant variables
						VarsGroup.relevant_vars.add(var_index)
						constraints_file.write("{}{} x{}\n".format("+" if coeff >= 0
																   else "",
																   coeff,
																   var_index))

				constraints_file.write("{} {}\n\n".format("=" if cons_data['sense'] == "=="
														  else cons_data['sense'],
														  cons_data['rhs']))
		tc1 = time()
		print('     ' + c.name + ': ' + str(int(tc1-tc0)) + ' s')

	constraints_file.close()
	if shadow:
		shadow_file.close()

	return None

def write_bounds(VarsGroup):
	'''
	Writes the bounds constraints for all variables of the model.

	Arguments:
		VarsGroup: Vars object
			Instance of the Vars class
	'''
	print('Writing variable bounds of the LP problem...')
	bounds_filename = os.path.join(VarsGroup.output_path, "bounds.txt")
	bounds_file = open(bounds_filename,"w")
	bounds_file.write("c_e_ONE_VAR_CONSTANT: \nONE_VAR_CONSTANT = 1.0\n\nbounds\n")

	for v in VarsGroup.all_vars:
		lower = v.lower
		upper = v.upper
		positions = range(v.positions['index_start'], v.positions['index_end']+1)
		# Write bounds only for variables that are actually used in constraints (i.e. relevant variables)
		relevant_positions = VarsGroup.relevant_vars.intersection(positions)
#        for position in range(v.positions['index_start'], v.positions['index_end']+1):
		for position in relevant_positions:
			bounds_file.write("   {} <= x{} <= {}\n".format(lower, position, upper))

		print('     ' + v.name)

	bounds_file.write("end\n")
	bounds_file.close()

	return None


def write_lp(output_path, keep_files=False):
	'''
	'''
	objective_filename = os.path.join(output_path, "objective.txt")
	constraints_filename = os.path.join(output_path, "constraints.txt")
	bounds_filename = os.path.join(output_path, "bounds.txt")
	lp_filename = os.path.join(output_path, "problem.lp")

	os.system("cat {} {} {} > {}".format(objective_filename,
										 constraints_filename,
										 bounds_filename,
										 lp_filename))
	if not keep_files:
	   for filename in [objective_filename, constraints_filename, bounds_filename]:
		   os.system("rm "+ filename)

	return None

#def write_bounds(VarsGroup):
#	'''
#	Writes the bounds constraints for all variables of the model.
#
#	Arguments:
#		VarsGroup: Vars object
#			Instance of the Vars class
#	'''
#	print('Writing variable bounds of the LP problem...')
#	bounds_filename = os.path.join(VarsGroup.output_path, "bounds.txt")
#	bounds_file = open(bounds_filename,"w")
#	bounds_file.write("c_e_ONE_VAR_CONSTANT: \nONE_VAR_CONSTANT = 1.0\n\nbounds\n")
#
#	for v in VarsGroup.all_vars:
#		lower = v.lower
#		upper = v.upper
#		positions = range(v.positions['index_start'], v.positions['index_end']+1)
#		# Write bounds only for variables that are actually used in constraints (i.e. relevant variables)
#		relevant_positions = VarsGroup.relevant_vars.intersection(positions)
##        for position in range(v.positions['index_start'], v.positions['index_end']+1):
#		for position in relevant_positions:
#			bounds_file.write("   {} <= x{} <= {}\n".format(lower, position, upper))
#
#		print('     ' + v.name)
#
#	bounds_file.write("end\n")
#	bounds_file.close()
#
#	return None


###########################################################################
###########################################################################

def write_parameters(*arg, output_path=None):
	'''
	Writes the parameter dataframes (filled out with default values).

	Arguments:
		*arg: Param objects
			Instances of the Param class
	'''
	print('Writing parameters of the LP problem...')

	for p in arg:
		p.data.to_csv(os.path.join(output_path, p.name+".csv"))

	return None

def write_constraints_overview(ConsGroup):
    '''
    Writes information relative to the index of each constraint.

    Arguments:
        ConsGroup: Constraints object
            Instance of the Constraints class
    '''
    print('Writing index information for constraints of the LP problem...')
    cons_filename = os.path.join(ConsGroup.output_path, "constraints_overview.txt")
    cons_file = open(cons_filename,"w")
    cons_file.write("cons_name,position,index_start,index_end,index_sets,\n")

    for c in ConsGroup.all_cons:
        cons_file.write("{},{},{},{},{}\n".format(c.name,
                                            c.positions['pos'], c.positions['index_start'], c.positions['index_end'],
                                            ';'.join([i.name for i in c.sets])))
    cons_file.close()

    return None


def write_variables_overview(VarsGroup):
    '''
    Writes information relative to the index of each variable.

    Arguments:
        VarsGroup: Vars object
            Instance of the Vars class
    '''
    print('Writing index information for variables of the LP problem...')
    vars_filename = os.path.join(VarsGroup.output_path, "variables_overview.txt")
    vars_file = open(vars_filename,"w")
    vars_file.write("var_name,index_length,index_sets,\n")

    for v in VarsGroup.all_vars:
        vars_file.write("{},{},{}\n".format(v.name,
                                            str(len(v.sets)),
                                            ';'.join([i.name for i in v.sets])))
    vars_file.close()

    return None


def write_variables(VarsGroup):
	'''
	Writes the variables as x_i and name(index).

	Arguments:
		VarsGroup: Vars object
			Instance of the Vars class
	'''
	print('Writing variables of the LP problem...')
	vars_filename = os.path.join(VarsGroup.output_path, "variables.txt")
	vars_file = open(vars_filename,"w")
	vars_file.write("x_index,x,var_name,var_index,var_lp\n")

	for v in VarsGroup.all_vars:
		# TODO here is an Exception needed for the Variable ModelPeriodCost that has no Sets and the _prepare_df_structure_ crashes

		len_sets = [s.len for s in v.sets]
		nb_sets = len(len_sets)
		cum_len_sets = [math.prod(len_sets[i:]) for i in range(0,len(len_sets))]

		positions = range(v.positions['index_start'], v.positions['index_end']+1)
		# Write only variables that are actually used in constraints (i.e. relevant variables)
		relevant_positions = VarsGroup.relevant_vars.intersection(positions)
		for position in relevant_positions:
			index_label = position - v.positions['index_start']
			# set_index of the form [0,0,0,0] then [0,0,0,1] etc.
			set_index = [(index_label//cum_len_sets[i+1])%len_sets[i]
							if i<nb_sets-1 else index_label%len_sets[i]
							for i in range(0,nb_sets)]
			# To replicate pyomo variable name format:
			# # String all index labels with '_' as separator
			# # Remove remaining "-" (e.g. in technology names) and replace with '_' too
			# # Remove remaining " " (e.g. in technology names) and replace with '_' too
			# set_index_lables of the form [EU27,cracker,naphtha,2020] then [EU27,cracker,naphtha,2030] etc.
			set_index_labels = [str(v.sets[i].datadict[set_index[i]]['VALUE']) for i in range(0,nb_sets)]
			var_name_pyomo = '_'.join('_'.join(set_index_labels).split('-'))
			var_name_pyomo = '_'.join(var_name_pyomo.split(' '))
			vars_file.write("{},x{},{},{},{}({})\n".format(position, position, v.name,
														';'.join(set_index_labels),
														v.name, var_name_pyomo))
	vars_file.close()
	return None

def write_variables_v2(VarsGroup):
	'''
	Writes the variables as x_i and name(index).

	Arguments:
		VarsGroup: Vars object
			Instance of the Vars class
	'''
	print('Writing variables of the LP problem...')
	vars_filename = os.path.join(VarsGroup.output_path, "variables.txt")
	vars_file = open(vars_filename,"w")
	vars_file.write("x_index,x,var_name,var_index,var_lp\n")

	for v in VarsGroup.all_vars:
		# TODO here is an Exception needed for the Variable ModelPeriodCost that has no Sets and the _prepare_df_structure_ crashes
		v_structure = _prepare_df_structure(v.sets, exchange=v.exchange)
		#df_set_index = _prepare_df_structure(self.sets)
		index_labels = v_structure.index
		v_structure = v_structure.to_dict('index')

		set_names = [s.name for s in v.sets]

		positions = range(v.positions['index_start'], v.positions['index_end']+1)
		# Write only variables that are actually used in constraints (i.e. relevant variables)
		relevant_positions = VarsGroup.relevant_vars.intersection(positions)
		for position in relevant_positions:
			v_index = position - v.positions['index_start']
			# To replicate pyomo variable name format:
			# # String all index with '_' as separator
			# # Remove remaining "-" (e.g. in technology names) and replace with '_' too
			set_index = [str(v_structure[v_index][set_name]) for set_name in set_names]
			var_name_pyomo = '_'.join('_'.join(set_index).split('-'))
			vars_file.write("{},x{},{},{},{}({})\n".format(position, position, v.name,
														';'.join(set_index),
														v.name, var_name_pyomo))

	vars_file.close()

	return None

def write_variables_v1(VarsGroup):
	'''
	Writes the variables as x_i and name(index).

	Arguments:
		VarsGroup: Vars object
			Instance of the Vars class
	'''
	print('Writing variables of the LP problem...')
	vars_filename = os.path.join(VarsGroup.output_path, "variables.txt")
	vars_file = open(vars_filename,"w")
	vars_file.write("x_index,x,var_name,var_index,var_lp\n")

	for v in VarsGroup.all_vars:
		# TODO here is an Exception needed for the Variable ModelPeriodCost that has no Sets and the _prepare_df_structure_ crashes
		v_structure = _prepare_df_structure(v.sets, exchange=v.exchange)

		positions = range(v.positions['index_start'], v.positions['index_end']+1)
		# Write only variables that are actually used in constraints (i.e. relevant variables)
		relevant_positions = VarsGroup.relevant_vars.intersection(positions)
		for position in relevant_positions:
			v_index = position - v.positions['index_start']
			# To replicate pyomo variable name format:
			# # String all index with '_' as separator
			# # Remove remaining "-" (e.g. in technology names) and replace with '_' too
			var_name_pyomo = '_'.join('_'.join([str(i) for i in v_structure.iloc[v_index].values]).split('-'))
			vars_file.write("{},x{},{},{},{}({})\n".format(position, position, v.name,
														';'.join([str(i) for i in v_structure.iloc[v_index].values]),
														v.name, var_name_pyomo))

	vars_file.close()

	return None

###########################################################################
# LIKE PYOMO
###########################################################################

def write_objective_likepyomo(Obj, output_path):
	'''
	Writes the objective function of the model.

	Arguments:
		Obj: Objective object
			Instance of the Objective class
	'''
	# Get all (relevant) variables in their short x(i) and long name(index) forms
	df_vars = pd.read_csv(os.path.join(output_path, "variables.txt"), sep=',')
	df_vars.loc[:,'x_index'] = df_vars['x_index'].astype('int32')

	print('[LIKE-PYOMO] Writing objective of the LP problem...')
	objective_filename = os.path.join(output_path, "objective_likepyomo.txt")
	objective_file = open(objective_filename,"w")
	objective_file.write("\\* ITOM_tinyomo *\\")
	objective_file.write("\n\n")
	objective_file.write("min\nOBJ:\n")

	# rule
	obj_data = Obj.rule()

	for pair in obj_data:
		coeff = pair[0]
		var_index = pair[1]
		# var_index is either a single variable index label or a list of
		# variable index labels (returned by .get_index_label)
		if isinstance(var_index, list):
			# coeff is either a single number or a list of numbers
			# (the same length as the var_index list)
			if isinstance (coeff, list):
				for i in range(0,len(coeff)):
					objective_file.write("{}{} {}\n".format("+" if coeff[i] >= 0
															 else "",
															 coeff[i],
															 df_vars.loc[df_vars['x_index']==var_index[i],'var_lp'].iloc[0]))
			else:
				for single_var_index in var_index:
					objective_file.write("{}{} {}\n".format("+" if coeff >= 0
															 else "",
															 coeff,
															 df_vars.loc[df_vars['x_index']==single_var_index,'var_lp'].iloc[0]))
		else:
			# When var_index is a single index label, coeff should also be a
			# single number
			objective_file.write("{}{} {}\n".format("+" if coeff >= 0
													  else "",
													  coeff,
													  df_vars.loc[df_vars['x_index']==var_index,'var_lp'].iloc[0]))
	objective_file.close()

	return None


def write_constraints_likepyomo(ConsGroup, VarsGroup, SingleCons=None):
	'''
	Writes the constraints of the model.

	Arguments:
		ConsGroup: Constraints object
			Instance of the Constraints class
		SingleCons [optional]: Constraint Object
			Instance of a single Constraint object.
			Can be used for testing/debugging to write out only one constraint.
	'''
	# Get all (relevant) variables in their short x(i) and long name(index) forms
	df_vars = pd.read_csv(os.path.join(ConsGroup.output_path, "variables.txt"), sep=',')
	df_vars.loc[:,'x_index'] = df_vars['x_index'].astype('int32')
	print('[LIKE-PYOMO] Writing constraints of the LP problem...')
	constraints_filename = os.path.join(ConsGroup.output_path, "constraints_likepyomo.txt")
	constraints_file = open(constraints_filename,"w")
	constraints_file.write("\ns.t.\n\n")

	# For testing/debugging purposes
	if not SingleCons is None:
		constraints = [SingleCons]
	else:
		constraints = ConsGroup.all_cons

	for c in constraints:

		tc0 = time()
#        set_index_gen = (c.get_set_index(p) for p in range(c.positions['index_start'], c.positions['index_end']+1))
		set_index_gen = c.get_set_index()
		for position in range(c.positions['index_start'], c.positions['index_end']+1):

			# Get the list of set values making the index of the constraint at that position.
			set_index = next(set_index_gen)

			# rule
			cons_data = c.rule(*set_index)

			# If the constraint rule returns None, skip the constraint.
			if not cons_data is None:
				# To replicate pyomo index format:
				# # String all index with '_' as separator
				# # Remove remaining "-" (e.g. in technology names) and replace with '_' too
				# # Remove remaining " " (e.g. in technology names) and replace with '_' too
				index_pyomo = '_'.join('_'.join([str(i) for i in set_index]).split('-'))
				index_pyomo = '_'.join(index_pyomo.split(' '))
				constraints_file.write("c_{}_{}({})_:\n".format("e" if cons_data['sense'] == "==" else ("u" if cons_data['sense'] == "<=" else "l"),
																c.name, index_pyomo))

				for pair in cons_data['lhs']:
					coeff = pair[0]
					var_index = pair[1]
					# var_index is either a single variable index label or a list of
					# variable index labels (returned by .get_index_label)
					if isinstance(var_index, list):
						# coeff is either a single number or a list of numbers
						# (the same length as the var_index list)
						# Add the variable indices to the set of relevant variables
						VarsGroup.relevant_vars.update(var_index)
						if isinstance (coeff, list):
							for i in range(0,len(coeff)):
								constraints_file.write("{}{} {}\n".format("+" if coeff[i] >= 0
																		   else "",
																		   coeff[i],
																		   df_vars.loc[df_vars['x_index']==var_index[i],'var_lp'].iloc[0]))
						else:
							# If coeff is a single number, use the same coeff for each variable.
							for single_var_index in var_index:
								constraints_file.write("{}{} {}\n".format("+" if coeff >= 0
																		   else "",
																		   coeff,
																		   df_vars.loc[df_vars['x_index']==single_var_index,'var_lp'].iloc[0]))
					else:
						# When var_index is a single index label, coeff should also be a
						# single number
						# Add the variable indices to the set of relevant variables
						VarsGroup.relevant_vars.add(var_index)
						constraints_file.write("{}{} {}\n".format("+" if coeff >= 0
																   else "",
																   coeff,
																   df_vars.loc[df_vars['x_index']==var_index,'var_lp'].iloc[0]))

				constraints_file.write("{} {}\n\n".format("=" if cons_data['sense'] == "=="
														  else cons_data['sense'],
														  cons_data['rhs']))
		tc1 = time()
		print('     ' + c.name + ': ' + str(int(tc1-tc0)) + ' s')

	constraints_file.close()

	return None


def write_bounds_likepyomo(VarsGroup):
	'''
	Writes the bounds constraints for all variables of the model.

	Arguments:
		VarsGroup: Vars object
			Instance of the Vars class
	'''
	# Get all (relevant) variables in their short x(i) and long name(index) forms
	df_vars = pd.read_csv(os.path.join(VarsGroup.output_path, "variables.txt"), sep=',')
	df_vars.loc[:,'x_index'] = df_vars['x_index'].astype('int32')

	print('[LIKE-PYOMO] Writing variable bounds of the LP problem...')
	bounds_filename = os.path.join(VarsGroup.output_path, "bounds_likepyomo.txt")
	bounds_file = open(bounds_filename,"w")
	bounds_file.write("c_e_ONE_VAR_CONSTANT: \nONE_VAR_CONSTANT = 1.0\n\nbounds\n")

	for v in VarsGroup.all_vars:
		lower = v.lower
		upper = v.upper
		v_structure = _prepare_df_structure(v.sets, exchange=v.exchange)

		positions = range(v.positions['index_start'], v.positions['index_end']+1)
		# Write bounds only for variables that are actually used in constraints (i.e. relevant variables)
		relevant_positions = VarsGroup.relevant_vars.intersection(positions)
		for position in relevant_positions:
			v_index = position - v.positions['index_start']
			bounds_file.write("   {} <= {} <= {}\n".format(lower,
															df_vars.loc[df_vars['x_index']==position,'var_lp'].iloc[0],
															upper))

		print('     ' + v.name)

	bounds_file.write("end\n")
	bounds_file.close()

	return None

def write_lp_likepyomo(output_path, keep_files=False):
	'''
	'''
	objective_filename = os.path.join(output_path, "objective_likepyomo.txt")
	constraints_filename = os.path.join(output_path, "constraints_likepyomo.txt")
	bounds_filename = os.path.join(output_path, "bounds_likepyomo.txt")
	lp_filename = os.path.join(output_path, "problem_likepyomo.lp")

	os.system("cat {} {} {} > {}".format(objective_filename,
										 constraints_filename,
										 bounds_filename,
										 lp_filename))
	if not keep_files:
	   for filename in [objective_filename, constraints_filename, bounds_filename]:
		   os.system("rm "+ filename)

	return None


##############################################################################
##############################################################################
