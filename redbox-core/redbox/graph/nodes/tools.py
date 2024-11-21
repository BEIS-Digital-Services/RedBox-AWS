from typing import Annotated, Iterable

import numpy as np
import requests
import tiktoken
from elasticsearch import Elasticsearch
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.documents import Document
from langchain_core.embeddings.embeddings import Embeddings
from langchain_core.messages import ToolCall
from langchain_core.tools import Tool, tool
from langgraph.prebuilt import InjectedState
from sklearn.metrics.pairwise import cosine_similarity

from redbox.api.format import format_documents
from redbox.chains.components import get_embeddings
from redbox.models.chain import RedboxState
from redbox.models.file import ChunkCreatorType, ChunkMetadata, ChunkResolution
from redbox.models.settings import get_settings
from redbox.retriever.queries import (
    add_document_filter_scores_to_query,
    build_document_query,
)
from redbox.retriever.retrievers import query_to_documents
from redbox.transform import (
    merge_documents,
    sort_documents,
)


def build_search_documents_tool(
    es_client: Elasticsearch,
    index_name: str,
    embedding_model: Embeddings,
    embedding_field_name: str,
    chunk_resolution: ChunkResolution | None,
) -> Tool:
    """Constructs a tool that searches the index and sets state.documents."""

    @tool(response_format="content_and_artifact")
    def _search_documents(query: str, state: Annotated[RedboxState, InjectedState]) -> tuple[str, list[Document]]:
        """
        Search for documents uploaded by the user based on a query string.

        This function performs a search over the user's uploaded documents
        and returns snippets from the documents ordered by relevance and
        grouped by document.

        Args:
            query (str): The search query string used to match documents.
                This could be a keyword, phrase, question, or text from
                the documents.

        Returns:
            dict[str, Any]: A collection of document objects that match the query.
        """
        query_vector = embedding_model.embed_query(query)
        selected_files = state.request.s3_keys
        permitted_files = state.request.permitted_s3_keys
        ai_settings = state.request.ai_settings

        # Initial pass
        initial_query = build_document_query(
            query=query,
            query_vector=query_vector,
            selected_files=selected_files,
            permitted_files=permitted_files,
            embedding_field_name=embedding_field_name,
            chunk_resolution=chunk_resolution,
            ai_settings=ai_settings,
        )
        initial_documents = query_to_documents(es_client=es_client, index_name=index_name, query=initial_query)

        # Handle nothing found (as when no files are permitted)
        if not initial_documents:
            return "", []

        # Adjacent documents
        with_adjacent_query = add_document_filter_scores_to_query(
            elasticsearch_query=initial_query,
            ai_settings=ai_settings,
            centres=initial_documents,
        )
        adjacent_boosted = query_to_documents(es_client=es_client, index_name=index_name, query=with_adjacent_query)

        # Merge and sort
        merged_documents = merge_documents(initial=initial_documents, adjacent=adjacent_boosted)
        sorted_documents = sort_documents(documents=merged_documents)

        # Return as state update
        return format_documents(sorted_documents), sorted_documents

    return _search_documents


