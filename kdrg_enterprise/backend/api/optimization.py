"""
전역 KDRG 최적화 API
- 개별 환자 최적화 분석
- 배치 최적화 분석
- 최적화 시뮬레이션
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from dataclasses import asdict

from services.optimization_service import (
    global_optimization_service,
    PatientOptimizationResult,
    GlobalOptimizationReport,
)
from services.kdrg_reference_data import (
    get_kdrg_info,
    get_kdrg_by_mdc,
    get_severity_options,
    get_drg7_kdrgss,
    MDCCode,
    KDRG_REFERENCE_DATA,
)

router = APIRouter(prefix="/optimization", tags=["Optimization"])


class PatientOptimizeRequest(BaseModel):
    """개별 환자 최적화 요청"""
    patient_id: str
    claim_id: Optional[str] = None
    kdrg: str
    main_diagnosis: str
    sub_diagnoses: List[str] = []
    procedures: List[str] = []
    los: int = 0
    age: int = 0
    sex: str = "M"


class BatchOptimizeRequest(BaseModel):
    """배치 최적화 요청"""
    patients: List[Dict[str, Any]]
    mdc_filter: Optional[str] = None
    min_potential: float = 0


class SimulateRequest(BaseModel):
    """최적화 시뮬레이션 요청"""
    patient_data: Dict[str, Any]
    target_kdrg: str


@router.get("/summary")
async def get_optimization_summary():
    """최적화 서비스 요약 정보"""
    return global_optimization_service.get_optimization_summary()


@router.get("/mdc-list")
async def get_mdc_list():
    """MDC 목록 조회"""
    return [
        {"code": mdc.code, "name": mdc.mdc_name}
        for mdc in MDCCode
    ]


@router.get("/kdrg/{kdrg_code}")
async def get_kdrg_details(kdrg_code: str):
    """KDRG 코드 상세 정보"""
    info = get_kdrg_info(kdrg_code)
    if not info:
        raise HTTPException(status_code=404, detail=f"KDRG code '{kdrg_code}' not found")
    
    return {
        "kdrg_code": info.kdrg_code,
        "aadrg_code": info.aadrg_code,
        "mdc": info.mdc,
        "severity": info.severity,
        "name": info.name,
        "relative_weight": info.relative_weight,
        "base_amount": info.base_amount,
        "los_lower": info.los_lower,
        "los_upper": info.los_upper,
        "los_outlier_per_diem": info.los_outlier_per_diem,
        "is_surgical": info.is_surgical,
        "drg7_code": info.drg7_code,
    }


@router.get("/kdrg-by-mdc/{mdc}")
async def get_kdrgss_by_mdc(mdc: str):
    """MDC별 KDRG 목록"""
    kdrgss = get_kdrg_by_mdc(mdc)
    return [
        {
            "kdrg_code": info.kdrg_code,
            "name": info.name,
            "severity": info.severity,
            "relative_weight": info.relative_weight,
            "base_amount": info.base_amount,
            "is_surgical": info.is_surgical,
        }
        for info in sorted(kdrgss, key=lambda x: x.kdrg_code)
    ]


@router.get("/severity-options/{aadrg}")
async def get_severity_opts(aadrg: str):
    """AADRG별 중증도 옵션"""
    options = get_severity_options(aadrg)
    if not options:
        raise HTTPException(status_code=404, detail=f"AADRG '{aadrg}' not found")
    return options


@router.get("/drg7-list")
async def get_drg7_list():
    """7개 DRG군 목록"""
    drg7_kdrgss = get_drg7_kdrgss()
    
    # DRG군 코드별로 그룹화
    grouped = {}
    for info in drg7_kdrgss:
        if info.drg7_code not in grouped:
            grouped[info.drg7_code] = {
                "drg7_code": info.drg7_code,
                "name": info.name.split(" - ")[0],  # 기본 이름만
                "kdrgss": [],
            }
        grouped[info.drg7_code]["kdrgss"].append({
            "kdrg_code": info.kdrg_code,
            "severity": info.severity,
            "relative_weight": info.relative_weight,
            "base_amount": info.base_amount,
        })
    
    return list(grouped.values())


@router.post("/analyze/patient")
async def analyze_patient_optimization(request: PatientOptimizeRequest):
    """개별 환자 최적화 분석"""
    
    patient_data = {
        "patient_id": request.patient_id,
        "claim_id": request.claim_id,
        "kdrg": request.kdrg,
        "main_diagnosis": request.main_diagnosis,
        "sub_diagnoses": request.sub_diagnoses,
        "procedures": request.procedures,
        "los": request.los,
        "age": request.age,
        "sex": request.sex,
    }
    
    result = global_optimization_service.analyze_patient_optimization(patient_data)
    
    return {
        "patient_id": result.patient_id,
        "claim_id": result.claim_id,
        "current_kdrg": result.current_kdrg,
        "current_mdc": result.current_mdc,
        "current_severity": result.current_severity,
        "current_amount": result.current_amount,
        "main_diagnosis": result.main_diagnosis,
        "procedures": result.procedures,
        "los": result.los,
        "suggestions": [asdict(s) for s in result.suggestions],
        "total_optimization_potential": result.total_optimization_potential,
        "best_suggestion": asdict(result.best_suggestion) if result.best_suggestion else None,
        "analysis_timestamp": result.analysis_timestamp,
    }


@router.post("/analyze/batch")
async def analyze_batch_optimization(request: BatchOptimizeRequest):
    """배치 최적화 분석"""
    
    if not request.patients:
        raise HTTPException(status_code=400, detail="No patients provided")
    
    if len(request.patients) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 patients per request")
    
    report = global_optimization_service.analyze_batch_optimization(
        patients_data=request.patients,
        mdc_filter=request.mdc_filter,
        min_potential=request.min_potential,
    )
    
    return {
        "report_id": report.report_id,
        "generated_at": report.generated_at,
        "total_cases_analyzed": report.total_cases_analyzed,
        "total_current_revenue": report.total_current_revenue,
        "total_potential_revenue": report.total_potential_revenue,
        "total_optimization_potential": report.total_optimization_potential,
        "optimization_rate": report.optimization_rate,
        "mdc_summaries": [asdict(s) for s in report.mdc_summaries],
        "top_opportunities": [
            {
                "patient_id": r.patient_id,
                "current_kdrg": r.current_kdrg,
                "current_amount": r.current_amount,
                "optimization_potential": r.total_optimization_potential,
                "best_suggestion": asdict(r.best_suggestion) if r.best_suggestion else None,
            }
            for r in report.top_opportunities
        ],
        "risk_distribution": report.risk_distribution,
    }


@router.post("/simulate")
async def simulate_optimization(request: SimulateRequest):
    """최적화 시뮬레이션"""
    
    result = global_optimization_service.simulate_optimization(
        patient_data=request.patient_data,
        target_kdrg=request.target_kdrg,
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Simulation failed"))
    
    return result


@router.get("/statistics")
async def get_optimization_statistics():
    """최적화 통계 (KDRG 데이터 기반)"""
    
    # MDC별 KDRG 수 계산
    mdc_counts = {}
    surgical_count = 0
    drg7_count = 0
    
    for kdrg in KDRG_REFERENCE_DATA.values():
        mdc = kdrg.mdc
        mdc_counts[mdc] = mdc_counts.get(mdc, 0) + 1
        if kdrg.is_surgical:
            surgical_count += 1
        if kdrg.drg7_code:
            drg7_count += 1
    
    return {
        "total_kdrg_codes": len(KDRG_REFERENCE_DATA),
        "surgical_kdrg_count": surgical_count,
        "non_surgical_kdrg_count": len(KDRG_REFERENCE_DATA) - surgical_count,
        "drg7_kdrg_count": drg7_count,
        "mdc_distribution": mdc_counts,
        "average_relative_weight": round(
            sum(k.relative_weight for k in KDRG_REFERENCE_DATA.values()) / len(KDRG_REFERENCE_DATA), 
            3
        ),
        "average_base_amount": round(
            sum(k.base_amount for k in KDRG_REFERENCE_DATA.values()) / len(KDRG_REFERENCE_DATA),
            0
        ),
    }


@router.get("/compare/{kdrg1}/{kdrg2}")
async def compare_kdrgss(kdrg1: str, kdrg2: str):
    """두 KDRG 코드 비교"""
    
    info1 = get_kdrg_info(kdrg1)
    info2 = get_kdrg_info(kdrg2)
    
    if not info1:
        raise HTTPException(status_code=404, detail=f"KDRG code '{kdrg1}' not found")
    if not info2:
        raise HTTPException(status_code=404, detail=f"KDRG code '{kdrg2}' not found")
    
    amount_diff = info2.base_amount - info1.base_amount
    weight_diff = info2.relative_weight - info1.relative_weight
    pct_diff = (amount_diff / info1.base_amount * 100) if info1.base_amount > 0 else 0
    
    return {
        "kdrg1": {
            "code": info1.kdrg_code,
            "name": info1.name,
            "mdc": info1.mdc,
            "severity": info1.severity,
            "relative_weight": info1.relative_weight,
            "base_amount": info1.base_amount,
        },
        "kdrg2": {
            "code": info2.kdrg_code,
            "name": info2.name,
            "mdc": info2.mdc,
            "severity": info2.severity,
            "relative_weight": info2.relative_weight,
            "base_amount": info2.base_amount,
        },
        "difference": {
            "amount": amount_diff,
            "weight": round(weight_diff, 4),
            "percentage": round(pct_diff, 2),
        },
        "same_aadrg": info1.aadrg_code == info2.aadrg_code,
        "same_mdc": info1.mdc == info2.mdc,
    }
