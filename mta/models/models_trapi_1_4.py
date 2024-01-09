"""
Pydantic models.
"""
from typing import Dict, List
from pydantic import BaseModel, constr, validator, root_validator
from reasoner_pydantic import (
    Query as ReasonerRequestBaseClass,
    QNode,
    QEdge
)


class ReasonerRequest(ReasonerRequestBaseClass):

    @root_validator
    def validate_unbound_nodes(cls, v):
        # check if message exist and not invalid upstream
        if not v.get('message'):
            return v
        q_nodes: Dict[str, QNode] = v['message'].query_graph.nodes
        if v.get('workflow'):
            is_lookup = 'lookup' in [x.__root__.id.name for x in v['workflow'].__root__]
        else:
            # by default its is a lookup if no workflow is specified
            is_lookup = True
        if is_lookup:
            has_bound_node = False
            for q_node_id in q_nodes:
                q_node = q_nodes[q_node_id]
                if q_node.ids:
                    has_bound_node = True
                    break
            assert has_bound_node, "Query graph should contain at least one bound node."
        return v

    @validator("message")
    def validate_broken_edge(cls, v):
        q_nodes: Dict[str, QNode] = v.query_graph.nodes
        q_edges: Dict[str, QEdge] = v.query_graph.edges
        for q_edge_id in q_edges:
            edge = q_edges[q_edge_id]
            if edge.subject == edge.object is None:
                continue
            assert edge.subject in q_nodes, f"Query graph edge {q_edge_id} references missing node key {edge.subject}" \
                                            f" in message.query_graph.nodes ."
            assert edge.object in q_nodes,  f"Query graph edge {q_edge_id} references missing node key {edge.object}" \
                                            f" in message.query_graph.nodes ."
        return v


class SimpleSpecElement(BaseModel):
    source_type: str
    target_type: str
    edge_type: str


SimpleSpecResponse = List[SimpleSpecElement]

TypeSet = constr(regex=r"\w+(:\w+)*")


class TypeSummary(BaseModel):
    nodes_count: int

    class Config:
        schema_extra = {
            "patternProperties": {
                r"\w+(:\w+)*": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "integer"
                    }
                }
            }
        }


GraphSummaryResponse = Dict[TypeSet, TypeSummary]

PredicatesResponse = Dict[str, Dict[str, List[str]]]
