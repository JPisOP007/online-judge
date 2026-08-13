"""JSON rendering helpers for the MongoDB-backed API.

The project uses django-mongodb-backend, so every primary key is a BSON
ObjectId rather than an integer. DRF's default JSON encoder does not know how
to serialise ObjectId, which made every endpoint that returned a model
instance fail with a 500. Related fields are the same story: a
PrimaryKeyRelatedField hands the raw ObjectId straight to the encoder.

Stringifying ObjectId in the encoder fixes all of those cases at once,
including nested and related fields we would otherwise have to annotate
one by one.
"""
from rest_framework.renderers import JSONRenderer
from rest_framework.utils import encoders

try:
    from bson import ObjectId
except ImportError:  # pragma: no cover - bson ships with the mongo backend
    ObjectId = None


class MongoJSONEncoder(encoders.JSONEncoder):
    """DRF's JSON encoder, extended to understand BSON ObjectId."""

    def default(self, obj):
        if ObjectId is not None and isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)


class MongoJSONRenderer(JSONRenderer):
    """JSON renderer that serialises ObjectId primary keys as strings."""

    encoder_class = MongoJSONEncoder
