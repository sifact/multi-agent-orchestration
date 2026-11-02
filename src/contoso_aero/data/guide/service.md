# service.py

Creates removals, shop visits, FAA-style difficulty reports and borescope inspections.

* Removes every train engine at its real failure, with a reason that matches its fault mode.
* Opens a shop visit per removal, with story-specific findings for story engines.
* Writes a difficulty report per removal using the FAA Form 8070-1 field layout.
* Borescopes every engine every 100 cycles, with worse findings late in a removed engine's life.
* Adds a post-bulletin borescope for active story engines that cites the bulletin.
