from azure.identity import AzureCliCredential, ClientSecretCredential
from azure.storage.blob import BlobServiceClient
from loguru import logger

from config.settings import settings

if __name__ == "__main__":
    logger.info("🎯 Testing access to Azure Blob Storage")

    if settings.AZURE_FLG_USE_APP_REGISTRATION:
        logger.info(f"Authenticating with app registration '{settings.AZURE_CLIENT_ID}'")
        credential = ClientSecretCredential(
            settings.AZURE_TENANT_ID,
            settings.AZURE_CLIENT_ID,
            settings.AZURE_CLIENT_SECRET,
        )
    else:
        logger.info("Authenticating with the current `az login` session")
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
