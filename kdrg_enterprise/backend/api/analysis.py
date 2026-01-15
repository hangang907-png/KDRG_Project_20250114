"""
분석 API 라우터 - 이익 극대화, 손실 감지, 통계
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import date
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.profit_service import profit_optimizer, AlertLevel
from api.auth import require_auth, require_admin, UserInfo
from api.patients import PATIENTS_DB

router = APIRouter()


# 모델 정의
class OptimizationResult(BaseModel):
    patient_id: str
    current_kdrg: str
    current_aadrg: str
    recommended_kdrg: str
    recommended_aadrg: str
    current_payment: float
    potential_payment: float
    payment_difference: float
    confidence_score: float
    reason: str
    alert_level: str


class LossAlertResult(BaseModel):
    patient_id: str
    alert_type: str
    current_value: str
    expected_value: str
    estimated_loss: float
    description: str
    alert_level: str


class AnalysisSummary(BaseModel):
    total_patients: int
    optimization_count: int
    total_potential_gain: float
    loss_alert_count: int
    total_estimated_loss: float


@router.get("/optimize/{patient_id}")
async def analyze_patient_optimization(
    patient_id: int,
    user: UserInfo = Depends(require_auth)
):
    """환자별 DRG 최적화 분석"""
    patient = next((p for p in PATIENTS_DB if p['id'] == patient_id), None)
    
    if not patient:
        raise HTTPException(status_code=404, detail="환자를 찾을 수 없습니다.")
    
    # 최적화 분석
    recommendation = profit_optimizer.analyze_kdrg_optimization(patient)
    
    if recommendation:
        return {
            "success": True,
            "has_recommendation": True,
            "optimization": OptimizationResult(
                patient_id=recommendation.patient_id,
                current_kdrg=recommendation.current_kdrg,
                current_aadrg=recommendation.current_aadrg,
                recommended_kdrg=recommendation.recommended_kdrg,
                recommended_aadrg=recommendation.recommended_aadrg,
                current_payment=recommendation.current_payment,
                potential_payment=recommendation.potential_payment,
                payment_difference=recommendation.payment_difference,
                confidence_score=recommendation.confidence_score,
                reason=recommendation.reason,
                alert_level=recommendation.alert_level.value
            )
        }
    
    return {
        "success": True,
        "has_recommendation": False,
        "message": "현재 KDRG 코드가 적절합니다."
    }


@router.get("/losses/{patient_id}")
async def detect_patient_losses(
    patient_id: int,
    user: UserInfo = Depends(require_auth)
):
    """환자별 청구 손실 감지"""
    patient = next((p for p in PATIENTS_DB if p['id'] == patient_id), None)
    
    if not patient:
        raise HTTPException(status_code=404, detail="환자를 찾을 수 없습니다.")
    
    # 손실 감지
    alerts = profit_optimizer.detect_claim_losses(patient)
    
    return {
        "success": True,
        "patient_id": patient_id,
        "alert_count": len(alerts),
        "alerts": [
            LossAlertResult(
                patient_id=alert.patient_id,
                alert_type=alert.alert_type,
                current_value=alert.current_value,
                expected_value=alert.expected_value,
                estimated_loss=alert.estimated_loss,
                description=alert.description,
                alert_level=alert.alert_level.value
            )
            for alert in alerts
        ]
    }


@router.get("/batch/optimize")
async def batch_optimization_analysis(
    department: Optional[str] = None,
    drg_group: Optional[str] = None,
    user: UserInfo = Depends(require_auth)
):
    """일괄 최적화 분석"""
    filtered = PATIENTS_DB.copy()
    
    if department:
        filtered = [p for p in filtered if p.get('department') == department]
    
    if drg_group:
        filtered = [p for p in filtered if p.get('drg_group') == drg_group]
    
    results = []
    total_current = 0
    total_potential = 0
    
    for patient in filtered:
        recommendation = profit_optimizer.analyze_kdrg_optimization(patient)
        if recommendation:
            results.append({
                "patient_id": patient['id'],
                "masked_name": patient.get('masked_name', '***'),
                "current_kdrg": recommendation.current_kdrg,
                "recommended_kdrg": recommendation.recommended_kdrg,
                "payment_difference": recommendation.payment_difference,
                "reason": recommendation.reason
            })
            total_current += recommendation.current_payment
            total_potential += recommendation.potential_payment
    
    return {
        "success": True,
        "total_analyzed": len(filtered),
        "optimization_count": len(results),
        "total_current_payment": total_current,
        "total_potential_payment": total_potential,
        "total_potential_gain": total_potential - total_current,
        "optimizations": results
    }


@router.get("/batch/losses")
async def batch_loss_detection(
    department: Optional[str] = None,
    alert_level: Optional[str] = None,
    user: UserInfo = Depends(require_auth)
):
    """일괄 손실 감지"""
    filtered = PATIENTS_DB.copy()
    
    if department:
        filtered = [p for p in filtered if p.get('department') == department]
    
    all_alerts = []
    
    for patient in filtered:
        alerts = profit_optimizer.detect_claim_losses(patient)
        
        for alert in alerts:
            if alert_level and alert.alert_level.value != alert_level:
                continue
            
            all_alerts.append({
                "patient_id": patient['id'],
                "masked_name": patient.get('masked_name', '***'),
                "alert_type": alert.alert_type,
                "estimated_loss": alert.estimated_loss,
                "description": alert.description,
                "alert_level": alert.alert_level.value
            })
    
    # 손실 금액 기준 정렬
    all_alerts.sort(key=lambda x: x['estimated_loss'], reverse=True)
    
    total_loss = sum(a['estimated_loss'] for a in all_alerts)
    
    # 심각도별 집계
    by_level = {}
    for alert in all_alerts:
        level = alert['alert_level']
        by_level[level] = by_level.get(level, 0) + 1
    
    return {
        "success": True,
        "total_patients": len(filtered),
        "total_alerts": len(all_alerts),
        "total_estimated_loss": total_loss,
        "by_alert_level": by_level,
        "alerts": all_alerts[:100]  # 상위 100개
    }


@router.get("/dashboard")
async def get_analysis_dashboard(user: UserInfo = Depends(require_auth)):
    """분석 대시보드 데이터"""
    if not PATIENTS_DB:
        return {
            "success": True,
            "dashboard": {
                "summary": {
                    "total_patients": 0,
                    "optimization_opportunities": 0,
                    "total_potential_gain": 0,
                    "loss_alerts": 0,
                    "total_estimated_loss": 0
                },
                "by_drg_group": [],
                "by_department": [],
                "critical_alerts": []
            }
        }
    
    # 전체 분석 실행
    optimization_count = 0
    total_potential_gain = 0
    all_alerts = []
    
    for patient in PATIENTS_DB:
        # 최적화 분석
        recommendation = profit_optimizer.analyze_kdrg_optimization(patient)
        if recommendation:
            optimization_count += 1
            total_potential_gain += recommendation.payment_difference
        
        # 손실 감지
        alerts = profit_optimizer.detect_claim_losses(patient)
        all_alerts.extend([
            {
                "patient_id": patient['id'],
                "masked_name": patient.get('masked_name', '***'),
                **{
                    "alert_type": a.alert_type,
                    "estimated_loss": a.estimated_loss,
                    "description": a.description,
                    "alert_level": a.alert_level.value
                }
            }
            for a in alerts
        ])
    
    total_estimated_loss = sum(a['estimated_loss'] for a in all_alerts)
    
    # DRG군별 통계
    drg_stats = {}
    for p in PATIENTS_DB:
        drg = p.get('drg_group', '미분류')
        if drg not in drg_stats:
            drg_stats[drg] = {'count': 0, 'claim': 0}
        drg_stats[drg]['count'] += 1
        drg_stats[drg]['claim'] += p.get('claim_amount', 0)
    
    by_drg = [
        {"drg_group": k, "patient_count": v['count'], "total_claim": v['claim']}
        for k, v in drg_stats.items()
    ]
    
    # 부서별 통계
    dept_stats = {}
    for p in PATIENTS_DB:
        dept = p.get('department', '미지정')
        if dept not in dept_stats:
            dept_stats[dept] = {'count': 0, 'claim': 0}
        dept_stats[dept]['count'] += 1
        dept_stats[dept]['claim'] += p.get('claim_amount', 0)
    
    by_dept = [
        {"department": k, "patient_count": v['count'], "total_claim": v['claim']}
        for k, v in dept_stats.items()
    ]
    
    # 심각한 경고 (CRITICAL)
    critical_alerts = [a for a in all_alerts if a['alert_level'] == 'critical'][:10]
    
    return {
        "success": True,
        "dashboard": {
            "summary": {
                "total_patients": len(PATIENTS_DB),
                "optimization_opportunities": optimization_count,
                "total_potential_gain": total_potential_gain,
                "loss_alerts": len(all_alerts),
                "total_estimated_loss": total_estimated_loss
            },
            "by_drg_group": by_drg,
            "by_department": by_dept,
            "critical_alerts": critical_alerts
        }
    }


@router.get("/revenue")
async def get_revenue_analysis(
    period: Optional[str] = Query("month", description="분석 기간: day, week, month, year"),
    user: UserInfo = Depends(require_auth)
):
    """수익 분석"""
    if not PATIENTS_DB:
        return {
            "success": True,
            "revenue": {
                "total": 0,
                "avg_per_patient": 0,
                "by_drg_group": {},
                "by_department": {}
            }
        }
    
    total_revenue = sum(p.get('claim_amount', 0) for p in PATIENTS_DB)
    avg_revenue = total_revenue / len(PATIENTS_DB) if PATIENTS_DB else 0
    
    # DRG군별
    by_drg = {}
    for p in PATIENTS_DB:
        drg = p.get('drg_group', '미분류')
        by_drg[drg] = by_drg.get(drg, 0) + p.get('claim_amount', 0)
    
    # 부서별
    by_dept = {}
    for p in PATIENTS_DB:
        dept = p.get('department', '미지정')
        by_dept[dept] = by_dept.get(dept, 0) + p.get('claim_amount', 0)
    
    return {
        "success": True,
        "revenue": {
            "total": total_revenue,
            "avg_per_patient": round(avg_revenue, 0),
            "patient_count": len(PATIENTS_DB),
            "by_drg_group": by_drg,
            "by_department": by_dept
        }
    }
