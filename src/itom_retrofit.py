#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Mar 19 10:56:18 2020

@author: mathieusa
"""

from pyomo.environ import Param, Var, Constraint, NonNegativeReals, value
from itom import abstract_itom
from itom_hub import abstract_itom_hub

class abstract_itom_retrofit(abstract_itom):
    '''
    Subclass of ITOM including retrofit capabilities.
    '''
    def __init__(self, InputPath=None):

        super().__init__(InputPath=InputPath)

        ##############
        # Parameters #
        ##############

        self.model.RetrofitTechnology = Param(self.model.TECHNOLOGY, default=0)
        self.model.TechnologyToRetrofit = Param(self.model.TECHNOLOGY, default=0)
        self.model.MatchTechnologyRetrofit = Param(self.model.TECHNOLOGY, self.model.TECHNOLOGY, default=0)

        #############
        # Variables #
        #############

        self.model.PotentialRetrofitFromResidual = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.PotentialRetrofitFromNew = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)

        ###############
        # Constraints #
        ###############

        self.model.R1_RetrofitPotentialFromResidualCapacity = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.R1_RetrofitPotentialFromResidualCapacity_rule)
        self.model.R2_RetrofitPotentialFromNewCapacity = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.R2_RetrofitPotentialFromNewCapacity_rule)
        self.model.R3_RetrofitCapacityConstraint = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.R3_RetrofitCapacityConstraint_rule)

    ###########
    # METHODS #
    ###########

    ###############
    # Constraints #
    ###############

    #########       	Retrofitting	     	#############

    def R1_RetrofitPotentialFromResidualCapacity_rule(self, model,l,t,y):
        '''
        *Constraint:* retrofit capacity potential is given by the residual
        capacity of technologies allowed to be retrofitted reaching their
        end-of-life in any given year.
        '''
        if (y==min(self.model.YEAR)) or (self.model.TechnologyToRetrofit[t]==0):
            return Constraint.Skip
        else:
            if self.model.LocalResidualCapacity[l,t,y-self.model.TimeStep[y]] - self.model.LocalResidualCapacity[l,t,y] > 0:
                return self.model.PotentialRetrofitFromResidual[l,t,y] == self.model.LocalResidualCapacity[l,t,y-self.model.TimeStep[y]] - self.model.LocalResidualCapacity[l,t,y]
            else:
                return self.model.PotentialRetrofitFromResidual[l,t,y] == 0

    def R2_RetrofitPotentialFromNewCapacity_rule(self, model,l,t,y):
        '''
        *Constraint:* retrofit capacity potential is given by the accumulated
        new capacity of technologies allowed to be retrofitted reaching their
        end-of-life in any given year.
        '''
        if y==min(self.model.YEAR) or (self.model.TechnologyToRetrofit[t]==0):
            return Constraint.Skip
        else:
            return self.model.PotentialRetrofitFromNew[l,t,y] == sum(self.model.LocalNewCapacity[l,t,yy] for yy in self.model.YEAR if (y-yy == sum(self.model.OperationalLife[r,t] * self.model.Geography[r,l] for r in self.model.REGION)) and (y-yy > 0))

    def R3_RetrofitCapacityConstraint_rule(self, model,l,t,y):
        '''
        *Constraint:* retrofit capacity is constrained by the installed capacity
        of technologies allowed to be retrofitted reaching their end-of-life
        in any given year.
        '''
        if self.model.RetrofitTechnology[t]==1:
            if y==min(self.model.YEAR):
                return self.model.LocalNewCapacity[l,t,y] == 0
            else:
                RelevantTechnology = [tech for tech in self.model.TECHNOLOGY if self.model.MatchTechnologyRetrofit[tech,t]==1]
                OtherRetrofitTechnology = [tech for tech in self.model.TECHNOLOGY if (self.model.RetrofitTechnology[tech]==1) and (sum(self.model.MatchTechnologyRetrofit[tt,tech] for tt in RelevantTechnology)>=1)]
                OtherRetrofitTechnology.remove(t)
                return self.model.LocalNewCapacity[l,t,y] + sum(self.model.LocalNewCapacity[l,tech,y] for tech in OtherRetrofitTechnology) <= (1 + 0.1) * sum(self.model.PotentialRetrofitFromResidual[l,tech,y] + self.model.PotentialRetrofitFromNew[l,tech,y] for tech in RelevantTechnology)
        else:
            return Constraint.Skip


###############################################################################


class abstract_itom_hub_retrofit(abstract_itom_hub):
    '''
    Subclass of ITOM Hub including retrofit capabilities.
    '''
    def __init__(self, InputPath=None):

        super().__init__(InputPath=InputPath)

        ##############
        # Parameters #
        ##############

        self.model.RetrofitTechnology = Param(self.model.TECHNOLOGY, default=0)
        self.model.TechnologyToRetrofit = Param(self.model.TECHNOLOGY, default=0)
        self.model.MatchTechnologyRetrofit = Param(self.model.TECHNOLOGY, self.model.TECHNOLOGY, default=0)

        #############
        # Variables #
        #############

        self.model.PotentialRetrofitFromResidual = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)
        self.model.PotentialRetrofitFromNew = Var(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, domain=NonNegativeReals, initialize=0.0)

        ###############
        # Constraints #
        ###############

        self.model.R1_RetrofitPotentialFromResidualCapacity = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.R1_RetrofitPotentialFromResidualCapacity_rule)
        self.model.R2_RetrofitPotentialFromNewCapacity = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.R2_RetrofitPotentialFromNewCapacity_rule)
        self.model.R3_RetrofitCapacityConstraint = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.YEAR, rule=self.R3_RetrofitCapacityConstraint_rule)

    ###########
    # METHODS #
    ###########

    ###############
    # Constraints #
    ###############

    #########       	Retrofitting	     	#############

    def R1_RetrofitPotentialFromResidualCapacity_rule(self, model,l,t,y):
        '''
        *Constraint:* retrofit capacity potential is given by the residual
        capacity of technologies allowed to be retrofitted reaching their
        end-of-life in any given year.
        '''
        if (self.model.HubLocation[l]==1) or (y==min(self.model.YEAR)) or (self.model.TechnologyToRetrofit[t]==0):
            return Constraint.Skip
        else:
            if self.model.LocalResidualCapacity[l,t,y-self.model.TimeStep[y]] - self.model.LocalResidualCapacity[l,t,y] > 0:
                return self.model.PotentialRetrofitFromResidual[l,t,y] == self.model.LocalResidualCapacity[l,t,y-self.model.TimeStep[y]] - self.model.LocalResidualCapacity[l,t,y]
            else:
                return self.model.PotentialRetrofitFromResidual[l,t,y] == 0

    def R2_RetrofitPotentialFromNewCapacity_rule(self, model,l,t,y):
        '''
        *Constraint:* retrofit capacity potential is given by the accumulated
        new capacity of technologies allowed to be retrofitted reaching their
        end-of-life in any given year.
        '''
        if (self.model.HubLocation[l]==1) or (y==min(self.model.YEAR)) or (self.model.TechnologyToRetrofit[t]==0):
            return Constraint.Skip
        else:
            return self.model.PotentialRetrofitFromNew[l,t,y] == sum(self.model.LocalNewCapacity[l,t,yy] for yy in self.model.YEAR if (y-yy == sum(self.model.OperationalLife[r,t] * self.model.Geography[r,l] for r in self.model.REGION)) and (y-yy > 0))

    def R3_RetrofitCapacityConstraint_rule(self, model,l,t,y):
        '''
        *Constraint:* retrofit capacity is constrained by the installed capacity
        of technologies allowed to be retrofitted reaching their end-of-life
        in any given year.
        '''
        if (self.model.HubLocation[l]==1) or (self.model.RetrofitTechnology[t]==0):
            return Constraint.Skip
        else:
            if y==min(self.model.YEAR):
                return self.model.LocalNewCapacity[l,t,y] == 0
            else:
                RelevantTechnology = [tech for tech in self.model.TECHNOLOGY if self.model.MatchTechnologyRetrofit[tech,t]==1]
                OtherRetrofitTechnology = [tech for tech in self.model.TECHNOLOGY if (self.model.RetrofitTechnology[tech]==1) and (sum(self.model.MatchTechnologyRetrofit[tt,tech] for tt in RelevantTechnology)>=1)]
                OtherRetrofitTechnology.remove(t)
                return self.model.LocalNewCapacity[l,t,y] + sum(self.model.LocalNewCapacity[l,tech,y] for tech in OtherRetrofitTechnology) <= (1 + 0.1) * sum(self.model.PotentialRetrofitFromResidual[l,tech,y] + self.model.PotentialRetrofitFromNew[l,tech,y] for tech in RelevantTechnology)
