# text.py

Turns look-alike characters in model-written text into the plain ones the data uses.

* Replaces non-breaking and narrow spaces with an ordinary space.
* Replaces non-breaking hyphens and the minus sign with a plain hyphen, so identifiers match.
* Removes zero-width characters that are invisible but break exact matching.
* Replaces full-width brackets used for source tags with plain square brackets.
* Is applied to plan questions, agent answers passed between steps, and the merged answer.
