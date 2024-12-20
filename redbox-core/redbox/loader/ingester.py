import logging
from typing import TYPE_CHECKING

from elasticsearch.helpers.vectorstore import BM25Strategy
from langchain_community.vectorstores import OpenSearchVectorSearch
from langchain_core.runnables import RunnableParallel
from langchain_elasticsearch import ElasticsearchStore
from redbox_app.setting_enums import Environment
from redbox.chains.components import get_embeddings
from redbox.chains.ingest import ingest_from_loader
from redbox.loader.loaders import MetadataLoader, UnstructuredChunkLoader
from redbox.models.settings import get_settings, ElasticLocalSettings, ElasticCloudSettings
from redbox.models.file import ChunkResolution
import environ
from langchain_core.exceptions import OutputParserException
import json
import re
from opensearchpy import exceptions
from langchain_core.embeddings import FakeEmbeddings


if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client
else:
    S3Client = object

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

env = get_settings()
env_vars = environ.Env()
ENVIRONMENT = Environment[env_vars.str("ENVIRONMENT").upper()]

alias = env.elastic_chunk_alias

if ENVIRONMENT.is_local:
    opensearch_url="http://opensearch:9200"
else:
    opensearch_host = env_vars.str('OPENSEARCH_HOST')  # Ensure this includes the endpoint
    username = env_vars.str('OPENSEARCH_USER')
    password = env_vars.str('OPENSEARCH_PASSWORD')
    opensearch_url = f"https://{username}:{password}@{opensearch_host}:443"

def clean_json_metadata(raw_metadata: str) -> str:
    """Clean and extract valid JSON from raw metadata."""
    try:
        # Use regex to extract JSON object
        json_match = re.search(r"{.*}", raw_metadata, re.DOTALL)
        if json_match:
            json_data = json_match.group()
            # Validate that it's valid JSON
            json.loads(json_data)
            return json_data
        else:
            raise ValueError("No JSON object found in metadata.")
    except json.JSONDecodeError as e:
        raise OutputParserException(f"Failed to parse metadata JSON: {e}")

def get_elasticsearch_store(es_index_name: str):
    log.info("using opensearch_url=%s", env.elastic.opensearch_url)
    return OpenSearchVectorSearch(
        index_name=es_index_name,
        opensearch_url=opensearch_url,
        embedding_function=get_embeddings(env),
        query_field="text",
        vector_query_field=env.embedding_document_field_name,
    )


def get_elasticsearch_store_without_embeddings(es_index_name: str):
    log.info("using opensearch_url=%s", env.elastic.opensearch_url)
    return OpenSearchVectorSearch(
        index_name=es_index_name,
        opensearch_url=opensearch_url,
        #embedding_function=get_embeddings(env),
        embedding_function=FakeEmbeddings(size=env.embedding_backend_vector_size),
    )


def create_alias(alias: str):
    log.warning("inside ingestor.py inside create_alias")
    es = env.elasticsearch_client()

    chunk_index_name = alias[:-8]  # removes -current

    # es.options(ignore_status=[400]).indices.create(index=chunk_index_name)
    #es.indices.create(index=chunk_index_name, ignore=400)  # ignore 400 error if index already exists
    es.indices.create(index=chunk_index_name, body=env.index_mapping, ignore=400)
    if not es.indices.exists_alias(name=alias):
        es.indices.put_alias(index=chunk_index_name, name=alias)

