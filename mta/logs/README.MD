List of files in current dir:
- **edge_errors.json:** contains summary of kgx edge validation
- **node_errors.json:** contains summary of kgx node validation
- **graph_summary.json:** contains summary of the graph. 
  To reset just delete this file or run the Monarch Translator ARA 
  with -rs (--reset-summary) cli argument .
- **graph_diff.json:** is created after a second run of the Monarch Translator ARA.
It is created using _graph_summary.json_ as reference. 
  It will summarize out differences in stats of the graph.
- **mta.log:** log file of the application