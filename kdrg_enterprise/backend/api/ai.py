"""
AI 분석 API 라우터
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from services.ai_service import ai_service, AIProvider
from api.auth import require_auth, require_admin, UserInfo
from api.patients import PATIENTS_DB

router = APIRouter()


# 모델 정의
class AIKeyConfig(BaseModel):
    provider: str  # "openai", "claude", "gemini"
    api_key: str


class DRGRecommendationRequest(BaseModel):
    primary_diagnosis_code: str
    diagnosis_name: Optional[str] = None
    kdrg_code: Optional[str] = None
    aadrg_code: Optional[str] = None
    surgery_name: Optional[str] = None
    length_of_stay: Optional[int] = None
    comorbidities: Optional[str] = None
    complications: Optional[str] = None


class DiagnosisMappingRequest(BaseModel):
    diagnosis_code: str
    diagnosis_name: Optional[str] = None


class AuditReportRequest(BaseModel):
    include_optimizations: bool = True


@router.post("/config/apikey")
async def set_ai_api_key(
    config: AIKeyConfig,
    user: UserInfo = Depends(require_admin)
):
    """AI API 키 설정 (관리자 전용)"""
    if config.provider.lower() == "openai":
        ai_service.set_openai_key(config.api_key)
    elif config.provider.lower() == "claude":
        ai_service.set_claude_key(config.api_key)
    elif config.provider.lower() == "gemini":
        ai_service.set_gemini_key(config.api_key)
    else:
        raise HTTPException(status_code=400, detail="provider는 'openai', 'claude', 'gemini' 중 하나여야 합니다.")
    
    return {
        "success": True,
        "message": f"{config.provider} API 키가 설정되었습니다."
    }


@router.get("/status")
async def get_ai_status(user: UserInfo = Depends(require_auth)):
    """AI 서비스 상태 확인"""
    has_openai = bool(ai_service.openai_key)
    has_claude = bool(ai_service.claude_key)
    has_gemini = bool(ai_service.gemini_key)
    
    available_provider = None
    if has_claude:
        available_provider = "claude"
    elif has_openai:
        available_provider = "openai"
    elif has_gemini:
        available_provider = "gemini"
    
    return {
        "success": True,
        "openai_configured": has_openai,
        "claude_configured": has_claude,
        "gemini_configured": has_gemini,
        "available_provider": available_provider,
        "ready": has_openai or has_claude or has_gemini
    }


@router.post("/recommend/drg")
async def recommend_drg(
    request: DRGRecommendationRequest,
    user: UserInfo = Depends(require_auth)
):
    """AI 기반 DRG 코드 추천"""
    patient_data = request.dict()
    
    result = await ai_service.analyze_drg_recommendation(patient_data)
    
    return {
        "success": result.success,
        "provider": result.provider,
        "analysis_type": result.analysis_type,
        "recommendation": result.result,
        "confidence": result.confidence,
        "tokens_used": result.tokens_used
    }


@router.post("/recommend/patient/{patient_id}")
async def recommend_drg_for_patient(
    patient_id: int,
    user: UserInfo = Depends(require_auth)
):
    """특정 환자에 대한 AI DRG 추천"""
    patient = next((p for p in PATIENTS_DB if p['id'] == patient_id), None)
    
    if not patient:
        raise HTTPException(status_code=404, detail="환자를 찾을 수 없습니다.")
    
    # 환자 데이터 준비
    patient_data = {
        'primary_diagnosis_code': patient.get('primary_diagnosis_code'),
        'diagnosis_name': patient.get('diagnosis_name'),
        'kdrg_code': patient.get('kdrg_code'),
        'aadrg_code': patient.get('aadrg_code'),
        'length_of_stay': patient.get('length_of_stay')
    }
    
    result = await ai_service.analyze_drg_recommendation(patient_data)
    
    return {
        "success": result.success,
        "patient_id": patient_id,
        "masked_name": patient.get('masked_name', '***'),
        "current_kdrg": patient.get('kdrg_code'),
        "provider": result.provider,
        "recommendation": result.result,
        "confidence": result.confidence
    }


@router.post("/optimize/claim")
async def optimize_claim(
    request: DRGRecommendationRequest,
    alternatives: Optional[List[Dict]] = None,
    user: UserInfo = Depends(require_auth)
):
    """AI 기반 청구 최적화 분석"""
    patient_data = request.dict()
    
    result = await ai_service.analyze_claim_optimization(patient_data, alternatives)
    
    return {
        "success": result.success,
        "provider": result.provider,
        "analysis_type": result.analysis_type,
        "optimization": result.result,
        "confidence": result.confidence,
        "tokens_used": result.tokens_used
    }


@router.post("/mapping/diagnosis")
async def map_diagnosis_to_drg(
    request: DiagnosisMappingRequest,
    user: UserInfo = Depends(require_auth)
):
    """진단코드-DRG 매핑 분석"""
    result = await ai_service.analyze_diagnosis_drg_mapping(
        diagnosis_code=request.diagnosis_code,
        diagnosis_name=request.diagnosis_name
    )
    
    return {
        "success": result.success,
        "provider": result.provider,
        "diagnosis_code": request.diagnosis_code,
        "mapping": result.result,
        "confidence": result.confidence,
        "tokens_used": result.tokens_used
    }


@router.post("/report/audit")
async def generate_audit_report(
    request: AuditReportRequest,
    user: UserInfo = Depends(require_auth)
):
    """AI 기반 심사 대비 보고서 생성"""
    if not PATIENTS_DB:
        raise HTTPException(status_code=400, detail="분석할 환자 데이터가 없습니다.")
    
    # 요약 데이터 준비
    total_patients = len(PATIENTS_DB)
    total_claim = sum(p.get('claim_amount', 0) for p in PATIENTS_DB)
    
    los_values = [p.get('length_of_stay', 0) for p in PATIENTS_DB if p.get('length_of_stay')]
    avg_los = sum(los_values) / len(los_values) if los_values else 0
    
    # 7개 DRG군 비율 계산
    drg7_count = sum(1 for p in PATIENTS_DB if p.get('drg_group') and p['drg_group'] != '기타 DRG' and p['drg_group'] != '미분류')
    drg7_ratio = (drg7_count / total_patients * 100) if total_patients > 0 else 0
    
    patients_summary = {
        'total_patients': total_patients,
        'total_claim': total_claim,
        'avg_los': round(avg_los, 1),
        'drg7_ratio': round(drg7_ratio, 1)
    }
    
    # 최적화 결과 (옵션)
    optimization_results = None
    if request.include_optimizations:
        from services.profit_service import profit_optimizer
        optimization_results = []
        for p in PATIENTS_DB:
            rec = profit_optimizer.analyze_kdrg_optimization(p)
            if rec:
                optimization_results.append({
                    'patient_id': rec.patient_id,
                    'current_kdrg': rec.current_kdrg,
                    'recommended_kdrg': rec.recommended_kdrg,
                    'payment_difference': rec.payment_difference
                })
    
    result = await ai_service.generate_audit_report(patients_summary, optimization_results)
    
    return {
        "success": result.success,
        "provider": result.provider,
        "report": result.result.get('report', result.raw_response) if result.success else None,
        "summary": patients_summary,
        "tokens_used": result.tokens_used,
        "error": result.result.get('error') if not result.success else None
    }


@router.get("/usage")
async def get_ai_usage_stats(user: UserInfo = Depends(require_admin)):
    """AI API 사용량 통계 (관리자 전용)"""
    # 실제 구현에서는 DB에서 사용량 조회
    return {
        "success": True,
        "usage": {
            "today_tokens": 0,
            "month_tokens": 0,
            "total_requests": 0,
            "message": "사용량 통계는 추후 구현 예정입니다."
        }
    }
