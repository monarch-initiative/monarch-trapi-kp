"""
GraphAdapter to Monarch graph API
"""
# from bmt import Toolkit


class GraphInterface:
    """
    Singleton class for interfacing with the graph.
    """
    class _GraphInterface:
        def __init__(self, query_timeout, bl_version="3.1"):
            self.schema = None
            # used to keep track of derived inverted predicates
            # self.inverted_predicates = defaultdict(lambda: defaultdict(set))
            self.query_timeout = query_timeout
            # self.toolkit = Toolkit()
            self.bl_version = bl_version

        # TODO: add useful _GraphInterface methods here!

    instance = None

    def __init__(self, query_timeout=600, bl_version="4.1.0"):
        # create a new instance if not already created.
        if not GraphInterface.instance:
            GraphInterface.instance = GraphInterface._GraphInterface(query_timeout=query_timeout, bl_version=bl_version)

    def __getattr__(self, item):
        # proxy function calls to the inner object.
        return getattr(self.instance, item)
