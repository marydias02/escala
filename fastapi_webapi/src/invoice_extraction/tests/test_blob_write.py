from azure.identity import AzureCliCredential, ClientSecretCredential
from azure.storage.blob import BlobServiceClient
from loguru import logger

from config.settings import settings

if __name__ == "__main__":
    logger.info("🎯 Testing write access to Azure Blob Storage")

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

    blob_name = "test/test_blob_write.txt"
    blob_client = container_client.get_blob_client(blob_name)

    logger.info(f"Uploading blob '{blob_name}' to container '{container_name}'")
    blob_client.upload_blob(b"hello from test_blob_write.py", overwrite=True)

    logger.info(f"Downloading blob '{blob_name}' to verify write")
    content = blob_client.download_blob().readall()
    logger.info(f"Read back content: {content!r}")

    logger.info(f"Deleting blob '{blob_name}'")
    blob_client.delete_blob()

    logger.info("Write test completed successfully")
