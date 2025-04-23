#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
This module defines:

    - the `abstract_itom` class that encapsulates a Pyomo ABSTRACT model definition for the energy-intensive industry system,
    - the `concrete_itom` class that encapsulates a Pyomo CONCRETE model built from the abstract model,
    - methods in both classes to import input data from csv, solve the model, export all variables to csv etc.
'''

__all__ = ('abstract_itom',
           'concrete_itom')

#from __future__ import division
import os
from pyomo.environ import AbstractModel, DataPortal, Set, Param, Var, Objective, Constraint, Reals, NonNegativeReals, NonNegativeIntegers, minimize, value
from pyomo.opt import SolverFactory

##############################################################################

class abstract_itom(object):
    '''
    Class encapsulating a Pyomo ABSTRACT model definition for the energy-intensive industry system.

    Important note:
    In this model every location is by default linked to every other location via "Transport".
    It allows to precisely follow exchanges of products between locations.
    However, for models with a significatnt number of locations, the problem becomes very large and might excess the capacites of your computer system.
    In such a case, you can use itom_hub.py instead.

    **Constructor arguments:**
        *InputPath [optional]: string*
            Path to directory of csv input data files. Default: None.

    **Public class attributes:**
        *model: Pyomo AbstractModel object*
            Instance of the Pyomo AbstractModel class. Parameter values are unspecified
            and will be supplied to a concrete model instance (see Class concrete_itom)
            when a solution is to be obtained.
        *data: Pyomo DataPortal object*
            Instance of the Pyomo DataPortal class. Data from csv files (located
            at InputPath) can be loaded into this object with the public method load_data().
        *InputPath: string*
           Path to directory of csv input data files.

    **Sets, parameters, variables**
        The Pyomo Set, Param, and Var objects are attributes of the public class attribute `abstract_itom.model`.

    **Objective**
        The Pyomo Ojective object is an attribute of the public class attribute `abstract_itom.model`.
        The objective function is defined as a method of this class.

    **Constraints**
        The Pyomo Constraint objects are attributes of the public class attribute `abstract_itom.model`.
        The constraint functions are defined as methods of this class. They are named after the constraint they
        define with `_rule` appended to the contraint's name.
        We distinguish the following constraint categories:

            - Capacity Adequacy (CA)
            - Product Balance (PB)
            - Transport Flows (TF)
            - Capital Costs (CC)
            - Salvage Value (SV)
            - Operating Costs (OC)
            - Transport Costs (TC)
            - Total Discounted Costs (TDC)
            - Total Capacity Constraints (TCC)
            - New Capacity Constraints (NCC)
            - Annual Activity Constraints (AAC)
            - Total Activity Constraints (TAC)
            - Emission Accounting (E)

        In the constraint function definitions, the model's Sets are referred to as the following arguments:

            - r = REGION
            - l = LOCATION
            - t = TECHNOLOGY
            - tr = TRANSPORTMODE
            - p = PRODUCT
            - m = MODE_OF_OPERATION
            - e = EMISSION
            - y = YEAR

    '''
    def __init__(self, InputPath=None):

        # Instantiate pyomo's AbstractModel
        self.model = AbstractModel()
        # Instantiate pyomo's DataPortal
        self.data = DataPortal()
        # Path to directory of csv input data files (optional)
        self.InputPath = InputPath

        ###############
        #    Sets     #
        ###############

        self.model.YEAR = Set()
        self.model.TECHNOLOGY = Set()
        self.model.TRANSPORTMODE = Set()
        self.model.PRODUCT = Set()
        self.model.REGION = Set()
        self.model.LOCATION = Set()
        self.model.EMISSION = Set()
        self.model.MODE_OF_OPERATION = Set()

        #####################
        #    Parameters     #
        #####################

        ########			Auxiliary parameters for reducing memory usage 						#############

        self.model.ModeForTechnology = Param(self.model.TECHNOLOGY, self.model.MODE_OF_OPERATION, default=0)
        self.model.ProductFromTechnology = Param(self.model.TECHNOLOGY, self.model.PRODUCT, default=0)
        self.model.ProductToTechnology = Param(self.model.TECHNOLOGY, self.model.PRODUCT, default=0)

        self.model.TimeStep = Param(self.model.YEAR, default=0)

        ########			Global 						#############

        self.model.DiscountRate = Param(self.model.REGION, default=0.05)
        self.model.TransportRoute = Param(self.model.LOCATION, self.model.LOCATION, self.model.PRODUCT, self.model.TRANSPORTMODE, self.model.YEAR, default=0)
        self.model.TransportCapacity = Param(self.model.LOCATION, self.model.LOCATION, self.model.PRODUCT, self.model.TRANSPORTMODE, self.model.YEAR, default=0.0)
        self.model.Geography = Param(self.model.REGION, self.model.LOCATION, default=0)
        self.model.DepreciationMethod = Param(self.model.REGION, default=1)

        ########			Demands 					#############

        self.model.Demand = Param(self.model.REGION, self.model.PRODUCT, self.model.YEAR, default=0)

        #########			Performance					#############

        self.model.TransportCapacityToActivity = Param(self.model.TRANSPORTMODE, default=1)
        self.model.CapacityToActivityUnit = Param(self.model.REGION, self.model.TECHNOLOGY, default=1)
        self.model.AvailabilityFactor = Param(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, default=1)
        self.model.OperationalLife = Param(self.model.REGION, self.model.TECHNOLOGY, default=1)
        self.model.LocalResidualCapacity = Param(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, default=0)
        self.model.InputActivityRatio = Param(self.model.REGION, self.model.TECHNOLOGY, self.model.PRODUCT, self.model.MODE_OF_OPERATION, self.model.YEAR, default=0)
        self.model.OutputActivityRatio = Param(self.model.REGION, self.model.TECHNOLOGY, self.model.PRODUCT, self.model.MODE_OF_OPERATION, self.model.YEAR, default=0)

        #########			Technology Costs			#############

        self.model.CapitalCost = Param(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, default=0)
        self.model.VariableCost = Param(self.model.REGION, self.model.TECHNOLOGY, self.model.MODE_OF_OPERATION, self.model.YEAR, default=0)
        self.model.FixedCost = Param(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, default=0)

        self.model.TransportCostByMode = Param(self.model.REGION, self.model.TRANSPORTMODE, self.model.YEAR, default=0.0)

        #########			Capacity Constraints		#############

#        self.model.CapacityOfOneTechnologyUnit = Param(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, default=0)
        self.model.TotalAnnualMaxCapacity = Param(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, default=1e20)
        self.model.TotalAnnualMinCapacity = Param(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, default=0)

        #########			Investment Constraints		#############

        self.model.LocalTotalAnnualMaxCapacityInvestment = Param(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, default=1e20)
        self.model.LocalTotalAnnualMinCapacityInvestment = Param(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, default=0)

        #########			Activity Constraints		#############

#        self.model.TotalTechnologyAnnualProductionLowerLimit = Param(self.model.REGION, self.model.TECHNOLOGY, self.model.PRODUCT,self.model.YEAR, default=0)
        self.model.TotalTechnologyAnnualActivityUpperLimit = Param(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, default=1e20)
        self.model.TotalTechnologyAnnualActivityLowerLimit = Param(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, default=0)
        self.model.TotalTechnologyModelPeriodActivityUpperLimit = Param(self.model.REGION, self.model.TECHNOLOGY, default=1e20)
        self.model.TotalTechnologyModelPeriodActivityLowerLimit = Param(self.model.REGION, self.model.TECHNOLOGY, default=0)

        #########			Emissions & Penalties		#############

        self.model.EmissionActivityRatio = Param(self.model.REGION, self.model.TECHNOLOGY, self.model.EMISSION, self.model.MODE_OF_OPERATION, self.model.YEAR, default=0)
        self.model.EmissionsPenalty = Param(self.model.REGION, self.model.EMISSION, self.model.YEAR, default=0)
        self.model.AnnualExogenousEmission = Param(self.model.REGION, self.model.EMISSION, self.model.YEAR, default=0)
        self.model.AnnualEmissionLimit = Param(self.model.REGION, self.model.EMISSION, self.model.YEAR, mutable=True, default=1e20) # Param(mutable=True) allows to change the value of this parameter dynamically after the parameter has been constructed.
        self.model.ModelPeriodExogenousEmission = Param(self.model.REGION, self.model.EMISSION, default=0)
        self.model.ModelPeriodEmissionLimit = Param(self.model.REGION, self.model.EMISSION, mutable=True, default=1e20) # Param(mutable=True) allows to change the value of this parameter dynamically after the parameter has been constructed.

        ######################
        #   Model Variables  #
        ######################

        #########		    Capacity Variables 			#############

#        self.model.NumberOfNewTechnologyUnits = Var(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeIntegers, initialize=0)
        self.model.LocalNewCapacity = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.NewCapacity = Var(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.LocalAccumulatedNewCapacity = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.AccumulatedNewCapacity = Var(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.LocalTotalCapacity = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.TotalCapacity = Var(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)

        #########		    Activity Variables 			#############

        self.model.LocalActivityByMode = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.MODE_OF_OPERATION, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.LocalActivity = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.Activity = Var(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.ModelPeriodActivity = Var(self.model.REGION, self.model.TECHNOLOGY, domain=NonNegativeReals, initialize=0.0)

        self.model.LocalProductionByMode = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.PRODUCT, self.model.MODE_OF_OPERATION, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.LocalProductionByTechnology = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.PRODUCT, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.LocalProduction = Var(self.model.LOCATION, self.model.PRODUCT, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.Production = Var(self.model.REGION, self.model.PRODUCT, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
#        self.model.ProductionByTechnology = Var(self.model.REGION, self.model.TECHNOLOGY, self.model.PRODUCT, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)

        self.model.LocalUseByMode = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.PRODUCT, self.model.MODE_OF_OPERATION, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.LocalUseByTechnology = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.PRODUCT, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.LocalUse = Var(self.model.LOCATION, self.model.PRODUCT, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.Use = Var(self.model.REGION, self.model.PRODUCT, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)

        #########		    Transport Variables 			#############

        self.model.Transport = Var(self.model.LOCATION, self.model.LOCATION, self.model.PRODUCT, self.model.TRANSPORTMODE, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.Import = Var(self.model.REGION, self.model.PRODUCT, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.Export = Var(self.model.REGION, self.model.PRODUCT, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)

        #########		    Costing Variables 			#############

        self.model.LocalCapitalInvestment = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.LocalDiscountedCapitalInvestment = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.DiscountedCapitalInvestment = Var(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)

        self.model.SalvageValue = Var(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.DiscountedSalvageValue = Var(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)

        # LocalVariableOperatingCost, LocalOperatingCost, LocalDiscountedOperatingCost, DiscountedOperatingCost:
        # allow for negative variable costs at a given location (e.g. through a stand-alone export terminal technology)
        self.model.LocalVariableOperatingCost = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, domain=Reals, initialize=0.0)
        self.model.LocalFixedOperatingCost = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.LocalOperatingCost = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, domain=Reals, initialize=0.0)
        self.model.LocalDiscountedOperatingCost = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, domain=Reals, initialize=0.0)
        self.model.DiscountedOperatingCost = Var(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, domain=Reals, initialize=0.0)

        self.model.LocalTransportCost = Var(self.model.LOCATION, self.model.PRODUCT, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.LocalDiscountedTransportCost = Var(self.model.LOCATION, self.model.PRODUCT, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.DiscountedTransportCostByProduct = Var(self.model.REGION, self.model.PRODUCT, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.DiscountedTransportCost = Var(self.model.REGION, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)

        self.model.TotalDiscountedCost = Var(self.model.REGION, self.model.YEAR, domain=Reals, initialize=0.0)
        self.model.ModelPeriodCostByRegion = Var(self.model.REGION, domain=Reals, initialize=0.0)
        self.model.ModelPeriodCost = Var(domain=Reals, initialize=0.0)

        #########			Emissions					#############

        self.model.LocalTechnologyEmissionByMode = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.EMISSION, self.model.MODE_OF_OPERATION, self.model.YEAR, domain=Reals, initialize=0.0)
        self.model.LocalTechnologyEmission = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.EMISSION, self.model.YEAR, domain=Reals, initialize=0.0)
        self.model.AnnualTechnologyEmission = Var(self.model.REGION, self.model.TECHNOLOGY, self.model.EMISSION, self.model.YEAR, domain=Reals, initialize=0.0)
        self.model.AnnualTechnologyEmissionPenaltyByEmission = Var(self.model.REGION, self.model.TECHNOLOGY, self.model.EMISSION, self.model.YEAR, domain=Reals, initialize=0.0)
        self.model.AnnualTechnologyEmissionsPenalty = Var(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, domain=Reals, initialize=0.0)
        self.model.DiscountedTechnologyEmissionsPenalty = Var(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, domain=Reals, initialize=0.0)
        self.model.AnnualEmissions = Var(self.model.REGION, self.model.EMISSION, self.model.YEAR, domain=Reals, initialize=0.0)
        self.model.ModelPeriodEmissions = Var(self.model.REGION, self.model.EMISSION, domain=Reals, initialize=0.0)

        ######################
        # Objective Function #
        ######################

        self.model.OBJ = Objective(rule=self.ObjectiveFunction_rule, sense=minimize, doc='min_costs')

        #####################
        # Constraints       #
        #####################

        #########       	Capacity Adequacy	     	#############

        self.model.CA0_NewCapacity = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.CA0_NewCapacity_rule)

        self.model.CA1_TotalNewCapacity_1 = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.CA1_TotalNewCapacity_1_rule)

        self.model.CA2_TotalNewCapacity_2 = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.CA2_TotalNewCapacity_2_rule)

        self.model.CA3_TotalAnnualCapacity_1 = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.CA3_TotalAnnualCapacity_1_rule)

        self.model.CA4_TotalAnnualCapacity_2 = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.CA4_TotalAnnualCapacity_2_rule)

        self.model.CA5_ConstraintCapacity = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.CA5_ConstraintCapacity_rule)

        #########	        Product Balance    	 	#############

        self.model.PB1_Production_1 = Constraint(self.model.LOCATION, self.model.PRODUCT, self.model.TECHNOLOGY, self.model.MODE_OF_OPERATION, self.model.YEAR, rule=self.PB1_Production_1_rule)

        self.model.PB2_Production_2 = Constraint(self.model.LOCATION, self.model.PRODUCT, self.model.TECHNOLOGY, self.model.YEAR, rule=self.PB2_Production_2_rule)

        self.model.PB3_Production_3 = Constraint(self.model.LOCATION, self.model.PRODUCT, self.model.YEAR, rule=self.PB3_Production_3_rule)

        self.model.PB4_Production_4 = Constraint(self.model.REGION, self.model.PRODUCT, self.model.YEAR, rule=self.PB4_Production_4_rule)

#        self.model.PB5_Production_5 = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.PRODUCT, self.model.YEAR, rule=self.PB5_Production_5_rule)

        self.model.PB5_Use_1 = Constraint(self.model.LOCATION, self.model.PRODUCT, self.model.TECHNOLOGY, self.model.MODE_OF_OPERATION, self.model.YEAR, rule=self.PB5_Use_1_rule)

        self.model.PB6_Use_2 = Constraint(self.model.LOCATION, self.model.PRODUCT, self.model.TECHNOLOGY, self.model.YEAR, rule=self.PB6_Use_2_rule)

        self.model.PB7_Use_3 = Constraint(self.model.LOCATION, self.model.PRODUCT, self.model.YEAR, rule=self.PB7_Use_3_rule)

        self.model.PB8_Use_4 = Constraint(self.model.REGION, self.model.PRODUCT, self.model.YEAR, rule=self.PB8_Use_4_rule)

        self.model.PB9_ProductBalance = Constraint(self.model.REGION, self.model.PRODUCT, self.model.YEAR, rule=self.PB9_ProductBalance_rule)

        #########        	Transport Flows	 	#############

        self.model.TF1_Transport_1 = Constraint(self.model.LOCATION, self.model.LOCATION, self.model.PRODUCT, self.model.TRANSPORTMODE, self.model.YEAR, rule=self.TF1_Transport_1_rule)

        self.model.TF2_Transport_2 = Constraint(self.model.LOCATION, self.model.PRODUCT, self.model.YEAR, rule=self.TF2_Transport_2_rule)

        self.model.TF3_Transport_3 = Constraint(self.model.LOCATION, self.model.PRODUCT, self.model.YEAR, rule=self.TF3_Transport_3_rule)

        self.model.TF4_Imports = Constraint(self.model.REGION, self.model.PRODUCT, self.model.YEAR, rule=self.TF4_Imports_rule)

        self.model.TF5_Exports = Constraint(self.model.REGION, self.model.PRODUCT, self.model.YEAR, rule=self.TF5_Exports_rule)

        #########       	Capital Costs 		     	#############

        self.model.CC1_UndiscountedCapitalInvestment = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.CC1_UndiscountedCapitalInvestment_rule)

        self.model.CC2_DiscountedCapitalInvestment_1_constraint = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.CC2_DiscountedCapitalInvestment_1_rule)

        self.model.CC3_DiscountedCapitalInvestment_2_constraint = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.CC3_DiscountedCapitalInvestment_2_rule)

        #########           Salvage Value            	#############

        self.model.SV1_SalvageValueAtEndOfPeriod = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.SV1_SalvageValueAtEndOfPeriod_rule)

        self.model.SV2_SalvageValueDiscountedToStartYear = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.SV2_SalvageValueDiscountedToStartYear_rule)

        #########        	Operating Costs 		 	#############

        self.model.OC1_OperatingCostsVariable = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.OC1_OperatingCostsVariable_rule)

        self.model.OC2_OperatingCostsFixedAnnual = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.OC2_OperatingCostsFixedAnnual_rule)

        self.model.OC3_OperatingCostsTotalAnnual = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.OC3_OperatingCostsTotalAnnual_rule)

        self.model.OC4_DiscountedOperatingCostsTotalAnnual_1 = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.OC4_DiscountedOperatingCostsTotalAnnual_1_rule)

        self.model.OC5_DiscountedOperatingCostsTotalAnnual_2 = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.OC5_DiscountedOperatingCostsTotalAnnual_2_rule)

        #########        	Transport Costs 		 	#############

        self.model.TC1_LocalTransportCosts = Constraint(self.model.LOCATION, self.model.PRODUCT, self.model.YEAR, rule=self.TC1_LocalTransportCosts_rule)

        self.model.TC2_DiscountedLocalTransportCosts = Constraint(self.model.LOCATION, self.model.PRODUCT, self.model.YEAR, rule=self.TC2_DiscountedLocalTransportCosts_rule)

        self.model.TC3_DiscountedTransportCostsByProduct = Constraint(self.model.REGION, self.model.PRODUCT, self.model.YEAR, rule=self.TC3_DiscountedTransportCostsByProduct_rule)

        self.model.TC4_DiscountedTransportCostsTotalAnnual = Constraint(self.model.REGION, self.model.YEAR, rule=self.TC4_DiscountedTransportCostsTotalAnnual_rule)

        #########       	Total Discounted Costs	 	#############

        self.model.TDC1_TotalDiscountedCostByTechnology = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.TDC1_TotalDiscountedCostByTechnology_rule)

        self.model.TDC2_ModelPeriodCostByRegion = Constraint(self.model.REGION, rule=self.TDC2_ModelPeriodCostByRegion_rule)

        self.model.TDC3_ModelPeriodCost = Constraint(rule=self.TDC3_ModelPeriodCost_rule)

        #########      		Total Capacity Constraints 	##############

        self.model.TCC1_TotalAnnualMaxCapacityConstraint = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.TCC1_TotalAnnualMaxCapacityConstraint_rule)

        self.model.TCC2_TotalAnnualMinCapacityConstraint = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.TCC2_TotalAnnualMinCapacityConstraint_rule)

        #########    		New Capacity Constraints  	##############

        self.model.NCC1_LocalTotalAnnualMaxNewCapacityConstraint = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.NCC1_LocalTotalAnnualMaxNewCapacityConstraint_rule)

        self.model.NCC2_LocalTotalAnnualMinNewCapacityConstraint = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.NCC2_LocalTotalAnnualMinNewCapacityConstraint_rule)


        #########   		Annual Activity Constraints	##############

        self.model.AAC0_LocalAnnualTechnologyActivity = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.AAC0_LocalAnnualTechnologyActivity_rule)

        self.model.AAC1_TotalAnnualTechnologyActivity = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.AAC1_TotalAnnualTechnologyActivity_rule)

        self.model.AAC2_TotalAnnualTechnologyActivityUpperlimit = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.AAC2_TotalAnnualTechnologyActivityUpperLimit_rule)

        self.model.AAC3_TotalAnnualTechnologyActivityLowerlimit = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.AAC3_TotalAnnualTechnologyActivityLowerLimit_rule)

#        self.model.AAC4_TotalAnnualTechnologyProductionLowerlimit = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.PRODUCT, self.model.YEAR, rule=self.AAC4_TotalAnnualTechnologyProductionLowerLimit_rule)

        #########    		Total Activity Constraints 	##############

        self.model.TAC1_TotalModelHorizonTechnologyActivity = Constraint(self.model.REGION, self.model.TECHNOLOGY, rule=self.TAC1_TotalModelHorizonTechnologyActivity_rule)

        self.model.TAC2_TotalModelHorizonTechnologyActivityUpperLimit = Constraint(self.model.REGION, self.model.TECHNOLOGY, rule=self.TAC2_TotalModelHorizonTechnologyActivityUpperLimit_rule)

        self.model.TAC3_TotalModelHorizonTechnologyActivityLowerLimit = Constraint(self.model.REGION, self.model.TECHNOLOGY, rule=self.TAC3_TotalModelHorizonTechnologyActivityLowerLimit_rule)

        #########   		Emissions Accounting		##############

        self.model.E1_LocalEmissionProductionByMode = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.EMISSION, self.model.MODE_OF_OPERATION, self.model.YEAR, rule=self.E1_LocalEmissionProductionByMode_rule)

        self.model.E2_LocalEmissionProduction = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.EMISSION, self.model.YEAR, rule=self.E2_LocalEmissionProduction_rule)

        self.model.E3_AnnualEmissionProduction = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.EMISSION, self.model.YEAR, rule=self.E3_AnnualEmissionProduction_rule)

        self.model.E4_EmissionPenaltyByTechAndEmission = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.EMISSION, self.model.YEAR, rule=self.E4_EmissionPenaltyByTechAndEmission_rule)

        self.model.E5_EmissionsPenaltyByTechnology = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.E5_EmissionsPenaltyByTechnology_rule)

        self.model.E6_DiscountedEmissionsPenaltyByTechnology = Constraint(self.model.REGION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.E6_DiscountedEmissionsPenaltyByTechnology_rule)

        self.model.E7_EmissionsAccounting1 = Constraint(self.model.REGION, self.model.EMISSION, self.model.YEAR, rule=self.E7_EmissionsAccounting1_rule)

        self.model.E8_EmissionsAccounting2 = Constraint(self.model.REGION, self.model.EMISSION, rule=self.E8_EmissionsAccounting2_rule)

        self.model.E9_AnnualEmissionsLimit = Constraint(self.model.REGION, self.model.EMISSION, self.model.YEAR, rule=self.E9_AnnualEmissionsLimit_rule)

        self.model.E10_ModelPeriodEmissionsLimit = Constraint(self.model.REGION, self.model.EMISSION, rule=self.E10_ModelPeriodEmissionsLimit_rule)

    ###########
    # METHODS #
    ###########

    ######################
    # Objective Function #
    ######################

    def ObjectiveFunction_rule(self, model):
        '''
        *Objective:* minimize total costs (capital, variable, fixed),
        aggregated for all regions, cumulated over the modelling period.
        '''
        return sum(self.model.ModelPeriodCostByRegion[r] for r in self.model.REGION)

    ###############
    # Constraints #
    ###############

    #########       	Capacity Adequacy	     	#############

    def CA0_NewCapacity_rule(self, model,r,t,y):
        '''
        *Constraint:* the new capacity available at each location is
        aggregated for each region. Note: this variable is only needed to
        calculate SalvageValue, which we only define at the regional level.
        '''
        return self.model.NewCapacity[r,t,y] == sum(self.model.LocalNewCapacity[l,t,y] * self.model.Geography[r,l] for l in self.model.LOCATION)

    def CA1_TotalNewCapacity_1_rule(self, model,l,t,y):
        '''
        *Constraint:* the accumulation of all new capacities of all technologies
        invested during the model period is calculated for each year.
        This is done first for each location.
        '''
        return self.model.LocalAccumulatedNewCapacity[l,t,y] == sum(self.model.LocalNewCapacity[l,t,yy] for yy in self.model.YEAR if ((y-yy < sum(self.model.OperationalLife[r,t] * self.model.Geography[r,l] for r in self.model.REGION)) and (y-yy >= 0)))

    def CA2_TotalNewCapacity_2_rule(self, model,r,t,y):
        '''
        *Constraint:* the accumulated new capacity available at each location is
        aggregated for each region.
        '''
        return self.model.AccumulatedNewCapacity[r,t,y] == sum(self.model.LocalAccumulatedNewCapacity[l,t,y] * self.model.Geography[r,l] for l in self.model.LOCATION)

    def CA3_TotalAnnualCapacity_1_rule(self, model,l,t,y):
        '''
        *Constraint:* add to CA1 any residual capacity of the same technology inherited
        from before the model period. From the addition of the accumulated new
        capacity and residual capacity in each year of the modeling period,
        the total annual capacity for each technology is determined. This is done
        for each location in the modeling period.
        '''
        return self.model.LocalAccumulatedNewCapacity[l,t,y] + self.model.LocalResidualCapacity[l,t,y] == self.model.LocalTotalCapacity[l,t,y]

    def CA4_TotalAnnualCapacity_2_rule(self, model,r,t,y):
        '''
        *Constraint:* the total capacity available at each location is
        aggregated for each region.
        '''
        return self.model.TotalCapacity[r,t,y] == sum(self.model.LocalTotalCapacity[l,t,y] * self.model.Geography[r,l] for l in self.model.LOCATION)

    def CA5_ConstraintCapacity_rule(self, model,l,t,y):
        '''
        *Constraint:* ensure that all technologies have enough capacity
        available to satisfy an overall yearly demand. Their annual
        production (rate of activity during any year) has to be less than
        their total available capacity multiplied by the fraction of the year
        for which the technology is available.
        '''
        return self.model.LocalActivity[l,t,y] <= self.model.LocalTotalCapacity[l,t,y] * sum(self.model.AvailabilityFactor[r,t,y] * self.model.CapacityToActivityUnit[r,t] * self.model.Geography[r,l] for r in self.model.REGION)

#    def CA5_ConstraintCapacity_rule(self, model,r,t,y):
#        '''
#        *Constraint:* ensure that all technologies have enough capacity
#        available to satisfy an overall yearly demand. Their annual
#        production (rate of activity during any year) has to be less than
#        their total available capacity multiplied by the fraction of the year
#        for which the technology is available.
#        '''
#        return self.model.Activity[r,t,y] <= self.model.TotalCapacity[r,t,y] * self.model.AvailabilityFactor[r,t,y] * self.model.CapacityToActivityUnit[r,t]

    # Mixed Integer Programming (MIP)
