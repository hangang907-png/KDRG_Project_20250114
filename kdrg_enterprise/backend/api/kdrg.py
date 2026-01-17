"""
KDRG 관리 API 라우터
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional, List, Dict
import pandas as pd
import os
import sys
import logging
import re
import pdfplumber

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from api.auth import require_auth, UserInfo
from services.kdrg_codebook_service import codebook_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Valid MDC (Major Diagnostic Category) prefixes for KDRG codes
# A-V: Standard MDC categories, X: Pre-MDC, Y: Error DRG, Z: Undefined
VALID_KDRG_MDC_PREFIXES = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

def is_valid_kdrg_code(code: str) -> bool:
    """Validate if a code matches KDRG format (MDC letter + 4 digits)"""
    if not code or len(code) != 5:
        return False
    if code[0] not in VALID_KDRG_MDC_PREFIXES:
        return False
    return code[1:].isdigit()


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


# 인메모리 KDRG 코드북 저장소 (deprecated, DB 사용)
KDRG_CODEBOOK: List[Dict] = []


def parse_pdf_codebook(file_path: str) -> List[Dict]:
    """
    PDF 파일에서 KDRG 코드북 데이터 추출
    심평원 KDRG 코드북 PDF 형식 지원
    """
    codes = []
    
    try:
        with pdfplumber.open(file_path) as pdf:
            logger.info(f"PDF has {len(pdf.pages)} pages")
            
            for page_num, page in enumerate(pdf.pages):
                # 테이블 추출 시도
                tables = page.extract_tables()
                
                for table in tables:
                    if not table:
                        continue
                    
                    # 헤더 찾기
                    header_row = None
                    for i, row in enumerate(table):
                        if row and any(cell and ('KDRG' in str(cell).upper() or 'DRG' in str(cell).upper()) for cell in row):
                            header_row = i
                            break
                    
                    if header_row is not None:
                        headers = [str(h).strip() if h else '' for h in table[header_row]]
                        logger.info(f"Page {page_num + 1} headers: {headers}")
                        
                        # 데이터 행 처리
                        for row in table[header_row + 1:]:
                            if not row or all(not cell for cell in row):
                                continue
                            
                            code_data = parse_pdf_row(headers, row)
                            if code_data and code_data.get('kdrg_code'):
                                codes.append(code_data)
                    else:
                        # 헤더 없이 데이터만 있는 경우 - KDRG 코드 패턴으로 찾기
                        for row in table:
                            if not row:
                                continue
                            for cell in row:
                                if cell:
                                    # KDRG 코드 패턴: 대문자+숫자 5자리 (예: A0110, B2031)
                                    matches = re.findall(r'\b([A-Z][0-9]{4})\b', str(cell))
                                    for match in matches:
                                        if is_valid_kdrg_code(match) and match not in [c['kdrg_code'] for c in codes]:
                                            codes.append({
                                                'kdrg_code': match,
                                                'kdrg_name': '',
                                                'aadrg_code': match[:3] if len(match) >= 3 else '',
                                            })
                
                # 테이블이 없으면 텍스트에서 추출
                if not tables:
                    text = page.extract_text()
                    if text:
                        # KDRG 코드 패턴 찾기
                        matches = re.findall(r'\b([A-Z][0-9]{4})\b', text)
                        for match in matches:
                            if is_valid_kdrg_code(match) and match not in [c['kdrg_code'] for c in codes]:
                                codes.append({
                                    'kdrg_code': match,
                                    'kdrg_name': '',
                                    'aadrg_code': match[:3] if len(match) >= 3 else '',
                                })
        
        logger.info(f"Extracted {len(codes)} codes from PDF")
        return codes
        
    except Exception as e:
        logger.error(f"PDF parsing error: {e}")
        raise


def parse_pdf_row(headers: List[str], row: List) -> Optional[Dict]:
    """PDF 테이블 행을 KDRG 코드 딕셔너리로 변환"""
    if len(row) != len(headers):
        return None
    
    # 컬럼명 매핑
    column_mapping = {
        'kdrg_code': ['KDRG', 'kdrg_code', 'KDRG코드', 'kdrg', 'kdrgCd', 'DRG코드', 'DRG'],
        'kdrg_name': ['KDRG명', 'kdrg_name', 'KDRG_NAME', 'kdrgNm', 'kdrg_nm', 'DRG명', '분류명'],
        'aadrg_code': ['AADRG', 'aadrg_code', 'AADRG코드', 'aadrg', 'aadrgCd', '인접DRG'],
        'aadrg_name': ['AADRG명', 'aadrg_name', 'AADRG_NAME', 'aadrgNm'],
        'mdc_code': ['MDC', 'mdc_code', 'MDC코드', 'mdc', 'mdcCd', '주진단범주'],
        'mdc_name': ['MDC명', 'mdc_name', 'MDC_NAME', 'mdcNm'],
        'cc_level': ['CC등급', 'cc_level', 'CC', 'ccLvl', '중증도', '합병증'],
        'relative_weight': ['상대가치', 'relative_weight', 'RW', 'relWght', '상대가치점수', '가중치'],
        'geometric_mean_los': ['기하평균재원일수', 'geometric_mean_los', 'geoAvgLos', 'GMLOS', '기하평균'],
        'arithmetic_mean_los': ['산술평균재원일수', 'arithmetic_mean_los', 'ariAvgLos', 'AMLOS', '평균재원일수', '산술평균'],
    }
    
    def find_col_index(possible_names):
        for name in possible_names:
            for i, h in enumerate(headers):
                if name.lower() in h.lower():
                    return i
        return None
    
    code = {}
    
    # KDRG 코드 찾기 (필수)
    kdrg_idx = find_col_index(column_mapping['kdrg_code'])
    if kdrg_idx is None or kdrg_idx >= len(row):
        # 첫 번째 컬럼이 KDRG 코드 패턴인지 확인
        if row[0] and re.match(r'^[A-Z][0-9]{4}$', str(row[0]).strip()):
            code['kdrg_code'] = str(row[0]).strip()
        else:
            return None
    else:
        val = row[kdrg_idx]
        if not val or not re.match(r'^[A-Z][0-9]{4}$', str(val).strip()):
            return None
        code['kdrg_code'] = str(val).strip()
    
    # 나머지 필드
    for field, possible_names in column_mapping.items():
        if field == 'kdrg_code':
            continue
        idx = find_col_index(possible_names)
        if idx is not None and idx < len(row) and row[idx]:
            val = row[idx]
            if field in ['relative_weight', 'geometric_mean_los', 'arithmetic_mean_los']:
                try:
                    code[field] = float(str(val).replace(',', ''))
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert '{val}' to float for field '{field}'")
                    code[field] = 0.0
            else:
                code[field] = str(val).strip()
        else:
            if field in ['relative_weight', 'geometric_mean_los', 'arithmetic_mean_los']:
                code[field] = 0.0
            else:
                code[field] = ''
    
    # AADRG 코드가 없으면 KDRG 앞 3자리로 추정
    if not code.get('aadrg_code') and code.get('kdrg_code'):
        code['aadrg_code'] = code['kdrg_code'][:3]
    
    return code


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
    """KDRG 코드북 조회 (DB에서)"""
    result = codebook_service.get_codebook(
        page=page,
        per_page=per_page,
        search=search,
        aadrg=aadrg,
        mdc=mdc
    )
    
    return {
        "success": True,
        "total": result['total'],
        "page": result['page'],
        "per_page": result['per_page'],
        "codes": result['codes']
    }


@router.post("/codebook/upload")
async def upload_kdrg_codebook(
    file: UploadFile = File(...),
    version: str = Query(..., description="KDRG 버전 (예: V4.6)"),
    user: UserInfo = Depends(require_auth)
):
    """KDRG 코드북 업로드 (DB에 저장) - CSV, Excel, PDF 지원"""
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일이 필요합니다.")
    
    file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
    
    try:
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)
        
        new_codes = []
        
        # 파일 형식에 따라 읽기
        if file.filename.lower().endswith('.pdf'):
            # PDF 파일 처리
            logger.info(f"Processing PDF file: {file.filename}")
            pdf_codes = parse_pdf_codebook(file_path)
            
            for code_data in pdf_codes:
                code_data['version'] = version
                # 기본값 설정
                for field in ['kdrg_name', 'aadrg_name', 'mdc_code', 'mdc_name', 'cc_level']:
                    if field not in code_data:
                        code_data[field] = ''
                for field in ['relative_weight', 'geometric_mean_los', 'arithmetic_mean_los']:
                    if field not in code_data:
                        code_data[field] = 0.0
                for field in ['low_trim', 'high_trim']:
                    if field not in code_data:
                        code_data[field] = 0
                new_codes.append(code_data)
            
            logger.info(f"PDF parsing complete: {len(new_codes)} codes extracted")
            
        elif file.filename.lower().endswith('.csv'):
            # CSV 파일 처리 - 다양한 인코딩 시도
            df = None
            for encoding in ['utf-8', 'cp949', 'euc-kr']:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                raise HTTPException(status_code=400, detail="파일 인코딩을 인식할 수 없습니다.")
            
            new_codes = parse_dataframe_codebook(df, version)
            
        elif file.filename.lower().endswith(('.xlsx', '.xls')):
            # Excel 파일 처리
            df = pd.read_excel(file_path)
            new_codes = parse_dataframe_codebook(df, version)
            
        else:
            raise HTTPException(status_code=400, detail="CSV, Excel, 또는 PDF 파일만 지원합니다.")
        
        if not new_codes:
            raise HTTPException(status_code=400, detail="파일에서 유효한 KDRG 코드를 찾을 수 없습니다. 파일 형식을 확인해주세요.")
        
        # DB에 저장
        saved_count = codebook_service.save_codebook_entries(new_codes)
        codebook_service.update_sync_metadata(
            sync_type='kdrg_codebook',
            total_records=saved_count,
            status='success',
            message=f'파일 업로드: {file.filename} ({saved_count}개 코드)'
        )
        
        logger.info(f"KDRG codebook uploaded: {saved_count} codes from {file.filename}")
        
        return {
            "success": True,
            "message": f"KDRG 코드북 {version} 업로드 완료: {saved_count}개 코드가 저장되었습니다.",
            "total_codes": saved_count,
            "codebook_status": codebook_service.get_sync_status()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Codebook upload error: {e}")
        raise HTTPException(status_code=500, detail=f"파일 처리 오류: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def parse_dataframe_codebook(df: pd.DataFrame, version: str) -> List[Dict]:
    """DataFrame에서 KDRG 코드북 데이터 파싱"""
    logger.info(f"Uploaded file columns: {df.columns.tolist()}")
    logger.info(f"Total rows: {len(df)}")
    
    # 컬럼명 매핑 (다양한 형식 지원)
    column_mapping = {
        'kdrg_code': ['KDRG', 'kdrg_code', 'KDRG코드', 'kdrg', 'kdrgCd'],
        'kdrg_name': ['KDRG명', 'kdrg_name', 'KDRG_NAME', 'kdrgNm', 'kdrg_nm'],
        'aadrg_code': ['AADRG', 'aadrg_code', 'AADRG코드', 'aadrg', 'aadrgCd'],
        'aadrg_name': ['AADRG명', 'aadrg_name', 'AADRG_NAME', 'aadrgNm'],
        'mdc_code': ['MDC', 'mdc_code', 'MDC코드', 'mdc', 'mdcCd'],
        'mdc_name': ['MDC명', 'mdc_name', 'MDC_NAME', 'mdcNm'],
        'cc_level': ['CC등급', 'cc_level', 'CC', 'ccLvl', '중증도'],
        'relative_weight': ['상대가치', 'relative_weight', 'RW', 'relWght', '상대가치점수'],
        'geometric_mean_los': ['기하평균재원일수', 'geometric_mean_los', 'geoAvgLos', 'GMLOS'],
        'arithmetic_mean_los': ['산술평균재원일수', 'arithmetic_mean_los', 'ariAvgLos', 'AMLOS', '평균재원일수'],
        'low_trim': ['하한재원일수', 'low_trim', 'lowTrim', '하한'],
        'high_trim': ['상한재원일수', 'high_trim', 'highTrim', '상한'],
    }
    
    def find_column(df_cols, possible_names):
        for name in possible_names:
            if name in df_cols:
                return name
        return None
    
    # 코드북 데이터 파싱
    new_codes = []
    for _, row in df.iterrows():
        code = {}
        
        # 필수 필드
        kdrg_col = find_column(df.columns, column_mapping['kdrg_code'])
        if not kdrg_col or pd.isna(row.get(kdrg_col)):
            continue
        
        code['kdrg_code'] = str(row.get(kdrg_col, '')).strip()
        if not code['kdrg_code']:
            continue
        
        # 선택 필드
        for field, possible_cols in column_mapping.items():
            if field == 'kdrg_code':
                continue
            col = find_column(df.columns, possible_cols)
            if col and not pd.isna(row.get(col)):
                val = row.get(col)
                if field in ['relative_weight', 'geometric_mean_los', 'arithmetic_mean_los']:
                    code[field] = float(val) if val else 0.0
                elif field in ['low_trim', 'high_trim']:
                    code[field] = int(val) if val else 0
                else:
                    code[field] = str(val).strip() if val else ''
            else:
                if field in ['relative_weight', 'geometric_mean_los', 'arithmetic_mean_los']:
                    code[field] = 0.0
                elif field in ['low_trim', 'high_trim']:
                    code[field] = 0
                else:
                    code[field] = ''
        
        code['version'] = version
        new_codes.append(code)
    
    return new_codes


@router.post("/validate", response_model=KDRGValidationResult)
async def validate_kdrg_code(
    request: KDRGValidationRequest,
    user: UserInfo = Depends(require_auth)
):
    """KDRG 코드 유효성 검증 (DB에서)"""
    kdrg_code = request.kdrg_code.upper()
    
    # 형식 검증
    if len(kdrg_code) != 5:
        return KDRGValidationResult(
            valid=False,
            kdrg_code=kdrg_code,
            message="KDRG 코드는 5자리여야 합니다."
        )
    
    # DB에서 검증
    result = codebook_service.validate_kdrg_code(kdrg_code)
    
    if result['valid'] and result['kdrg_info']:
        found = result['kdrg_info']
        return KDRGValidationResult(
            valid=True,
            kdrg_code=kdrg_code,
            message=result['message'],
            kdrg_info=KDRGCode(
                kdrg_code=found.get('kdrg_code', ''),
                kdrg_name=found.get('kdrg_name', ''),
                aadrg_code=found.get('aadrg_code', ''),
                aadrg_name=found.get('aadrg_name'),
                mdc_code=found.get('mdc_code'),
                mdc_name=found.get('mdc_name'),
                cc_level=found.get('cc_level'),
                relative_weight=found.get('relative_weight'),
                avg_los=found.get('arithmetic_mean_los')
            )
        )
    
    return KDRGValidationResult(
        valid=result['valid'],
        kdrg_code=kdrg_code,
        message=result['message']
    )


@router.get("/7drg", response_model=Dict)
async def get_7drg_info(user: UserInfo = Depends(require_auth)):
    """7개 DRG군 정보 조회"""
    result = []
    
    for code, info in SEVEN_DRG_GROUPS.items():
        # DB에서 해당 AADRG 코드 조회
        related = codebook_service.get_codebook(aadrg=code, per_page=10)
        related_codes = related.get('codes', [])
        
        result.append({
            'aadrg_code': code,
            'name': info['name'],
            'description': info['description'],
            'conditions': info['conditions'],
            'kdrg_count': related.get('total', 0),
            'related_kdrg': [k['kdrg_code'] for k in related_codes[:5]]
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
    related = codebook_service.get_codebook(aadrg=aadrg_code, per_page=100)
    
    return {
        "success": True,
        "drg_group": {
            'aadrg_code': aadrg_code,
            'name': info['name'],
            'description': info['description'],
            'conditions': info['conditions'],
            'kdrg_codes': related.get('codes', [])
        }
    }


@router.get("/search")
async def search_kdrg(
    q: str = Query(..., min_length=1, description="검색어"),
    user: UserInfo = Depends(require_auth)
):
    """KDRG 코드/명칭 검색 (DB에서)"""
    results = codebook_service.search_kdrg(q, limit=50)
    
    return {
        "success": True,
        "query": q,
        "total": len(results),
        "results": results
    }
