import json
from http import HTTPStatus
from pathlib import Path

import pytest
from elasticsearch import NotFoundError
from fastapi.testclient import TestClient
from redbox.models import File
from redbox.storage import ElasticsearchStorageHandler

from core_api.routes.file import env


@pytest.mark.asyncio()
async def test_post_file_upload(app_client: TestClient, file_pdf_path: Path, headers: dict[str, str]):
    """
    Given a new file
    When I POST it to /file
    I Expect to see it persisted in elastic-search
    """

    file_key = file_pdf_path.name

    response = app_client.post(
        "/file",
        json={
            "key": file_key,
            "bucket": env.bucket_name,
        },
        headers=headers,
    )
    assert response.status_code == HTTPStatus.CREATED

    file = json.loads(response.content.decode("utf-8"))
    assert file["ingest_status"] == "processing"


def test_list_files(app_client: TestClient, stored_file_1: File, headers: dict[str, str]):
    """
    Given a previously saved file
    When I GET all files from /file
    I Expect the response to contain this file
    """
    response = app_client.get("/file", headers=headers)
    assert response.status_code == HTTPStatus.OK

    file_list = json.loads(response.content.decode("utf-8"))
    assert len(file_list) > 0

    assert str(stored_file_1.uuid) in [file["uuid"] for file in file_list]


def test_get_file(app_client: TestClient, stored_file_1: File, headers: dict[str, str]):
    """
    Given a previously saved file
    When I GET it from /file/uuid
    I Expect to receive it
    """
    response = app_client.get(f"/file/{stored_file_1.uuid}", headers=headers)
    assert response.status_code == HTTPStatus.OK


def test_get_missing_file(app_client: TestClient, headers: dict[str, str]):
    """
    Given a nonexistent file
    When I GET it from /file/uuid
    I Expect to receive a 404 error
    """
    response = app_client.get("/file/ffffffff-ffff-ffff-ffff-ffffffffffff", headers=headers)
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_file(
    app_client: TestClient, es_storage_handler: ElasticsearchStorageHandler, chunked_file: File, headers: dict[str, str]
):
    """
    Given a previously saved file
    When I DELETE it to /file
    I Expect to see it removed from s3 and elastic-search, including the chunks
    """
    # check assets exist
    assert es_storage_handler.read_item(item_uuid=chunked_file.uuid, model_type="file")
    assert es_storage_handler.list_all_items("chunk", chunked_file.creator_user_uuid)

    response = app_client.delete(f"/file/{chunked_file.uuid}", headers=headers)
    assert response.status_code == HTTPStatus.OK

    es_storage_handler.refresh()

    # check assets dont exist

    with pytest.raises(NotFoundError):
        es_storage_handler.read_item(item_uuid=chunked_file.uuid, model_type="file")

    assert not es_storage_handler.list_all_items("chunk", chunked_file.creator_user_uuid)


def test_delete_missing_file(app_client: TestClient, headers: dict[str, str]):
    """
    Given a nonexistent file
    When I DELETE it to /file
    I Expect to receive a 404 error
    """
    response = app_client.delete("/file/ffffffff-ffff-ffff-ffff-ffffffffffff", headers=headers)
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_missing_file_chunks(app_client: TestClient, headers: dict[str, str]):
    """
    Given a nonexistent file
    When I GET it from /file/uuid/chunks
    I Expect to receive a 404 error
    """
    response = app_client.get("/file/ffffffff-ffff-ffff-ffff-ffffffffffff/chunks", headers=headers)
    assert response.status_code == HTTPStatus.NOT_FOUND
