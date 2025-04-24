#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
This module defines:

	- the `itom_hub_retrofit_tinyomo` class that extends the class `itom_hub_tinyomo`
	  which replaces a Pyomo ABSTRACT and CONCRETE model definition using classes from tinyomo

@author: mathieusa
'''

__all__ = ('itom_hub_retrofit_tinyomo')

from tinyomo import Set, Param, Vars, Var, Constraints, Constraint
from tinyomo import NonNegativeReals

from itom_hub_tinyomo import itom_hub_tinyomo

class itom_hub_retrofit_tinyomo(itom_hub_tinyomo):
	"""
	Subclass of ITOM Hub including retrofit capabilities.
	"""

	def __init__(self, InputPath=None, OutputPath=None, config=None):

		super().__init__(InputPath=InputPath, OutputPath=OutputPath, config=config)

		###############
		#    Sets     #
		###############

		# Object containing info on all Sets

		# Do not remove or rename these sets, they are copies of the TECHNOLOGY set
		# to differentiate between "technology current" (TECHNOLOGY_1) and "technology retrofit" (TECHNOLOGY_2)
		self.TECHNOLOGY_1 = Set(SetName='TECHNOLOGY_1', SetsGroup=self.AllSets)
		self.TECHNOLOGY_2 = Set(SetName='TECHNOLOGY_2', SetsGroup=self.AllSets)

		##############
		# Parameters #
		##############

		self.RetrofitTechnology = Param(self.TECHNOLOGY, default=0, ParamsGroup=self.AllParams,
										ParamName='RetrofitTechnology')
		self.TechnologyToRetrofit = Param(self.TECHNOLOGY, default=0, ParamsGroup=self.AllParams,
										  ParamName='TechnologyToRetrofit')
		self.MatchTechnologyRetrofit = Param(self.TECHNOLOGY, self.TECHNOLOGY, default=0, ParamsGroup=self.AllParams,
											 ParamName='MatchTechnologyRetrofit')

		#############
		# Variables #
		#############

		self.PotentialRetrofitFromResidual = Var(self.LOCATION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals,
												 initialize=0.0, VarsGroup=self.AllVars, VarName='PotentialRetrofitFromResidual')
		self.PotentialRetrofitFromNew = Var(self.LOCATION, self.TECHNOLOGY, self.YEAR, domain=NonNegativeReals,
											initialize=0.0, VarsGroup=self.AllVars, VarName='PotentialRetrofitFromNew')

		###############
		# Constraints #
		###############

		self.R1_RetrofitPotentialFromResidualCapacity = Constraint(self.LOCATION, self.TECHNOLOGY, self.YEAR,
																   rule=self.R1_RetrofitPotentialFromResidualCapacity_rule,
																   ConsGroup=self.AllCons,
																   ConsName='R1_RetrofitPotentialFromResidualCapacity')
		self.R2_RetrofitPotentialFromNewCapacity = Constraint(self.LOCATION, self.TECHNOLOGY, self.YEAR,
															  rule=self.R2_RetrofitPotentialFromNewCapacity_rule,
															  ConsGroup=self.AllCons,
															  ConsName='R2_RetrofitPotentialFromNewCapacity')
		self.R3_RetrofitCapacityConstraint = Constraint(self.LOCATION, self.TECHNOLOGY, self.YEAR,
														rule=self.R3_RetrofitCapacityConstraint_rule,
														ConsGroup=self.AllCons,
														ConsName='R3_RetrofitCapacityConstraint')

	###########
	# METHODS #
	###########

	###############
	# Constraints #
	###############

	#########       	Retrofitting	     	#############

	def R1_RetrofitPotentialFromResidualCapacity_rule(self, l, t, y):
		"""
		*Constraint:* retrofit capacity potential is given by the residual
		capacity of technologies allowed to be retrofitted reaching their
		end-of-life in any given year.

		PotentialRetrofitFromResidual(l, t, y) == LocalResidualCapacity(l, t, y - TimeStep(y)) - LocalResidualCapacity(l, t, y)

		PotentialRetrofitFromResidual(l, t, y) == 0
		"""
		if (self.HubLocation.get_value(l) == 1) or (y == min(self.YEAR.data.VALUE)) or (self.TechnologyToRetrofit.get_value(t) == 0):
			return None
		else:
			if self.LocalResidualCapacity.get_value(l, t, y - self.TimeStep.get_value(y)) - self.LocalResidualCapacity.get_value(
				l, t, y) > 0:
				lhs = [(1, self.PotentialRetrofitFromResidual.get_index_label(l, t, y))]
				rhs = (self.LocalResidualCapacity.get_value(l, t, y - self.TimeStep.get_value(y)) -
					   self.LocalResidualCapacity.get_value(l, t, y))
				sense = '=='
				return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
			else:
				lhs = [(1, self.PotentialRetrofitFromResidual.get_index_label(l, t, y))]
				rhs = 0
				sense = '=='
				return {'lhs': lhs, 'rhs': rhs, 'sense': sense}


	def R2_RetrofitPotentialFromNewCapacity_rule(self, l, t, y):
		"""
		*Constraint:* retrofit capacity potential is given by the accumulated
		new capacity of technologies allowed to be retrofitted reaching their
		end-of-life in any given year.

		PotentialRetrofitFromNew(l, t, y) == sum(LocalNewCapacity(l, t, yy) for yy in YEAR if (y - yy == sum(
					OperationalLife(r, t) * Geography(r, l) for r in REGION)) and (y - yy > 0))
		"""

		if (self.HubLocation.get_value(l) == 1) or (y == min(self.YEAR.data.VALUE)) or (self.TechnologyToRetrofit.get_value(t) == 0):
			return None
		else:
			lhs =  [(1, self.PotentialRetrofitFromNew.get_index_label(l, t, y)),
					(-1, [self.LocalNewCapacity.get_index_label(l, t, yy) for yy in self.YEAR.data.VALUE if (y - yy == sum(
					self.OperationalLife.get_value(r, t) * self.Geography.get_value(r, l) for r in self.REGION.data.VALUE)) and (
							y - yy > 0)])]
			rhs = 0
			sense = '=='
			return {'lhs': lhs, 'rhs': rhs, 'sense': sense}


	def R3_RetrofitCapacityConstraint_rule(self, l, t, y):
		"""
		*Constraint:* retrofit capacity is constrained by the installed capacity
		of technologies allowed to be retrofitted reaching their end-of-life
		in any given year.

		LocalNewCapacity(l, t, y) == 0
		(LocalNewCapacity(l, t, y) + sum(LocalNewCapacity(l, tech, y) for tech in OtherRetrofitTechnology) <=
				(1 + 0.1) * sum(PotentialRetrofitFromResidual(l, tech, y) + PotentialRetrofitFromNew(l, tech, y) for tech in RelevantTechnology))
		"""

		if (self.HubLocation.get_value(l) == 1) or (self.RetrofitTechnology.get_value(t) == 0):
			return None
		else:
			if y == min(self.YEAR.data.VALUE):
				lhs = [(1, self.LocalNewCapacity.get_index_label(l, t, y))]
				rhs = 0
				sense = '=='
				return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
			else:
				RelevantTechnology = [tech for tech in self.TECHNOLOGY.data.VALUE if
									  self.MatchTechnologyRetrofit.get_value(tech, t) == 1]
				OtherRetrofitTechnology = [tech for tech in self.TECHNOLOGY.data.VALUE if
										   (self.RetrofitTechnology.get_value(tech) == 1) and (sum(
											   self.MatchTechnologyRetrofit.get_value(tt, tech) for tt in
											   RelevantTechnology) >= 1)]
				OtherRetrofitTechnology.remove(t)

				lhs = [(1, self.LocalNewCapacity.get_index_label(l, t, y)),
						(1, [self.LocalNewCapacity.get_index_label(l, tech, y) for tech in OtherRetrofitTechnology]),
						(-1*(1 + 0.1), [self.PotentialRetrofitFromResidual.get_index_label(l, tech, y) for tech in RelevantTechnology]),
						(-1*(1 + 0.1), [self.PotentialRetrofitFromNew.get_index_label(l, tech, y) for tech in RelevantTechnology])]
				rhs = 0
				sense = '<='
				return {'lhs': lhs, 'rhs': rhs, 'sense': sense}
