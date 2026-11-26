import asyncio
import uuid
from dataclasses import dataclass

import boto3
from fastapi import HTTPException, UploadFile, status

from app.core.config import (
    AWS_S3_BUCKET,
    AWS_S3_REGION,
    MAX_PUBLICATION_IMAGE_BYTES,
    S3_PRESIGNED_URL_TTL_SECONDS,
)


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


@dataclass(frozen=True)
class StoredImage:
    key: str
    content_type: str


class S3ImageStorage:
    def __init__(self):
        self.bucket = AWS_S3_BUCKET
        self.client = boto3.client("s3", region_name=AWS_S3_REGION) if self.bucket else None

    def _require_configured(self):
        if not self.client or not self.bucket:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="El almacenamiento de imágenes no está configurado",
            )

    @staticmethod
    def _validate_signature(content: bytes, content_type: str):
        signatures = {
            "image/jpeg": content.startswith(b"\xff\xd8\xff"),
            "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/webp": len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP",
        }
        if not signatures.get(content_type, False):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="El contenido del archivo no corresponde a una imagen permitida",
            )

    async def _upload(self, key_prefix: str, file: UploadFile, too_large_message: str) -> StoredImage:
        self._require_configured()
        content_type = (file.content_type or "").lower()
        extension = ALLOWED_IMAGE_TYPES.get(content_type)
        if not extension:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Solo se permiten imágenes JPEG, PNG o WebP",
            )

        content = await file.read(MAX_PUBLICATION_IMAGE_BYTES + 1)
        if len(content) > MAX_PUBLICATION_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=too_large_message,
            )
        if not content:
            raise HTTPException(status_code=400, detail="La imagen está vacía")
        self._validate_signature(content, content_type)

        key = f"{key_prefix}/{uuid.uuid4()}.{extension}"
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )
        return StoredImage(key=key, content_type=content_type)

    async def upload(self, publication_id: str, file: UploadFile) -> StoredImage:
        return await self._upload(
            f"publicaciones/{publication_id}",
            file,
            "Cada imagen debe pesar como máximo 12 MB",
        )

    async def upload_profile(self, user_id: str, file: UploadFile) -> StoredImage:
        return await self._upload(
            f"usuarios/{user_id}/perfil",
            file,
            "La foto de perfil debe pesar como máximo 12 MB",
        )

    async def delete(self, key: str):
        if self.client and self.bucket:
            await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)

    def resolve_url(self, value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith(("https://", "http://")):
            return value
        return self.signed_url(value)

    def signed_url(self, key: str) -> str | None:
        if not self.client or not self.bucket:
            return None
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=S3_PRESIGNED_URL_TTL_SECONDS,
        )


image_storage = S3ImageStorage()
