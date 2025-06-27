*******
Concept
*******

.. warning::
    Work in progress!
    
    Concept and model development are iterative processes. We are at iteration 1.
 
This chapter presents the conceptual decisions made to develop the WI-EDM Re-Invest model.
We distinguish in the following between *[implemented]* and *[planed]* concepts and features. If no indication is given, it means the described feature is implemented.

We borrowed a number of design ideas and their code implementation from the OSeMOSYS project (Open Source Energy Modeling System) [#f1]_.

Background
===========

Aim
----

In the realm of WI-EDM modules the decision when to reinvest in a process plant at a certain location (including plant type and capacity) was so far made manually during scenario design.
The Re-Invest module aims at making such decisions endogenous. The **Re-Invest module is a capacity-expansion optimisation model, minimizing total discounted costs**.
The module (initially) only covers the chemical sector. Further areas of application would be e.g. cement.

Overall guidelines
-------------------

The development of the Re-Invest module should follow the following guiding principles:

- The module should remain as simple and transparent as possible in order to (continue to) serve as a basis for discussions with stakeholders.
- The assumptions made for the Re-Invest module should be consistent with the assumptions in other WISEE industry model parts (especially the dispatch module of the model).
- ...

Conceptual modelling decisions
===============================

Core Sets
----------

In traditional capacity expansion energy models such as OSeMOSYS, "anything" represented in the model belongs either to the FUEL or TECHNOLOGY Set.
Fuels are any input (coal, electricity, diesel etc.) to a technology (power plant, distribution grid, car etc.) that "does something" with the fuel (such as burn or transport it).

In our model anything is either a PRODUCT (e.g. oil, H2, naphta, ethylene, polypropylene) or a TECHNOLOGY (e.g. steamcracker, polymerisation plant, power plant). 
The main difference is, however, that transport technologies are defined in the Set TRANSPORTMODE (and not within TECHNOLOGY).

Core constraints
-----------------

Core constraints of the model are those defining product flows in the system.

**1. Production**

The production (or output) of a "product" from a technology (at a given location) is equal to the (rate of) activity 
of this technology multiplied to a product output vs. production activity ratio entered by the analyst
(parameter *OutputActivityRatio*).

**2. Use**

The use (or input) of a "product" by a technology (at a given location) is equal 
to the (rate of) activity multiplied to a product input vs. production activity ratio entered by the analyst
(parameter *InputActivityRatio*.

*These constraints require the definition of one more category of core constraints:*

**3. Activity**

The activity of a given technology (at a given location) is set by the solver in order to 
generate production to meet demand. There are several additional constraints constraints that 
can be put on the activity level. These are defined at the regional level (i.e. they regard 
the sum of activities in the locations of a region) and can apply either annually 
(parameters *TotalTechnologyAnnualActivityUpperLimit* and *TotalTechnologyAnnualActivityLowerLimit*) 
or over the whole modelling period (parameters *TotalTechnologyModelPeriodActivityUpperLimit* 
and *TotalTechnologyModelPeriodActivityLowerLimit*).

*The next core constraint builds on the above and ensures that demand is met:*

**4. Product balance**

For each each year and region the total production of each product + imports 
(of this product) from locations outside the region should be larger than or equal to 
this product's demand in the considered region. If production + imports is larger than 
demand, this can mean that this region is a net exporter (*via* transport to locations outside the region).

.. note::

    The *Demand* parameter passed to the model represent the final net demand for a product 
    (in our case an end-product such as a polymere), i.e. it does not account for potential
    intermediary product use in the industry. This may differ from traditional power system 
    models (e.g. OSeMOSYS) where the energy balance constraint is usually defined as 
    *production + imports >= demand* **+ use**. 

*The above constraint all rely at some level on the constraints dealing with capacity:*

**5. New capacity**

For each technology, constraints on minimum and maximum investments per time step 
are defined locally. This allows to reflect business and political decisions know today 
that will affect investments in the future, or simply to simulate the impact of 
potential such decisions.

For both *LocalTotalAnnualMaxCapacityInvestment* and *LocalTotalAnnualMinCapacityInvestmentdefault* 
the default value is 0, meaning that by default no investment is allowed in any technology, anywhere. 
To allow potential investment in a given technology at a given location, the parameter 
*LocalTotalAnnualMaxCapacityInvestment* must set to a non-zero value in the input data.

**6. Installed capacity**

Both upper and lower limits can be set for the total installed capacity at the regional level. 
This may be used to reflect political targets set e.g. at the national level.

.. note::
    
    Since maximum investment constraints are defined at the local (not regional) level, 
    such constraints as  "maximum investment in world-size polymerisation plant per 
    region per decade" is not directly possible.

Geography
----------

Geographical categories
^^^^^^^^^^^^^^^^^^^^^^^^

Traditional capacity expansion energy models (e.g. power system models) consider different *regions*, some of which can exchange energy flows at no cost via coupling points.
In our case, we ideally need to consider two geographical levels:

- **regions**: the level at which demand for end-products (e.g. polyethylene) is considered in the model (as an exogenous parameter input).
- **locations** (*Standorte*): the sub-regional level at which production activity and production capacity are modelled.

We define which location belongs to which region in the parameter *Geography* (see section :ref:`ref-input`). 
A location LOC_i can be split into LOC_i_1 (e.g. steamcracker) and LOC_i_2 (e.g. ethylene polymerisation). 
These geographically close (or even integrated) production sites will be treated as separate locations by the model. 
They can be differentiated from further away locations via the available maximum transport capacity (virtually infinite) 
between LOC_1_1 and LOC_i_2 and the cost of transport (practically zero). See sections :ref:`ref-TF` and :ref:`ref-TC` for more information.

In the following sections, when writing about a specific parameter or variable we try to indicate if this parameter or variable is defined at the local or regional level.

.. _ref-TF:

Transport flows
^^^^^^^^^^^^^^^^

Contrary to traditional capacity expansion models, we do not define exchanges between regions. 
Instead we define *directional* transport links (parameter *TransportRoute*) between locations (regardless of the regions these locations belong to). 
Between two locations there can exist no transport link or one or more links, each using a different mode of transport (defined by the Set TRANSPORTMODE). 
For each transport link between two locations, a maximum yearly carrying capacity is given (parameter *TransportCapacity*).

The *Transport* variable of the model records yearly transport flows for each product and transport mode between two locations. 
The variable must comply to the following constraints:

**1. Transport capacity**

For each product, each transport mode, in each year, transport from location l to location ll is either smaller or equal to the transport link capacity if a transport route exists, or 0 if there is no route.

**2. Outgoing transport**

For each product, at each (origin) location, in each year, the total quantity of product transported to other locations is equal to the production at the (origin) location.

**3. Incoming transport**

For each product, at each (destination) location, in each year, the total quantity of product transported from other locations equal to the use at the (destination) location.

**4. Import flows**

For each product and region, the imports to that region are the sum of the transport flows from locations outside that region to locations in that region.

*There are some important additions to the constraints 2 and 3:*

**2. Outgoing transport**

If there is no transport link at all departing from the (origin) location, the constraint is skipped. 
This deals with locations at the end of the value chain that we assume only produce for their own regional demand 
(e.g. a polymerisation plant in Germany producing polypropylene for the German market, it has non-zero production 
but zero outward transport in our model, hence the two cannot be equal).
    
**3. Incoming transport**

If there is no transport link at all arriving to the (destination) location, the constraint is skipped. 
This deals with locations at the beginning of the value chain that we assume will always be supplied with 
enough raw materials without requiring their input to come from somewhere 
(e.g. a German location with steamcracker technology produces HVC from naphta that 
seemingly comes out of nowhere -we actually just cut off the more upstream part of the value chain, 
the refineries, from the scope of the model-, it has a non-zero use of naphta but zero 
incoming transport, therefore the two cannot bet equal).

Costs
------

Capital and fixed costs
^^^^^^^^^^^^^^^^^^^^^^^^

These cost intensity parameters (*CapitalCost* and *FixedCost*) are defined for each technology at the *regional* level. These costs can change over time, e.g. assuming declining costs due to accumulated learning.

Variable costs
^^^^^^^^^^^^^^^

This parameter (*VariableCost*) covers costs per unit of activity of each technology, that is per unit of main product output. 
This variable records both the operation and maintenance costs of processes and costs of each product inputs supplied to those processes. 
For example, for a conventional steamcracker, the variable costs are given per unit of ethylene output and these costs cover both process energy costs and the costs of naphta inputs.

.. note::

    [implementd] At the moment the variable costs are defined at the *regional* level (to keep things simpler and save a few equations). 
    
    [planed] We may change that in the future and defined variable costs at the *local* level, which would allow for a higher granularity of production costs. 
    One could for example imagine to have different process energy costs (e.g. as H2) for different locations within the same region (maybe due to political reasons).

.. _ref-TC:

Transport costs
^^^^^^^^^^^^^^^^

Transport cost intensities for each mode of transport (parameter *TransportCostByMode*) are defined *regionally* (and can vary over time, e.g. if assuming that shipping costs will increase). 

Actual transport costs (variables *LocalTransportCost* and *LocalDiscountedTransportCost*) are first calculated at the local level, however. 
For each location, transport costs for a given product are the costs of transporting this product FROM other locations to that location 
(as the sum of the quantities transported per mode of transport multiplied by the specific costs of each mode of transport). 
In other words, the importer is the buyer and pays the transport costs.

When aggregated at the regional level (variables *DiscountedTransportCostByProduct* and *DiscountedTransportCost*), transport costs include both intra-regional transport AND imports from other regions. 
There is no double-counting, however, since transport costs are only registered at the importing location.

Salvage value
^^^^^^^^^^^^^^

From *Howells et al. (2011)* [#f1]_:

    "When a technology is invested in during the model period but ends its operational 
    life before, it is assumed to have no value at the end of the model period. However, 
    if a technology (invested in during the model period) still has some component of 
    its operational life at the end of the period, that should be estimated. Several 
    methods exist to determine the extent to which a technology has depreciated. And this 
    in turn is used to calculate its salvage value by the end of the period. Sinking fund 
    depreciation is assumed here.

    A salvage value is determined, based on the technology’s operational life, its 
    year of investment and discount rate. Following this it is discounted to the 
    beginning first model year by a discount rate applied over the modeling period."

.. warning::
    I implemented salvage value just like in OSeMOSYS (see constraints SV1 and SV2) 
    and used it in the calculation of the total discounted costs (constraint TDC1) 
    as follows:
    
        TotalDiscountedCost = DiscountedOperatingCost + DiscountedCapitalInvestment - DiscountedSalvageValue + DiscountedTransportCost
    
    However, when doing this, we obtain *TotalDiscountedCost = 0* in the optimal solution. 
    What happens is that the *DiscountedSalvageValue* takes the opposite value of the sum 
    of the other costs. I couldn^t find what I did wrong, but the problem is that I don^t 
    really understand what salvage value is supposed to do / to be. I need someone who 
    understands a bit of economics to explain this to me again...
    
    In the meantime, I just shut off salvage value from the total cost calculation, 
    as follows (constraint TDC1):
    
         TotalDiscountedCost = DiscountedOperatingCost + DiscountedCapitalInvestment + DiscountedTransportCost
    
    Doing this, we have a non-zero *TotalDiscountedCost* in the optimal solution, 
    which makes more sense.

Discounted costs
^^^^^^^^^^^^^^^^^

Each cost item [capital, fixed, variable, transport, salvage value] should be calculated in constant monetary terms and then discounted to determine a net present value (NPV). 
To calculate the NPV cost, each technology can have either a default global discount rate or one specific to that technology.

Since in our model we calculate costs first at the *local* level and then aggregate at the *regional* level, 
we try to discount costs early, i.e. already at the local level, so as to allow comparisons of different cost categories across both locations and time. 
Variable names give indications on the level processing of different cost items, for example:

- *LocalCapitalInvestment*: local, undiscounted
- *LocalDiscountedCapitalInvestment*: local, discounted
- *DiscountedCapitalInvestment*: regional, discounted

Continuous vs. discrete capacity expansion
------------------------------------------

[implemented]
Continuous capacity expansion.

[planed]
Discrete capacity expansion (e.g. new steamcracker capacity can be invested in only 100 Mt ethylenne production block capacity). 

.. note::
    Discrete capacity expansion will require Mix Integer Programing (MIP), which will inevitably strongly increase calculation time.


.. rubric:: Footnotes

.. [#f1] Howells, M., Rogner, H., Strachan, N., Heaps, C., Huntington, H., Kypreos, S., Hughes, A., Silveira, S., DeCarolis, J., Bazillian, M., Roehrl, A. (2011) OSeMOSYS: The Open Source Energy Modeling System - An introduction to its ethos, structure and development. *Energy Policy*, 39 (2011), 5850–5870.