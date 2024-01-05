"""
GraphAdapter to Monarch graph API
"""
from typing import Any, List, Dict
# from bmt import Toolkit


LATEST_BIOLINK_MODEL = "1.4.0"


class GraphInterface:
    """
    Singleton class for interfacing with the graph.
    """
    class _GraphInterface:
        def __init__(self, query_timeout, bl_version=LATEST_BIOLINK_MODEL):
            self.schema = None
            # used to keep track of derived inverted predicates
            # self.inverted_predicates = defaultdict(lambda: defaultdict(set))
            self.query_timeout = query_timeout
            # self.toolkit = Toolkit()
            self.bl_version = bl_version

        # TODO: add useful _GraphInterface methods here!
        async def get_node(self, node_type: str, curie: str) -> Dict:
            """
            Returns a node that matches curie as its ID.
            :param node_type: Type of the node.
            :type node_type:str
            :param curie: Curie.
            :type curie: str
            :return: Contents of the node in Monarch.
            :rtype: Dict
            """
            # TODO: Implement me!
            return dict()

        async def get_single_hops(self, source_type: str, target_type: str, curie: str) -> List:
            """
            Returns a triplets of source to target where source id is curie.
            :param source_type: Type of the source node.
            :type source_type: str
            :param target_type: Type of target node.
            :type target_type: str
            :param curie: Curie of source node.
            :type curie: str
            :return: List of triplets where each item contains source node, edge, target.
            :rtype: List
            """
            # TODO: Implement me!
            return list()

        #
        # TODO: deprecate PLATER neo4j access to graph
        #
        # async def run_cypher(self, cypher: str, **kwargs) -> list:
        #     """
        #     Runs cypher directly.
        #     :param cypher: cypher query.
        #     :type cypher: str
        #     :return: unprocessed neo4j response.
        #     :rtype: list
        #     """
        #     kwargs['timeout'] = self.query_timeout
        #     return await self.driver.run(cypher, **kwargs)

        async def run_query(self, question_json: Dict, **kwargs) -> List[Dict[str, Any]]:
            """
            Drop in replacement for the above PLATER 'run_cypher()' method, accessing Monarch instead.
            :param question_json: Python dictionary version of TRAPI Query JSON
            :type question_json: Dict
            :return: List of Query results as (TRAPI JSON) dictionaries
            :rtype: List[Dict[str, Any]]
            """
            kwargs['timeout'] = self.query_timeout
            # return await self.driver.run(cypher, **kwargs)
            # TODO: Implement me!
            result: List[Dict[str, Any]] = [dict()]
            return result

    def convert_to_dict(self, result) -> List[Dict[str, Any]]:
        # TODO: Implement me!
        return [dict(entry) for entry in result]

    instance = None

    def __init__(self, query_timeout=600, bl_version=LATEST_BIOLINK_MODEL):
        # create a new instance if not already created.
        if not GraphInterface.instance:
            GraphInterface.instance = GraphInterface._GraphInterface(
                query_timeout=query_timeout,
                bl_version=bl_version
            )

    def __getattr__(self, item):
        # proxy function calls to the inner object.
        return getattr(self.instance, item)
