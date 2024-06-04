# Change Log

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
