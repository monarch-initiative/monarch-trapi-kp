# Change Log

## 0.0.10

- added "directionality": "object_to_subject" to SemSimian API call (as per recommendation of MMCQ team)

## 0.0.9

- Repaired MMCQ error reporting to report all validation state as TRAPI Response logs array of LogEntry items, returning empty TRAPI Response Message knowledge graph and results if there are errors (but not for just warnings, debug or info messages)

## 0.0.8

- Additional Phenotype-to-Disease query term sets added to Jupyter Notebook

## 0.0.7

- Added a [Multi-Curie Queries Jupyter Notebook](./docs/MultiCurieQueries.ipynb), with some basic Phenotype-to-Disease queries. 
- Some tiny code fixes to make more robust. Note Python 3.11 constraint and some extra (optional) poetry dependencies to run the notebook! 

## 0.0.6

- Algorithm now differentiates between 'MANY' and 'ALL' SemSimian matches filtering out duplicate matches by taking the highest scoring (phenotypic) query term to (disease-related phenotype) match pairs

## 0.0.5

- trapi::is_mcq_subject_qnode() method now throws a RuntimeException if a node with "set_interpretation" value equal to either "MANY", or "ALL", is not formatted as expected. Sends back an error message, as a result, to the user.

## 0.0.4

- Hacky patch to Dockerfile for environment file variables
- 
## 0.0.3

- Significant refactoring of MMCQ TRAPI Response to comply with latest thinking about MCQ output for SemSimian.
- Clean up of additional technical debt within the application.

## 0.0.2

- Basic June 2024 TRAPI 1.5 update to January MCQ prototype, including Docker (Compose) operations.

## 0.0.1

- Initial January 2024 prototype of the TRAPI phenotype-disease multi-curie query against the Monarch SemSimian.
