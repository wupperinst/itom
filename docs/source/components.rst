.. _components:

**********
Components
**********

Code documentation of the classes building the core structure of ITOM.

Module *itom*
======================

General information
--------------------

.. automodule:: src.itom


.. _ref-input:

Inputs
-------

Sets
^^^^^

.. csv-table::
   :file: csv/sets.csv
   :widths: 15, 25
   :header-rows: 1

Parameters
^^^^^^^^^^^

.. csv-table:: **Economics**
   :file: csv/param_eco.csv
   :widths: 20, 20, 5, 10, 30
   :header-rows: 1
   
|
   
.. csv-table:: **Geography**
   :file: csv/param_geo.csv
   :widths: 20, 20, 5, 10, 30
   :header-rows: 1

|

.. csv-table:: **Demand**
   :file: csv/param_demand.csv
   :widths: 20, 20, 5, 10, 30
   :header-rows: 1
   
|

.. csv-table:: **Performance**
   :file: csv/param_perf.csv
   :widths: 20, 20, 5, 10, 30
   :header-rows: 1
   
|
   
.. csv-table:: **Technology costs**
   :file: csv/param_tech_cost.csv
   :widths: 20, 20, 5, 10, 30
   :header-rows: 1
   
|

.. csv-table:: **Capacity constraints**
   :file: csv/param_cap_cons.csv
   :widths: 20, 20, 5, 10, 30
   :header-rows: 1
   
|

.. csv-table:: **Investment constraints**
   :file: csv/param_inv_cons.csv
   :widths: 20, 20, 5, 10, 30
   :header-rows: 1
   
|

.. csv-table:: **Activity constraints**
   :file: csv/param_act_cons.csv
   :widths: 20, 20, 5, 10, 30
   :header-rows: 1


Abstract model class
---------------------

.. autoclass:: src.itom.abstract_itom
   :undoc-members:
   :members:
   :private-members:

Concrete model class
---------------------
.. autoclass:: src.itom.concrete_itom
   :members:
   :private-members:


