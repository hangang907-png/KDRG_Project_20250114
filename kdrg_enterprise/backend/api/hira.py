"""
심평원 API 라우터
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from services.hira_api_service import hira_api_service, KDRGInfo, HospitalInfo
from services.kdrg_codebook_service import codebook_service
from api.auth import require_auth, require_admin, UserInfo

logger = logging.getLogger(__name__)
router = APIRouter()


# 모델 정의
class APIKeyConfig(BaseModel):
    api_key: str


class KDRGInfoResponse(BaseModel):
    kdrg_code: str
    kdrg_name: str
    aadrg_code: str
    aadrg_name: str
    mdc_code: str
    mdc_name: str
    cc_level: str
    relative_weight: float
    geometric_mean_los: float
    arithmetic_mean_los: float
    low_trim: int
    high_trim: int


@router.post("/config/apikey")
async def set_api_key(
    config: APIKeyConfig,
    user: UserInfo = Depends(require_admin)
):
    """심평원 API 키 설정 (관리자 전용)"""
    hira_api_service.set_api_key(config.api_key)
    
    return {
        "success": True,
        "message": "API 키가 설정되었습니다."
    }


@router.get("/status")
async def get_api_status(user: UserInfo = Depends(require_auth)):
    """API 연동 상태 확인"""
    has_key = bool(hira_api_service.api_key)
    sync_status = codebook_service.get_sync_status()
    
    return {
        "success": True,
        "api_configured": has_key,
        "base_url": hira_api_service.base_url,
        "message": "API 키가 설정되었습니다." if has_key else "API 키가 설정되지 않았습니다.",
        "codebook_status": sync_status
    }


@router.post("/sync")
async def sync_kdrg_codebook(
    version: str = Query("V4.7", description="KDRG 버전 (예: V4.6, V4.7)"),
    user: UserInfo = Depends(require_auth)
):
    """KDRG 코드북 동기화 (심평원 API에서 데이터 가져와 DB에 저장)"""
    if not hira_api_service.api_key:
        return {
            "success": False,
            "message": "API 키가 설정되지 않았습니다. 먼저 API 키를 설정해주세요."
        }
    
    try:
        logger.info("Starting KDRG codebook sync...")
        all_entries = []
        
        # MDC별로 데이터 가져오기
        mdc_codes = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']
        
        for mdc in mdc_codes:
            try:
                response = await hira_api_service.get_kdrg_info(
                    mdc_code=mdc,
                    page_no=1,
                    num_of_rows=500
                )
                
                if response.success and response.data:
                    for item in response.data:
                        if isinstance(item, KDRGInfo):
                            all_entries.append({
                                'kdrg_code': item.kdrg_code,
                                'kdrg_name': item.kdrg_name,
                                'aadrg_code': item.aadrg_code,
                                'aadrg_name': item.aadrg_name,
                                'mdc_code': item.mdc_code,
                                'mdc_name': item.mdc_name,
                                'cc_level': item.cc_level,
                                'relative_weight': item.relative_weight,
                                'geometric_mean_los': item.geometric_mean_los,
                                'arithmetic_mean_los': item.arithmetic_mean_los,
                                'low_trim': item.low_trim,
                                'high_trim': item.high_trim,
                                'version': version
                            })
                    logger.info(f"MDC {mdc}: {len(response.data)} entries fetched")
            except Exception as e:
                logger.warning(f"Failed to fetch MDC {mdc}: {e}")
        
        if not all_entries:
            # API에서 데이터를 가져오지 못한 경우, 로컬 참조 데이터 사용
            logger.info("No data from API, using local reference data...")
            from services.kdrg_reference_data import KDRG_REFERENCE_DATA
            
            for kdrg_code, info in KDRG_REFERENCE_DATA.items():
                all_entries.append({
                    'kdrg_code': info.kdrg_code,
                    'kdrg_name': info.name,
                    'aadrg_code': info.aadrg_code,
                    'aadrg_name': '',
                    'mdc_code': info.mdc,
                    'mdc_name': '',
                    'cc_level': str(info.severity),
                    'relative_weight': info.relative_weight,
                    'geometric_mean_los': 0,
                    'arithmetic_mean_los': 0,
                    'low_trim': info.los_lower,
                    'high_trim': info.los_upper,
                    'version': f'{version}-LOCAL'
                })
        
        # DB에 저장
        saved_count = codebook_service.save_codebook_entries(all_entries)
        codebook_service.update_sync_metadata(
            sync_type='kdrg_codebook',
            total_records=saved_count,
            status='success',
            message=f'{saved_count}개 KDRG 코드 동기화 완료'
        )
        
        logger.info(f"KDRG codebook sync completed: {saved_count} entries saved")
        
        return {
            "success": True,
            "message": f"KDRG 코드북 동기화 완료: {saved_count}개 코드가 저장되었습니다.",
            "synced_count": saved_count,
            "codebook_status": codebook_service.get_sync_status()
        }
        
    except Exception as e:
        logger.error(f"KDRG codebook sync failed: {e}")
        codebook_service.update_sync_metadata(
            sync_type='kdrg_codebook',
            total_records=0,
            status='error',
            message=str(e)
        )
        return {
            "success": False,
            "message": f"동기화 실패: {str(e)}"
        }


@router.get("/kdrg")
async def query_kdrg_info(
    kdrg_code: Optional[str] = None,
    aadrg_code: Optional[str] = None,
    mdc_code: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: UserInfo = Depends(require_auth)
):
    """KDRG 기준정보 조회 (심평원 API)"""
    response = await hira_api_service.get_kdrg_info(
        kdrg_code=kdrg_code,
        aadrg_code=aadrg_code,
        mdc_code=mdc_code,
        page_no=page,
        num_of_rows=per_page
    )
    
    if not response.success:
        return {
            "success": False,
            "message": response.message,
            "data": []
        }
    
    # KDRGInfo 객체를 딕셔너리로 변환
    data = []
    if response.data:
        for item in response.data:
            if isinstance(item, KDRGInfo):
                data.append({
                    "kdrg_code": item.kdrg_code,
                    "kdrg_name": item.kdrg_name,
                    "aadrg_code": item.aadrg_code,
                    "aadrg_name": item.aadrg_name,
                    "mdc_code": item.mdc_code,
                    "mdc_name": item.mdc_name,
                    "cc_level": item.cc_level,
                    "relative_weight": item.relative_weight,
                    "geometric_mean_los": item.geometric_mean_los,
                    "arithmetic_mean_los": item.arithmetic_mean_los,
                    "low_trim": item.low_trim,
                    "high_trim": item.high_trim
                })
            else:
                data.append(item)
    
    return {
        "success": True,
        "total": response.total_count,
        "page": response.page_no,
        "per_page": response.num_of_rows,
        "data": data
    }


@router.get("/kdrg/weight")
async def query_kdrg_weight(
    year: Optional[str] = Query(None, description="적용 연도 (예: 2024)"),
    kdrg_code: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: UserInfo = Depends(require_auth)
):
    """KDRG 상대가치점수 조회"""
    response = await hira_api_service.get_kdrg_weight(
        year=year,
        kdrg_code=kdrg_code,
        page_no=page,
        num_of_rows=per_page
    )
    
    return {
        "success": response.success,
        "message": response.message if not response.success else None,
        "total": response.total_count,
        "data": response.data if response.success else []
    }


@router.get("/7drg")
async def query_7drg_info(user: UserInfo = Depends(require_auth)):
    """7개 DRG군 기준정보 조회"""
    response = await hira_api_service.get_7drg_info()
    
    if not response.success:
        return {
            "success": False,
            "message": response.message,
            "data": []
        }
    
    # 그룹별로 정리
    grouped = {}
    for item in response.data:
        if isinstance(item, KDRGInfo):
            aadrg = item.aadrg_code[:3] if item.aadrg_code else 'OTHER'
            if aadrg not in grouped:
                grouped[aadrg] = []
            grouped[aadrg].append({
                "kdrg_code": item.kdrg_code,
                "kdrg_name": item.kdrg_name,
                "relative_weight": item.relative_weight,
                "cc_level": item.cc_level
            })
    
    return {
        "success": True,
        "total": response.total_count,
        "groups": grouped
    }


@router.get("/hospitals")
async def query_hospitals(
    sido: Optional[str] = Query(None, description="시/도 코드"),
    sigungu: Optional[str] = Query(None, description="시/군/구 코드"),
    name: Optional[str] = Query(None, description="병원명 검색"),
    hospital_type: Optional[str] = Query(None, description="병원 종류"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: UserInfo = Depends(require_auth)
):
    """병원 목록 조회"""
    response = await hira_api_service.get_hospital_list(
        sido=sido,
        sigungu=sigungu,
        hospital_name=name,
        hospital_type=hospital_type,
        page_no=page,
        num_of_rows=per_page
    )
    
    if not response.success:
        return {
            "success": False,
            "message": response.message,
            "data": []
        }
    
    data = []
    if response.data:
        for item in response.data:
            if isinstance(item, HospitalInfo):
                data.append({
                    "hospital_code": item.hospital_code,
                    "hospital_name": item.hospital_name,
                    "address": item.address,
                    "tel": item.tel,
                    "hospital_type": item.hospital_type,
                    "sido": item.sido,
                    "sigungu": item.sigungu
                })
            else:
                data.append(item)
    
    return {
        "success": True,
        "total": response.total_count,
        "page": response.page_no,
        "per_page": response.num_of_rows,
        "data": data
    }


@router.get("/validate/{kdrg_code}")
async def validate_kdrg_via_api(
    kdrg_code: str,
    user: UserInfo = Depends(require_auth)
):
    """KDRG 코드 유효성 검증 (심평원 API)"""
    result = await hira_api_service.validate_kdrg_code(kdrg_code)
    
    kdrg_info = None
    if result['kdrg_info']:
        info = result['kdrg_info']
        kdrg_info = {
            "kdrg_code": info.kdrg_code,
            "kdrg_name": info.kdrg_name,
            "aadrg_code": info.aadrg_code,
            "relative_weight": info.relative_weight
        }
    
    return {
        "success": True,
        "valid": result['valid'],
        "message": result['message'],
        "kdrg_info": kdrg_info
    }


@router.get("/compare")
async def compare_kdrg_codes(
    current: str = Query(..., description="현재 KDRG 코드"),
    alternative: str = Query(..., description="대안 KDRG 코드"),
    user: UserInfo = Depends(require_auth)
):
    """두 KDRG 코드 비교 분석"""
    result = await hira_api_service.get_kdrg_comparison(current, alternative)
    
    current_info = None
    alt_info = None
    
    if result['current']:
        c = result['current']
        current_info = {
            "kdrg_code": c.kdrg_code,
            "kdrg_name": c.kdrg_name,
            "relative_weight": c.relative_weight,
            "avg_los": c.arithmetic_mean_los
        }
    
    if result['alternative']:
        a = result['alternative']
        alt_info = {
            "kdrg_code": a.kdrg_code,
            "kdrg_name": a.kdrg_name,
            "relative_weight": a.relative_weight,
            "avg_los": a.arithmetic_mean_los
        }
    
    return {
        "success": True,
        "current": current_info,
        "alternative": alt_info,
        "weight_difference": result['weight_difference'],
        "recommendation": result['recommendation']
    }
