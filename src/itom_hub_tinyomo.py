#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
This module defines:

	- the `itom_hub_tinyomo` class that replaces a Pyomo ABSTRACT and CONCRETE model definition using classes from tinyomo
	for the energy-intensive industry system, where locations are indirectly connected via a transport hub.

@author: mathieusa, alexanderkl
'''

__all__ = ('itom_hub_tinyomo')

# from __future__ import division
import os
import numpy as np
from tinyomo import Sets, Set, Params, Param, Vars, Var, Constraints, Constraint, Objective
from tinyomo import NonNegativeReals, Reals
from tinyomo import write_objective, write_constraints, write_bounds, write_lp
from tinyomo import write_variables_overview, write_variables, write_constraints_overview
from tinyomo import write_objective_likepyomo, write_constraints_likepyomo, write_bounds_likepyomo, write_lp_likepyomo
from tinyomo import write_parameters


##############################################################################

class itom_hub_tinyomo(object):
	'''
	Class defining an ITOM model object with transport hubs.

	**Constructor arguments:**
		*InputPath [optional]: string*
			Path to directory of csv input data files. Default: None.
		*OutputPath [optional]: string*
			Path to directory where the LP model files and model result files will be saved. Default: None.

	**Public class attributes:**
		tbc
	'''

	def __init__(self, InputPath=None, OutputPath=None, config=None):
		# Path to directory of csv input data files
		self.InputPath = InputPath
		# Path to directory where csv result files will be saved
		self.OutputPath = OutputPath

		# Dictionary of configuration items
		self.config = config

		# High default max value for inequality constraints
		# The point is to actually skip such constraints (bounds are enough)
		# to reduce the size of the LP problem.
		self.HighMaxDefault = 1e20

		###############
		#    Sets     #
		###############

		# Object containing info on all Sets
		self.AllSets = Sets(InputPath=self.InputPath)

		self.YEAR = Set(SetName='YEAR', SetsGroup=self.AllSets)
		self.TECHNOLOGY = Set(SetName='TECHNOLOGY', SetsGroup=self.AllSets)
		self.TRANSPORTMODE = Set(SetName='TRANSPORTMODE', SetsGroup=self.AllSets)
		self.PRODUCT = Set(SetName='PRODUCT', SetsGroup=self.AllSets)
		self.REGION = Set(SetName='REGION', SetsGroup=self.AllSets)
		self.LOCATION = Set(SetName='LOCATION', SetsGroup=self.AllSets)
		self.EMISSION = Set(SetName='EMISSION', SetsGroup=self.AllSets)
		self.MODE_OF_OPERATION = Set(SetName='MODE_OF_OPERATION', SetsGroup=self.AllSets)

		# Do not remove or rename these sets, they are copies of the LOCATION set
		# to differentiate between "location from" (LOCATION_1) and "location_to" (LOCATION_2)
		self.LOCATION_1 = Set(SetName='LOCATION_1', SetsGroup=self.AllSets)
		self.LOCATION_2 = Set(SetName='LOCATION_2', SetsGroup=self.AllSets)
		# Same with REGION
		self.REGION_1 = Set(SetName='REGION_1', SetsGroup=self.AllSets)
		self.REGION_2 = Set(SetName='REGION_2', SetsGroup=self.AllSets)

		#####################
		#    Parameters     #
		#####################

		# Object containing info on all Params
		self.AllParams = Params(InputPath=self.InputPath, SetsGroup=self.AllSets)

		########			Auxiliary parameters for reducing memory usage 						#############

		self.ModeForTechnology = Param(self.TECHNOLOGY, self.MODE_OF_OPERATION, default=0,
									   ParamName='ModeForTechnology', ParamsGroup=self.AllParams)
		self.ProductFromTechnology = Param(self.TECHNOLOGY, self.PRODUCT, default=0, ParamName='ProductFromTechnology',
										   ParamsGroup=self.AllParams)
		self.ProductToTechnology = Param(self.TECHNOLOGY, self.PRODUCT, default=0, ParamName='ProductToTechnology',
										 ParamsGroup=self.AllParams)
		self.TimeStep = Param(self.YEAR, default=0, ParamName='TimeStep', ParamsGroup=self.AllParams)

		########			Transport hub: Auxiliary parameters for reducing memory usage 						#############

		self.HubLocation = Param(self.LOCATION, default=0, ParamName='HubLocation', ParamsGroup=self.AllParams)
		self.HubTechnology = Param(self.TECHNOLOGY, default=0, ParamName='HubTechnology', ParamsGroup=self.AllParams)

		########			Global 						#############
		self.DiscountRate = Param(self.REGION, default=0.05, ParamName='DiscountRate', ParamsGroup=self.AllParams)
		self.TransportRoute = Param(self.LOCATION, self.LOCATION, self.PRODUCT, self.TRANSPORTMODE, self.YEAR,
									default=0, exchange=True, ParamName='TransportRoute', ParamsGroup=self.AllParams)
		self.TransportCapacity = Param(self.LOCATION, self.LOCATION, self.PRODUCT, self.TRANSPORTMODE, self.YEAR,
									   default=0.0, exchange=True, ParamName='TransportCapacity',
									   ParamsGroup=self.AllParams)
		self.MultiPurposeTransport = Param(self.TRANSPORTMODE, default=0, ParamName='MultiPurposeTransport',
										   ParamsGroup=self.AllParams)
		self.Geography = Param(self.REGION, self.LOCATION, default=0, ParamName='Geography', ParamsGroup=self.AllParams)
		self.DepreciationMethod = Param(self.REGION, default=1, ParamName='DepreciationMethod',
										ParamsGroup=self.AllParams)
		########			Demands 					#############

		self.Demand = Param(self.REGION, self.PRODUCT, self.YEAR, default=0, ParamName='Demand',
							ParamsGroup=self.AllParams)

		#########			Performance					#############

		self.TransportCapacityToActivity = Param(self.TRANSPORTMODE, default=1, ParamName='TransportCapacityToActivity',
												 ParamsGroup=self.AllParams)
		self.CapacityToActivityUnit = Param(self.REGION, self.TECHNOLOGY, default=1, ParamName='CapacityToActivityUnit',
											ParamsGroup=self.AllParams)
		self.AvailabilityFactor = Param(self.REGION, self.TECHNOLOGY, self.YEAR, default=1,
										ParamName='AvailabilityFactor', ParamsGroup=self.AllParams)
		self.OperationalLife = Param(self.REGION, self.TECHNOLOGY, default=1, ParamName='OperationalLife',
									 ParamsGroup=self.AllParams)
		self.LocalResidualCapacity = Param(self.LOCATION, self.TECHNOLOGY, self.YEAR, default=0,
										   ParamName='LocalResidualCapacity', ParamsGroup=self.AllParams)
		self.InputActivityRatio = Param(self.REGION, self.TECHNOLOGY, self.PRODUCT, self.MODE_OF_OPERATION, self.YEAR,
										default=0, ParamName='InputActivityRatio', ParamsGroup=self.AllParams)
		self.OutputActivityRatio = Param(self.REGION, self.TECHNOLOGY, self.PRODUCT, self.MODE_OF_OPERATION, self.YEAR,
										 default=0, ParamName='OutputActivityRatio', ParamsGroup=self.AllParams)

		#########			Technology Costs			#############

		self.CapitalCost = Param(self.REGION, self.TECHNOLOGY, self.YEAR, default=0, ParamName='CapitalCost',
								 ParamsGroup=self.AllParams)
		self.VariableCost = Param(self.REGION, self.TECHNOLOGY, self.MODE_OF_OPERATION, self.YEAR, default=0,
								  ParamName='VariableCost', ParamsGroup=self.AllParams)
		self.FixedCost = Param(self.REGION, self.TECHNOLOGY, self.YEAR, default=0, ParamName='FixedCost',
							   ParamsGroup=self.AllParams)

		self.TransportCostByMode = Param(self.REGION, self.TRANSPORTMODE, self.YEAR, default=0.0,
										 ParamName='TransportCostByMode', ParamsGroup=self.AllParams)
		self.TransportCostInterReg = Param(self.REGION, self.REGION, self.TRANSPORTMODE, self.YEAR, default=0.0,
											ParamName='TransportCostInterReg', ParamsGroup=self.AllParams)

		#########			Capacity Constraints		#############

		self.TotalAnnualMaxCapacity = Param(self.REGION, self.TECHNOLOGY, self.YEAR, default=self.HighMaxDefault,
											ParamName='TotalAnnualMaxCapacity', ParamsGroup=self.AllParams)
		self.TotalAnnualMinCapacity = Param(self.REGION, self.TECHNOLOGY, self.YEAR, default=0,
											ParamName='TotalAnnualMinCapacity', ParamsGroup=self.AllParams)

		#########			Investment Constraints		#############

		self.LocalTotalAnnualMaxCapacityInvestment = Param(self.LOCATION, self.TECHNOLOGY, self.YEAR,
														   default=self.HighMaxDefault,
														   ParamName='LocalTotalAnnualMaxCapacityInvestment',
														   ParamsGroup=self.AllParams)
		self.LocalTotalAnnualMinCapacityInvestment = Param(self.LOCATION, self.TECHNOLOGY, self.YEAR, default=0,
														   ParamName='LocalTotalAnnualMinCapacityInvestment',
														   ParamsGroup=self.AllParams)

		#########			Activity Constraints		#############

		self.TotalTechnologyAnnualActivityUpperLimit = Param(
			self.REGION, self.TECHNOLOGY, self.YEAR, default=self.HighMaxDefault,
			ParamName='TotalTechnologyAnnualActivityUpperLimit', ParamsGroup=self.AllParams)

		self.TotalTechnologyAnnualActivityLowerLimit = Param(
			self.REGION, self.TECHNOLOGY, self.YEAR, default=0, ParamName='TotalTechnologyAnnualActivityLowerLimit',
			ParamsGroup=self.AllParams)

		self.TotalTechnologyModelPeriodActivityUpperLimit = Param(
			self.REGION, self.TECHNOLOGY, default=self.HighMaxDefault,
			ParamName='TotalTechnologyModelPeriodActivityUpperLimit', ParamsGroup=self.AllParams)

		self.TotalTechnologyModelPeriodActivityLowerLimit = Param(
			self.REGION, self.TECHNOLOGY, default=0,
			ParamName='TotalTechnologyModelPeriodActivityLowerLimit', ParamsGroup=self.AllParams)

		#########			Emissions & Penalties		#############

		self.EmissionActivityRatio = Param(self.REGION, self.TECHNOLOGY, self.EMISSION, self.MODE_OF_OPERATION,
										   self.YEAR, default=0, ParamName='EmissionActivityRatio',
										   ParamsGroup=self.AllParams)

		self.EmissionsPenalty = Param(self.REGION, self.EMISSION, self.YEAR, default=0, ParamName='EmissionsPenalty',
									  ParamsGroup=self.AllParams)

		self.AnnualExogenousEmission = Param(self.REGION, self.EMISSION, self.YEAR, default=0,
											 ParamName='AnnualExogenousEmission', ParamsGroup=self.AllParams)

		self.AnnualEmissionLimit = Param(self.REGION, self.EMISSION, self.YEAR, default=self.HighMaxDefault,
										 ParamName='AnnualEmissionLimit', ParamsGroup=self.AllParams)

		self.ModelPeriodExogenousEmission = Param(self.REGION, self.EMISSION, default=0,
												  ParamName='ModelPeriodExogenousEmission', ParamsGroup=self.AllParams)

		self.ModelPeriodEmissionLimit = Param(self.REGION, self.EMISSION, default=self.HighMaxDefault,
											  ParamName='ModelPeriodEmissionLimit', ParamsGroup=self.AllParams)

		################
		#   Variables  #
		################

		# Object containing info on all Vars
		self.AllVars = Vars(OutputPath=self.OutputPath, SetsGroup=self.AllSets)

		#########		    Capacity Variables 			#############

		self.LocalNewCapacity = Var(self.LOCATION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals, initialize=0.0,
									VarName='LocalNewCapacity', VarsGroup=self.AllVars)

		self.NewCapacity = Var(self.REGION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals, initialize=0.0,
							   VarName='NewCapacity', VarsGroup=self.AllVars)

		self.LocalAccumulatedNewCapacity = Var(self.LOCATION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals,
											   initialize=0.0, VarName='LocalAccumulatedNewCapacity',
											   VarsGroup=self.AllVars)

		self.AccumulatedNewCapacity = Var(self.REGION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals,
										  initialize=0.0, VarName='AccumulatedNewCapacity', VarsGroup=self.AllVars)

		self.LocalTotalCapacity = Var(self.LOCATION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals,
									  initialize=0.0,
									  VarName='LocalTotalCapacity', VarsGroup=self.AllVars)

		self.TotalCapacity = Var(self.REGION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals, initialize=0.0,
								 VarName='TotalCapacity', VarsGroup=self.AllVars)

		#########		    Activity Variables 			#############

		self.LocalActivityByMode = Var(self.LOCATION, self.TECHNOLOGY, self.MODE_OF_OPERATION, self.YEAR,
									   domain=NonNegativeReals, initialize=0.0, VarName="LocalActivityByMode",
									   VarsGroup=self.AllVars)

		self.LocalActivity = Var(self.LOCATION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals, initialize=0.0,
								 VarName="LocalActivity", VarsGroup=self.AllVars)

		self.Activity = Var(self.REGION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals, initialize=0.0,
							VarName="Activity", VarsGroup=self.AllVars)

		self.ModelPeriodActivity = Var(self.REGION, self.TECHNOLOGY, domain=NonNegativeReals, initialize=0.0,
									   VarName="ModelPeriodActivity", VarsGroup=self.AllVars)

		self.LocalProductionByMode = Var(self.LOCATION, self.TECHNOLOGY, self.PRODUCT, self.MODE_OF_OPERATION,
										 self.YEAR,
										 domain=NonNegativeReals, initialize=0.0, VarName="LocalProductionByMode",
										 VarsGroup=self.AllVars)

		self.LocalProductionByTechnology = Var(self.LOCATION, self.TECHNOLOGY, self.PRODUCT, self.YEAR,
											   domain=NonNegativeReals, initialize=0.0,
											   VarName="LocalProductionByTechnology", VarsGroup=self.AllVars)

		self.LocalProduction = Var(self.LOCATION, self.PRODUCT, self.YEAR, domain=NonNegativeReals, initialize=0.0,
								   VarName="LocalProduction", VarsGroup=self.AllVars)
		self.Production = Var(self.REGION, self.PRODUCT, self.YEAR, domain=NonNegativeReals, initialize=0.0,
							  VarName="Production", VarsGroup=self.AllVars)
		# self.ProductionByTechnology = Var(
		#     self.REGION, self.TECHNOLOGY, self.PRODUCT, self.YEAR, domain=NonNegativeReals, initialize=0.0,
		#     VarName="ProductionByTechnology", VarsGroup=self.AllVars)

		self.LocalUseByMode = Var(self.LOCATION, self.TECHNOLOGY, self.PRODUCT, self.MODE_OF_OPERATION, self.YEAR,
								  domain=NonNegativeReals, initialize=0.0, VarName="LocalUseByMode",
								  VarsGroup=self.AllVars)
		self.LocalUseByTechnology = Var(self.LOCATION, self.TECHNOLOGY, self.PRODUCT, self.YEAR,
										domain=NonNegativeReals,
										initialize=0.0, VarName="LocalUseByTechnology", VarsGroup=self.AllVars)
		self.LocalUse = Var(self.LOCATION, self.PRODUCT, self.YEAR, domain=NonNegativeReals, initialize=0.0,
							VarName="LocalUse", VarsGroup=self.AllVars)
		self.Use = Var(self.REGION, self.PRODUCT, self.YEAR, domain=NonNegativeReals, initialize=0.0, VarName="Use",
					   VarsGroup=self.AllVars)

		#########		    Transport Variables 			#############

		self.Transport = Var(self.LOCATION, self.LOCATION, self.PRODUCT,
							 self.TRANSPORTMODE, self.YEAR, domain=NonNegativeReals, initialize=0.0, exchange=True,
							 VarName="Transport", VarsGroup=self.AllVars)
		self.Import = Var(self.REGION, self.PRODUCT, self.YEAR, domain=NonNegativeReals,
						  initialize=0.0, VarName="Import", VarsGroup=self.AllVars)
		self.Export = Var(self.REGION, self.PRODUCT, self.YEAR, domain=NonNegativeReals,
						  initialize=0.0, VarName="Export", VarsGroup=self.AllVars)

		#########		    Costing Variables 			#############
		self.LocalCapitalInvestment = Var(self.LOCATION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals,
										  initialize=0.0, VarName="LocalCapitalInvestment", VarsGroup=self.AllVars)
		self.LocalDiscountedCapitalInvestment = Var(self.LOCATION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals,
													initialize=0.0, VarName="LocalDiscountedCapitalInvestment",
													VarsGroup=self.AllVars)
		self.DiscountedCapitalInvestment = Var(self.REGION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals,
											   initialize=0.0, VarName="DiscountedCapitalInvestment",
											   VarsGroup=self.AllVars)

		self.SalvageValue = Var(self.REGION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals, initialize=0.0,
								VarName="SalvageValue", VarsGroup=self.AllVars)
		self.DiscountedSalvageValue = Var(self.REGION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals,
										  initialize=0.0, VarName="DiscountedSalvageValue", VarsGroup=self.AllVars)

		# LocalVariableOperatingCost, LocalOperatingCost, LocalDiscountedOperatingCost, DiscountedOperatingCost:
		# allow for negative variable costs at a given location (e.g. through a stand-alone export terminal technology)
		self.LocalVariableOperatingCost = Var(self.LOCATION, self.TECHNOLOGY, self.YEAR, domain=Reals, initialize=0.0,
											  VarName="LocalVariableOperatingCost", VarsGroup=self.AllVars)
		self.LocalFixedOperatingCost = Var(self.LOCATION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals,
										   initialize=0.0, VarName="LocalFixedOperatingCost", VarsGroup=self.AllVars)
		self.LocalOperatingCost = Var(self.LOCATION, self.TECHNOLOGY, self.YEAR, domain=Reals, initialize=0.0,
									  VarName="LocalOperatingCost", VarsGroup=self.AllVars)
		self.LocalDiscountedOperatingCost = Var(self.LOCATION, self.TECHNOLOGY, self.YEAR, domain=Reals, initialize=0.0,
												VarName="LocalDiscountedOperatingCost", VarsGroup=self.AllVars)
		self.DiscountedOperatingCost = Var(self.REGION, self.TECHNOLOGY, self.YEAR, domain=Reals, initialize=0.0,
										   VarName="DiscountedOperatingCost", VarsGroup=self.AllVars)

		self.LocalTransportCost = Var(self.LOCATION, self.PRODUCT, self.YEAR, domain=NonNegativeReals, initialize=0.0,
									  VarName="LocalTransportCost", VarsGroup=self.AllVars)
		self.LocalDiscountedTransportCost = Var(self.LOCATION, self.PRODUCT, self.YEAR, domain=NonNegativeReals,
												initialize=0.0, VarName="LocalDiscountedTransportCost",
												VarsGroup=self.AllVars)
		self.DiscountedTransportCostByProduct = Var(self.REGION, self.PRODUCT, self.YEAR, domain=NonNegativeReals,
													initialize=0.0, VarName="DiscountedTransportCostByProduct",
													VarsGroup=self.AllVars)
		self.DiscountedTransportCost = Var(self.REGION, self.YEAR, domain=NonNegativeReals, initialize=0.0,
										   VarName="DiscountedTransportCost", VarsGroup=self.AllVars)

		self.TotalDiscountedCost = Var(self.REGION, self.YEAR, domain=Reals, initialize=0.0,
									   VarName="TotalDiscountedCost", VarsGroup=self.AllVars)
		self.ModelPeriodCostByRegion = Var(self.REGION, domain=Reals, initialize=0.0, VarName="ModelPeriodCostByRegion",
										   VarsGroup=self.AllVars)
		# self.ModelPeriodCost = Var(domain=Reals, initialize=0.0, VarName="ModelPeriodCost", VarsGroup=self.AllVars)

		#########			Emissions					#############

		self.LocalTechnologyEmissionByMode = Var(self.LOCATION, self.TECHNOLOGY, self.EMISSION, self.MODE_OF_OPERATION,
												 self.YEAR, domain=Reals, initialize=0.0,
												 VarName="LocalTechnologyEmissionByMode", VarsGroup=self.AllVars)
		self.LocalTechnologyEmission = Var(self.LOCATION, self.TECHNOLOGY, self.EMISSION, self.YEAR, domain=Reals,
										   initialize=0.0, VarName="LocalTechnologyEmission", VarsGroup=self.AllVars)
		self.AnnualTechnologyEmission = Var(self.REGION, self.TECHNOLOGY, self.EMISSION, self.YEAR, domain=Reals,
											initialize=0.0, VarName="AnnualTechnologyEmission", VarsGroup=self.AllVars)
		self.AnnualTechnologyEmissionPenaltyByEmission = Var(self.REGION, self.TECHNOLOGY, self.EMISSION, self.YEAR,
															 domain=Reals, initialize=0.0,
															 VarName="AnnualTechnologyEmissionPenaltyByEmission",
															 VarsGroup=self.AllVars)
		self.AnnualTechnologyEmissionsPenalty = Var(self.REGION, self.TECHNOLOGY, self.YEAR, domain=Reals,
													initialize=0.0, VarName="AnnualTechnologyEmissionsPenalty",
													VarsGroup=self.AllVars)
		self.DiscountedTechnologyEmissionsPenalty = Var(self.REGION, self.TECHNOLOGY, self.YEAR, domain=Reals,
														initialize=0.0, VarName="DiscountedTechnologyEmissionsPenalty",
														VarsGroup=self.AllVars)
		self.AnnualEmissions = Var(self.REGION, self.EMISSION, self.YEAR, domain=Reals, initialize=0.0,
								   VarName="AnnualEmissions", VarsGroup=self.AllVars)
		self.ModelPeriodEmissions = Var(self.REGION, self.EMISSION, domain=Reals, initialize=0.0,
										VarName="ModelPeriodEmissions", VarsGroup=self.AllVars)
		#        self.ModelPeriodCost = Var(domain=Reals, initialize=0.0, VarName="ModelPeriodCost", VarsGroup=self.AllVars)

		######################
		# Objective Function #
		######################

		self.OBJ = Objective(rule=self.ObjectiveFunction_rule, ObjName='min_costs')

		#####################
		# Constraints       #
		#####################

		# Object containing info on all Constraints
		self.AllCons = Constraints(OutputPath=self.OutputPath, SetsGroup=self.AllSets)

		#########       	Capacity Adequacy	     	#############
		self.CA0_NewCapacity = Constraint(self.REGION, self.TECHNOLOGY, self.YEAR, rule=self.CA0_NewCapacity_rule,
										  ConsName="CA0_NewCapacity", ConsGroup=self.AllCons)
		self.CA1_TotalNewCapacity_1 = Constraint(self.LOCATION, self.TECHNOLOGY, self.YEAR,
												 rule=self.CA1_TotalNewCapacity_1_rule,
												 ConsName="CA1_TotalNewCapacity_1", ConsGroup=self.AllCons)
		self.CA2_TotalNewCapacity_2 = Constraint(self.REGION, self.TECHNOLOGY, self.YEAR,
												 rule=self.CA2_TotalNewCapacity_2_rule,
												 ConsName="CA2_TotalNewCapacity_2", ConsGroup=self.AllCons)
		self.CA3_TotalAnnualCapacity_1 = Constraint(self.LOCATION, self.TECHNOLOGY, self.YEAR,
													rule=self.CA3_TotalAnnualCapacity_1_rule,
													ConsName="CA3_TotalAnnualCapacity_1", ConsGroup=self.AllCons)
		self.CA4_TotalAnnualCapacity_2 = Constraint(self.REGION, self.TECHNOLOGY, self.YEAR,
													rule=self.CA4_TotalAnnualCapacity_2_rule,
													ConsName="CA4_TotalAnnualCapacity_2", ConsGroup=self.AllCons)
		self.CA5_ConstraintCapacity = Constraint(self.LOCATION, self.TECHNOLOGY, self.YEAR,
												 rule=self.CA5_ConstraintCapacity_rule,
												 ConsName="CA5_ConstraintCapacity", ConsGroup=self.AllCons)

		#########	        Product Balance    	 	#############
		self.PB1_Production_1 = Constraint(self.LOCATION, self.PRODUCT, self.TECHNOLOGY, self.MODE_OF_OPERATION,
										   self.YEAR, rule=self.PB1_Production_1_rule, ConsName="PB1_Production_1",
										   ConsGroup=self.AllCons)

		self.PB2_Production_2 = Constraint(self.LOCATION, self.PRODUCT, self.TECHNOLOGY, self.YEAR,
										   rule=self.PB2_Production_2_rule, ConsName="PB2_Production_2",
										   ConsGroup=self.AllCons)

		self.PB3_Production_3 = Constraint(self.LOCATION, self.PRODUCT, self.YEAR, rule=self.PB3_Production_3_rule,
										   ConsName="PB3_Production_3", ConsGroup=self.AllCons)

		self.PB4_Production_4 = Constraint(self.REGION, self.PRODUCT, self.YEAR, rule=self.PB4_Production_4_rule,
										   ConsName="PB4_Production_4", ConsGroup=self.AllCons)

		# self.PB5_Production_5 = Constraint(self.REGION, self.TECHNOLOGY, self.PRODUCT, self.YEAR,
		#                                   rule=self.PB5_Production_5_rule, ConsName="PB5_Production_5",
		#                                   ConsGroup=self.AllCons)

		self.PB5_Use_1 = Constraint(self.LOCATION, self.PRODUCT, self.TECHNOLOGY, self.MODE_OF_OPERATION, self.YEAR,
									rule=self.PB5_Use_1_rule, ConsName="PB5_Use_1", ConsGroup=self.AllCons)

		self.PB6_Use_2 = Constraint(self.LOCATION, self.PRODUCT, self.TECHNOLOGY, self.YEAR, rule=self.PB6_Use_2_rule,
									ConsName="PB6_Use_2", ConsGroup=self.AllCons)

		self.PB7_Use_3 = Constraint(self.LOCATION, self.PRODUCT, self.YEAR, rule=self.PB7_Use_3_rule,
									ConsName="PB7_Use_3", ConsGroup=self.AllCons)

		self.PB8_Use_4 = Constraint(self.REGION, self.PRODUCT, self.YEAR, rule=self.PB8_Use_4_rule,
									ConsName="PB8_Use_4", ConsGroup=self.AllCons)

		self.PB9_ProductBalance = Constraint(self.REGION, self.PRODUCT, self.YEAR, rule=self.PB9_ProductBalance_rule,
											 ConsName="PB9_ProductBalance", ConsGroup=self.AllCons)

		#########        	Transport Flows	 	#############
		self.TF1a_Transport_1a = Constraint(self.LOCATION, self.LOCATION, self.PRODUCT, self.TRANSPORTMODE, self.YEAR,
											rule=self.TF1a_Transport_1a_rule, ConsName="TF1a_Transport_1a",
											ConsGroup=self.AllCons, exchange=True)

		self.TF1b_Transport_1b = Constraint(self.LOCATION, self.LOCATION, self.TRANSPORTMODE, self.YEAR,
											rule=self.TF1b_Transport_1b_rule, ConsName="TF1b_Transport_1b",
											ConsGroup=self.AllCons, exchange=True)
		self.TF2_Transport_2 = Constraint(self.LOCATION, self.PRODUCT, self.YEAR, rule=self.TF2_Transport_2_rule,
										  ConsName="TF2_Transport_2", ConsGroup=self.AllCons)

		self.TF3_Transport_3 = Constraint(self.LOCATION, self.PRODUCT, self.YEAR, rule=self.TF3_Transport_3_rule,
										  ConsName="TF3_Transport_3", ConsGroup=self.AllCons)

		self.TF4_Imports = Constraint(self.REGION, self.PRODUCT, self.YEAR, rule=self.TF4_Imports_rule,
									  ConsName="TF4_Imports", ConsGroup=self.AllCons)

		self.TF5_Exports = Constraint(self.REGION, self.PRODUCT, self.YEAR, rule=self.TF5_Exports_rule,
									  ConsName="TF5_Exports", ConsGroup=self.AllCons)

		#########       	Capital Costs 		     	#############
		self.CC1_UndiscountedCapitalInvestment = Constraint(self.LOCATION, self.TECHNOLOGY, self.YEAR,
															rule=self.CC1_UndiscountedCapitalInvestment_rule,
															ConsName="CC1_UndiscountedCapitalInvestment",
															ConsGroup=self.AllCons)

		self.CC2_DiscountedCapitalInvestment_1_constraint = Constraint(self.LOCATION, self.TECHNOLOGY, self.YEAR,
																	   rule=self.CC2_DiscountedCapitalInvestment_1_rule,
																	   ConsName="CC2_DiscountedCapitalInvestment_1_constraint",
																	   ConsGroup=self.AllCons)

		self.CC3_DiscountedCapitalInvestment_2_constraint = Constraint(self.REGION, self.TECHNOLOGY, self.YEAR,
																	   rule=self.CC3_DiscountedCapitalInvestment_2_rule,
																	   ConsName="CC3_DiscountedCapitalInvestment_2_constraint",
																	   ConsGroup=self.AllCons)

		#########           Salvage Value            	#############
		self.SV1_SalvageValueAtEndOfPeriod = Constraint(self.REGION, self.TECHNOLOGY, self.YEAR,
														rule=self.SV1_SalvageValueAtEndOfPeriod_rule,
														ConsName="SV1_SalvageValueAtEndOfPeriod",
														ConsGroup=self.AllCons)

		self.SV2_SalvageValueDiscountedToStartYear = Constraint(self.REGION, self.TECHNOLOGY, self.YEAR,
																rule=self.SV2_SalvageValueDiscountedToStartYear_rule,
																ConsName="SV2_SalvageValueDiscountedToStartYear",
																ConsGroup=self.AllCons)

		#########        	Operating Costs 		 	#############
		self.OC1_OperatingCostsVariable = Constraint(self.LOCATION, self.TECHNOLOGY, self.YEAR,
													 rule=self.OC1_OperatingCostsVariable_rule,
													 ConsName="OC1_OperatingCostsVariable", ConsGroup=self.AllCons)

		self.OC2_OperatingCostsFixedAnnual = Constraint(self.LOCATION, self.TECHNOLOGY, self.YEAR,
														rule=self.OC2_OperatingCostsFixedAnnual_rule,
														ConsName="OC2_OperatingCostsFixedAnnual",
														ConsGroup=self.AllCons)

		self.OC3_OperatingCostsTotalAnnual = Constraint(self.LOCATION, self.TECHNOLOGY, self.YEAR,
														rule=self.OC3_OperatingCostsTotalAnnual_rule,
														ConsName="OC3_OperatingCostsTotalAnnual",
														ConsGroup=self.AllCons)

		self.OC4_DiscountedOperatingCostsTotalAnnual_1 = Constraint(self.LOCATION, self.TECHNOLOGY, self.YEAR,
																	rule=self.OC4_DiscountedOperatingCostsTotalAnnual_1_rule,
																	ConsName="OC4_DiscountedOperatingCostsTotalAnnual_1",
																	ConsGroup=self.AllCons)

		self.OC5_DiscountedOperatingCostsTotalAnnual_2 = Constraint(self.REGION, self.TECHNOLOGY, self.YEAR,
																	rule=self.OC5_DiscountedOperatingCostsTotalAnnual_2_rule,
																	ConsName="OC5_DiscountedOperatingCostsTotalAnnual_2",
																	ConsGroup=self.AllCons)

		#########        	Transport Costs 		 	#############

		self.TC1_LocalTransportCosts = Constraint(self.LOCATION, self.PRODUCT, self.YEAR,
												  rule=self.TC1_LocalTransportCosts_rule,
												  ConsName="TC1_LocalTransportCosts", ConsGroup=self.AllCons)

		self.TC2_DiscountedLocalTransportCosts = Constraint(self.LOCATION, self.PRODUCT, self.YEAR,
															rule=self.TC2_DiscountedLocalTransportCosts_rule,
															ConsName="TC2_DiscountedLocalTransportCosts",
															ConsGroup=self.AllCons)

		self.TC3_DiscountedTransportCostsByProduct = Constraint(self.REGION, self.PRODUCT, self.YEAR,
																rule=self.TC3_DiscountedTransportCostsByProduct_rule,
																ConsName="TC3_DiscountedTransportCostsByProduct",
																ConsGroup=self.AllCons)

		self.TC4_DiscountedTransportCostsTotalAnnual = Constraint(self.REGION, self.YEAR,
																  rule=self.TC4_DiscountedTransportCostsTotalAnnual_rule,
																  ConsName="TC4_DiscountedTransportCostsTotalAnnual",
																  ConsGroup=self.AllCons)

		#########       	Total Discounted Costs	 	#############

		self.TDC1_TotalDiscountedCostByTechnology = Constraint(self.REGION, self.TECHNOLOGY, self.YEAR,
															   rule=self.TDC1_TotalDiscountedCostByTechnology_rule,
															   ConsName="TDC1_TotalDiscountedCostByTechnology",
															   ConsGroup=self.AllCons)

		self.TDC2_ModelPeriodCostByRegion = Constraint(self.REGION, rule=self.TDC2_ModelPeriodCostByRegion_rule,
													   ConsName="TDC2_ModelPeriodCostByRegion", ConsGroup=self.AllCons)

		#        self.TDC3_ModelPeriodCost = Constraint(rule=self.TDC3_ModelPeriodCost_rule, ConsName="TDC3_ModelPeriodCost",
		#                                               ConsGroup=self.AllCons)

		#########      		Total Capacity Constraints 	##############
		self.TCC1_TotalAnnualMaxCapacityConstraint = Constraint(self.REGION, self.TECHNOLOGY, self.YEAR,
																rule=self.TCC1_TotalAnnualMaxCapacityConstraint_rule,
																ConsName="TCC1_TotalAnnualMaxCapacityConstraint",
																ConsGroup=self.AllCons)

		self.TCC2_TotalAnnualMinCapacityConstraint = Constraint(self.REGION, self.TECHNOLOGY, self.YEAR,
																rule=self.TCC2_TotalAnnualMinCapacityConstraint_rule,
																ConsName="TCC2_TotalAnnualMinCapacityConstraint",
																ConsGroup=self.AllCons)

		#########    		New Capacity Constraints  	##############
		self.NCC1_LocalTotalAnnualMaxNewCapacityConstraint = Constraint(self.LOCATION, self.TECHNOLOGY, self.YEAR,
																		rule=self.NCC1_LocalTotalAnnualMaxNewCapacityConstraint_rule,
																		ConsName="NCC1_LocalTotalAnnualMaxNewCapacityConstraint",
																		ConsGroup=self.AllCons)

		self.NCC2_LocalTotalAnnualMinNewCapacityConstraint = Constraint(self.LOCATION, self.TECHNOLOGY, self.YEAR,
																		rule=self.NCC2_LocalTotalAnnualMinNewCapacityConstraint_rule,
																		ConsName="NCC2_LocalTotalAnnualMinNewCapacityConstraint",
																		ConsGroup=self.AllCons)

		#########   		Annual Activity Constraints	##############

		self.AAC0_LocalAnnualTechnologyActivity = Constraint(self.LOCATION, self.TECHNOLOGY, self.YEAR,
															 rule=self.AAC0_LocalAnnualTechnologyActivity_rule,
															 ConsName="AAC0_LocalAnnualTechnologyActivity",
															 ConsGroup=self.AllCons)

		self.AAC1_TotalAnnualTechnologyActivity = Constraint(self.REGION, self.TECHNOLOGY, self.YEAR,
															 rule=self.AAC1_TotalAnnualTechnologyActivity_rule,
															 ConsName="AAC1_TotalAnnualTechnologyActivity",
															 ConsGroup=self.AllCons)

		self.AAC2_TotalAnnualTechnologyActivityUpperlimit = Constraint(self.REGION, self.TECHNOLOGY, self.YEAR,
																	   rule=self.AAC2_TotalAnnualTechnologyActivityUpperLimit_rule,
																	   ConsName="AAC2_TotalAnnualTechnologyActivityUpperlimit",
																	   ConsGroup=self.AllCons)

		self.AAC3_TotalAnnualTechnologyActivityLowerlimit = Constraint(self.REGION, self.TECHNOLOGY, self.YEAR,
																	   rule=self.AAC3_TotalAnnualTechnologyActivityLowerLimit_rule,
																	   ConsName="AAC3_TotalAnnualTechnologyActivityLowerlimit",
																	   ConsGroup=self.AllCons)

		# self.AAC4_TotalAnnualTechnologyProductionLowerlimit = Constraint(self.REGION, self.TECHNOLOGY, self.PRODUCT, self.YEAR, rule=self.AAC4_TotalAnnualTechnologyProductionLowerLimit_rule,
		# ConsName="AAC4_TotalAnnualTechnologyProductionLowerlimit",ConsGroup=self.AllCons)

		#########    		Total Activity Constraints 	##############
		self.TAC1_TotalModelHorizonTechnologyActivity = Constraint(self.REGION, self.TECHNOLOGY,
																   rule=self.TAC1_TotalModelHorizonTechnologyActivity_rule,
																   ConsName="TAC1_TotalModelHorizonTechnologyActivity",
																   ConsGroup=self.AllCons)

		self.TAC2_TotalModelHorizonTechnologyActivityUpperLimit = Constraint(self.REGION, self.TECHNOLOGY,
																			 rule=self.TAC2_TotalModelHorizonTechnologyActivityUpperLimit_rule,
																			 ConsName="TAC2_TotalModelHorizonTechnologyActivityUpperLimit",
																			 ConsGroup=self.AllCons)

		self.TAC3_TotalModelHorizonTechnologyActivityLowerLimit = Constraint(self.REGION, self.TECHNOLOGY,
																			 rule=self.TAC3_TotalModelHorizonTechnologyActivityLowerLimit_rule,
																			 ConsName="TAC3_TotalModelHorizonTechnologyActivityLowerLimit",
																			 ConsGroup=self.AllCons)

		#########   		Emissions Accounting		##############

		self.E1_LocalEmissionProductionByMode = Constraint(self.LOCATION, self.TECHNOLOGY, self.EMISSION,
														   self.MODE_OF_OPERATION, self.YEAR,
														   rule=self.E1_LocalEmissionProductionByMode_rule,
														   ConsName="E1_LocalEmissionProductionByMode",
														   ConsGroup=self.AllCons)

		self.E2_LocalEmissionProduction = Constraint(self.LOCATION, self.TECHNOLOGY, self.EMISSION, self.YEAR,
													 rule=self.E2_LocalEmissionProduction_rule,
													 ConsName="E2_LocalEmissionProduction", ConsGroup=self.AllCons)

		self.E3_AnnualEmissionProduction = Constraint(self.REGION, self.TECHNOLOGY, self.EMISSION, self.YEAR,
													  rule=self.E3_AnnualEmissionProduction_rule,
													  ConsName="E3_AnnualEmissionProduction", ConsGroup=self.AllCons)

		self.E4_EmissionPenaltyByTechAndEmission = Constraint(self.REGION, self.TECHNOLOGY, self.EMISSION, self.YEAR,
															  rule=self.E4_EmissionPenaltyByTechAndEmission_rule,
															  ConsName="E4_EmissionPenaltyByTechAndEmission",
															  ConsGroup=self.AllCons)

		self.E5_EmissionsPenaltyByTechnology = Constraint(self.REGION, self.TECHNOLOGY, self.YEAR,
														  rule=self.E5_EmissionsPenaltyByTechnology_rule,
														  ConsName="E5_EmissionsPenaltyByTechnology",
														  ConsGroup=self.AllCons)

		self.E6_DiscountedEmissionsPenaltyByTechnology = Constraint(self.REGION, self.TECHNOLOGY, self.YEAR,
																	rule=self.E6_DiscountedEmissionsPenaltyByTechnology_rule,
																	ConsName="E6_DiscountedEmissionsPenaltyByTechnology",
																	ConsGroup=self.AllCons)

		self.E7_EmissionsAccounting1 = Constraint(self.REGION, self.EMISSION, self.YEAR,
												  rule=self.E7_EmissionsAccounting1_rule,
												  ConsName="E7_EmissionsAccounting1", ConsGroup=self.AllCons)

		self.E8_EmissionsAccounting2 = Constraint(self.REGION, self.EMISSION, rule=self.E8_EmissionsAccounting2_rule,
												  ConsName="E8_EmissionsAccounting2", ConsGroup=self.AllCons)

		self.E9_AnnualEmissionsLimit = Constraint(self.REGION, self.EMISSION, self.YEAR,
												  rule=self.E9_AnnualEmissionsLimit_rule,
												  ConsName="E9_AnnualEmissionsLimit", ConsGroup=self.AllCons)

		self.E10_ModelPeriodEmissionsLimit = Constraint(self.REGION, self.EMISSION,
														rule=self.E10_ModelPeriodEmissionsLimit_rule,
														ConsName="E10_ModelPeriodEmissionsLimit",
														ConsGroup=self.AllCons)

	###########
	# METHODS #
	###########

	#################
	#   LP PROBLEM  #
	#################

	#	write_parameters(self.TechnologyToFromStorage, output_path=self.OutputPath)

	def build_lp(self):
		'''
		Build the components of the LP problem and stitch them together in one LP file.
		Note: using x-names for variables (not human-readable but saves space).
		Write info about all variables (x-names, human-readable names, index etc.)
		'''
		write_objective(self.OBJ, self.OutputPath)
		write_constraints(self.AllCons, self.AllVars, shadow=self.config['solver']['shadow_prices'])
		write_bounds(self.AllVars)
		write_lp(self.OutputPath, keep_files=True)

		write_variables_overview(self.AllVars)
		write_variables(self.AllVars)
		write_constraints_overview(self.AllCons)

	def build_lp_likepyomo(self):
		"""
		Build the components of the LP problem and stitch them together in one LP file.
		Note: using human-readable variable names using the pyomo format (hence "likepyomo").
		"""
		write_constraints(self.AllCons, self.AllVars)
		write_variables_overview(self.AllVars)
		write_variables(self.AllVars)

		write_objective_likepyomo(self.OBJ, self.OutputPath)
		write_constraints_likepyomo(self.AllCons, self.AllVars)
		write_bounds_likepyomo(self.AllVars)
		write_lp_likepyomo(self.OutputPath, keep_files=True)

	######################
	# Objective Function #
	######################

	def ObjectiveFunction_rule(self):
		"""
		*Objective:* minimize total costs (capital, variable, fixed),
		aggregated for all regions, cumulated over the modelling period.


		sum(ModelPeriodCostByRegion(r) for r in REGION)
		"""

		obj = [(1, [self.ModelPeriodCostByRegion.get_index_label(r) for r in self.REGION.data.VALUE])]
		return obj

	###############
	# Constraints #
	###############
	#########       	Capacity Adequacy	     	#############

	def CA0_NewCapacity_rule(self, r, t, y):
		"""
		*Constraint:* the new capacity available at each location is
		aggregated for each region. Note: this variable is only needed to
		calculate SalvageValue, which we only define at the regional level.

		NewCapacity == sum(LocalNewCapacity(l, t, y) * Geography(r, l) for l in RelevantLocation)
		"""

		if self.HubTechnology.get_value(t) == 1:
			RelevantLocation = [l for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l) == 1]
		elif self.HubTechnology.get_value(t) == 0:
			RelevantLocation = [l for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l) == 0]

		lhs = [(1, self.NewCapacity.get_index_label(r, t, y)),
			   (-1, [self.LocalNewCapacity.get_index_label(l, t, y) for l in RelevantLocation
					 if self.Geography.get_value(r, l) == 1])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def CA1_TotalNewCapacity_1_rule(self, l, t, y):
		"""
		*Constraint:* the accumulation of all new capacities of all technologies
		invested during the model period is calculated for each year.
		This is done first for each location.

		LocalAccumulatedNewCapacity.(l, t, y)  == sum(LocalNewCapacity(l, t, yy)  for yy in YEAR
												if ((y - yy < sum(OperationalLife(r, t) * Geography(r, l)
												for r in REGION)) and (y - yy >= 0)))
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or \
				((self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
			lhs = [(1, self.LocalAccumulatedNewCapacity.get_index_label(l, t, y)),
				   (-1,
					[self.LocalNewCapacity.get_index_label(l, t, yy) for yy in self.YEAR.data.VALUE if ((y - yy < sum(
						self.OperationalLife.get_value(r, t) * self.Geography.get_value(r, l) for r in
						self.REGION.data.VALUE)) and (y - yy >= 0))])]
			rhs = 0
			sense = '=='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	def CA2_TotalNewCapacity_2_rule(self, r, t, y):
		"""
		*Constraint:* the accumulated new capacity available at each location is
		aggregated for each region.

		AccumulatedNewCapacity(r, t, y) == sum(LocalAccumulatedNewCapacity(l, t, y) * Geography(r, l) for l in RelevantLocation)
		"""

		if self.HubTechnology.get_value(t) == 1:
			RelevantLocation = [l for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l) == 1]
		elif self.HubTechnology.get_value(t) == 0:
			RelevantLocation = [l for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l) == 0]
		lhs = [(1, self.AccumulatedNewCapacity.get_index_label(r, t, y)),
			   (-1, [self.LocalAccumulatedNewCapacity.get_index_label(l, t, y) for l in RelevantLocation
					 if self.Geography.get_value(r, l) == 1])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def CA3_TotalAnnualCapacity_1_rule(self, l, t, y):
		"""
		*Constraint:* add to CA1 any residual capacity of the same technology inherited
		from before the model period. From the addition of the accumulated new
		capacity and residual capacity in each year of the modeling period,
		the total annual capacity for each technology is determined. This is done
		for each location in the modeling period.

		LocalAccumulatedNewCapacity(l, t, y)  + LocalResidualCapacity(l, t, y) == LocalTotalCapacity(l, t, y)
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
				(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
			lhs = [(1, self.LocalAccumulatedNewCapacity.get_index_label(l, t, y)),
				   (-1, self.LocalTotalCapacity.get_index_label(l, t, y))]
			rhs = -1 * self.LocalResidualCapacity.get_value(l, t, y)
			sense = '=='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	def CA4_TotalAnnualCapacity_2_rule(self, r, t, y):
		"""
		*Constraint:* the total capacity available at each location is
		aggregated for each region.

		TotalCapacity(r, t, y) == sum(
			LocalTotalCapacity(l, t, y) * Geography(r, l) for l in RelevantLocation)
		"""

		if self.HubTechnology.get_value(t) == 1:
			RelevantLocation = [l for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l) == 1]
		elif self.HubTechnology.get_value(t) == 0:
			RelevantLocation = [l for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l) == 0]
		lhs = [(1, self.TotalCapacity.get_index_label(r, t, y)),
			   (-1, [self.LocalTotalCapacity.get_index_label(l, t, y) for l in RelevantLocation
					 if self.Geography.get_value(r, l) == 1])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def CA5_ConstraintCapacity_rule(self, l, t, y):
		"""
		*Constraint:* ensure that all technologies have enough capacity
		available to satisfy an overall yearly demand. Their annual
		production (rate of activity during any year) has to be less than
		their total available capacity multiplied by the fraction of the year
		for which the technology is available.

		LocalActivity(l, t, y) <= LocalTotalCapacity(l, t, y) * sum(
				AvailabilityFactor(r, t, y) * CapacityToActivityUnit(r, t) *
				Geography.(r, l) for r in REGION)
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
				(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
			lhs = [(1, self.LocalActivity.get_index_label(l, t, y)),
				   (-1 * sum(self.AvailabilityFactor.get_value(r, t, y) * self.CapacityToActivityUnit.get_value(r, t) *
							 self.Geography.get_value(r, l) for r in self.REGION.data.VALUE),
					self.LocalTotalCapacity.get_index_label(l, t, y))]
			rhs = 0
			sense = '<='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	#########	        Product Balance    	 	#############

	def PB1_Production_1_rule(self, l, p, t, m, y):
		"""
		*Constraint:* the production or output (of a `product`) for each technology,
		in each mode of operation is determined by multiplying the (rate of) activity
		to a product output vs. production activity ratio entered by the analyst.

		LocalProductionByMode.(l, t, p, m, y) == \
					LocalActivityByMode(l, t, m, y) * sum(
					OutputActivityRatio(r, t, p, m, y) * Geography(r, l) for r in
					REGION)
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
				(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
			if self.ModeForTechnology.get_value(t, m) == 1 and self.ProductFromTechnology.get_value(t, p) == 1:
				lhs = [(1, self.LocalProductionByMode.get_index_label(l, t, p, m, y)),
					   (-1 * sum(self.OutputActivityRatio.get_value(r, t, p, m, y) *
								 self.Geography.get_value(r, l) for r in self.REGION.data.VALUE),
						self.LocalActivityByMode.get_index_label(l, t, m, y))]
				rhs = 0
				sense = '=='
				return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
			else:
				return None
		else:
			return None

	def PB2_Production_2_rule(self, l, p, t, y):
		"""
		*Constraint:* the production or output (of a `product`) for each technology
		is the sum of production in each operation mode.

		LocalProductionByTechnology.(l, t, p, y)== sum(
					LocalProductionByMode(l, t, p, m, y) for m in ModeOfOperation)
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
				(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
			ModeOfOperation = [m for m in self.MODE_OF_OPERATION.data.VALUE if
							   self.ModeForTechnology.get_value(t, m) == 1]
			if self.ProductFromTechnology.get_value(t, p) == 1:
				lhs = [(1, self.LocalProductionByTechnology.get_index_label(l, t, p, y)),
					   (-1, [self.LocalProductionByMode.get_index_label(l, t, p, m, y) for m in ModeOfOperation])]
				rhs = 0
				sense = '=='
				return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
			else:
				return None
		else:
			return None

	def PB3_Production_3_rule(self, l, p, y):
		'''
		*Constraint:* for each product, year and location, the production by each
		technology is added to determine the total local production of
		each product.

		LocalProduction(l, p, y) == sum(
			LocalProductionByTechnology(l, t, p, y) for t in RelevantTechnology)
		'''

		if self.HubLocation.get_value(l) == 1:
			RelevantTechnology = [t for t in self.TECHNOLOGY.data.VALUE if self.HubTechnology.get_value(t) == 1]
		elif self.HubLocation.get_value(l) == 0:
			RelevantTechnology = [t for t in self.TECHNOLOGY.data.VALUE if self.HubTechnology.get_value(t) == 0]
		RelevantTechnology = [t for t in RelevantTechnology if self.ProductFromTechnology.get_value(t, p) == 1]
		lhs = [(1, self.LocalProduction.get_index_label(l, p, y)),
			   (-1, [self.LocalProductionByTechnology.get_index_label(l, t, p, y) for t in RelevantTechnology])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def PB4_Production_4_rule(self, r, p, y):
		"""
		*Constraint:* for each product, year and region, the production by each
		location is added to determine the total regional production of
		each product.

		 Production(r, p, y) == sum(
			LocalProduction(l, p, y) * Geography(r, l) for l in LOCATION)
		"""

		lhs = [(1, self.Production.get_index_label(r, p, y)),
			   ([-1 * self.Geography.get_value(r, l) for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l)==0],
				[self.LocalProduction.get_index_label(l, p, y) for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l)==0])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	#    def PB5_Production_5_rule(self,r,t,p,y):
	#        '''
	#        *Constraint:* for each technology, product, year and region, the production by each
	#        location is added to determine the total regional production of
	#        each product by technology.
	#        '''
	#        return self.ProductionByTechnology[r,t,p,y] == sum(self.LocalProductionByTechnology[l,t,p,y] * self.Geography[r,l] for l in self.LOCATION.data.VALUE)

	def PB5_Use_1_rule(self, l, p, t, m, y):
		"""
		*Constraint:* the use or input (of a `product`) for each technology, in
		each mode of operation is determined by multiplying the (rate of) activity
		to a product input vs. production activity ratio entered by the analyst.

		LocalUseByMode(l, t, p, m, y) == LocalActivityByMode(l, t, m, y) * sum(
					InputActivityRatio(r, t, p, m, y) * Geography(r, l) for r in REGION)
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
				(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
			if self.ModeForTechnology.get_value(t, m) == 1 and self.ProductToTechnology.get_value(t, p) == 1:
				lhs = [(1, self.LocalUseByMode.get_index_label(l, t, p, m, y)),
					   (-1 * sum(
						   self.InputActivityRatio.get_value(r, t, p, m, y) * self.Geography.get_value(r, l) for r in
						   self.REGION.data.VALUE), self.LocalActivityByMode.get_index_label(l, t, m, y))]
				rhs = 0
				sense = '=='
				return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
			else:
				return None
		else:
			return None

	def PB6_Use_2_rule(self, l, p, t, y):
		"""
		*Constraint:* the use or input (of a `product`) for each technology
		is the sum of use in each operation mode.

		LocalUseByTechnology(l, t, p, y) == sum(
					LocalUseByMode(l, t, p, m, y) for m in ModeOfOperation)
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
				(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
			ModeOfOperation = [m for m in self.MODE_OF_OPERATION.data.VALUE if
							   self.ModeForTechnology.get_value(t, m) == 1]
			if self.ProductToTechnology.get_value(t, p) == 1:
				lhs = [(1, self.LocalUseByTechnology.get_index_label(l, t, p, y)),
					   (-1, [self.LocalUseByMode.get_index_label(l, t, p, m, y) for m in ModeOfOperation])]
				rhs = 0
				sense = '=='
				return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
			else:
				return None
		else:
			return None

	def PB7_Use_3_rule(self, l, p, y):
		"""
		*Constraint:* for each product, year and location, the use by each
		technology is added to determine the total local use of each product.

		LocalUse(l, p, y) == sum(LocalUseByTechnology(l, t, p, y) for t in RelevantTechnology)
		"""

		if self.HubLocation.get_value(l) == 1:
			RelevantTechnology = [t for t in self.TECHNOLOGY.data.VALUE if self.HubTechnology.get_value(t) == 1]
		elif self.HubLocation.get_value(l) == 0:
			RelevantTechnology = [t for t in self.TECHNOLOGY.data.VALUE if self.HubTechnology.get_value(t) == 0]
		RelevantTechnology = [t for t in RelevantTechnology if self.ProductToTechnology.get_value(t, p) == 1]

		lhs = [(1, self.LocalUse.get_index_label(l, p, y)),
			   (-1, [self.LocalUseByTechnology.get_index_label(l, t, p, y) for t in RelevantTechnology])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def PB8_Use_4_rule(self, r, p, y):
		"""
		*Constraint:* for each product, year and region, the use by each
		location is added to determine the total regional use of each product.

		Use(r, p, y) == sum(LocalUse(l, p, y) * Geography(r, l) for l in LOCATION)
		"""

		lhs = [(1, self.Use.get_index_label(r, p, y)),
			   ([-1 * self.Geography.get_value(r, l) for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l)==0],
				[self.LocalUse.get_index_label(l, p, y) for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l)==0])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def PB9_ProductBalance_rule(self, r, p, y):
		"""
		*Constraint:* for each product, in each year, and region the total production
		of each product + imports from locations outside the region - exports to
		locations outside the region should be larger than or equal to demand.

		Production(r, p, y) + Import(r, p, y) - Export(r, p, y) >= Demand(r, p, y)
		"""

		lhs = [(1, self.Production.get_index_label(r, p, y)),
			   (1, self.Import.get_index_label(r, p, y)),
			   (-1, self.Export.get_index_label(r, p, y))]
		rhs = self.Demand.get_value(r, p, y)
		sense = '>='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	#########        	Transport flows		 	#############

	def TF1a_Transport_1a_rule(self, l, ll, p, tr, y):
		"""
		*Constraint:* for each product, each non-multi-purpose transport mode, in each year,
		transport from location l to location ll is either smaller or equal to the transport
		link capacity if a transport route exists, or 0 if there is no route.
		For bi-directional transport routes, the sum of transport in both directions should
		be smaller or equal to the transport link capacity.

		Transport(l, ll, p, tr, y) <= TransportCapacity(l, ll, p, tr, y) * TransportCapacityToActivity(tr)

		Transport(l, ll, p, tr, y) + Transport(ll, l, p, tr, y) <= TransportCapacity(l, ll, p, tr, y) * TransportCapacityToActivity(tr)
		"""
		if self.TransportCapacity.get_value(l,ll,p,tr,y) != self.HighMaxDefault:
			if self.TransportRoute.get_value(l, ll, p, tr, y) == 1 and self.TransportRoute.get_value(ll, l, p, tr,
																									y) == 0 and \
					self.MultiPurposeTransport.get_value(tr) == 0:
				lhs = [(1, self.Transport.get_index_label(l, ll, p, tr, y))]
				rhs = self.TransportCapacity.get_value(l, ll, p, tr, y) * self.TransportCapacityToActivity.get_value(tr)
				sense = '<='
				return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

			elif self.TransportRoute.get_value(l, ll, p, tr, y) == 0 and self.TransportRoute.get_value(ll, l, p, tr,
																									y) == 1 and \
					self.MultiPurposeTransport.get_value(tr) == 0:
				return None
			elif self.TransportRoute.get_value(l, ll, p, tr, y) == 1 and self.TransportRoute.get_value(ll, l, p, tr,
																									y) == 1 and \
					self.MultiPurposeTransport.get_value(tr) == 0 and l != ll:
				lhs = [(1, self.Transport.get_index_label(l, ll, p, tr, y)),
					(1, self.Transport.get_index_label(ll, l, p, tr, y))]
				rhs = self.TransportCapacity.get_value(l, ll, p, tr, y) * self.TransportCapacityToActivity.get_value(tr)
				sense = '<='
				return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
			elif self.TransportRoute.get_value(l, ll, p, tr, y) == 1 and self.TransportRoute.get_value(ll, l, p, tr,
																									y) == 1 and \
					self.MultiPurposeTransport.get_value(tr) == 0 and l == ll:
				lhs = [(2, self.Transport.get_index_label(l, ll, p, tr, y))]
				rhs = self.TransportCapacity.get_value(l, ll, p, tr, y) * self.TransportCapacityToActivity.get_value(tr)
				sense = '<='
				return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
			else:
				return None
		else:
			return None

	def TF1b_Transport_1b_rule(self, l, ll, tr, y):
		"""
		*Constraint:* for each multi-purpose transport mode, in each year,
		transport of the sum of relevant purposes from location l to location ll
		is either smaller or equal to the transport link capacity if a transport
		route exists, or 0 if there is no route. Note: in the input parameter
		TransportCapacity, the same total max capacity is given for each relevant product.
		For bi-directional transport routes, the sum of transport in both directions should
		be smaller or equal to the transport link capacity.

		(sum(Transport(l, ll, p, tr, y) for p in RELEVANT_PRODUCT_to_ll)
							<= 1 / len(RELEVANT_PRODUCT_to_ll)
							* sum(TransportCapacity(l, ll, p, tr, y) for p in RELEVANT_PRODUCT_to_ll)
							* TransportCapacityToActivity(tr))

		(sum(Transport(l, ll, p, tr, y) for p in RELEVANT_PRODUCT_to_ll)
							+ sum(Transport(ll, l, p, tr, y) for p in RELEVANT_PRODUCT_from_ll)
							<= 1 / len(RELEVANT_PRODUCT_to_ll)
							* sum(TransportCapacity(l, ll, p, tr, y) for p in RELEVANT_PRODUCT_to_ll)
							* TransportCapacityToActivity(tr))
		"""

		if self.MultiPurposeTransport.get_value(tr) == 1:
			RELEVANT_PRODUCT_to_ll = [p for p in self.PRODUCT.data.VALUE if
									  self.TransportRoute.get_value(l, ll, p, tr, y) == 1]
			RELEVANT_PRODUCT_from_ll = [p for p in self.PRODUCT.data.VALUE if
										self.TransportRoute.get_value(ll, l, p, tr, y) == 1]
			if RELEVANT_PRODUCT_to_ll == [] and RELEVANT_PRODUCT_from_ll == []:
				return None
			else:

				if RELEVANT_PRODUCT_to_ll != [] and RELEVANT_PRODUCT_from_ll == []:
					lhs = [(1, [self.Transport.get_index_label(l, ll, p, tr, y) for p in RELEVANT_PRODUCT_to_ll])]
					rhs = 1 / len(RELEVANT_PRODUCT_to_ll) * sum(self.TransportCapacity.get_value(l, ll, p, tr, y)
																for p in
																RELEVANT_PRODUCT_to_ll) * self.TransportCapacityToActivity.get_value(
						tr)
					sense = '<='
					return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

				elif RELEVANT_PRODUCT_to_ll == [] and RELEVANT_PRODUCT_from_ll != []:
					return None
				elif RELEVANT_PRODUCT_to_ll != [] and RELEVANT_PRODUCT_from_ll != []:
					lhs = [(1, [self.Transport.get_index_label(l, ll, p, tr, y) for p in RELEVANT_PRODUCT_to_ll]),
						   (1, [self.Transport.get_index_label(ll, l, p, tr, y) for p in RELEVANT_PRODUCT_from_ll])]
					rhs = 1 / len(RELEVANT_PRODUCT_to_ll) * sum(self.TransportCapacity.get_value(l, ll, p, tr, y)
																for p in RELEVANT_PRODUCT_to_ll) * \
						  self.TransportCapacityToActivity.get_value(tr)
					sense = '<='
					return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

		else:
			return None

	def TF2_Transport_2_rule(self, l, p, y):
		"""
		*Constraint:* for each product, at each (origin) location, in each year, the total
		quantity of product transported to other locations is equal to the
		production at the (origin) location. If there is no transport link at all
		departing from the (origin) location, the constraint is skipped.

		sum(sum(Transport(l, ll, p, tr, y) for tr in [trm for trm in TRANSPORTMODE if
							TransportRoute(l, ll, p, trm, y) == 1]) for ll in LOCATION) <= LocalProduction(l, p, y)

		sum(sum(Transport(l, ll, p, tr, y) for tr in [trm for trm in TRANSPORTMODE if
							TransportRoute(l, ll, p, trm, y) == 1]) for ll in LOCATION) == LocalProduction(l, p, y)
		"""

		if self.HubLocation.get_value(l) == 0:
			self.TransportRoute.get_value(l, 'DELTA_DEMAND', p, 'ONSITE', y)
			lhs = [(1, [self.Transport.get_index_label(l, ll, p, tr, y) for ll in self.LOCATION.data.VALUE
						for tr in [trm for trm in self.TRANSPORTMODE.data.VALUE if
								   self.TransportRoute.get_value(l, ll, p, trm, y) == 1]]),
				   (-1, self.LocalProduction.get_index_label(l, p, y))]
			rhs = 0
			sense = '<='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			lhs = [(1, [self.Transport.get_index_label(l, ll, p, tr, y) for ll in self.LOCATION.data.VALUE
						for tr in [trm for trm in self.TRANSPORTMODE.data.VALUE if
								   self.TransportRoute.get_value(l, ll, p, trm, y) == 1]]),
				   (-1, self.LocalProduction.get_index_label(l, p, y))]
			rhs = 0
			sense = '=='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def TF3_Transport_3_rule(self, l, p, y):
		"""
		*Constraint:* for each product, at each (destination) location, in each year, the total
		quantity of product transported from other locations equal to the use
		at the (destination) location. If there is no transport link at all
		arriving to the (destination) location, the constraint is skipped.

		sum(sum(Transport(ll, l, p, tr, y) for tr in [trm for trm in TRANSPORTMODE if
			TransportRoute(ll, l, p, trm, y) == 1]) for ll in LOCATION) == LocalUse(l, p, y)
		"""

		lhs = [(1, [self.Transport.get_index_label(ll, l, p, tr, y)
					for ll in self.LOCATION.data.VALUE
					for tr in [trm for trm in self.TRANSPORTMODE.data.VALUE
							   if self.TransportRoute.get_value(ll, l, p, trm, y) == 1]]),
			   (-1, self.LocalUse.get_index_label(l, p, y))]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def TF4_Imports_rule(self, r, p, y):
		"""
		*Constraint:* for each product and region, the imports to that region
		are the sum of the transport flows from locations outside that region
		to locations in that region.

		Import(r, p, y) == sum(sum(sum(Transport(ll, l, p, tr, y) * (1 - Geography(r, ll)) for tr in
			[trm for trm in TRANSPORTMODE if TransportRoute(ll, l, p, trm, y) == 1]) for ll in
													 LOCATION) * Geography(r, l) for l in LOCATION)
		"""

		lhs = [(1, self.Import.get_index_label(r, p, y)),

			   (-1,
				[self.Transport.get_index_label(ll, l, p, tr, y)
				 for ll in [loc for loc in self.LOCATION.data.VALUE if self.Geography.get_value(r, loc) == 0]
				 for l in [loc for loc in self.LOCATION.data.VALUE if self.Geography.get_value(r, loc) == 1]
				 for tr in
				 [trm for trm in self.TRANSPORTMODE.data.VALUE if
				  self.TransportRoute.get_value(ll, l, p, trm, y) == 1]])]

		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def TF5_Exports_rule(self, r, p, y):
		"""
		*Constraint:* for each product and region, the imports to that region
		are the sum of the transport flows from locations outside that region
		to locations in that region.

		Export(r, p, y) == sum(sum(sum(
			Transport(l, ll, p, tr, y) * (1 - Geography(r, ll)) for tr in [trm for trm in TRANSPORTMODE if
			TransportRoute(l, ll, p, trm, y) == 1]) for ll in LOCATION) * Geography(r, l) for l in LOCATION)
		"""

		lhs = [(1, self.Export.get_index_label(r, p, y)),

			   (-1,
				[self.Transport.get_index_label(l, ll, p, tr, y)
				 for l in [loc for loc in self.LOCATION.data.VALUE if self.Geography.get_value(r, loc) == 1]
				 for ll in [loc for loc in self.LOCATION.data.VALUE if self.Geography.get_value(r, loc) == 0]
				 for tr in
				 [trm for trm in self.TRANSPORTMODE.data.VALUE if
				  self.TransportRoute.get_value(l, ll, p, trm, y) == 1]])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	#########       	Capital Costs 		     	#############

	def CC1_UndiscountedCapitalInvestment_rule(self, l, t, y):
		"""
		*Constraint:* investments (how much of what type of technology when)
		are calculated on an annual basis for each location, and are assumed to
		be commissioned and available at the beginning of the year.
		The investment expenditures are determined by the level of new capacity
		invested in multiplied by a per-unit capital cost known to the analyst.

		LocalCapitalInvestment(l, t, y) == sum(
			CapitalCost(r, t, y) * Geography(r, l) for r in REGION) * LocalNewCapacity(l, t, y)
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
				(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):

			lhs = [(1, self.LocalCapitalInvestment.get_index_label(l, t, y)),
				   (-1 * sum(self.CapitalCost.get_value(r, t, y) * self.Geography.get_value(r, l) for r in
							 self.REGION.data.VALUE),
					self.LocalNewCapacity.get_index_label(l, t, y))]
			rhs = 0
			sense = '=='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	def CC2_DiscountedCapitalInvestment_1_rule(self, l, t, y):
		"""
		*Constraint:* investment cost is discounted from the beginning of the
		current time interval back to the first year of the first time interval
		modeled. E.g. for y=2040 and 10 year time steps, investment cost is discounted
		from 2036 back to 2016 (which is the same as from 2040 to 2020).

		LocalDiscountedCapitalInvestment(l, t, y) == LocalCapitalInvestment(l, t, y) / ((1 + sum(
				DiscountRate(r) * Geography(r, l) for r in REGION)) ** (y - min(YEAR)))
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
				(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
			lhs = [(1, self.LocalDiscountedCapitalInvestment.get_index_label(l, t, y)),
				   (-1 / ((1 + sum(self.DiscountRate.get_value(r) * self.Geography.get_value(r, l)
								   for r in self.REGION.data.VALUE)) ** (y - min(self.YEAR.data.VALUE))),
					self.LocalCapitalInvestment.get_index_label(l, t, y))]
			rhs = 0
			sense = '=='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	def CC3_DiscountedCapitalInvestment_2_rule(self, r, t, y):
		"""
		*Constraint:* the investments at each location are added to determine
		the total regional investments in each technology.

		DiscountedCapitalInvestment(r, t, y) == sum(LocalDiscountedCapitalInvestment(l, t, y) *
			Geography(r, l) for l in RelevantLocation)
		"""

		if self.HubTechnology.get_value(t) == 1:
			RelevantLocation = [l for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l) == 1]
		elif self.HubTechnology.get_value(t) == 0:
			RelevantLocation = [l for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l) == 0]

		lhs = [(1, self.DiscountedCapitalInvestment.get_index_label(r, t, y)),
			   (-1, [self.LocalDiscountedCapitalInvestment.get_index_label(l, t, y) for l in RelevantLocation
					 if self.Geography.get_value(r, l) == 1])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	#########           Salvage Value            	#############

	def SV1_SalvageValueAtEndOfPeriod_rule(self, r, t, y):
		"""
		*Constraint:* salvage value is determined regionally, based on
		the technology's operational life, its year of investment and discount rate.

		SalvageValue(r, t, y) == CapitalCost(r, t, y) * NewCapacity(r, t, y) * (1 - (((1 + DiscountRate(r)) ** (
						max(YEAR) + TimeStep(max(YEAR)) / 2 - (
							y - TimeStep(y) / 2 + 1) + 1) - 1) / (
											 (1 + DiscountRate(r)) ** OperationalLife[r, t] - 1)))

		SalvageValue(r, t, y) == CapitalCost(r, t, y) * NewCapacity(r, t, y) * (1 - (max(YEAR) - y + 1) /
															 OperationalLife(r, t))

		SalvageValue(r, t, y) == 0
		"""

		if (self.DepreciationMethod.get_value(r) == 1) and (
				(y + self.TimeStep.get_value(y) / 2 + self.OperationalLife.get_value(r, t) - 1) > (
				max(self.YEAR.data.VALUE) + self.TimeStep.get_value(max(self.YEAR.data.VALUE)) / 2)) and (
				self.DiscountRate.get_value(r) > 0):
			lhs = [(1, self.SalvageValue.get_index_label(r, t, y)),
				   (-1 * self.CapitalCost.get_value(r, t, y) * (1 - (((1 + self.DiscountRate.get_value(r)) ** (
						   max(self.YEAR.data.VALUE) + self.TimeStep.get_value(max(self.YEAR.data.VALUE)) / 2 - (
						   y - self.TimeStep.get_value(y) / 2 + 1) + 1) - 1) / (
																			 (1 + self.DiscountRate.get_value(r)) **
																			 self.OperationalLife.get_value(r,
																											t) - 1))),
					self.NewCapacity.get_index_label(r, t, y))]
			rhs = 0
			sense = '=='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

		elif (self.DepreciationMethod.get_value(r) == 1 and (
				(y + self.TimeStep.get_value(y) / 2 + self.OperationalLife.get_value(r, t) - 1) > (
				max(self.YEAR.data.VALUE) + self.TimeStep.get_value(max(self.YEAR.data.VALUE)) / 2)) and
			  self.DiscountRate.get_value(r) == 0) or (self.DepreciationMethod.get_value(r) == 2 and (
				(y + self.TimeStep.get_value(y) / 2 + self.OperationalLife.get_value(r, t) - 1) > (
				max(self.YEAR.data.VALUE) + self.TimeStep.get_value(max(self.YEAR.data.VALUE)) / 2))):

			lhs = [(1, self.SalvageValue.get_index_label(r, t, y)),
				   (-1 * self.CapitalCost.get_value(r, t, y) * (1 - (max(self.YEAR.data.VALUE) + self.TimeStep.get_value(max(self.YEAR.data.VALUE))/2 - (y - self.TimeStep.get_value(y)/2 +1) + 1) /
																self.OperationalLife.get_value(r, t)),
					self.SalvageValue.get_index_label(r, t, y))]
			rhs = 0
			sense = '=='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			lhs = [(1, self.SalvageValue.get_index_label(r, t, y))]
			rhs = 0
			sense = '=='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def SV2_SalvageValueDiscountedToStartYear_rule(self, r, t, y):
		"""
		*Constraint:* the salvage value is discounted to the beginning of the
		first year of the first time interval by a discount rate applied over
		the modeling period, i.e. from the first year of the first interval
		(min y - step/2 +1) and the last year of the last interval (max y + step/2).

		DiscountedSalvageValue(r, t, y) == SalvageValue(r, t, y) / (
				(1 + DiscountRate(r)) ** (
				1 + max(YEAR) + TimeStep(max(YEAR)) / 2 - (
				min(YEAR) - TimeStep(min(YEAR)) / 2 + 1)))
		"""

		lhs = [(1, self.DiscountedSalvageValue.get_index_label(r, t, y)),
			   (-1 / ((1 + self.DiscountRate.get_value(r)) ** (
					   1 + max(self.YEAR.data.VALUE) + self.TimeStep.get_value(max(self.YEAR.data.VALUE)) / 2 - (
					   min(self.YEAR.data.VALUE) - self.TimeStep.get_value(min(self.YEAR.data.VALUE)) / 2 + 1))),
				self.SalvageValue.get_index_label(r, t, y))]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	#########        	Operating Costs 		 	#############

	def OC1_OperatingCostsVariable_rule(self, l, t, y):
		"""
		*Constraint*: for each location, technology, and year the variable cost
		is a function of the rate of activity of each technology and a per-unit
		cost defined by the analyst.

		LocalVariableOperatingCost(l, t, y) == sum(LocalActivityByMode(l, t, m, y) * sum(
					VariableCost(r, t, m, y) * Geography(r, l) for r in	REGION) for m in ModeOfOperation)
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
				(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
			ModeOfOperation = [m for m in self.MODE_OF_OPERATION.data.VALUE if
							   self.ModeForTechnology.get_value(t, m) == 1]

			lhs = [(1, self.LocalVariableOperatingCost.get_index_label(l, t, y)),
				   ([-1 * sum(self.VariableCost.get_value(r, t, m, y) * self.Geography.get_value(r, l)
							  for r in self.REGION.data.VALUE) for m in ModeOfOperation],
					[self.LocalActivityByMode.get_index_label(l, t, m, y) for m in ModeOfOperation])]
			rhs = 0
			sense = '=='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	def OC2_OperatingCostsFixedAnnual_rule(self, l, t, y):
		"""
		*Constraint*: for each location, technology, and year the annual fixed
		operating cost is calculated by multiplying the total installed capacity
		of a technology with a per-unit cost defined by the analyst.

		LocalFixedOperatingCost(l, t, y) == LocalTotalCapacity(l, t, y) * sum(
				FixedCost(r, t, y) * Geography(r, l) for r in REGION)
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
				(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
			lhs = [(1, self.LocalFixedOperatingCost.get_index_label(l, t, y)),
				   (-1 * sum(self.FixedCost.get_value(r, t, y) * self.Geography.get_value(r, l) for r in
							 self.REGION.data.VALUE),
					self.LocalTotalCapacity.get_index_label(l, t, y))]
			rhs = 0
			sense = '=='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	def OC3_OperatingCostsTotalAnnual_rule(self, l, t, y):
		"""
		*Constraint:* the total annual operating cost is the sum of the fixed
		and variable costs.

		LocalOperatingCost(l, t, y) == LocalFixedOperatingCost(l, t, y) + LocalVariableOperatingCost(l, t, y)
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
				(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
			lhs = [(1, self.LocalOperatingCost.get_index_label(l, t, y)),
				   (-1, self.LocalFixedOperatingCost.get_index_label(l, t, y)),
				   (-1, self.LocalVariableOperatingCost.get_index_label(l, t, y))]
			rhs = 0
			sense = '=='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	def OC4_DiscountedOperatingCostsTotalAnnual_1_rule(self, l, t, y):
		"""
		*Constraint:* total operating cost is discounted back to the first year
		of the first interval modeled. That is done, using either a technology-specific
		or a global discount rate applied to the middle of the interval in which
		the costs are incurred.

		LocalDiscountedOperatingCost(l, t, y) == LocalOperatingCost(l, t, y) / (
							(1 + sum(DiscountRate(r) * Geography(r, l) for r in REGION)) ** (
									1 + y - (min(YEAR) - TimeStep(min(YEAR)) / 2 + 1)))
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
				(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
			lhs = [(1, self.LocalDiscountedOperatingCost.get_index_label(l, t, y)),
				   (-1 / ((1 + sum(self.DiscountRate.get_value(r) * self.Geography.get_value(r, l)
								   for r in self.REGION.data.VALUE)) ** (
								  1 + y - (min(self.YEAR.data.VALUE) - self.TimeStep.get_value(
							  min(self.YEAR.data.VALUE)) / 2 + 1))),
					self.LocalOperatingCost.get_index_label(l, t, y))]
			rhs = 0
			sense = '=='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	def OC5_DiscountedOperatingCostsTotalAnnual_2_rule(self, r, t, y):
		"""
		*Constraint:* total operating cost is discounted back to the first year
		modeled. That is done, using either a technology-specific or a global
		discount rate applied to the middle of the year in which the costs are
		incurred.

		DiscountedOperatingCost(r, t, y) == sum(LocalDiscountedOperatingCost(l, t, y) * Geography(r, l) for l in
			RelevantLocation)
		"""

		if self.HubTechnology.get_value(t) == 1:
			RelevantLocation = [l for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l) == 1]
		elif self.HubTechnology.get_value(t) == 0:
			RelevantLocation = [l for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l) == 0]
		lhs = [(1, self.DiscountedOperatingCost.get_index_label(r, t, y)),
			   (-1, [self.LocalDiscountedOperatingCost.get_index_label(l, t, y) for l in RelevantLocation
					 if self.Geography.get_value(r, l) == 1])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	#########       	Transport Costs	 	#############

	def TC1_LocalTransportCosts_rule(self, l, p, y):
		"""
		*Constraint:* for each product, at each location, in each year, the total
		cost of transporting the produced product FROM other locations (i.e. cost
		of imports) is the sum of the quantities transported per mode of transport
		multiplied by the specific costs of each mode of transport  per region.
        Transport between regions occurs between the TRANSPORT_HUB locations. The transport
        cost is defined for each region pair..

		if HubLocation[l]==0
		LocalTransportCost(l, p, y) == sum(sum(Transport(ll, l, p, tr, y) * sum(
				TransportCostByMode(r, tr, y) * Geography(r, l) for r in REGION) for tr
				in [trm for trm in TRANSPORTMODE if TransportRoute[ll, l, p, trm, y] == 1]) for ll in LOCATION)

		if HubLocation[l]==1
		LocalTransportCost[l,p,y] == (sum(sum(Transport[ll,l,p,tr,y] * sum(
				TransportCostByMode[r,tr,y] * Geography[r,l] for r in REGION) for tr
				in [trm for trm in TRANSPORTMODE if TransportRoute[ll,l,p,trm,y]==1]) for ll in LOCATION)

				+ sum(sum(sum(Transport[ll,l,p,tr,y] * sum(
					TransportCostInterReg[rr,r,tr,y] * Geography[r,l] for r in REGION) * Geography[rr,ll] for rr in REGION)
					for tr in [trm for trm in TRANSPORTMODE if TransportRoute[ll,l,p,trm,y]==1])
					for ll in LOCATION if HubLocation[ll]==1))

		"""
		if self.HubLocation.get_value(l)==0:
			lhs = [(1, self.LocalTransportCost.get_index_label(l, p, y)),

				([-1 * sum(self.TransportCostByMode.get_value(r, tr, y)
							* self.Geography.get_value(r, l) for r in self.REGION.data.VALUE)
					for ll in self.LOCATION.data.VALUE
					for tr in [trm for trm in self.TRANSPORTMODE.data.VALUE
								if self.TransportRoute.get_value(ll, l, p, trm, y) == 1]],

					[self.Transport.get_index_label(ll, l, p, tr, y)
					for ll in self.LOCATION.data.VALUE
					for tr in [trm for trm in self.TRANSPORTMODE.data.VALUE
								if self.TransportRoute.get_value(ll, l, p, trm, y) == 1]])]
			rhs = 0
			sense = '=='
		else: # for HubLocation[l]==1
			lhs = [(1, self.LocalTransportCost.get_index_label(l, p, y)),

				([-1 * sum(self.TransportCostByMode.get_value(r, tr, y)
							* self.Geography.get_value(r, l) for r in self.REGION.data.VALUE)
					for ll in self.LOCATION.data.VALUE
					for tr in [trm for trm in self.TRANSPORTMODE.data.VALUE
								if self.TransportRoute.get_value(ll, l, p, trm, y) == 1]],

					[self.Transport.get_index_label(ll, l, p, tr, y)
					for ll in self.LOCATION.data.VALUE
					for tr in [trm for trm in self.TRANSPORTMODE.data.VALUE
								if self.TransportRoute.get_value(ll, l, p, trm, y) == 1]]),

				([-1 * sum(sum(self.TransportCostInterReg.get_value(rr, r, tr, y)
							* self.Geography.get_value(r, l) for r in self.REGION.data.VALUE)
							* self.Geography.get_value(rr, ll) for rr in self.REGION.data.VALUE)
					for ll in self.LOCATION.data.VALUE  if self.HubLocation.get_value(ll)==1
					for tr in [trm for trm in self.TRANSPORTMODE.data.VALUE
								if self.TransportRoute.get_value(ll, l, p, trm, y) == 1]],

					[self.Transport.get_index_label(ll, l, p, tr, y)
					for ll in self.LOCATION.data.VALUE if self.HubLocation.get_value(ll)==1
					for tr in [trm for trm in self.TRANSPORTMODE.data.VALUE
								if self.TransportRoute.get_value(ll, l, p, trm, y) == 1]])]
			rhs = 0
			sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def TC2_DiscountedLocalTransportCosts_rule(self, l, p, y):
		"""
		*Constraint:* local transport cost is discounted back to the first interval
		modeled. That is done, using either a technology-specific or a global
		discount rate applied to the middle of the interval in which the costs are
		incurred.

		LocalDiscountedTransportCost(l, p, y) ==
			LocalTransportCost(l, p, y) / ((1 + sum(DiscountRate(r) *
						Geography(r, l) for r in REGION)) ** (1 + y - (min(YEAR) - TimeStep(min(YEAR)) / 2 + 1)))
		"""

		lhs = [(1, self.LocalDiscountedTransportCost.get_index_label(l, p, y)),
			   (-1 / ((1 + sum(self.DiscountRate.get_value(r) *
							   self.Geography.get_value(r, l) for r in self.REGION.data.VALUE)) ** (
							  1 + y - (min(self.YEAR.data.VALUE) -
									   self.TimeStep.get_value(
										   min(self.YEAR.data.VALUE)) / 2 + 1))),
				self.LocalTransportCost.get_index_label(l, p, y))]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def TC3_DiscountedTransportCostsByProduct_rule(self, r, p, y):
		"""
		*Constraint:* for each region, product and year, the total costs of transport
		is the sum of the transport costs at each location. These transport costs
		include both intra-regional transport AND imports from other regions.

		DiscountedTransportCostByProduct(r, p, y) == sum(
			LocalDiscountedTransportCost(l, p, y) * Geography(r, l) for l in LOCATION)
		"""

		lhs = [(1, self.DiscountedTransportCostByProduct.get_index_label(r, p, y)),
			   (-1, [self.LocalDiscountedTransportCost.get_index_label(l, p, y) for l in self.LOCATION.data.VALUE
					 if self.Geography.get_value(r, l) == 1])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def TC4_DiscountedTransportCostsTotalAnnual_rule(self, r, y):
		"""
		*Constraint:* for each region and year, transport costs by product are added
		to determine total transport costs towards and within this region.

		DiscountedTransportCost(r, y) == sum(DiscountedTransportCostByProduct(r, p, y) for p in PRODUCT)
		"""

		lhs = [(1, self.DiscountedTransportCost.get_index_label(r, y)),
			   (-1, [self.DiscountedTransportCostByProduct.get_index_label(r, p, y) for p in self.PRODUCT.data.VALUE])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	#########       	Total Discounted Costs	 	#############

	def TDC1_TotalDiscountedCostByTechnology_rule(self, r, t, y):
		"""
		*Constraint:* for each region and year, total discounted costs are the
		sum for each technology of investment and operating costs, minus salvage
		costs, to which transport costs for the region are added.

		TotalDiscountedCost(r, y) == sum(DiscountedOperatingCost(r, t, y) + DiscountedCapitalInvestment(r, t, y) +
			DiscountedTechnologyEmissionsPenalty(r, t, y) - DiscountedSalvageValue(r, t, y)
			for t in TECHNOLOGY) + DiscountedTransportCost(r, y)
		"""

		lhs = [(1, self.TotalDiscountedCost.get_index_label(r, y)),
			   (-1, [self.DiscountedOperatingCost.get_index_label(r, t, y) for t in self.TECHNOLOGY.data.VALUE]),
			   (-1, [self.DiscountedCapitalInvestment.get_index_label(r, t, y) for t in self.TECHNOLOGY.data.VALUE]),
			   (-1, [self.DiscountedTechnologyEmissionsPenalty.get_index_label(r, t, y) for t in
					 self.TECHNOLOGY.data.VALUE]),
			   (1, [self.DiscountedSalvageValue.get_index_label(r, t, y) for t in self.TECHNOLOGY.data.VALUE]),
			   (-1, self.DiscountedTransportCost.get_index_label(r, y))]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def TDC2_ModelPeriodCostByRegion_rule(self, r):
		"""
		*Constraint:* total discounted costs are added for each year over the
		modelling period.

		ModelPeriodCostByRegion(r) == sum(TotalDiscountedCost(r, y) for y in YEAR)
		"""

		lhs = [(1, self.ModelPeriodCostByRegion.get_index_label(r)),
			   (-1, [self.TotalDiscountedCost.get_index_label(r, y) for y in self.YEAR.data.VALUE])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def TDC3_ModelPeriodCost_rule(self):
		"""
		*Constraint:* discounted model period costs are added for each region.

	 	ModelPeriodCost == sum(ModelPeriodCostByRegion(r) for r in REGION)
		"""

		lhs = [(1, self.ModelPeriodCost.get_index_label()),
			   (-1, [self.ModelPeriodCostByRegion.get_index_label(r) for r in self.REGION.data.VALUE])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	#########      		Total Capacity Constraints 	##############

	def TCC1_TotalAnnualMaxCapacityConstraint_rule(self, r, t, y):
		"""
		*Constraint:* there can be a maximum limit on the total capacity of a
		particular technology allowed in a particular year and region.

		TotalCapacity(r, t, y) <= TotalAnnualMaxCapacity(r, t, y)
		"""

		if self.TotalAnnualMaxCapacity.get_value(r, t, y) != self.HighMaxDefault:
			lhs = [(1, self.TotalCapacity.get_index_label(r, t, y))]
			rhs = self.TotalAnnualMaxCapacity.get_value(r, t, y)
			sense = '<='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	def TCC2_TotalAnnualMinCapacityConstraint_rule(self, r, t, y):
		"""
		*Constraint:* there can be a mainimu limit on the total capacity of a
		particular technology allowed in a particular year and region.

		TotalCapacity(r, t, y) >= TotalAnnualMinCapacity(r, t, y)
		"""

		if self.TotalAnnualMinCapacity.get_value(r, t, y) != 0:
			lhs = [(1, self.TotalCapacity.get_index_label(r, t, y))]
			rhs = self.TotalAnnualMinCapacity.get_value(r, t, y)
			sense = '>='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	#########    		New Capacity Constraints  	##############

	def NCC1_LocalTotalAnnualMaxNewCapacityConstraint_rule(self, l, t, y):
		"""
		*Constraint:* there can be a maximum new capacity investment limit placed
		on a particular technology per year and region.

		LocalNewCapacity(l, t, y) <= LocalTotalAnnualMaxCapacityInvestment(l, t, y)
		"""
		if self.LocalTotalAnnualMaxCapacityInvestment.get_value(l, t, y) != self.HighMaxDefault:
			if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
					(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
				lhs = [(1, self.LocalNewCapacity.get_index_label(l, t, y))]
				rhs = self.LocalTotalAnnualMaxCapacityInvestment.get_value(l, t, y)
				sense = '<='
				return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
			else:
				return None
		else:
			return None

	def NCC2_LocalTotalAnnualMinNewCapacityConstraint_rule(self, l, t, y):
		"""
		*Constraint:* there can be a minimum new capacity investment limit placed
		on a particular technology per year and region.

		LocalNewCapacity(l, t, y) >= LocalTotalAnnualMinCapacityInvestment(l, t, y)
		"""

		if self.LocalTotalAnnualMinCapacityInvestment.get_value(l, t, y) != 0:
			if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
					(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
				lhs = [(1, self.LocalNewCapacity.get_index_label(l, t, y))]
				rhs = self.LocalTotalAnnualMinCapacityInvestment.get_value(l, t, y)
				sense = '>='
				return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
			else:
				return None
		else:
			return None

	#########   		Annual Activity Constraints	##############

	def AAC0_LocalAnnualTechnologyActivity_rule(self, l, t, y):
		"""
		*Constraint:* the total activity of a technology for each year in a location
		is the sum of the local activities by mode of operation.

		LocalActivity(l, t, y) == sum(LocalActivityByMode(l, t, m, y) for m in ModeOfOperation)
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
				(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
			ModeOfOperation = [m for m in self.MODE_OF_OPERATION.data.VALUE if
							   self.ModeForTechnology.get_value(t, m) == 1]
			lhs = [(1, self.LocalActivity.get_index_label(l, t, y)),
				   (-1, [self.LocalActivityByMode.get_index_label(l, t, m, y) for m in ModeOfOperation])]
			rhs = 0
			sense = '=='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	def AAC1_TotalAnnualTechnologyActivity_rule(self, r, t, y):
		"""
		*Constraint:* the total activity of a technology for each year in a region
		is the sum of the local activities in that region.

		Activity(r, t, y) == sum(LocalActivity(l, t, y) * Geography(r, l) for l in RelevantLocation)
		"""

		if self.HubTechnology.get_value(t) == 1:
			RelevantLocation = [l for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l) == 1]
		elif self.HubTechnology.get_value(t) == 0:
			RelevantLocation = [l for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l) == 0]
		lhs = [(1, self.Activity.get_index_label(r, t, y)),
			   ([-1 * self.Geography.get_value(r, l) for l in RelevantLocation],
				[self.LocalActivity.get_index_label(l, t, y) for l in RelevantLocation])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def AAC2_TotalAnnualTechnologyActivityUpperLimit_rule(self, r, t, y):
		"""
		*Constraint:* where specified, a maximum annual limit may be placed
		on the annual activity of a technology in a region.

		Activity(r, t, y) <= TotalTechnologyAnnualActivityUpperLimit(r,t,y)
		"""

		if self.TotalTechnologyAnnualActivityUpperLimit.get_value(r, t, y) != self.HighMaxDefault:
			lhs = [(1, self.Activity.get_index_label(r, t, y))]
			rhs = self.TotalTechnologyAnnualActivityUpperLimit.get_value(r, t, y)
			sense = '<='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	def AAC3_TotalAnnualTechnologyActivityLowerLimit_rule(self, r, t, y):
		"""
		*Constraint:* where specified, a minimum annual limit may be placed
		on the annual activity of a technology in a region.

		Activity(r, t, y) >= TotalTechnologyAnnualActivityLowerLimit(r,t,y)
		"""

		if self.TotalTechnologyAnnualActivityLowerLimit.get_value(r, t, y) != 0:
			lhs = [(1, self.Activity.get_index_label(r, t, y))]
			rhs = self.TotalTechnologyAnnualActivityLowerLimit.get_value(r, t, y)
			sense = '>='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

		else:
			return None

	#    def AAC4_TotalAnnualTechnologyProductionLowerLimit_rule(self,r,t,p,y):
	#        '''
	#        *Constraint:* where specified, a minimum annual limit may be placed
	#        on the annual production of a technology, for a given product in a region.
	#        '''
	#        return self.ProductionByTechnology[r,t,p,y] >= self.TotalTechnologyAnnualProductionLowerLimit[r,t,p,y]

	#########    		Total Activity Constraints 	##############

	def TAC1_TotalModelHorizonTechnologyActivity_rule(self, r, t):
		"""
		*Constraint:* the model period activity of each technology is obtained
		by summing the total annual activity of each technology for each year
		for each region.

		ModelPeriodActivity(r, t) == sum(Activity(r, t, y) for y in YEAR)
		"""

		lhs = [(1, self.ModelPeriodActivity.get_index_label(r, t)),
			   (-1, [self.Activity.get_index_label(r, t, y) for y in self.YEAR.data.VALUE])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def TAC2_TotalModelHorizonTechnologyActivityUpperLimit_rule(self, r, t):
		"""
		*Constraint:* where specified, a maximum limit may be placed on the
		model period activity of a technology.

		ModelPeriodActivity(r, t) <= TotalTechnologyModelPeriodActivityUpperLimit(r, t)
		"""

		if self.TotalTechnologyModelPeriodActivityUpperLimit.get_value(r, t) != self.HighMaxDefault:
			lhs = [(1, self.ModelPeriodActivity.get_index_label(r, t))]
			rhs = self.TotalTechnologyModelPeriodActivityUpperLimit.get_value(r, t)
			sense = '<='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	def TAC3_TotalModelHorizonTechnologyActivityLowerLimit_rule(self, r, t):
		"""
		*Constraint:* where specified, a minimum limit may be placed on the
		model period activity of a technology.

		ModelPeriodActivity(r, t) >= TotalTechnologyModelPeriodActivityLowerLimit(r, t)
		"""

		if self.TotalTechnologyModelPeriodActivityLowerLimit.get_value(r, t) != 0:
			lhs = [(1, self.ModelPeriodActivity.get_index_label(r, t))]
			rhs = self.TotalTechnologyModelPeriodActivityLowerLimit.get_value(r, t)
			sense = '>='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	#########   		Emissions Accounting		##############

	def E1_LocalEmissionProductionByMode_rule(self, l, t, e, m, y):
		"""
		*Constraint:* for each location, technology, emission type, operation mode
		and year the emission quantity is a function of the rate of activity of
		each technology and a per-unit emission factor defined by the analyst.


		LocalTechnologyEmissionByMode(l, t, e, m, y) == LocalActivityByMode(l, t, m, y) * sum(
							EmissionActivityRatio(r, t, e, m, y) * Geography(r, l) for r
							in REGION)

		LocalTechnologyEmissionByMode(l, t, e, m, y) == 0
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
				(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
			if self.ModeForTechnology.get_value(t, m) == 1:
				if sum(self.EmissionActivityRatio.get_value(r, t, e, m, y) * self.Geography.get_value(r, l) for r in
					   self.REGION.data.VALUE) != 0:
					lhs = [(1, self.LocalTechnologyEmissionByMode.get_index_label(l, t, e, m, y)),
						   (-1 * sum(self.EmissionActivityRatio.get_value(r, t, e, m, y) *
									 self.Geography.get_value(r, l) for r in self.REGION.data.VALUE),
							self.LocalActivityByMode.get_index_label(l, t, m, y))]
					rhs = 0
					sense = '=='
					return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

				else:
					lhs = [(1, self.LocalTechnologyEmissionByMode.get_index_label(l, t, e, m, y))]
					rhs = 0
					sense = '=='
					return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

			else:
				return None
		else:
			return None

	def E2_LocalEmissionProduction_rule(self, l, t, e, y):
		"""
		*Constraint: for each location, technology, emission type, and year total
		emissions are the sum of emissions in each operation mode.*

		LocalTechnologyEmission(l, t, e, y) == sum(LocalTechnologyEmissionByMode(l, t, e, m, y) for m in ModeOfOperation)
		"""

		if ((self.HubLocation.get_value(l) == 1) and (self.HubTechnology.get_value(t) == 1)) or (
				(self.HubLocation.get_value(l) == 0) and (self.HubTechnology.get_value(t) == 0)):
			ModeOfOperation = [m for m in self.MODE_OF_OPERATION.data.VALUE if
							   self.ModeForTechnology.get_value(t, m) == 1]
			lhs = [(1, self.LocalTechnologyEmission.get_index_label(l, t, e, y)),
				   (-1, [self.LocalTechnologyEmissionByMode.get_index_label(l, t, e, m, y) for m in ModeOfOperation])]
			rhs = 0
			sense = '=='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	def E3_AnnualEmissionProduction_rule(self, r, t, e, y):
		"""
		*Constraint:* for each region, technology, emission type, and year total
		emissions are the sum of emissions in each location.

		AnnualTechnologyEmission(r, t, e, y) == sum(LocalTechnologyEmission(l, t, e, y) * Geography(r, l) for l in
			RelevantLocation)
		"""

		if self.HubTechnology.get_value(t) == 1:
			RelevantLocation = [l for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l) == 1]
		elif self.HubTechnology.get_value(t) == 0:
			RelevantLocation = [l for l in self.LOCATION.data.VALUE if self.HubLocation.get_value(l) == 0]
		lhs = [(1, self.AnnualTechnologyEmission.get_index_label(r, t, e, y)),
			   (-1, [self.LocalTechnologyEmission.get_index_label(l, t, e, y) for l in RelevantLocation
					 if self.Geography.get_value(r, l) == 1])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def E4_EmissionPenaltyByTechAndEmission_rule(self, r, t, e, y):
		"""
		*Constraint:* for each region, technology, emission type, and year there is
		an emission penalty associated with the quantity of emissions.

		AnnualTechnologyEmissionPenaltyByEmission(r, t, e, y) == AnnualTechnologyEmission(r, t, e, y) *
			EmissionsPenalty(r, e, y)
		"""

		lhs = [(1, self.AnnualTechnologyEmissionPenaltyByEmission.get_index_label(r, t, e, y)),
			   (-1 * self.EmissionsPenalty.get_value(r, e, y),
				self.AnnualTechnologyEmission.get_index_label(r, t, e, y))]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def E5_EmissionsPenaltyByTechnology_rule(self, r, t, y):
		"""
		*Constraint:* for each location, technology, and year the total emission
		penalty is the sum of emission penalties for each emission type.

		AnnualTechnologyEmissionsPenalty(r, t, y) == sum(AnnualTechnologyEmissionPenaltyByEmission(r, t, e, y) for e in
			EMISSION)
		"""

		lhs = [(1, self.AnnualTechnologyEmissionsPenalty.get_index_label(r, t, y)),
			   (-1, [self.AnnualTechnologyEmissionPenaltyByEmission.get_index_label(r, t, e, y) for e in
					 self.EMISSION.data.VALUE])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def E6_DiscountedEmissionsPenaltyByTechnology_rule(self, r, t, y):
		"""
		*Constraint:* emission penalties are discounted back to the first interval
		modeled. That is done, using either a technology-specific or a global
		discount rate applied to the middle of the interval in which the costs are
		incurred.

		DiscountedTechnologyEmissionsPenalty(r, t, y) == AnnualTechnologyEmissionsPenalty(r, t, y) /
			((1 + DiscountRate(r)) ** (1 + y - (min(YEAR) - TimeStep(min(YEAR)) / 2 + 1)))
		"""

		lhs = [(1, self.DiscountedTechnologyEmissionsPenalty.get_index_label(r, t, y)),
			   (-1 / ((1 + self.DiscountRate.get_value(r)) ** (1 + y - (min(self.YEAR.data.VALUE) -
																		self.TimeStep.get_value(
																			min(self.YEAR.data.VALUE)) / 2 + 1))),
				self.AnnualTechnologyEmissionsPenalty.get_index_label(r, t, y))]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def E7_EmissionsAccounting1_rule(self, r, e, y):
		"""
		*Constraint:* for each region, emission type, and year total emissions
		are the sum of emissions from each technology.

		AnnualEmissions(r, e, y) == sum(AnnualTechnologyEmission(r, t, e, y) for t in TECHNOLOGY)
		"""
		lhs = [(1, self.AnnualEmissions.get_index_label(r, e, y)),
			   (-1, [self.AnnualTechnologyEmission.get_index_label(r, t, e, y) for t in self.TECHNOLOGY.data.VALUE])]
		rhs = 0
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def E8_EmissionsAccounting2_rule(self, r, e):
		"""
		*Constraint:* for each region and emission type total emissions over the
		whole modelling period is the sum of all technology emissions plus
		exogenous emissions entered by the analyst.

		ModelPeriodEmissions(r, e) == sum(AnnualEmissions(r, e, y) for y in	YEAR) + ModelPeriodExogenousEmission(r, e)
		"""

		lhs = [(1, self.ModelPeriodEmissions.get_index_label(r, e)),
			   (-1, [self.AnnualEmissions.get_index_label(r, e, y) for y in self.YEAR.data.VALUE])]
		rhs = self.ModelPeriodExogenousEmission.get_value(r, e)
		sense = '=='
		return {'lhs': lhs, 'rhs': rhs, 'sense': sense}

	def E9_AnnualEmissionsLimit_rule(self, r, e, y):
		"""
		*Constraint:* for each region, emission type, and year total emissions
		should be lower than the emission limit entered by the analyst.

		AnnualEmissions(r, e, y) + AnnualExogenousEmission(r, e, y) <= AnnualEmissionLimit(r, e, y)
		"""

		if self.AnnualEmissionLimit.get_value(r, e, y) != self.HighMaxDefault:
			lhs = [(1, self.AnnualEmissions.get_index_label(r, e, y))]
			rhs = self.AnnualEmissionLimit.get_value(r, e, y) - self.AnnualExogenousEmission.get_value(r, e, y)
			sense = '<='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

	def E10_ModelPeriodEmissionsLimit_rule(self, r, e):
		"""
		*Constraint:* for each region and emission type total emissions over the
		whole emission period should be lower than the emission limit entered by
		the analyst.

		ModelPeriodEmissions(r, e) <= ModelPeriodEmissionLimit(r, e)
		"""

		if self.ModelPeriodEmissionLimit.get_value(r, e) != self.HighMaxDefault:
			lhs = [(1, self.ModelPeriodEmissions.get_index_label(r, e))]
			rhs = self.ModelPeriodEmissionLimit.get_value(r, e)
			sense = '<='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
		else:
			return None

##############################################################################
