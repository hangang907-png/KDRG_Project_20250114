"""
KDRG Enterprise - FastAPI 메인 앱
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import os
import sys

# 경로 설정
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from api.patients import router as patients_router
from api.kdrg import router as kdrg_router
from api.analysis import router as analysis_router
from api.hira import router as hira_router
from api.ai import router as ai_router
from api.auth import router as auth_router
from api.feedback import router as feedback_router
from api.comparison import router as comparison_router
from api.pregrouper import router as pregrouper_router
from api.optimization import router as optimization_router

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{settings.LOG_DIR}/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 생명주기 관리"""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    # 필요한 디렉토리 생성
    for dir_path in [settings.DATA_DIR, settings.UPLOAD_DIR, settings.EXPORT_DIR, settings.LOG_DIR]:
        os.makedirs(dir_path, exist_ok=True)
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")


# FastAPI 앱 생성
app = FastAPI(
    title=settings.APP_NAME,
    description="KDRG(한국형 DRG) 관리 및 최적화 시스템",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 전역 예외 처리
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "내부 서버 오류가 발생했습니다.",
            "error": str(exc) if settings.DEBUG else "Internal Server Error"
        }
    )


# 라우터 등록
app.include_router(auth_router, prefix="/api/auth", tags=["인증"])
app.include_router(patients_router, prefix="/api/patients", tags=["환자관리"])
app.include_router(kdrg_router, prefix="/api/kdrg", tags=["KDRG"])
app.include_router(analysis_router, prefix="/api/analysis", tags=["분석"])
app.include_router(hira_router, prefix="/api/hira", tags=["심평원API"])
app.include_router(ai_router, prefix="/api/ai", tags=["AI분석"])
app.include_router(feedback_router, prefix="/api/feedback", tags=["환류데이터"])
app.include_router(comparison_router, prefix="/api/comparison", tags=["비교분석"])
app.include_router(pregrouper_router, prefix="/api/pregrouper", tags=["Pre-Grouper"])
app.include_router(optimization_router, prefix="/api", tags=["전역최적화"])


# 헬스체크
@app.get("/health", tags=["시스템"])
async def health_check():
    """서버 상태 확인"""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.get("/", tags=["시스템"])
async def root():
    """루트 엔드포인트"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
