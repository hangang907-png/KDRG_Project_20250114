import os
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "KDRG Enterprise"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8081
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/kdrg.db"
    
    # Security
    SECRET_KEY: str = "change-this-in-prod"
    ENCRYPTION_KEY: str = "change-this-to-32-bytes-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    
    # Privacy Settings
    MASK_PATIENT_NAME: bool = True
    MASK_PATIENT_ID: bool = True
    ENCRYPT_SENSITIVE_DATA: bool = True
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    
    # HIRA API Settings (심평원)
    HIRA_API_KEY: Optional[str] = None
    HIRA_API_BASE_URL: str = "http://apis.data.go.kr/B551182"
    
    # Data.go.kr API Settings (공공데이터포털)
    DATA_GO_KR_API_KEY: Optional[str] = None
    
    # AI/ML API Settings
    OPENAI_API_KEY: Optional[str] = None
    CLAUDE_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    
    # File Paths
    DATA_DIR: str = "./data"
    UPLOAD_DIR: str = "./data/uploads"
    EXPORT_DIR: str = "./data/exports"
    LOG_DIR: str = "./logs"
    
    # Upload constraints
    MAX_UPLOAD_SIZE_MB: int = 10
    MAX_UPLOAD_ROWS: int = 5000
    MAX_RESULT_PREVIEW: int = 100
    MAX_ERROR_PREVIEW: int = 20

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value):
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value
    
    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def MAX_UPLOAD_BYTES(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()

# Ensure directories exist
for dir_path in [settings.DATA_DIR, settings.UPLOAD_DIR, settings.EXPORT_DIR, settings.LOG_DIR]:
    os.makedirs(dir_path, exist_ok=True)