def retry_ingest(file_name, es_index_name, metadata, max_retries=3):
    """Retry the entire RunnableParallel block with metadata."""
    for attempt in range(max_retries):
        try:
            # Reinitialize the client on each retry
            es = env.elasticsearch_client()
            log.warning("Retrying ingest, attempt %d/%d", attempt + 1, max_retries)

            # Rebuild the chains to ensure fresh client connections
            log.warning("Before vectorstore_normal")
            vectorstore_normal = get_elasticsearch_store(es_index_name)
            log.warning("After vectorstore_normal")

            log.warning("Before chunk_ingest_chain")
            chunk_ingest_chain = ingest_from_loader(
                loader=UnstructuredChunkLoader(
                    chunk_resolution=ChunkResolution.normal,
                    env=env,
                    min_chunk_size=env.worker_ingest_min_chunk_size,
                    max_chunk_size=env.worker_ingest_max_chunk_size,
                    overlap_chars=0,
                    metadata=metadata,  # Pass metadata
                ),
                s3_client=env.s3_client(),
                vectorstore=vectorstore_normal,
                env=env,
            )
            log.warning("After chunk_ingest_chain")
            
            log.warning("Before vectorstore_large")
            vectorstore_large = get_elasticsearch_store_without_embeddings(es_index_name)
            log.warning("After vectorstore_large")

            log.warning("Before large_chunk_ingest_chain")
            large_chunk_ingest_chain = ingest_from_loader(
                loader=UnstructuredChunkLoader(
                    chunk_resolution=ChunkResolution.largest,
                    env=env,
                    min_chunk_size=env.worker_ingest_largest_chunk_size,
                    max_chunk_size=env.worker_ingest_largest_chunk_size,
                    overlap_chars=env.worker_ingest_largest_chunk_overlap,
                    metadata=metadata,  # Pass metadata
                ),
                s3_client=env.s3_client(),
                vectorstore=vectorstore_large,
                env=env,
            )
            log.warning("After large_chunk_ingest_chain")

            # Run RunnableParallel
            log.warning("Before new_ids")
            new_ids = RunnableParallel(
                {"normal": chunk_ingest_chain, "largest": large_chunk_ingest_chain}
            ).invoke(file_name)
            log.warning("After new_ids")

            return new_ids  # Exit if successful
        except exceptions.ConnectionError as e:
            log.warning(f"Connection error: {e}. Retrying...")
        except Exception as e:
            log.error(f"Unexpected error: {e}")
            break
    raise RuntimeError(f"Failed to ingest file {file_name} after {max_retries} attempts")


def _ingest_file(file_name: str, es_index_name: str = alias):
    log.warning("inside ingestor.py inside _ingest_file")
    log.warning("Ingesting file: %s", file_name)

    es = env.elasticsearch_client()

    if es_index_name == alias:
        if not es.indices.exists_alias(name=alias):
            log.warning("The alias does not exist")
            log.warning(f"Alias: {alias}, Exists: {es.indices.exists_alias(name=alias)}")
            create_alias(alias)
    else:
        #es.indices.create(index=es_index_name, ignore=400)
        es.indices.create(index=es_index_name, body=env.index_mapping, ignore=400)

    # Extract metadata
    metadata_loader = MetadataLoader(env=env, s3_client=env.s3_client(), file_name=file_name)
    raw_metadata = metadata_loader.extract_metadata()
    try:
        if isinstance(raw_metadata, dict) or hasattr(raw_metadata, "dict"):
            raw_metadata_json = json.dumps(raw_metadata.dict() if hasattr(raw_metadata, "dict") else raw_metadata)
        else:
            raw_metadata_json = str(raw_metadata)

        metadata = clean_json_metadata(raw_metadata_json)
        log.warning(f"Cleaned metadata: {metadata}")
    except OutputParserException as e:
        log.error(f"Failed to clean metadata: {e}")
        raise

    # Retry ingest with metadata
    new_ids = retry_ingest(file_name, es_index_name, metadata=metadata)

    log.info(
        "File: %s %s chunks ingested",
        file_name,
        {k: len(v) for k, v in new_ids.items()},
    )



def ingest_file(file_name: str, es_index_name: str = alias) -> str | None:
    try:
        _ingest_file(file_name, es_index_name)
    except Exception as e:
        logging.exception("Error while processing file [%s]", file_name)
        return f"{type(e)}: {e.args[0]}"
