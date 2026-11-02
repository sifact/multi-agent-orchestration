# production.py

Creates engine builds, module builds and the supplier lots they consumed.

* Records one build per engine with plant, line, dates and pass-off EGT margin.
* Records six module builds per engine, each with a station and build date.
* Routes Riverside line 2 HPC modules through station HPC-04, the story station.
* Groups module builds into supplier lots of 6 to 10 engines in build order.
* Pins the fan story lot to the story engines plus two engines that did not fail by fan wear.
