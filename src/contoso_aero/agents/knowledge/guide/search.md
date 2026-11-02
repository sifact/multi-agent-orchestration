# search.py

Provides a small BM25 search over the knowledge documents, one chunk per section.

* Splits each Markdown document on second-level headings.
* Scores chunks with BM25 using fixed constants, so results are deterministic.
* Tokenizes to lowercase alphanumerics, including the document id.
* Returns no hits when no query term matches any chunk.
* Uses only the standard library, in line with the no-heavy-retrieval constraint.