def build_govuk_search_tool(num_results: int = 1, filter=True) -> Tool:
    """Constructs a tool that searches gov.uk and sets state["documents"]."""

    tokeniser = tiktoken.encoding_for_model("gpt-4o")

    def recalculate_similarity(response, query, num_results):
        embedding_model = get_embeddings(get_settings())
        em_query = embedding_model.embed_query(query)
        for r in response.get("results"):
            description = r.get("description")
            em_des = embedding_model.embed_query(description)
            r["similarity"] = cosine_similarity(np.array(em_query).reshape(1, -1), np.array(em_des).reshape(1, -1))[0][
                0
            ]
        response["results"] = sorted(response.get("results"), key=lambda x: x["similarity"], reverse=True)[:num_results]
        return response

    @tool(response_format="content_and_artifact")
    def _search_govuk(query: str) -> tuple[str, list[Document]]:
        """
        Search for documents on gov.uk based on a query string.
        This endpoint is used to search for documents on gov.uk. There are many types of documents on gov.uk.
        Types include:
        - guidance
        - policy
        - legislation
        - news
        - travel advice
        - departmental reports
        - statistics
        - consultations
        - appeals
        """

        url_base = "https://www.gov.uk"
        required_fields = [
            "format",
            "title",
            "description",
            "indexable_content",
            "link",
        ]

        response = requests.get(
            f"{url_base}/api/search.json",
            params={
                "q": query,
                "count": 10 if filter else num_results,
                "fields": required_fields,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        response = response.json()

        if filter:
            response = recalculate_similarity(response, query, num_results)

        mapped_documents = []
        for i, doc in enumerate(response["results"]):
            if any(field not in doc for field in required_fields):
                continue

            mapped_documents.append(
                Document(
                    page_content=doc["indexable_content"],
                    metadata=ChunkMetadata(
                        index=i,
                        uri=f"{url_base}{doc['link']}",
                        token_count=len(tokeniser.encode(doc["indexable_content"])),
                        creator_type=ChunkCreatorType.gov_uk,
                    ).model_dump(),
                )
            )

        return format_documents(mapped_documents), mapped_documents

    return _search_govuk


def build_search_wikipedia_tool(number_wikipedia_results=1, max_chars_per_wiki_page=12000) -> Tool:
    """Constructs a tool that searches Wikipedia"""
    _wikipedia_wrapper = WikipediaAPIWrapper(
        top_k_results=number_wikipedia_results,
        doc_content_chars_max=max_chars_per_wiki_page,
    )
    tokeniser = tiktoken.encoding_for_model("gpt-4o")

    @tool(response_format="content_and_artifact")
    def _search_wikipedia(query: str) -> tuple[str, list[Document]]:
        """
        Search Wikipedia for information about the queried entity.
        Useful for when you need to answer general questions about people, places, objects, companies, facts, historical events, or other subjects.
        Input should be a search query.

        Args:
            query (str): The search query string used to find pages.
                This could be a keyword, phrase, or name

        Returns:
            response (str): The content of the relevant Wikipedia page
        """
        response = _wikipedia_wrapper.load(query)
        mapped_documents = [
            Document(
                page_content=doc.page_content,
                metadata=ChunkMetadata(
                    index=i,
                    uri=doc.metadata["source"],
                    token_count=len(tokeniser.encode(doc.page_content)),
                    creator_type=ChunkCreatorType.wikipedia,
                ).model_dump(),
            )
            for i, doc in enumerate(response)
        ]
        docs = mapped_documents
        return format_documents(docs), docs

    return _search_wikipedia


class BaseRetrievalToolLogFormatter:
    def __init__(self, t: ToolCall) -> None:
        self.tool_call = t

    def log_call(self, tool_call: ToolCall):
        return f"Used {tool_call["name"]} to get more information"

    def log_result(self, documents: Iterable[Document]):
        if len(documents) == 0:
            return f"{self.tool_call["name"]} returned no documents"
        return f"Reading {documents[1].get("creator_type")} document{"s" if len(documents)>1 else ""} {','.join(set([d.metadata["uri"].split("/")[-1] for d in documents]))}"


class SearchWikipediaLogFormatter(BaseRetrievalToolLogFormatter):
    def log_call(self):
        return f"Searching Wikipedia for '{self.tool_call["args"]["query"]}'"

    def log_result(self, documents: Iterable[Document]):
        return f"Reading Wikipedia page{"s" if len(documents)>1 else ""} {','.join(set([d.metadata["uri"].split("/")[-1] for d in documents]))}"


class SearchDocumentsLogFormatter(BaseRetrievalToolLogFormatter):
    def log_call(self):
        return f"Searching your documents for '{self.tool_call["args"]["query"]}'"

    def log_result(self, documents: Iterable[Document]):
        return f"Reading {len(documents)} snippets from your documents {','.join(set([d.metadata.get("name", "") for d in documents]))}"


class SearchGovUKLogFormatter(BaseRetrievalToolLogFormatter):
    def log_call(self):
        return f"Searching .gov.uk pages for '{self.tool_call["args"]["query"]}'"

    def log_result(self, documents: Iterable[Document]):
        return f"Reading pages from .gov.uk, {','.join(set([d.metadata["uri"].split("/")[-1] for d in documents]))}"


__RETRIEVEAL_TOOL_MESSAGE_FORMATTERS = {
    "_search_wikipedia": SearchWikipediaLogFormatter,
    "_search_documents": SearchDocumentsLogFormatter,
    "_search_govuk": SearchGovUKLogFormatter,
}


def get_log_formatter_for_retrieval_tool(t: ToolCall) -> BaseRetrievalToolLogFormatter:
    return __RETRIEVEAL_TOOL_MESSAGE_FORMATTERS.get(t["name"], BaseRetrievalToolLogFormatter)(t)
