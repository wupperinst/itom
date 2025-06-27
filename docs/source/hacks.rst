*********************
Implementation hacks
*********************

By design anything can be modelled with the ITOM framework as a TECHNOLOGY either transforming or transporting PRODUCTs.
Those technologies are characterised with costs, yields and emissions while constraints can be imposed on the investments, 
activities and capacities of the technologies.

The previous sections describe the general logic and structure of the model, focusing primarily on the structures 
that more intuitively are representations of the real world. However, the model is bound by its inherent structure, 
by the types of input and outputs it is able to provide, which makes certain aspects more difficult to implement. 

For example, how can you model the effects of sub-regional energy prices, when prices for technologies can only be defined on a larger, regional level? 
How can you see the benefits of CCS, when it does not produce any actual products that are useful for chemicals production? 
How can you tell the value of intermediate products, for which there are no directly given exogenous assumptions?
In order to use the model to answer such questions, or for the model to work as intended, it is sometimes necessary 
to make certain implementations that are less intuitive, and do not directly correspond to actual real-world structures 
(such as real-world processes, products and capacities). This section explains and summarizes the most central “hacks and tricks” 
that are used to get around these issues. 


Restricting using high costs
=============================

Direct limitations on what the model is allowed to do can be put on the model for instance via 
“LocalTotalAnnualMaxCapacityInvestment” and “TotalTechnologyAnnualActivityUpperLimit”. 
However, for many cases, parameters are not sufficient - they are only on technology-level and not mode-level, 
- or, more typically, they are not desirable - such hard limits can make the model unsolvable 
and the cause can be difficult to find, and it can be difficult to maintain an overview the more parameters are involved. 
Therefore, restrictions are instead often made via cost parameters (typically CapitalCost or VariableCost). For instance:

    • Technology A is still at a pilot-level, and is expected to be available only from 2040 🡪 CapitalCost is set to e.g., 1000000 for 2020-2035
    • Product X is a toxic gas, and cannot be transported between sites 🡪 transport_hub technology for Product X is set as 1000000

In most cases, such high costs are sufficient for the model to avoid the unwanted behaviour. 
If they are used despite these high costs, i.e., Technology A is invested in in 2020 or Product X is transported, 
it signals a problem which can be identified through the extreme costs.

