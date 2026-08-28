from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient
from loguru import logger

from config.settings import settings

if __name__ == "__main__":
    logger.info("🎯 Testing access to Azure Blob Storage")

    credential = AzureCliCredential()

    logger.info(f"Connecting to blob endpoint '{settings.BLOB_STORAGE_ENDPOINT}'")
    blob_service_client = BlobServiceClient(
        account_url=settings.BLOB_STORAGE_ENDPOINT,
        credential=credential,
    )

    container_name = settings.BLOB_CONTAINER_NAME
    container_client = blob_service_client.get_container_client(container_name)

    logger.info(f"Listing blobs in container '{container_name}'")
    blobs = sorted(blob.name for blob in container_client.list_blobs())
    logger.info(f"Found {len(blobs)} blobs")
    for name in blobs:
        print(" -", name)
