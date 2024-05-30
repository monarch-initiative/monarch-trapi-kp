from bmt import Toolkit

# TODO: assume that this is safe,
#       to keep up-to-date with latest Biolink Model.
#       If not, then we'll hardcode this in the future?
LATEST_BIOLINK_MODEL = Toolkit().get_model_version()