#    def CA6_TotalNewCapacity_rule(self, model,r,t,y):
#    	if self.model.CapacityOfOneTechnologyUnit != 0:
#    		return self.model.CapacityOfOneTechnologyUnit[r,t,y]*self.model.NumberOfNewTechnologyUnits[r,t,y] == self.model.NewCapacity[r,t,y]
#    	else:
#    		return Constraint.Skip

    #########	        Product Balance    	 	#############

    def PB1_Production_1_rule(self, model,l,p,t,m,y):
        '''
        *Constraint:* the production or output (of a `product`) for each technology,
        in each mode of operation is determined by multiplying the (rate of) activity
        to a product output vs. production activity ratio entered by the analyst.
        '''
        if self.model.ModeForTechnology[t,m] == 1 and self.model.ProductFromTechnology[t,p] == 1:
            return self.model.LocalProductionByMode[l,t,p,m,y] == self.model.LocalActivityByMode[l,t,m,y] * sum(self.model.OutputActivityRatio[r,t,p,m,y] * self.model.Geography[r,l] for r in self.model.REGION)
        else:
            return Constraint.Skip

    def PB2_Production_2_rule(self, model,l,p,t,y):
        '''
        *Constraint:* the production or output (of a `product`) for each technology
        is the sum of production in each operation mode.
        '''
        ModeOfOperation = [m for m in self.model.MODE_OF_OPERATION if self.model.ModeForTechnology[t,m]==1]
        if self.model.ProductFromTechnology[t,p] == 1:
            return self.model.LocalProductionByTechnology[l,t,p,y] == sum(self.model.LocalProductionByMode[l,t,p,m,y] for m in ModeOfOperation)
        else:
            return Constraint.Skip

    def PB3_Production_3_rule(self, model,l,p,y):
        '''
        *Constraint:* for each product, year and location, the production by each
        technology is added to determine the total local production of
        each product.
        '''
        RelevantTechnology = [t for t in self.model.TECHNOLOGY if self.model.ProductFromTechnology[t,p]==1]
        return self.model.LocalProduction[l,p,y] == sum(self.model.LocalProductionByTechnology[l,t,p,y] for t in RelevantTechnology)

    def PB4_Production_4_rule(self, model,r,p,y):
        '''
        *Constraint:* for each product, year and region, the production by each
        location is added to determine the total regional production of
        each product.
        '''
        return self.model.Production[r,p,y] == sum(self.model.LocalProduction[l,p,y] * self.model.Geography[r,l] for l in self.model.LOCATION)

