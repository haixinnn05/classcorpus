# Privacy

ClassCorpus performs extraction, indexing, retrieval, and storage locally.
There is no telemetry, account, hosted backend, or built-in model-provider API.

The active AI agent still receives any text returned by the scripts and any
image it is asked to inspect. Its provider, account, and data-handling policy
therefore control that interaction. Ask before processing confidential,
restricted, customer, or otherwise sensitive materials when clearance is not
known.

Visual analysis is opt-in. Generated records, renders, assets, embeddings, and
descriptions use the operating system's user data directory, or the directory
set by `CLASSCORPUS_DATA_DIR`. Confirmed course removal deletes generated data
only; source lecture files are never modified.

Persistent flashcard review stores card fingerprints, citation identity, source
hashes, scheduling values, confidence, and timestamps in that same local data
directory. It does not store card fronts or backs. A progress export contains
the same metadata and is written only to the path the user chooses.

Optional OCR runs through a user-installed local adapter. ClassCorpus does not
send images or OCR text to a hosted service. OCR backend and confidence remain
attached to the result so uncertain machine-read text is not confused with
native extraction.
