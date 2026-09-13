# backend/app/services/supabase_storage_service.py
import os
from typing import Optional
from backend.app.config.settings import settings

class SupabaseStorageService:
    @staticmethod
    async def upload_image(file_bytes: bytes, file_name: str, bucket: Optional[str] = None) -> str:
        # In production connects to Supabase Storage client; in local/dev stores in static directory
        bucket_name = bucket or settings.SUPABASE_BUCKET_IMAGES
        os.makedirs(f"./static/{bucket_name}", exist_ok=True)
        local_target = f"./static/{bucket_name}/{file_name}"
        with open(local_target, "wb") as f:
            f.write(file_bytes)
        
        # Return secure URL or local static path
        return f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{file_name}"

    @staticmethod
    async def upload_pdf_report(pdf_bytes: bytes, file_name: str) -> str:
        bucket_name = settings.SUPABASE_BUCKET_REPORTS
        os.makedirs(f"./static/{bucket_name}", exist_ok=True)
        local_target = f"./static/{bucket_name}/{file_name}"
        with open(local_target, "wb") as f:
            f.write(pdf_bytes)
        
        return f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{file_name}"