#    def PB5_Production_5_rule(self, model,r,t,p,y):
#        '''
#        *Constraint:* for each technology, product, year and region, the production by each
#        location is added to determine the total regional production of
#        each product by technology.
#        '''
#        return self.model.ProductionByTechnology[r,t,p,y] == sum(self.model.LocalProductionByTechnology[l,t,p,y] * self.model.Geography[r,l] for l in self.model.LOCATION)

    def PB5_Use_1_rule(self, model,l,p,t,m,y):
        '''
        *Constraint:* the use or input (of a `product`) for each technology, in
        each mode of operation is determined by multiplying the (rate of) activity
        to a product input vs. production activity ratio entered by the analyst.
        '''
        if self.model.ModeForTechnology[t,m] == 1 and self.model.ProductToTechnology[t,p] == 1:
            return self.model.LocalUseByMode[l,t,p,m,y] == self.model.LocalActivityByMode[l,t,m,y] * sum(self.model.InputActivityRatio[r,t,p,m,y] * self.model.Geography[r,l] for r in self.model.REGION)
        else:
            return Constraint.Skip

    def PB6_Use_2_rule(self, model,l,p,t,y):
        '''
        *Constraint:* the use or input (of a `product`) for each technology
        is the sum of use in each operation mode.
        '''
        ModeOfOperation = [m for m in self.model.MODE_OF_OPERATION if self.model.ModeForTechnology[t,m]==1]
        if self.model.ProductToTechnology[t,p] == 1:
            return self.model.LocalUseByTechnology[l,t,p,y] == sum(self.model.LocalUseByMode[l,t,p,m,y] for m in ModeOfOperation)
        else:
            return Constraint.Skip

    def PB7_Use_3_rule(self, model,l,p,y):
        '''
        *Constraint:* for each product, year and location, the use by each
        technology is added to determine the total local use of each product.
        '''
        RelevantTechnology = [t for t in self.model.TECHNOLOGY if self.model.ProductToTechnology[t,p]==1]
        return self.model.LocalUse[l,p,y] == sum(self.model.LocalUseByTechnology[l,t,p,y] for t in RelevantTechnology)

    def PB8_Use_4_rule(self, model,r,p,y):
        '''
        *Constraint:* for each product, year and region, the use by each
        location is added to determine the total regional use of each product.
        '''
        return self.model.Use[r,p,y] == sum(self.model.LocalUse[l,p,y] * self.model.Geography[r,l] for l in self.model.LOCATION)

    def PB9_ProductBalance_rule(self, model,r,p,y):
        '''
        *Constraint:* for each product, in each year, and region the total production
        of each product + imports from locations outside the region - exports to
        locations outside the region should be larger than or equal to demand.
        '''
        return self.model.Production[r,p,y] + self.model.Import[r,p,y] - self.model.Export[r,p,y] >= self.model.Demand[r,p,y]

    #########        	Transport flows		 	#############

    def TF1_Transport_1_rule(self, model,l,ll,p,tr,y):
        '''
        *Constraint:* for each product, each transport mode, in each year,
        transport from location l to location ll is either smaller or equal to the transport
        link capacity if a transport route exists, or 0 if there is no route.
        '''
        if self.model.TransportRoute[l,ll,p,tr,y] == 1:
            return self.model.Transport[l,ll,p,tr,y] + self.model.Transport[ll,l,p,tr,y] <= self.model.TransportCapacity[l,ll,p,tr,y] * self.model.TransportCapacityToActivity[tr]
        else:
            return Constraint.Skip

    def TF2_Transport_2_rule(self, model,l,p,y):
        '''
        *Constraint:* for each product, at each (origin) location, in each year, the total
        quantity of product transported to other locations is equal to the
        production at the (origin) location. If there is no transport link at all
        departing from the (origin) location, the constraint is skipped.
        '''
        return sum(sum(self.model.Transport[l,ll,p,tr,y] for tr in [trm for trm in self.model.TRANSPORTMODE if self.model.TransportRoute[l,ll,p,trm,y]==1]) for ll in self.model.LOCATION) <= self.model.LocalProduction[l,p,y]

    def TF3_Transport_3_rule(self, model,l,p,y):
        '''
        *Constraint:* for each product, at each (destination) location, in each year, the total
        quantity of product transported from other locations equal to the use
        at the (destination) location. If there is no transport link at all
        arriving to the (destination) location, the constraint is skipped.
        '''
        return sum(sum(self.model.Transport[ll,l,p,tr,y] for tr in [trm for trm in self.model.TRANSPORTMODE if self.model.TransportRoute[ll,l,p,trm,y]==1]) for ll in self.model.LOCATION) == self.model.LocalUse[l,p,y]

    def TF4_Imports_rule(self, model,r,p,y):
        '''
        *Constraint:* for each product and region, the imports to that region
        are the sum of the transport flows from locations outside that region
        to locations in that region.
        '''
        return self.model.Import[r,p,y] == sum(sum(sum(self.model.Transport[ll,l,p,tr,y] * (1 - self.model.Geography[r,ll]) for tr in [trm for trm in self.model.TRANSPORTMODE if self.model.TransportRoute[ll,l,p,trm,y]==1]) for ll in self.model.LOCATION) * self.model.Geography[r,l] for l in self.model.LOCATION)

    def TF5_Exports_rule(self, model,r,p,y):
        '''
        *Constraint:* for each product and region, the imports to that region
        are the sum of the transport flows from locations outside that region
        to locations in that region.
        '''
        return self.model.Export[r,p,y] == sum(sum(sum(self.model.Transport[l,ll,p,tr,y] * (1 - self.model.Geography[r,ll]) for tr in [trm for trm in self.model.TRANSPORTMODE if self.model.TransportRoute[l,ll,p,trm,y]==1]) for ll in self.model.LOCATION) * self.model.Geography[r,l] for l in self.model.LOCATION)

    #########       	Capital Costs 		     	#############

    def CC1_UndiscountedCapitalInvestment_rule(self, model,l,t,y):
        '''
        *Constraint:* investments (how much of what type of technology when)
        are calculated on an annual basis for each location, and are assumed to
        be commissioned and available at the beginning of the year.
        The investment expenditures are determined by the level of new capacity
        invested in multiplied by a per-unit capital cost known to the analyst.
        '''
        return self.model.LocalCapitalInvestment[l,t,y] == sum(self.model.CapitalCost[r,t,y] * self.model.Geography[r,l] for r in self.model.REGION) * self.model.LocalNewCapacity[l,t,y]

    def CC2_DiscountedCapitalInvestment_1_rule(self, model,l,t,y):
        '''
        *Constraint:* investment cost is discounted back to the first year modeled.
        That is done, either using either a technology-specific or global discount
        rate applied to the beginning of the year in which the technology is available.
        '''
        return self.model.LocalDiscountedCapitalInvestment[l,t,y] == self.model.LocalCapitalInvestment[l,t,y] / ((1 + sum(self.model.DiscountRate[r] * self.model.Geography[r,l] for r in self.model.REGION))**(y - min(self.model.YEAR)))

    def CC3_DiscountedCapitalInvestment_2_rule(self, model,r,t,y):
        '''
        *Constraint:* the investments at each location are added to determine
        the total regional investments in each technology.
        '''
        return self.model.DiscountedCapitalInvestment[r,t,y] == sum(self.model.LocalDiscountedCapitalInvestment[l,t,y] * self.model.Geography[r,l] for l in self.model.LOCATION)

    #########           Salvage Value            	#############

    def SV1_SalvageValueAtEndOfPeriod_rule(self, model,r,t,y):
        '''
        *Constraint:* salvage value is determined regionally, based on
        the technology’s operational life, its year of investment and discount rate.
        '''
        if (self.model.DepreciationMethod[r] == 1) and ((y + self.model.TimeStep[y]/2 + self.model.OperationalLife[r,t] - 1) > (max(self.model.YEAR) + self.model.TimeStep[max(self.model.YEAR)]/2)) and (self.model.DiscountRate[r] > 0):
            return self.model.SalvageValue[r,t,y] == self.model.CapitalCost[r,t,y] * self.model.NewCapacity[r,t,y] * (1 - (((1 + self.model.DiscountRate[r])**(max(self.model.YEAR) + self.model.TimeStep[max(self.model.YEAR)]/2 - (y - self.model.TimeStep[y]/2 +1) + 1) - 1) / ((1 + self.model.DiscountRate[r])**self.model.OperationalLife[r,t] - 1)))
        elif (self.model.DepreciationMethod[r] == 1 and ((y + self.model.TimeStep[y]/2 + self.model.OperationalLife[r,t] - 1) > (max(self.model.YEAR) + self.model.TimeStep[max(self.model.YEAR)]/2)) and self.model.DiscountRate[r] == 0) or (self.model.DepreciationMethod[r] == 2 and ((y + self.model.TimeStep[y]/2 + self.model.OperationalLife[r,t] - 1) > (max(self.model.YEAR) + self.model.TimeStep[max(self.model.YEAR)]/2))):
            return self.model.SalvageValue[r,t,y] == self.model.CapitalCost[r,t,y] * self.model.NewCapacity[r,t,y] * (1 - (max(self.model.YEAR) - y + 1) / self.model.OperationalLife[r,t])
        else:
            return self.model.SalvageValue[r,t,y] == 0

    def SV2_SalvageValueDiscountedToStartYear_rule(self, model,r,t,y):
        '''
        *Constraint:* the salvage value is discounted to the beginning of the
        first model year by a discount rate applied over the modeling period.
        '''
        return self.model.DiscountedSalvageValue[r,t,y] == self.model.SalvageValue[r,t,y] / ((1 + self.model.DiscountRate[r])**(1 + max(self.model.YEAR) + self.model.TimeStep[max(self.model.YEAR)]/2 - (min(self.model.YEAR) - self.model.TimeStep[min(self.model.YEAR)]/2 +1)))

    #########        	Operating Costs 		 	#############

    def OC1_OperatingCostsVariable_rule(self, model,l,t,y):
        '''
        *Constraint*: for each location, technology, and year the variable cost
        is a function of the rate of activity of each technology and a per-unit
        cost defined by the analyst.
        '''
        ModeOfOperation = [m for m in self.model.MODE_OF_OPERATION if self.model.ModeForTechnology[t,m]==1]
        return self.model.LocalVariableOperatingCost[l,t,y] == sum(self.model.LocalActivityByMode[l,t,m,y] * sum(self.model.VariableCost[r,t,m,y] * self.model.Geography[r,l] for r in self.model.REGION) for m in ModeOfOperation)

    def OC2_OperatingCostsFixedAnnual_rule(self, model,l,t,y):
        '''
        *Constraint*: for each location, technology, and year the annual fixed
        operating cost is calculated by multiplying the total installed capacity
        of a technology with a per-unit cost defined by the analyst.
        '''
        return self.model.LocalFixedOperatingCost[l,t,y] == self.model.LocalTotalCapacity[l,t,y] * sum(self.model.FixedCost[r,t,y] * self.model.Geography[r,l] for r in self.model.REGION)

    def OC3_OperatingCostsTotalAnnual_rule(self, model,l,t,y):
        '''
        *Constraint:* the total annual operating cost is the sum of the fixed
        and variable costs.
        '''
        return self.model.LocalOperatingCost[l,t,y] == self.model.LocalFixedOperatingCost[l,t,y] + self.model.LocalVariableOperatingCost[l,t,y]

    def OC4_DiscountedOperatingCostsTotalAnnual_1_rule(self, model,l,t,y):
        '''
        *Constraint:* total operating cost is discounted back to the first year
        modeled. That is done, using either a technology-specific or a global
        discount rate applied to the middle of the year in which the costs are
        incurred.
        '''
        return self.model.LocalDiscountedOperatingCost[l,t,y] == self.model.LocalOperatingCost[l,t,y] / ((1 + sum(self.model.DiscountRate[r] * self.model.Geography[r,l] for r in self.model.REGION))**(1 + y - (min(self.model.YEAR) - self.model.TimeStep[min(self.model.YEAR)]/2 +1)))

    def OC5_DiscountedOperatingCostsTotalAnnual_2_rule(self, model,r,t,y):
        '''
        *Constraint:* total operating cost is discounted back to the first year
        modeled. That is done, using either a technology-specific or a global
        discount rate applied to the middle of the year in which the costs are
        incurred.
        '''
        return self.model.DiscountedOperatingCost[r,t,y] == sum(self.model.LocalDiscountedOperatingCost[l,t,y] * self.model.Geography[r,l] for l in self.model.LOCATION)

    #########       	Transport Costs	 	#############

    def TC1_LocalTransportCosts_rule(self, model,l,p,y):
        '''
        *Constraint:* for each product, at each location, in each year, the total
        cost of transporting the produced product FROM other locations (i.e. cost
        of imports) is the sum of the quantities transported per mode of transport
        multiplied by the specific costs of each mode of transport.
        '''
        return self.model.LocalTransportCost[l,p,y] == sum(sum(self.model.Transport[ll,l,p,tr,y] * sum(self.model.TransportCostByMode[r,tr,y] * self.model.Geography[r,l] for r in self.model.REGION) for tr in [trm for trm in self.model.TRANSPORTMODE if self.model.TransportRoute[ll,l,p,trm,y]==1]) for ll in self.model.LOCATION)

    def TC2_DiscountedLocalTransportCosts_rule(self, model,l,p,y):
        '''
        *Constraint:* local transport cost is discounted back to the first year
        modeled. That is done, using either a technology-specific or a global
        discount rate applied to the middle of the year in which the costs are
        incurred.
        '''
        return self.model.LocalDiscountedTransportCost[l,p,y] == self.model.LocalTransportCost[l,p,y] / ((1 + sum(self.model.DiscountRate[r] * self.model.Geography[r,l] for r in self.model.REGION))**(1 + y - (min(self.model.YEAR) - self.model.TimeStep[min(self.model.YEAR)]/2 +1)))

    def TC3_DiscountedTransportCostsByProduct_rule(self, model,r,p,y):
        '''
        *Constraint:* for each region, product and year, the total costs of transport
        is the sum of the transport costs at each location. These transport costs
        include both intra-regional transport AND imports from other regions.
        '''
        return self.model.DiscountedTransportCostByProduct[r,p,y] == sum(self.model.LocalDiscountedTransportCost[l,p,y] * self.model.Geography[r,l] for l in self.model.LOCATION)

    def TC4_DiscountedTransportCostsTotalAnnual_rule(self, model,r,y):
        '''
        *Constraint:* for each region and year, transport costs by product are added
        to determine total transport costs towards and within this region.
        '''
        return self.model.DiscountedTransportCost[r,y] == sum(self.model.DiscountedTransportCostByProduct[r,p,y] for p in self.model.PRODUCT)

    #########       	Total Discounted Costs	 	#############

    def TDC1_TotalDiscountedCostByTechnology_rule(self, model,r,t,y):
        '''
        *Constraint:* for each region and year, total discounted costs are the
        sum for each technology of investment and operating costs, minus salvage
        costs, to which transport costs for the region are added.
        '''
        return  self.model.TotalDiscountedCost[r,y] == sum(self.model.DiscountedOperatingCost[r,t,y] + self.model.DiscountedCapitalInvestment[r,t,y] + self.model.DiscountedTechnologyEmissionsPenalty[r,t,y] - self.model.DiscountedSalvageValue[r,t,y] for t in self.model.TECHNOLOGY) + self.model.DiscountedTransportCost[r,y]

    def TDC2_ModelPeriodCostByRegion_rule(self, model,r):
        '''
        *Constraint:* total discounted costs are added for each year over the
        modelling period.
        '''
        return self.model.ModelPeriodCostByRegion[r] == sum(self.model.TotalDiscountedCost[r,y] for y in self.model.YEAR)

    def TDC3_ModelPeriodCost_rule(self, model):
        '''
        *Constraint:* discounted model period costs are added for each region.
        '''
        return self.model.ModelPeriodCost == sum(self.model.ModelPeriodCostByRegion[r] for r in self.model.REGION)

    #########      		Total Capacity Constraints 	##############

    def TCC1_TotalAnnualMaxCapacityConstraint_rule(self, model,r,t,y):
        '''
        *Constraint:* there can be a maximum limit on the total capacity of a
        particular technology allowed in a particular year and region.
        '''
        return self.model.TotalCapacity[r,t,y] <= self.model.TotalAnnualMaxCapacity[r,t,y]

    def TCC2_TotalAnnualMinCapacityConstraint_rule(self, model,r,t,y):
        '''
        *Constraint:* there can be a mainimu limit on the total capacity of a
        particular technology allowed in a particular year and region.
        '''
        return self.model.TotalCapacity[r,t,y] >= self.model.TotalAnnualMinCapacity[r,t,y]

    #########    		New Capacity Constraints  	##############

    def NCC1_LocalTotalAnnualMaxNewCapacityConstraint_rule(self, model,l,t,y):
        '''
        *Constraint:* there can be a maximum new capacity investment limit placed
        on a particular technology per year and region.
        '''
        return self.model.LocalNewCapacity[l,t,y] <= self.model.LocalTotalAnnualMaxCapacityInvestment[l,t,y]

    def NCC2_LocalTotalAnnualMinNewCapacityConstraint_rule(self, model,l,t,y):
        '''
        *Constraint:* there can be a minimum new capacity investment limit placed
        on a particular technology per year and region.
        '''
        return self.model.LocalNewCapacity[l,t,y] >= self.model.LocalTotalAnnualMinCapacityInvestment[l,t,y]

    #########   		Annual Activity Constraints	##############

    def AAC0_LocalAnnualTechnologyActivity_rule(self, model,l,t,y):
        '''
        *Constraint:* the total activity of a technology for each year in a location
        is the sum of the local activities by mode of operation.
        '''
        ModeOfOperation = [m for m in self.model.MODE_OF_OPERATION if self.model.ModeForTechnology[t,m]==1]
        return self.model.LocalActivity[l,t,y] == sum(self.model.LocalActivityByMode[l,t,m,y] for m in ModeOfOperation)

    def AAC1_TotalAnnualTechnologyActivity_rule(self, model,r,t,y):
        '''
        *Constraint:* the total activity of a technology for each year in a region
        is the sum of the local activities in that region.
        '''
        return self.model.Activity[r,t,y] == sum(self.model.LocalActivity[l,t,y] * self.model.Geography[r,l] for l in self.model.LOCATION)

    def AAC2_TotalAnnualTechnologyActivityUpperLimit_rule(self, model,r,t,y):
        '''
        *Constraint:* where specified, a maximum annual limit may be placed
        on the annual activity of a technology in a region.
        '''
        return self.model.Activity[r,t,y] <= self.model.TotalTechnologyAnnualActivityUpperLimit[r,t,y]

    def AAC3_TotalAnnualTechnologyActivityLowerLimit_rule(self, model,r,t,y):
        '''
        *Constraint:* where specified, a minimum annual limit may be placed
        on the annual activity of a technology in a region.
        '''
        return self.model.Activity[r,t,y] >= self.model.TotalTechnologyAnnualActivityLowerLimit[r,t,y]

