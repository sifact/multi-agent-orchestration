# stories.py

Defines the two planted factory-to-fleet stories and picks the engines that carry them.

* The fan story is a blade lot accepted under a coating deviation, later quarantined.
* The HPC story is an under-reading torque wrench at one Riverside station, raised as an NCR.
* Each story has fixed dates, IDs and a service bulletin that closes it.
* Removed story engines are the shortest-lived engines with the matching fault mode.
* Active story engines are those with the lowest true remaining life and enough history.
