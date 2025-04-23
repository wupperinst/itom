#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This module defines:

    - the `abstract_itom_retrofit_impurities` subclass of `abstract_itom_retrofit`,
    - the `abstract_itom_hub_retrofit_impurities` subclass of `abstract_itom_hub_retrofit`.

Both classes encapsulate Pyomo ABSTRACT models extending the core ITOM framework definition
to include constraints on impurity levels in products from the energy-intensive industry system.

@author: mathieusa
"""

__all__ = ('abstract_itom_retrofit_impurities',
           'abstract_itom_hub_retrofit_impurities')

from pyomo.environ import Param, Var, Constraint, NonNegativeReals, value
from itom_retrofit import abstract_itom_retrofit
from itom_retrofit import abstract_itom_hub_retrofit


class abstract_itom_retrofit_impurities(abstract_itom_retrofit):
    '''
    Subclass of ITOM Retrofit including constraints on impurity levels (e.g. for steel sector modelling).
    '''
    def __init__(self, InputPath=None):

        super().__init__(InputPath=InputPath)

        ##############
        # Parameters #
        ##############

        self.model.MaxImpurity = Param(self.model.PRODUCT, self.model.PRODUCT, default=self.HighMaxDefault)

        #############
        # Variables #
        #############

        ###############
        # Constraints #
        ###############

        self.model.IP1_ImpuritiesInProductsLimit = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.PRODUCT, self.model.YEAR, rule=self.IP1_ImpuritiesInProductsLimit_rule)

    ###########
    # METHODS #
    ###########

    ###############
    # Constraints #
    ###############

    #########       	Impurities in products	     	#############

    def IP1_ImpuritiesInProductsLimit_rule(self, model,l,t,i,y):
        '''
        *Constraint:* some technologies generate "by-products" that actually represent impurities in the main product
        (e.g. Cu in steel). The parameter MaxImpurity defines the impurity limit (share) tolerated for a given product.
        In this constraint, for technologies where materials of different grades are mixed, the final product's
        impurity content should be be smaller than MaxImpurity rate applied to
        '''
        if self.model.ProductFromTechnology[t,i] == 1:
            RelevantProduct = [p for p in self.model.PRODUCT if (p!=i) and (self.model.ProductFromTechnology[t,p] == 1)]
            if RelevantProduct:
                for p in RelevantProduct:
                    if self.model.MaxImpurity[p,i]==self.HighMaxDefault:
                        return Constraint.Skip
                    else:
                        return self.model.LocalProductionByTechnology[l,t,i,y] <= self.model.MaxImpurity[p,i] * self.model.LocalProductionByTechnology[l,t,p,y]
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip


class abstract_itom_hub_retrofit_impurities(abstract_itom_hub_retrofit):
    '''
    Subclass of ITOM Hub Retrofit including constraints on impurity levels (e.g. for steel sector modelling).
    '''
    def __init__(self, InputPath=None):

        super().__init__(InputPath=InputPath)

        ##############
        # Parameters #
        ##############

        self.model.MaxImpurity = Param(self.model.PRODUCT, self.model.PRODUCT, default=self.HighMaxDefault)

        #############
        # Variables #
        #############

        ###############
        # Constraints #
        ###############

        self.model.IP1_ImpuritiesInProductsLimit = Constraint(self.model.LOCATION, self.model.TECHNOLOGY, self.model.PRODUCT, self.model.YEAR, rule=self.IP1_ImpuritiesInProductsLimit_rule)

    ###########
    # METHODS #
    ###########

    ###############
    # Constraints #
    ###############

    #########       	Impurities in products	     	#############

    def IP1_ImpuritiesInProductsLimit_rule(self, model,l,t,i,y):
        '''
        *Constraint:* some technologies generate "by-products" that actually represent impurities in the main product
        (e.g. Cu in steel). The parameter MaxImpurity defines the impurity limit (share) tolerated for a given product.
        In this constraint, for technologies where materials of different grades are mixed, the final product's
        impurity content should be be smaller than MaxImpurity rate applied to
        '''
        if self.model.ProductFromTechnology[t,i] == 1:
            RelevantProduct = [p for p in self.model.PRODUCT if (p!=i) and (self.model.ProductFromTechnology[t,p] == 1)]
            if RelevantProduct:
                for p in RelevantProduct:
                    if self.model.MaxImpurity[p,i]==self.HighMaxDefault:
                        return Constraint.Skip
                    else:
                        return self.model.LocalProductionByTechnology[l,t,i,y] <= self.model.MaxImpurity[p,i] * self.model.LocalProductionByTechnology[l,t,p,y]
            else:
                return Constraint.Skip
        else:
            return Constraint.Skip