#    def AAC4_TotalAnnualTechnologyProductionLowerLimit_rule(self, model,r,t,p,y):
#        '''
#        *Constraint:* where specified, a minimum annual limit may be placed
#        on the annual production of a technology, for a given product in a region.
#        '''
#        return self.model.ProductionByTechnology[r,t,p,y] >= self.model.TotalTechnologyAnnualProductionLowerLimit[r,t,p,y]

    #########    		Total Activity Constraints 	##############

    def TAC1_TotalModelHorizonTechnologyActivity_rule(self, model,r,t):
        '''
        *Constraint:* the model period activity of each technology is obtained
        by summing the total annual activity of each technology for each year
        for each region.
        '''
        return self.model.ModelPeriodActivity[r,t] == sum(self.model.Activity[r,t,y] for y in self.model.YEAR)

    def TAC2_TotalModelHorizonTechnologyActivityUpperLimit_rule(self, model,r,t):
        '''
        *Constraint:* where specified, a maximum limit may be placed on the
        model period activity of a technology.
        '''
        return self.model.ModelPeriodActivity[r,t] <= self.model.TotalTechnologyModelPeriodActivityUpperLimit[r,t]

    def TAC3_TotalModelHorizonTechnologyActivityLowerLimit_rule(self, model,r,t):
        '''
        *Constraint:* where specified, a minimum limit may be placed on the
        model period activity of a technology.
        '''
        return self.model.ModelPeriodActivity[r,t] >= self.model.TotalTechnologyModelPeriodActivityLowerLimit[r,t]

    #########   		Emissions Accounting		##############

    def E1_LocalEmissionProductionByMode_rule(self, model,l,t,e,m,y):
        '''
        *Constraint:* for each location, technology, emission type, operation mode
        and year the emission quantity is a function of the rate of activity of
        each technology and a per-unit emission factor defined by the analyst.
        '''
        if self.model.ModeForTechnology[t,m] == 1:
            if sum(self.model.EmissionActivityRatio[r,t,e,m,y] * self.model.Geography[r,l] for r in self.model.REGION) > 0:
                return self.model.LocalTechnologyEmissionByMode[l,t,e,m,y] == self.model.LocalActivityByMode[l,t,m,y] * sum(self.model.EmissionActivityRatio[r,t,e,m,y] * self.model.Geography[r,l] for r in self.model.REGION)
            else:
                return self.model.LocalTechnologyEmissionByMode[l,t,e,m,y] == 0
        else:
            return Constraint.Skip

    def E2_LocalEmissionProduction_rule(self, model,l,t,e,y):
        '''
        *Constraint: for each location, technology, emission type, and year total
        emissions are the sum of emissions in each operation mode.*
        '''
        ModeOfOperation = [m for m in self.model.MODE_OF_OPERATION if self.model.ModeForTechnology[t,m]==1]
        return self.model.LocalTechnologyEmission[l,t,e,y] == sum(self.model.LocalTechnologyEmissionByMode[l,t,e,m,y] for m in ModeOfOperation)

    def E3_AnnualEmissionProduction_rule(self, model,r,t,e,y):
        '''
        *Constraint:* for each region, technology, emission type, and year total
        emissions are the sum of emissions in each location.
        '''
        return self.model.AnnualTechnologyEmission[r,t,e,y] == sum(self.model.LocalTechnologyEmission[l,t,e,y] * self.model.Geography[r,l] for l in self.model.LOCATION)

    def E4_EmissionPenaltyByTechAndEmission_rule(self, model,r,t,e,y):
        '''
        *Constraint:* for each region, technology, emission type, and year there is
        an emission penalty associated with the quantity of emissions.
        '''
        return self.model.AnnualTechnologyEmissionPenaltyByEmission[r,t,e,y] == self.model.AnnualTechnologyEmission[r,t,e,y] * self.model.EmissionsPenalty[r,e,y]

    def E5_EmissionsPenaltyByTechnology_rule(self, model,r,t,y):
        '''
        *Constraint:* for each location, technology, and year the total emission
        penalty is the sum of emission penalties for each emission type.
        '''
        return self.model.AnnualTechnologyEmissionsPenalty[r,t,y] == sum(self.model.AnnualTechnologyEmissionPenaltyByEmission[r,t,e,y] for e in self.model.EMISSION)

    def E6_DiscountedEmissionsPenaltyByTechnology_rule(self, model,r,t,y):
        '''
        *Constraint:* emission penalties are discounted back to the first year
        modeled. That is done, using either a technology-specific or a global
        discount rate applied to the middle of the year in which the costs are
        incurred.
        '''
        return self.model.DiscountedTechnologyEmissionsPenalty[r,t,y] == self.model.AnnualTechnologyEmissionsPenalty[r,t,y] / ((1 + self.model.DiscountRate[r])**(1 + y - (min(self.model.YEAR) - self.model.TimeStep[min(self.model.YEAR)]/2 +1)))

    def E7_EmissionsAccounting1_rule(self, model,r,e,y):
        '''
        *Constraint:* for each region, emission type, and year total emissions
        are the sum of emissions from each technology.
        '''
        return self.model.AnnualEmissions[r,e,y] == sum(self.model.AnnualTechnologyEmission[r,t,e,y] for t in self.model.TECHNOLOGY)

    def E8_EmissionsAccounting2_rule(self, model,r,e):
        '''
        *Constraint:* for each region and emission type total emissions over the
        whole modelling period is the sum of all technology emissions plus
        exogenous emissions entered by the analyst.
        '''
        return self.model.ModelPeriodEmissions[r,e] == sum(self.model.AnnualEmissions[r,e,y] for y in self.model.YEAR) + self.model.ModelPeriodExogenousEmission[r,e]

    def E9_AnnualEmissionsLimit_rule(self, model,r,e,y):
        '''
        *Constraint:* for each region, emission type, and year total emissions
        should be lower than the emission limit entered by the analyst.
        '''
        return self.model.AnnualEmissions[r,e,y] + self.model.AnnualExogenousEmission[r,e,y] <= self.model.AnnualEmissionLimit[r,e,y]

    def E10_ModelPeriodEmissionsLimit_rule(self, model,r,e):
        '''
        *Constraint:* for each region and emission type total emissions over the
        whole emission period should be lower than the emission limit entered by
        the analyst.
        '''
        return self.model.ModelPeriodEmissions[r,e] <= self.model.ModelPeriodEmissionLimit[r,e]

    #############################
    # Initialize abstract model #
    #############################

    def load_data(self):
        '''
        Loads input data for Sets and Params from csv files into a Pyomo DataPortal.

        This method is pretty verbose, that is it checks for each Set and Param of
        the abstract model if a csv file with the same name and .csv extension exists
        at InputPath. If no such file exists, it warns the user that default values
        will be used.

        No csv file at all (incl. no empty file or with header only) should be provided
        for the Sets and Params for which the user wishes to use default values. If you
        do Pyomo will throw an error indicating that it cannot initialize the
        corresponding Set or Param.

        *Arguments:*
            None
        *Returns:*
            None
        '''
        # SETS
        # Get a dict of the abstract's model Set names (key) and Set objects (value)
        # The condition is to remove the param with e.g. _index_index_0 from the list
        ModelSets = {s.name:s for  s in self.model.component_objects(Set, descend_into=True) if 'index' not in s.name}
        # If there is a csv file at location InputPath with the same name as the Set, load the data
        print('\n####################################')
        print('\nInitializing Sets of abstract model...')
        for set_name, set_object in ModelSets.items():
            if os.path.isfile(os.path.join(self.InputPath, set_name + '.csv')):
                self.data.load(filename=os.path.join(self.InputPath, set_name + '.csv'), set=set_object)
            else:
                print('\nCannot find file <' + os.path.join(self.InputPath, set_name + '.csv') + '>. Using default values instead.')

        # PARAMETERS
        # Get a list of the abstract's model param names
        ModelParams = {p.name:p for  p in self.model.component_objects(Param, descend_into=True)}
        # If there is a csv file at location InputPath with the same name as the Param, load the data
        print('\n####################################')
        print('\nInitializing Params of abstract model...')
        for param_name, param_object in ModelParams.items():
            if os.path.isfile(os.path.join(self.InputPath, param_name + '.csv')):
                print(os.path.join(self.InputPath, param_name + '.csv'))
                self.data.load(filename=os.path.join(self.InputPath, param_name + '.csv'), param=param_object)
            else:
                print('\nCannot find file <' + os.path.join(self.InputPath, param_name + '.csv') + '>. Using default values instead.')


