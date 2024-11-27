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
    opensearch_url="https://localhost:9200"
else:
    opensearch_url = env_vars.str('ELASTIC__COLLECTION_ENPDOINT')

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
        opensearch_url=env.elastic.opensearch_url,
        embedding_function=get_embeddings(env),
        query_field="text",
        vector_query_field=env.embedding_document_field_name,
    )


def get_elasticsearch_store_without_embeddings(es_index_name: str):
    log.info("using opensearch_url=%s", env.elastic.opensearch_url)
    return OpenSearchVectorSearch(
        index_name=es_index_name,
        opensearch_url=env.elastic.opensearch_url,
        embedding_function=get_embeddings(env),
    )


def create_alias(alias: str):
    log.warning("inside ingestor.py inside create_alias")
    es = env.elasticsearch_client()

    chunk_index_name = alias[:-8]  # removes -current

    # es.options(ignore_status=[400]).indices.create(index=chunk_index_name)
    es.indices.create(index=chunk_index_name, ignore=400)  # ignore 400 error if index already exists
    if not es.indices.exists_alias(name=alias):
        es.indices.put_alias(index=chunk_index_name, name=alias)


def _ingest_file(file_name: str, es_index_name: str = alias):
    log.warning("inside ingestor.py inside _ingest_file")
    log.info("Ingesting file: %s", file_name)

    es = env.elasticsearch_client()

    if es_index_name == alias:
        if not es.indices.exists_alias(name=alias):
            log.info("The alias does not exist")
            log.info(f"Alias: {alias}, Exists: {es.indices.exists_alias(name=alias)}")
            create_alias(alias)
    else:
        # es.options(ignore_status=[400]).indices.create(index=es_index_name)
        es.indices.create(index=es_index_name, ignore=400)

    # Extract metadata
    metadata_loader = MetadataLoader(env=env, s3_client=env.s3_client(), file_name=file_name)
    raw_metadata = metadata_loader.extract_metadata()
    try:
        # Ensure `raw_metadata` is converted to a JSON string if it's an object
        if isinstance(raw_metadata, dict) or hasattr(raw_metadata, "dict"):
            raw_metadata_json = json.dumps(raw_metadata.dict() if hasattr(raw_metadata, "dict") else raw_metadata)
        else:
            raw_metadata_json = str(raw_metadata)

        metadata = clean_json_metadata(raw_metadata_json)
        log.info(f"Cleaned metadata: {metadata}")
    except OutputParserException as e:
        log.error(f"Failed to clean metadata: {e}")
        raise

    # Initialize chunk_ingest_chain
    vectorstore_normal = get_elasticsearch_store(es, es_index_name)
    log.warning(f"Vectorstore (normal) initialized: {vectorstore_normal}")

    chunk_ingest_chain = ingest_from_loader(
        loader=UnstructuredChunkLoader(
            chunk_resolution=ChunkResolution.normal,
            env=env,
            min_chunk_size=env.worker_ingest_min_chunk_size,
            max_chunk_size=env.worker_ingest_max_chunk_size,
            overlap_chars=0,
            metadata=metadata,
        ),
        s3_client=env.s3_client(),
        vectorstore=get_elasticsearch_store(es_index_name),
        env=env,
    )

    # Initialize large_chunk_ingest_chain
    vectorstore_large = get_elasticsearch_store_without_embeddings(es, es_index_name)
    log.warning(f"Vectorstore (large) initialized: {vectorstore_large}")

    large_chunk_ingest_chain = ingest_from_loader(
        loader=UnstructuredChunkLoader(
            chunk_resolution=ChunkResolution.largest,
            env=env,
            min_chunk_size=env.worker_ingest_largest_chunk_size,
            max_chunk_size=env.worker_ingest_largest_chunk_size,
            overlap_chars=env.worker_ingest_largest_chunk_overlap,
            metadata=metadata,
        ),
        s3_client=env.s3_client(),
        vectorstore=get_elasticsearch_store_without_embeddings(es_index_name),
        env=env,
    )

    # Process the chains
    new_ids = RunnableParallel({"normal": chunk_ingest_chain, "largest": large_chunk_ingest_chain}).invoke(file_name)

    logging.info(
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
