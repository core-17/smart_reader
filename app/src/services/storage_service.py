import logging
import os

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://127.0.0.1:8333")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "smartreader_key")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "smartreader_secret")
BUCKET_NAME = os.getenv("S3_BUCKET", "smart-reader-books")

s3_client = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)


def init_s3_bucket() -> None:
    try:
        s3_client.head_bucket(Bucket=BUCKET_NAME)
    except ClientError:
        try:
            s3_client.create_bucket(Bucket=BUCKET_NAME)
            logger.info("Створено bucket %s", BUCKET_NAME)
        except Exception:
            logger.exception("Не вдалося створити bucket %s", BUCKET_NAME)
    except Exception:
        logger.exception("S3 недоступний за адресою %s", S3_ENDPOINT)


def upload_pdf_to_s3(key: str, data: bytes) -> str:
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType="application/pdf",
    )
    return key


def get_pdf_from_s3(key: str) -> bytes:
    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
    return response["Body"].read()


def delete_pdf_from_s3(key: str) -> None:
    try:
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=key)
    except Exception:
        logger.exception("Не вдалося видалити %s", key)