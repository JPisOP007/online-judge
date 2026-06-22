import os
import pymongo
from urllib.parse import quote_plus

uri = os.getenv('MONGODB_URI')
if not uri:
    raise RuntimeError('MONGODB_URI not set')
client = pymongo.MongoClient(uri)
db = client.get_default_database()
# Drop migration collection
if 'django_migrations' in db.list_collection_names():
    db.drop_collection('django_migrations')
print('Dropped django_migrations collection')
