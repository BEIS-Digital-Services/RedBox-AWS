import logging
from functools import partial
from io import BytesIO
from typing import TYPE_CHECKING, Iterator
import boto3

from langchain.vectorstores import VectorStore
from langchain_core.documents.base import Document
from langchain_core.runnables import Runnable, RunnableLambda, chain

from redbox.loader.loaders import UnstructuredChunkLoader
from redbox.models.settings import Settings
from opensearchpy.exceptions import AuthorizationException
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client
else:
    S3Client = object

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()
log.warning("inside ingest.py")

@chain
def log_chunks(chunks: list[Document]):
    try:
        log.warning("Processing %s chunks", len(chunks))
        return chunks
    except AuthorizationException as e:
        log.error(f"403 Authorization Error in log_chunks: {e}")
        raise
    except Exception as e:
        log.error(f"Unexpected error in log_chunks: {e}")
        raise


def document_loader(document_loader: UnstructuredChunkLoader, s3_client: S3Client, env: Settings) -> Runnable:
    @chain
    def wrapped(file_name: str) -> Iterator[Document]:
        try:
            log.warning(f"Fetching file '{file_name}' from S3 bucket '{env.bucket_name}'.")
            file_bytes = s3_client.get_object(Bucket=env.bucket_name, Key=file_name)["Body"].read()
            log.warning("S3 file fetched successfully, passing to document loader.")
            return document_loader.lazy_load(file_name=file_name, file_bytes=BytesIO(file_bytes))
        except ClientError as e:
            log.error(f"S3 ClientError while fetching file '{file_name}': {e}")
            if e.response.get("Error", {}).get("Code") == "403":
                log.error("S3 returned a 403 Authorization Error.")
            raise
        except AuthorizationException as e:
            log.error(f"403 Authorization Error in document_loader: {e}")
            raise
        except Exception as e:
            log.error(f"Unexpected error in document_loader: {e}")
            raise

    return wrapped


def ingest_from_loader(
    loader: UnstructuredChunkLoader,
    s3_client: S3Client,
    vectorstore: VectorStore,
    env: Settings,
) -> Runnable:
    log.warning("inside ingest.py inside ingest_from_loader")
    try:
        doc_loader = document_loader(document_loader=loader, s3_client=s3_client, env=env)
        doc_list = RunnableLambda(list)
        log_chunk_step = log_chunks

        def safe_add_documents(docs):
            try:
                log.warning("Attempting to add documents to vectorstore...")

                credentials = boto3.Session().get_credentials()
                if not credentials.token:
                    log.warning("Warning: No session token, request may be anonymous.")

                log.warning(f"Client host: {vectorstore.client.transport.hosts}")

                #index_exists = vectorstore.client.indices.exists(index="redbox-data-chunk")
                #log.warning(f"Index exists check: {index_exists}")
                
                return vectorstore.add_documents(docs, create_index_if_not_exists=False)
            except AuthorizationException as e:
                log.error(f"403 Authorization Error in vectorstore.add_documents: {e}")
                raise
            except Exception as e:
                log.error(f"Unexpected error in vectorstore.add_documents: {e}")
                raise

        add_docs = RunnableLambda(safe_add_documents)

        return doc_loader | doc_list | log_chunk_step | add_docs
    except AuthorizationException as e:
        log.error(f"403 Authorization Error in ingest_from_loader: {e}")
        raise
    except Exception as e:
        log.error(f"Unexpected error in ingest_from_loader: {e}")
        raise
