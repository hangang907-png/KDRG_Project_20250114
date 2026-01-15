"""
예측 vs 실제 KDRG 비교 분석 API 라우터
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from dataclasses import asdict
import logging

from services.comparison_service import (
    KDRGComparisonService, 
    kdrg_comparison_service,
    MismatchType
)
from services.feedback_parser_service import feedback_parser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comparison", tags=["비교분석"])


# ===== Pydantic Models =====

class ComparisonRequest(BaseModel):
    """비교 분석 요청"""
    predicted_file_id: str  # 청구 데이터 (예측)
    actual_file_id: str  # 심사 결과 (실제)


class ComparisonSummary(BaseModel):
    """비교 분석 요약"""
    total_cases: int
    accuracy_rate: float
    severity_accuracy: float
    aadrg_accuracy: float
    total_difference: float


class MismatchBreakdown(BaseModel):
    """불일치 유형 분류"""
    exact_matches: int
    severity_mismatches: int
    aadrg_mismatches: int
    mdc_mismatches: int


# ===== 저장소 (메모리) =====
comparison_results: Dict[str, Dict[str, Any]] = {}
# feedback.py의 uploaded_files 참조
from api.feedback import uploaded_files


# ===== API Endpoints =====

@router.post("/analyze")
async def analyze_comparison(
    predicted_file_id: str = Query(..., description="청구 데이터 파일 ID (예측)"),
    actual_file_id: str = Query(..., description="심사 결과 파일 ID (실제)")
):
    """
    예측(청구) vs 실제(심사) KDRG 비교 분석 실행
    
    - 정확도 계산 (전체, 중증도, AADRG)
    - 불일치 유형 분류
    - 원인 추정 및 권고사항 생성
    """
    # 파일 존재 확인
    if predicted_file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="청구 데이터 파일을 찾을 수 없습니다.")
    
    if actual_file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="심사 결과 파일을 찾을 수 없습니다.")
    
    predicted_data = uploaded_files[predicted_file_id]
    actual_data = uploaded_files[actual_file_id]
    
    # 데이터 유형 검증
    if predicted_data.get('data_type') not in ['drg_claim', 'kdrg_grouper']:
        raise HTTPException(status_code=400, detail="청구 데이터 파일이 아닙니다.")
    
    if actual_data.get('data_type') != 'review_result':
        raise HTTPException(status_code=400, detail="심사 결과 파일이 아닙니다.")
    
    try:
        # 비교 서비스 실행
        service = KDRGComparisonService()
        
        comparisons = service.compare_records(
            predicted_data.get('records', []),
            actual_data.get('records', [])
        )
        
        statistics = service.calculate_statistics()
        recommendations = service.generate_improvement_recommendations()
        drg7_analysis = service.get_drg7_analysis()
        
        # 결과 저장
        result_id = f"comp_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        comparison_results[result_id] = {
            'result_id': result_id,
            'created_at': datetime.now().isoformat(),
            'predicted_file': predicted_file_id,
            'actual_file': actual_file_id,
            'service': service,
            'report': service.export_report(),
        }
        
        return {
            'success': True,
            'result_id': result_id,
            'summary': {
                'total_cases': statistics.total_cases,
                'accuracy_rate': statistics.accuracy_rate,
                'severity_accuracy': statistics.severity_accuracy,
                'aadrg_accuracy': statistics.aadrg_accuracy,
                'total_predicted_amount': statistics.total_predicted_amount,
                'total_actual_amount': statistics.total_actual_amount,
                'total_difference': statistics.total_difference,
            },
            'mismatch_breakdown': {
                'exact_matches': statistics.exact_matches,
                'severity_mismatches': statistics.severity_mismatches,
                'aadrg_mismatches': statistics.aadrg_mismatches,
                'mdc_mismatches': statistics.mdc_mismatches,
            },
            'cause_distribution': statistics.cause_distribution,
            'top_mismatch_patterns': statistics.drg_mismatch_patterns[:10],
            'drg7_analysis': drg7_analysis,
            'recommendations': [asdict(r) for r in recommendations[:5]],
        }
        
    except Exception as e:
        logger.error(f"비교 분석 오류: {e}")
        raise HTTPException(status_code=500, detail=f"비교 분석 중 오류 발생: {str(e)}")


@router.get("/results")
async def list_comparison_results():
    """
    비교 분석 결과 목록 조회
    """
    results = []
    for result_id, data in comparison_results.items():
        report = data.get('report', {})
        summary = report.get('summary', {})
        results.append({
            'result_id': result_id,
            'created_at': data.get('created_at', ''),
            'predicted_file': data.get('predicted_file', ''),
            'actual_file': data.get('actual_file', ''),
            'total_cases': summary.get('total_cases', 0),
            'accuracy_rate': summary.get('accuracy_rate', 0),
        })
    
    return {
        'success': True,
        'total': len(results),
        'results': sorted(results, key=lambda x: x['created_at'], reverse=True)
    }


@router.get("/results/{result_id}")
async def get_comparison_result(result_id: str):
    """
    특정 비교 분석 결과 상세 조회
    """
    if result_id not in comparison_results:
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")
    
    data = comparison_results[result_id]
    report = data.get('report', {})
    
    return {
        'success': True,
        'result_id': result_id,
        'created_at': data.get('created_at', ''),
        **report
    }


@router.get("/results/{result_id}/details")
async def get_comparison_details(
    result_id: str,
    mismatch_only: bool = Query(False, description="불일치 건만 조회"),
    mismatch_type: Optional[str] = Query(None, description="불일치 유형 필터"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200)
):
    """
    비교 분석 상세 데이터 조회 (페이지네이션)
    """
    if result_id not in comparison_results:
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")
    
    service: KDRGComparisonService = comparison_results[result_id].get('service')
    if not service:
        raise HTTPException(status_code=500, detail="분석 데이터가 없습니다.")
    
    # 필터링
    comparisons = service.comparisons
    
    if mismatch_only:
        comparisons = [c for c in comparisons if not c.is_match]
    
    if mismatch_type:
        comparisons = [c for c in comparisons if c.mismatch_type == mismatch_type]
    
    # 페이지네이션
    total = len(comparisons)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated = comparisons[start_idx:end_idx]
    
    return {
        'success': True,
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size,
        'records': [asdict(c) for c in paginated]
    }


@router.get("/results/{result_id}/recommendations")
async def get_recommendations(result_id: str):
    """
    개선 권고사항 조회
    """
    if result_id not in comparison_results:
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")
    
    service: KDRGComparisonService = comparison_results[result_id].get('service')
    if not service:
        raise HTTPException(status_code=500, detail="분석 데이터가 없습니다.")
    
    recommendations = service.generate_improvement_recommendations()
    
    return {
        'success': True,
        'total': len(recommendations),
        'recommendations': [asdict(r) for r in recommendations]
    }


@router.get("/results/{result_id}/drg7")
async def get_drg7_analysis(result_id: str):
    """
    7개 DRG군별 정확도 분석
    """
    if result_id not in comparison_results:
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")
    
    service: KDRGComparisonService = comparison_results[result_id].get('service')
    if not service:
        raise HTTPException(status_code=500, detail="분석 데이터가 없습니다.")
    
    drg7_analysis = service.get_drg7_analysis()
    
    return {
        'success': True,
        'drg7_analysis': drg7_analysis
    }


@router.get("/results/{result_id}/trend")
async def get_trend_analysis(result_id: str):
    """
    추세 분석
    """
    if result_id not in comparison_results:
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")
    
    service: KDRGComparisonService = comparison_results[result_id].get('service')
    if not service:
        raise HTTPException(status_code=500, detail="분석 데이터가 없습니다.")
    
    trend = service.get_trend_analysis()
    
    return {
        'success': True,
        **trend
    }


@router.get("/results/{result_id}/export")
async def export_report(result_id: str):
    """
    종합 보고서 내보내기
    """
    if result_id not in comparison_results:
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")
    
    report = comparison_results[result_id].get('report', {})
    
    return {
        'success': True,
        'report': report
    }


@router.delete("/results/{result_id}")
async def delete_comparison_result(result_id: str):
    """
    비교 분석 결과 삭제
    """
    if result_id not in comparison_results:
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")
    
    del comparison_results[result_id]
    
    return {
        'success': True,
        'message': '결과가 삭제되었습니다.'
    }


@router.get("/mismatch-types")
async def get_mismatch_types():
    """
    불일치 유형 목록
    """
    return {
        'success': True,
        'types': [
            {'value': MismatchType.EXACT_MATCH.value, 'label': '정확히 일치', 'description': 'KDRG 코드 완전 일치'},
            {'value': MismatchType.SEVERITY_DIFF.value, 'label': '중증도 차이', 'description': 'AADRG 동일, 중증도만 다름'},
            {'value': MismatchType.AADRG_DIFF.value, 'label': 'AADRG 차이', 'description': 'MDC 동일, AADRG 다름'},
            {'value': MismatchType.MDC_DIFF.value, 'label': 'MDC 차이', 'description': '주진단범주(MDC)부터 다름'},
        ]
    }
