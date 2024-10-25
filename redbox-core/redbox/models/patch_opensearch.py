from elasticsearch import Elasticsearch
from langchain_elasticsearch import _utilities
from opensearchpy import OpenSearch


def custom_with_user_agent_header(client, user_agent):
    if isinstance(client, OpenSearch):
        # OpenSearch does not have the _headers attribute, skip this step
        return client
    
    # If it's Elasticsearch, proceed with header handling
    if hasattr(client, '_headers'):
        headers = dict(client._headers)
        headers["User-Agent"] = f"{headers.get('User-Agent', '')} {user_agent}".strip()
        client._headers = headers

    return client

# Apply the monkey patch
_utilities.with_user_agent_header = custom_with_user_agent_header