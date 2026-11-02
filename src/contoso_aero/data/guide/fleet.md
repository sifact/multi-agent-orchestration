# fleet.py

Turns C-MAPSS runs into Contoso engines with serials, dates, plants and aircraft positions.

* Puts the 100 active engines in today's 100 aircraft positions.
* Fills each position's history backwards, so a removed engine leaves before the next one arrives.
* Pins story engines' build dates inside their story window before placing the others.
* Spaces one condition report per C-MAPSS cycle across each engine's time on wing.
* Numbers engines CX7-10001 upward in build order after all dates are fixed.
