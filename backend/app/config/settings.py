# backend/app/config/settings.py
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "OnionSetu Backend API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "dev"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./onionsetu_backend.db"
    
    # Auth & JWT
    JWT_SECRET_KEY: str = "onionsetu_secure_dev_jwt_secret_change_in_prod"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    
    # Supabase File Storage
    SUPABASE_URL: str = "https://mock-onionsetu.supabase.co"
    SUPABASE_KEY: str = "mock-supabase-service-key"
    SUPABASE_BUCKET_IMAGES: str = "onion-evidence-images"
    SUPABASE_BUCKET_REPORTS: str = "onion-digital-reports"
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # Public base URL of this deployment. Report QR codes encode
    # {PUBLIC_BASE_URL}/v1/verify/{scan_id} so printed reports resolve to the
    # real verification endpoint. Must be set to the deployed host for QRs
    # to verify outside localhost.
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    
    # Grading Policy Version
    GRADING_POLICY_VERSION: str = "v1.0.0"

    # Roboflow Hosted Vision Inference (SERVER-SIDE ONLY).
    # The API key must never be shipped to Flutter clients, committed to git,
    # or placed in any frontend asset/config. Configure via environment only.
    ROBOFLOW_API_KEY: str = ""
    ROBOFLOW_MODEL_ID: str = "onion-yhzc7-mo9ib/1"
    ROBOFLOW_API_URL: str = "https://serverless.roboflow.com"
    ROBOFLOW_TIMEOUT_SECONDS: float = 30.0
    # Server-side prediction filters (Roboflow 0-100 scale):
    # `confidence` = minimum prediction confidence, `overlap` = NMS IoU limit.
    ROBOFLOW_MIN_CONFIDENCE: int = 45
    ROBOFLOW_OVERLAP: int = 30

    # Batch visual assessment via OpenRouter (SERVER-SIDE ONLY).
    # Same secrecy rules as ROBOFLOW_API_KEY: key in Authorization header
    # only, never in URLs/bodies/logs/responses, never committed.
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL_ID: str = "qwen/qwen2.5-vl-72b-instruct:free"
    OPENROUTER_API_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_TIMEOUT_SECONDS: float = 90.0
    # Multi-view batch capture: graders photograph the SAME physical batch
    # from several angles. Views are submitted in ONE request for the whole
    # batch; the representative set is capped here for provider payload size.
    OPENROUTER_MAX_IMAGES: int = 15
    # Minimum submitted views for a representative batch assessment. Fewer
    # views do not abort (fail loudly only on total evidence failure) but
    # force human review.
    BATCH_MIN_VIEWS: int = 10
    # Grader-declared physical batch size (number of onions in the lot being
    # graded). This user-entered count is the ONLY denominator for URS% —
    # per-view detection tallies are never summed as unique onions because
    # the same physical onions recur across views (no double-counting).
    BATCH_MIN_ASSESSED_ONIONS: int = 100
    BATCH_MAX_ASSESSED_ONIONS: int = 200
    # Longest image side after server-side normalization (JPEG, Pillow).
    OPENROUTER_MAX_IMAGE_DIM: int = 1024

    # Deterministic batch grading policy (A/B/C/Reject).
    # BLOCKER: no official APMC A/B/C/Reject thresholds exist in this
    # repository. Every value below is an explicitly PROVISIONAL default
    # (see BATCH_POLICY_VERSION) that must be replaced by officially
    # signed-off thresholds. The policy never invents measurements — it
    # only applies these configured rules to validated AI outputs.
    BATCH_POLICY_VERSION: str = "v0.2-provisional"
    # Minimum provider assessment_confidence to avoid forced human review.
    BATCH_MIN_ASSESSMENT_CONFIDENCE: float = 0.70
    # Conservative grade used when no valid AI suggestion exists.
    BATCH_FALLBACK_GRADE: str = "Reject"
    # Cap applied when a high-severity issue coexists with a high suggestion.
    BATCH_MAX_GRADE_WITH_HIGH_SEVERITY: str = "C"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
