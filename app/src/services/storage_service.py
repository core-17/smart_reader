import boto3
from botocore.client import Config

S3_ENDPOINT = "http://127.0.0.1:8333"
S3_ACCESS_KEY = "smartreader_key"
S3_SECRET_KEY = "smartreader_secret"
BUCKET_NAME = "smart-reader-books"

s3_client = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)


def init_s3_bucket():
    try:
        buckets = [b["Name"] for b in s3_client.list_buckets().get("Buckets", [])]
        if BUCKET_NAME not in buckets:
            s3_client.create_bucket(Bucket=BUCKET_NAME)
    except Exception as e:
        print(f"S3 init warning: {e}")


def upload_pdf_to_s3(key: str, data: bytes) -> str:
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType="application/pdf",
    )
    return key
