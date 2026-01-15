"""
KDRG 관리 API 라우터
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional, List, Dict
import pandas as pd
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from api.auth import require_auth, UserInfo

router = APIRouter()


# 모델 정의
class KDRGCode(BaseModel):
    kdrg_code: str
    kdrg_name: str
    aadrg_code: str
    aadrg_name: Optional[str] = None
    mdc_code: Optional[str] = None
    mdc_name: Optional[str] = None
    cc_level: Optional[str] = None
    relative_weight: Optional[float] = None
    avg_los: Optional[float] = None


class KDRGValidationRequest(BaseModel):
    kdrg_code: str
    aadrg_code: Optional[str] = None


class KDRGValidationResult(BaseModel):
    valid: bool
    kdrg_code: str
    message: str
    kdrg_info: Optional[KDRGCode] = None


# 인메모리 KDRG 코드북 저장소
KDRG_CODEBOOK: List[Dict] = []

# 7개 DRG군 정보
SEVEN_DRG_GROUPS = {
    'T01': {
        'name': '편도 및 아데노이드 절제술',
        'description': '편도/축농증 관련 수술',
        'conditions': ['편도염', '아데노이드 비대', '편도 비대']
    },
    'T03': {
        'name': '적혈구장애 및 응고장애',
        'description': '수혈 관련',
        'conditions': ['빈혈', '혈소판 감소증', '응고장애']
    },
    'X04': {
        'name': '망막수술 및 수정체 수술',
        'description': '망막/백내장 수술',
        'conditions': ['백내장', '망막박리', '망막질환']
    },
    'X05': {
        'name': '요관 및 신장 결석 수술',
        'description': '결석 수술',
        'conditions': ['신장결석', '요관결석', '방광결석']
    },
    'T05': {
        'name': '중이수술',
        'description': '중이염 수술',
        'conditions': ['중이염', '고막천공', '유양돌기염']
    },
    'T11': {
        'name': '피부 절개 및 배농술',
        'description': '모낭염/농양 절개',
        'conditions': ['모낭염', '농양', '봉와직염']
    },
    'T12': {
        'name': '항문 수술',
        'description': '치핵 수술',
        'conditions': ['치핵', '치루', '치열']
    }
}


@router.get("/codebook", response_model=Dict)
async def get_kdrg_codebook(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    aadrg: Optional[str] = None,
    mdc: Optional[str] = None,
    user: UserInfo = Depends(require_auth)
):
    """KDRG 코드북 조회"""
    filtered = KDRG_CODEBOOK.copy()
    
    if search:
        search_lower = search.lower()
        filtered = [
            k for k in filtered 
            if search_lower in k.get('kdrg_code', '').lower() 
            or search_lower in k.get('kdrg_name', '').lower()
        ]
    
    if aadrg:
        filtered = [k for k in filtered if k.get('aadrg_code', '').startswith(aadrg)]
    
    if mdc:
        filtered = [k for k in filtered if k.get('mdc_code') == mdc]
    
    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    
    return {
        "success": True,
        "total": total,
        "page": page,
        "per_page": per_page,
        "codes": filtered[start:end]
    }


@router.post("/codebook/upload")
async def upload_kdrg_codebook(
    file: UploadFile = File(...),
    version: str = Query(..., description="KDRG 버전 (예: V4.6)"),
    user: UserInfo = Depends(require_auth)
):
    """KDRG 코드북 업로드"""
    global KDRG_CODEBOOK
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일이 필요합니다.")
    
    file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
    
    try:
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)
        
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file_path, encoding='utf-8')
        elif file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path)
        else:
            raise HTTPException(status_code=400, detail="CSV 또는 Excel 파일만 지원합니다.")
        
        # 코드북 데이터 파싱
        new_codes = []
        for _, row in df.iterrows():
            code = {
                'kdrg_code': str(row.get('KDRG', row.get('kdrg_code', ''))),
                'kdrg_name': str(row.get('KDRG명', row.get('kdrg_name', ''))),
                'aadrg_code': str(row.get('AADRG', row.get('aadrg_code', ''))),
                'aadrg_name': str(row.get('AADRG명', row.get('aadrg_name', ''))) or None,
                'mdc_code': str(row.get('MDC', row.get('mdc_code', ''))) or None,
                'mdc_name': str(row.get('MDC명', row.get('mdc_name', ''))) or None,
                'cc_level': str(row.get('CC등급', row.get('cc_level', ''))) or None,
                'relative_weight': float(row.get('상대가치', row.get('relative_weight', 0)) or 0),
                'avg_los': float(row.get('평균재원일수', row.get('avg_los', 0)) or 0),
                'version': version
            }
            if code['kdrg_code']:
                new_codes.append(code)
        
        KDRG_CODEBOOK = new_codes
        
        return {
            "success": True,
            "message": f"KDRG 코드북 {version}을 업로드했습니다.",
            "total_codes": len(new_codes)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 처리 오류: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@router.post("/validate", response_model=KDRGValidationResult)
async def validate_kdrg_code(
    request: KDRGValidationRequest,
    user: UserInfo = Depends(require_auth)
):
    """KDRG 코드 유효성 검증"""
    kdrg_code = request.kdrg_code.upper()
    
    # 형식 검증
    if len(kdrg_code) != 5:
        return KDRGValidationResult(
            valid=False,
            kdrg_code=kdrg_code,
            message="KDRG 코드는 5자리여야 합니다."
        )
    
    # 코드북에서 검색
    found = next((k for k in KDRG_CODEBOOK if k['kdrg_code'] == kdrg_code), None)
    
    if found:
        return KDRGValidationResult(
            valid=True,
            kdrg_code=kdrg_code,
            message="유효한 KDRG 코드입니다.",
            kdrg_info=KDRGCode(
                kdrg_code=found['kdrg_code'],
                kdrg_name=found['kdrg_name'],
                aadrg_code=found['aadrg_code'],
                aadrg_name=found.get('aadrg_name'),
                mdc_code=found.get('mdc_code'),
                mdc_name=found.get('mdc_name'),
                cc_level=found.get('cc_level'),
                relative_weight=found.get('relative_weight'),
                avg_los=found.get('avg_los')
            )
        )
    
    # 코드북이 비어있으면 형식만 검증
    if not KDRG_CODEBOOK:
        return KDRGValidationResult(
            valid=True,
            kdrg_code=kdrg_code,
            message="코드북이 로드되지 않아 형식만 검증되었습니다."
        )
    
    return KDRGValidationResult(
        valid=False,
        kdrg_code=kdrg_code,
        message="코드북에서 해당 KDRG 코드를 찾을 수 없습니다."
    )


@router.get("/7drg", response_model=Dict)
async def get_7drg_info(user: UserInfo = Depends(require_auth)):
    """7개 DRG군 정보 조회"""
    result = []
    
    for code, info in SEVEN_DRG_GROUPS.items():
        # 코드북에서 해당 AADRG 코드 조회
        related_codes = [k for k in KDRG_CODEBOOK if k.get('aadrg_code', '').startswith(code)]
        
        result.append({
            'aadrg_code': code,
            'name': info['name'],
            'description': info['description'],
            'conditions': info['conditions'],
            'kdrg_count': len(related_codes),
            'related_kdrg': [k['kdrg_code'] for k in related_codes[:5]]  # 최대 5개만
        })
    
    return {
        "success": True,
        "drg_groups": result
    }


@router.get("/7drg/{aadrg_code}")
async def get_7drg_detail(
    aadrg_code: str,
    user: UserInfo = Depends(require_auth)
):
    """특정 7개 DRG군 상세 정보"""
    aadrg_code = aadrg_code.upper()
    
    if aadrg_code not in SEVEN_DRG_GROUPS:
        raise HTTPException(status_code=404, detail="해당 DRG군을 찾을 수 없습니다.")
    
    info = SEVEN_DRG_GROUPS[aadrg_code]
    related_codes = [k for k in KDRG_CODEBOOK if k.get('aadrg_code', '').startswith(aadrg_code)]
    
    return {
        "success": True,
        "drg_group": {
            'aadrg_code': aadrg_code,
            'name': info['name'],
            'description': info['description'],
            'conditions': info['conditions'],
            'kdrg_codes': related_codes
        }
    }


@router.get("/search")
async def search_kdrg(
    q: str = Query(..., min_length=1, description="검색어"),
    user: UserInfo = Depends(require_auth)
):
    """KDRG 코드/명칭 검색"""
    q_lower = q.lower()
    
    results = [
        k for k in KDRG_CODEBOOK
        if q_lower in k.get('kdrg_code', '').lower()
        or q_lower in k.get('kdrg_name', '').lower()
        or q_lower in k.get('aadrg_name', '').lower()
    ]
    
    return {
        "success": True,
        "query": q,
        "total": len(results),
        "results": results[:50]  # 최대 50개
    }
