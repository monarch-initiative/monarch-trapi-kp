"""
GraphAdapter to Monarch graph API
"""
from starlette.responses import Response
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
        async def get_node(self, node_type: str, curie: str) -> Response:
            """
            Returns a node that matches curie as its ID.
            :param node_type: Type of the node.
            :type node_type:str
            :param curie: Curie.
            :type curie: str
            :return: starlette Response wrapped value of the node in Monarch.
            :rtype: Response(List)
            """
            # node = list()
            # return Response(node)
            raise NotImplementedError

        async def get_single_hops(self, source_type: str, target_type: str, curie: str) -> Response:
            """
            Returns a triplets of source to target where source id is curie.
            :param source_type: Type of the source node.
            :type source_type: str
            :param target_type: Type of target node.
            :type target_type: str
            :param curie: Curie of source node.
            :type curie: str
            :return: starlette Response wrapped list of triplets where each item contains source node, edge, target.
            :rtype: Response(List)
            """
            # node = list()
            # return Response(node)
            raise NotImplementedError

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
