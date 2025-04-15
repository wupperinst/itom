
# ITOM -- Industry Transformation Optimization Model

**Welcome to ITOM -- the Industry Transformation Optimization Model framework.**[^1]

With this framework you have all the building blocks you need to generate full-fledged systems optimization models that you can apply to explore future pathways for the basic industries.

ITOM is meant for geographically detailed techno-economic bottom-up linear optimization model. It optimises investments in production assets and plant operations, generating cost-optimal pathways towards future production networks in the industrial sectors that you have defined. It can account for single plants or production sites and the infrastructure between them. The minimum total cost solution is constrained by boundary conditions defined by the modeller such as emission limits, waste and scrap availability, and quality requirements for final products.

# Acknowledgement
- ITOM's structure and philosophy is inspired from **OSeMOSYS -- the Open Source energy MOdelling SYStem** (Howells *et al.*, 2011).[^2]
- The development for this repository was funded in part by:
	-  the German Federal Ministry for Economic Affairs and Climate Action (BMWK) under Grant Aggreement Number 03EI5003A (research project [GreenFeed -- Green Feedstock for a Sustainable Chemistry](https://wupperinst.org/en/p/wi/p/s/pd/1993)). All responsibility for the content of this repository lies with the authors.
	- the European Union (EU) under Grant Agreement Number 101137606 (HORIZON EUROPE Research and Innovation Action project [TRANSIENCE -- TRANSItioning towards an Efficient, carbon-Neutral Circular European industry](https://www.transience.eu/)). Views and opinions expressed are however those of the author(s) only and do not necessarily reflect those of the European Union or the European Health and Digital Executive Agency (HaDEA). Neither the European Union nor the granting authority can be held responsible for them.

# Installation
 - Download the code from this repository or `git clone` it.
 - Install the requirements in a [python virtual environment](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/).
 - Run `python main.py SCENARIO_NAME` from the repo's folder after you have prepared input data in the required format.

# Documentation
Soon available at [readthedocs](https://about.readthedocs.com/)!

# Contributions
If you'd like to contribute, the [issues page](https://github.com/wupperinst/itom/issues) lists possible extensions and improvements.
If you wish to contribute your own, just create a fork and open a PR!

# License
[ITOM](https://github.com/wupperinst/itom) © 2025 by [Wuppertal Institute for climate, environment and energy](https://wupperinst.org/) is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/?ref=chooser-v1)

[^1]: Before being open sourced in this repository, ITOM was developped and applied in a number of projects under the name WISEE EDM-I (Wuppertal Institute System model architecture for Energy and Emission scenarios Energy Demand Model - Invest).
[^2]: Mark Howells, Holger Rogner, Neil Strachan, Charles Heaps, Hillard Huntington, Socrates Kypreos, Alison Hughes, Semida Silveira, Joe DeCarolis, Morgan Bazillian, Alexander Roehrl,
*OSeMOSYS: The Open Source Energy Modeling System: An introduction to its ethos, structure and development*,
Energy Policy, Volume 39, Issue 10, 2011, Pages 5850-5870,
ISSN 0301-4215, https://doi.org/10.1016/j.enpol.2011.06.033.
Repository: https://github.com/OSeMOSYS/OSeMOSYS
