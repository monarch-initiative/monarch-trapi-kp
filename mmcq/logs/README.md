List of files in current dir:
- **mmcq.log:** log file of the application

TODO: note that except for the mmcq.log file, the contents of this README may be out-of-date
- **edge_errors.json:** contains summary of kgx edge validation
- **node_errors.json:** contains summary of kgx node validation
- **graph_summary.json:** contains summary of the graph. 
  To reset just delete this file or run the Monarch TRAPI KP
  with -rs (--reset-summary) cli argument .
- **graph_diff.json:** is created after a second run of the TRAPI KP.
It is created using _graph_summary.json_ as reference. 
  It will summarize out differences in stats of the graph.

