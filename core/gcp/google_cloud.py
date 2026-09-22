import logging
import mimetypes
import os
import random

import google.auth.transport.requests
import google.oauth2.id_token
import requests
from django.conf import settings
from google.cloud import storage

logger = logging.getLogger(__name__)


def uploadFile(file, destinationFileName):
    """Uploads a file object to GCS, returns the blob name or None on failure."""
    try:
        storage_client = storage.Client.from_service_account_json(settings.GOOGLE_APPLICATION_CREDENTIALS)
        bucket = storage_client.bucket(settings.GS_BUCKET_NAME)
        blob = bucket.blob(destinationFileName)
        blob.upload_from_file(file)
        return blob.name
    except Exception:
        logger.exception("[GCS UPLOAD] Failed to upload file to %s", destinationFileName)
        return None


def uploadBlob(content, filename):
    """Uploads text content to GCS, returns the blob name or None on failure."""
    try:
        storage_client = storage.Client.from_service_account_json(settings.GOOGLE_APPLICATION_CREDENTIALS)
        bucket = storage_client.bucket(settings.GS_BUCKET_NAME)
        blob = bucket.blob(filename)
        with blob.open("w") as f:
            f.write(content)
        return blob.name
    except Exception:
        logger.exception("[GCS UPLOAD] Failed to upload blob to %s", filename)
        return None


def readBlob(filename):
    """Returns the GCS blob for filename, or None on failure."""
    try:
        storage_client = storage.Client.from_service_account_json(settings.GOOGLE_APPLICATION_CREDENTIALS)
        bucket = storage_client.bucket(settings.GS_BUCKET_NAME)
        return bucket.blob(filename)
    except Exception:
        logger.exception("[GCS READ] Failed to read blob %s", filename)
        return None


def make_authorized_post_request(endpoint, audience, files):
    """
    POSTs to an authenticated HTTP endpoint (e.g. a Cloud Run service) using
    an ID token obtained via google-auth for the given audience.
    """
    auth_req = google.auth.transport.requests.Request()
    id_token = google.oauth2.id_token.fetch_id_token(auth_req, audience)

    headers = {"Authorization": f"Bearer {id_token}"}
    response = requests.post(endpoint, headers=headers, files=files)

    if response.status_code != 200:
        raise IOError(f"Error processing image in Cloud Run service: {response.text}")

    return response


def get_mime_type_with_mimetypes(filename):
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type


def saveFileToGivenDirectory(file, destinationDirectory):
    random_name = str(random.randint(2345678909800, 9923456789000))
    return uploadFile(file, destinationDirectory + "/" + random_name + os.path.splitext(file.name)[1])
