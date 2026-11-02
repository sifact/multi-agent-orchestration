# agent.py

Answers questions from Contoso procedures and service bulletins with citations.

* Offers two tools: search_documents and read_document.
* Requires the model to cite the document id for each fact it states.
* Says so when the documents lack the answer instead of guessing.
* Exposes one public function, handle(question, context).
* Owns no database tables; it reads only the knowledge folder.
