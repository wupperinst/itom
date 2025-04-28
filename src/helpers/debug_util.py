#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 31 16:59:35 2019

@author: mathieusa
"""

import os, contextlib
import logging

from pyomo.environ import value

# Instantiate a logger for this module
logger = logging.getLogger(__name__)
#logger.setLevel(logging.INFO)
# Warning messages will be shown in the console)
c_handler = logging.StreamHandler()
c_handler.setLevel(logging.ERROR)
logger.addHandler(c_handler)

def debug_infeas(concrete_model_instance, log_path):
    '''
    Get a concrete model instance, calls Pyomo's infeasibility debugging methods, 
    writes the output to log file.
    '''
    from pyomo.util.infeasible import log_infeasible_constraints, log_infeasible_bounds, log_close_to_bounds, log_active_constraints
    # Info messages from pyomo.util.infeasible will be logged in the file specified
    f_handler = logging.FileHandler(os.path.join(log_path,'infeasibility.log'))
    f_handler.setLevel(logging.INFO)
    logger.addHandler(f_handler)
    # Call Pyomo's debugging utilities
    # Silence stdout (it will be written to the log file anyway)
#    with open(os.devnull, 'w') as devnull:
#        with contextlib.redirect_stdout(devnull):
#            log_infeasible_constraints(concrete_model_instance, tol=1E-6, logger=logger)
#    log_infeasible_bounds(concrete_model_instance, tol=1E-6, logger=logger)
#    log_close_to_bounds(concrete_model_instance, tol=1E-6, logger=logger)
#    log_active_constraints(concrete_model_instance, logger=logger)
#    sys.stdout = stdout
    log_infeasible_constraints(concrete_model_instance, tol=1E-6, logger=logger)