##############################################################################
##############################################################################

class concrete_itom(object):
    '''
    Class providing methods to instantiate a concrete model from an abstract ITOM
    model, solve it and export results using Pyomo.

    **Constructor arguments:**
        *AbstractModel: abstract_itom object*
            Instance of the abstract_OSeMOSYS class.
        *InputFile [optional]: string*
            Path (incl. file name) to a .dat input data file in AMPL format.
        *OutputPath [optional]: string*
            Path to directory where all variables ca be saved as csv files after
            solving the model. Default: None.
        *OutputCode [optional]: string*
            Short string that will be appended at the beginning of the csv file names
            when exporting variables (useful if one wants to save different model
            runs in the same output directory). Also used as the name of the ConcreteModel
            instance. Default: None.
        *Solver [optional]: string*
            Name of the solver that will be passed to the function pyomo.opt.SolverFactory.
            Default: 'glpk'

    **Public class attributes:**
        *instance: Pyomo ConcreteModel object*
            Instantiated model built from OSeMOSYSAbstractModel.model AbstractModel object.
            Parameter values are supplied via the AMPL InputFile if provided or via the
            OSeMOSYSAbstractModel.data DataPortal object (loaded with input data from csv files).
        *OptSolver: Pyomo SolverFactory object*
            Solver object obtained from pyomo.opt.SolverFactory(Solver) where 'Solver'
            is 'glpk' by default.
        *results: Pyomo results object*
            Result object returned by OptSolver.solve().
        *OutputPath: string*
            Path to directory where all variables ca be saved as csv files after
            solving the model.
        *OutputCode: string*
            Short string that will be appended at the beginning of the csv file names
            when exporting variables (useful if one wants to save different model
            runs in the same output directory). Also used as the name of the ConcreteModel
            instance.
    '''
    def __init__(self, AbstractModel, InputFile=None, OutputPath=None, OutputCode=None, Solver='glpk'):

        print('\n####################################')
        print('\nBuilding a concrete model...')

        # Path to directory where to export variables as csv files (optional)
        self.OutputPath = OutputPath
        # Code that will be inserted before the variable name when exporting variables to csv
        # (useful if you want to export results of different model runs to the same directory)
        # It is also used to name concrete model instances
        self.OutputCode = OutputCode

        # Select LP solver
        self.OptSolver = SolverFactory(Solver)
        # Create a concrete model instance
        # If an input file (*.dat) is provided, use it, otherwise assume that
        # input data have been loaded in a pyomo DataPortal for the abstract model
        if InputFile is not None:
            self.instance = AbstractModel.model.create_instance(InputFile)
            self.instance.name = OutputCode
        else:
            self.instance = AbstractModel.model.create_instance(
                AbstractModel.data)
            self.instance.name = OutputCode

    ###########
    # METHODS #
    ###########

    def solve_model(self, keepfiles=False, keeplog=True):
        '''
        Calls the solver on the initialised concrete model.

        This method instantiates the public attribute 'results' and prints it out.

        *Arguments:*
            None
        *Returns:*
            None
        '''
        print('\n####################################')
        if self.instance.name is not None:
            print('\nModel: ' + self.instance.name)
        print('\nSolving concrete model...')
        if keepfiles:
            logfile_name = self.instance.name + "_gurobi.log"
            self.results = self.OptSolver.solve(self.instance, keepfiles=True, logfile=logfile_name)
        elif keeplog:
            logfile_name = self.instance.name + "_gurobi.log"
            self.results = self.OptSolver.solve(self.instance, logfile=logfile_name)
        else:
            self.results = self.OptSolver.solve(self.instance)
        print('\nResults:')
        print(self.results)

    def export_results(self):
        '''
        Saves the results summary to a text file at the provided OutputPath.

        *Arguments:*
            None
        *Returns:*
            None
        '''
#        self.instance.write(os.path.join(self.OutputPath, 'results.txt'),
#                                         io_options={'symbolic_solver_labels':True})


    def export_lp_problem(self):
        '''
        Saves the LP problem equations to a text file at the provided OutputPath.

        *Arguments:*
            None
        *Returns:*
            None
        '''
        self.instance.write(os.path.join(self.OutputPath, 'problem.lp'),
                                         io_options={'symbolic_solver_labels':True})

    def export_all_var(self):
        '''
        Exports all variables to csv files in the directory provided
        with OutputPath.

        OutputPath should exist, otherwise the function will crash.
        If OutputPath exists and is not empty, existing csv files may be silently overwritten.
        OutputCode, if provided, is appended at the beginning of the csv file names
        (useful if one wants to save different model runs in the same output directory).

        The csv files are structured as follows:
            * header: comma separated names of sets making of the index of
              the variable + variable name at the end of the row
            * values: comma separated set values + variable value at the end of the row

        *Examples:*

            - variable with one set in index:

                | REGION,ModelPeriodCostByRegion
                | DE,1243122.6263322

            - variable with multiple sets in index:

                | REGION,TECHNOLOGY,YEAR,DiscountedCapitalInvestment
                | DE,PP_NG_CC,2048,0.0
                | DE,PP_NG_CC,2049,0.0
                | DE,PP_NG_CC,2050,0.0
                | ...

        *Arguments:*
            None
        *Returns:*
            None
        '''
        # Export all active variables
        for variable in self.instance.component_objects(Var, active=True):

            if self.OutputCode is not None:
                csv_file = open(os.path.join(self.OutputPath, self.OutputCode + '_' + variable.name + '.csv'), 'w')
            else:
                csv_file = open(os.path.join(self.OutputPath, variable.name + '.csv'), 'w')

            # '_implicit_subsets' is an attribute of the pyomo's IndexedComponent
            # class (parent class of Var class). It is a temporary data element that
            # stores sets that are transfered to the model. We use it here to get the
            # names of the set to use in the csv file's header.
            subsets = getattr(variable, '_implicit_subsets')
            # No index or index made of one set only => subsets is None
            # Index made of at least two sets => subsets is not None

            # At least two subsets
            if subsets is not None:
                header = ''
                for subset in subsets:
                    header = header + subset.name + ","
                header = header + variable.name + "\n"
                csv_file.write(header)
                for index in variable:
                    row = ''
                    for item in index:
                        row = row + str(item) + ','
                    row = row + str(value(variable[index])) + "\n"
                    csv_file.write(row)

            #index_obj = getattr(variable, '_index')
            #if len(index_obj) > 1:

            # 0 or 1 subset
            else:
                # IndexedComponent's method dim() returns the dimension of the index
                # Index made of only one set
                if variable.dim() == 1:
                    header = ''
                    #header = header + variable._index.name + "," + variable.name + "\n"
                    # Attribute _index of Var object is deprecated, use _index_set instead.
                    header = header + str(variable._index_set) + "," + variable.name + "\n"
                    csv_file.write(header)
                    for index in variable:
                        row = ''
                        row = row + str(index) + ','
                        row = row + str(value(variable[index])) + "\n"
                        csv_file.write(row)
                # No index
                if variable.dim() == 0:
                    header = ''
                    header = header + variable.name + "\n"
                    csv_file.write(header)
                    for index in variable:
                        row = ''
                        row = row + str(value(variable)) + "\n"
                        csv_file.write(row)

            csv_file.close()
