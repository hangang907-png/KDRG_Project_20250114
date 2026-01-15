"""
환류 데이터 API 라우터
- 심평원 환류 데이터 업로드 및 파싱
- 청구/심사 결과 비교 분석
- 환류 데이터 조회 및 통계
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from services.feedback_parser_service import feedback_parser, FeedbackDataType
from services.hira_portal_service import (
    hira_portal_service, 
    PortalCredentials, 
    PortalLoginMethod,
    AutoDownloadConfig
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["환류 데이터"])


# ===== Pydantic Models =====

class FeedbackUploadResponse(BaseModel):
    """환류 데이터 업로드 응답"""
    success: bool
    message: str
    file_name: str
    data_type: str
    total_records: int
    columns: List[str]
    summary: Dict[str, Any]


class FeedbackDataResponse(BaseModel):
    """환류 데이터 조회 응답"""
    success: bool
    data_type: str
    total_records: int
    records: List[Dict[str, Any]]
    summary: Dict[str, Any]


class ComparisonRequest(BaseModel):
    """비교 분석 요청"""
    claim_file_id: str
    review_file_id: str


class ComparisonResponse(BaseModel):
    """비교 분석 응답"""
    success: bool
    total_claims: int
    total_reviews: int
    matched: int
    kdrg_changed: List[Dict[str, Any]]
    amount_adjusted: List[Dict[str, Any]]
    statistics: Dict[str, Any]


class SheetListResponse(BaseModel):
    """시트 목록 응답"""
    success: bool
    sheets: List[str]


# ===== 메모리 저장소 (실제 환경에서는 DB 사용) =====
uploaded_files: Dict[str, Dict[str, Any]] = {}


# ===== API Endpoints =====

@router.post("/upload", response_model=FeedbackUploadResponse)
async def upload_feedback_file(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Query(None, description="엑셀 시트명 (선택)")
):
    """
    심평원 환류 데이터 파일 업로드 및 파싱
    
    - 지원 형식: Excel (.xlsx, .xls), CSV
    - 자동 데이터 유형 감지 (청구내역, 심사결과, 그루퍼결과 등)
    - 7개 DRG군 자동 분류
    """
    try:
        # 파일 확장자 검증
        file_ext = file.filename.lower().split('.')[-1]
        if file_ext not in ['xlsx', 'xls', 'csv']:
            raise HTTPException(
                status_code=400,
                detail="지원하지 않는 파일 형식입니다. xlsx, xls, csv만 지원합니다."
            )
        
        # 파일 읽기
        content = await file.read()
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="빈 파일입니다.")
        
        # 파일 크기 제한 (50MB)
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="파일 크기는 50MB를 초과할 수 없습니다.")
        
        # 파싱
        result = feedback_parser.parse_bytes(content, file.filename, sheet_name)
        
        # 저장 (메모리)
        file_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
        uploaded_files[file_id] = {
            **result,
            'file_id': file_id,
            'uploaded_at': datetime.now().isoformat(),
            'content': content,  # 나중에 재파싱 가능하도록
        }
        
        return FeedbackUploadResponse(
            success=True,
            message=f"파일이 성공적으로 업로드되었습니다. ({result['data_type']})",
            file_name=file.filename,
            data_type=result['data_type'],
            total_records=result['total_records'],
            columns=result['columns'],
            summary=result['summary'],
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"파일 업로드 오류: {e}")
        raise HTTPException(status_code=500, detail=f"파일 처리 중 오류가 발생했습니다: {str(e)}")


@router.post("/upload/sheets", response_model=SheetListResponse)
async def get_excel_sheets(file: UploadFile = File(...)):
    """
    엑셀 파일의 시트 목록 조회
    """
    try:
        content = await file.read()
        sheets = feedback_parser.get_excel_sheets(content, file.filename)
        
        return SheetListResponse(
            success=True,
            sheets=sheets
        )
    except Exception as e:
        logger.error(f"시트 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files")
async def list_uploaded_files():
    """
    업로드된 환류 데이터 파일 목록 조회
    """
    files = []
    for file_id, data in uploaded_files.items():
        files.append({
            'file_id': file_id,
            'file_name': data.get('file_name', ''),
            'data_type': data.get('data_type', ''),
            'total_records': data.get('total_records', 0),
            'uploaded_at': data.get('uploaded_at', ''),
            'summary': data.get('summary', {}),
        })
    
    return {
        'success': True,
        'total': len(files),
        'files': sorted(files, key=lambda x: x['uploaded_at'], reverse=True)
    }


@router.get("/files/{file_id}")
async def get_file_data(
    file_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500)
):
    """
    특정 파일의 파싱된 데이터 조회 (페이지네이션)
    """
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    
    data = uploaded_files[file_id]
    records = data.get('records', [])
    
    # 페이지네이션
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_records = records[start_idx:end_idx]
    
    return {
        'success': True,
        'file_id': file_id,
        'data_type': data.get('data_type', ''),
        'total_records': len(records),
        'page': page,
        'page_size': page_size,
        'total_pages': (len(records) + page_size - 1) // page_size,
        'records': paginated_records,
        'summary': data.get('summary', {}),
    }


@router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """
    업로드된 파일 삭제
    """
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    
    del uploaded_files[file_id]
    
    return {
        'success': True,
        'message': '파일이 삭제되었습니다.'
    }


@router.post("/compare")
async def compare_claim_review(
    claim_file_id: str = Query(..., description="청구 데이터 파일 ID"),
    review_file_id: str = Query(..., description="심사 결과 파일 ID")
):
    """
    청구 데이터와 심사 결과 비교 분석
    
    - KDRG 변경 건 추출
    - 금액 조정 분석
    - 조정률 계산
    """
    if claim_file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="청구 데이터 파일을 찾을 수 없습니다.")
    
    if review_file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="심사 결과 파일을 찾을 수 없습니다.")
    
    claim_data = uploaded_files[claim_file_id]
    review_data = uploaded_files[review_file_id]
    
    # 데이터 유형 검증
    if claim_data.get('data_type') != FeedbackDataType.DRG_CLAIM.value:
        raise HTTPException(status_code=400, detail="청구 데이터 파일이 아닙니다.")
    
    if review_data.get('data_type') != FeedbackDataType.REVIEW_RESULT.value:
        raise HTTPException(status_code=400, detail="심사 결과 파일이 아닙니다.")
    
    # 비교 분석
    comparison = feedback_parser.compare_claim_vs_review(claim_data, review_data)
    
    return {
        'success': True,
        **comparison
    }


@router.get("/statistics")
async def get_feedback_statistics():
    """
    전체 환류 데이터 통계
    """
    stats = {
        'total_files': len(uploaded_files),
        'by_data_type': {},
        'total_records': 0,
        'total_claimed_amount': 0,
        'total_reviewed_amount': 0,
        'total_adjustment': 0,
        'overall_adjustment_rate': 0,
        'drg_distribution': {},
    }
    
    for file_id, data in uploaded_files.items():
        data_type = data.get('data_type', 'unknown')
        stats['by_data_type'][data_type] = stats['by_data_type'].get(data_type, 0) + 1
        stats['total_records'] += data.get('total_records', 0)
        
        summary = data.get('summary', {})
        stats['total_claimed_amount'] += summary.get('total_claimed_amount', 0)
        stats['total_reviewed_amount'] += summary.get('total_reviewed_amount', 0)
        stats['total_adjustment'] += summary.get('total_adjustment', 0)
        
        # DRG 분포 합산
        for drg, count in summary.get('drg_distribution', {}).items():
            stats['drg_distribution'][drg] = stats['drg_distribution'].get(drg, 0) + count
    
    # 전체 조정률
    if stats['total_claimed_amount'] > 0:
        stats['overall_adjustment_rate'] = round(
            stats['total_adjustment'] / stats['total_claimed_amount'] * 100, 2
        )
    
    return {
        'success': True,
        **stats
    }


@router.get("/analysis/kdrg-changes")
async def analyze_kdrg_changes(file_id: Optional[str] = None):
    """
    KDRG 코드 변경 분석
    
    - 심사 후 KDRG 변경 패턴 분석
    - 변경 빈도가 높은 KDRG 코드 추출
    """
    changes = []
    change_patterns = {}  # 원래 KDRG -> 변경 KDRG 패턴
    
    files_to_analyze = (
        {file_id: uploaded_files[file_id]} if file_id and file_id in uploaded_files 
        else uploaded_files
    )
    
    for fid, data in files_to_analyze.items():
        if data.get('data_type') != FeedbackDataType.REVIEW_RESULT.value:
            continue
        
        for record in data.get('records', []):
            original = record.get('original_kdrg', '')
            reviewed = record.get('reviewed_kdrg', '')
            
            if original and reviewed and original != reviewed:
                changes.append({
                    'file_id': fid,
                    'claim_id': record.get('claim_id', ''),
                    'original_kdrg': original,
                    'reviewed_kdrg': reviewed,
                    'adjustment_amount': record.get('adjustment_amount', 0),
                    'adjustment_reason': record.get('adjustment_reason', ''),
                })
                
                # 패턴 집계
                pattern_key = f"{original} → {reviewed}"
                if pattern_key not in change_patterns:
                    change_patterns[pattern_key] = {'count': 0, 'total_adjustment': 0}
                change_patterns[pattern_key]['count'] += 1
                change_patterns[pattern_key]['total_adjustment'] += record.get('adjustment_amount', 0)
    
    # 패턴 정렬 (빈도순)
    sorted_patterns = sorted(
        [{'pattern': k, **v} for k, v in change_patterns.items()],
        key=lambda x: x['count'],
        reverse=True
    )
    
    return {
        'success': True,
        'total_changes': len(changes),
        'changes': changes[:100],  # 최대 100건
        'top_patterns': sorted_patterns[:20],  # 상위 20개 패턴
    }


@router.get("/analysis/adjustment-reasons")
async def analyze_adjustment_reasons(file_id: Optional[str] = None):
    """
    조정 사유 분석
    
    - 조정 사유별 빈도 및 금액 분석
    - 주요 삭감 사유 추출
    """
    reasons = {}
    
    files_to_analyze = (
        {file_id: uploaded_files[file_id]} if file_id and file_id in uploaded_files 
        else uploaded_files
    )
    
    for fid, data in files_to_analyze.items():
        if data.get('data_type') != FeedbackDataType.REVIEW_RESULT.value:
            continue
        
        for record in data.get('records', []):
            reason = record.get('adjustment_reason', '').strip()
            if not reason:
                reason = '사유 미기재'
            
            adjustment = record.get('adjustment_amount', 0)
            
            if reason not in reasons:
                reasons[reason] = {
                    'count': 0,
                    'total_adjustment': 0,
                    'avg_adjustment': 0,
                }
            reasons[reason]['count'] += 1
            reasons[reason]['total_adjustment'] += adjustment
    
    # 평균 계산 및 정렬
    for reason in reasons:
        if reasons[reason]['count'] > 0:
            reasons[reason]['avg_adjustment'] = round(
                reasons[reason]['total_adjustment'] / reasons[reason]['count'], 0
            )
    
    sorted_reasons = sorted(
        [{'reason': k, **v} for k, v in reasons.items()],
        key=lambda x: x['total_adjustment'],
        reverse=True
    )
    
    return {
        'success': True,
        'total_reasons': len(sorted_reasons),
        'reasons': sorted_reasons
    }


@router.get("/analysis/drg7-summary")
async def analyze_drg7_summary():
    """
    7개 DRG군별 환류 분석 요약
    """
    drg7_stats = {
        'D12': {'name': '편도 및 아데노이드 절제술', 'claims': 0, 'adjustments': 0, 'kdrg_changes': 0},
        'D13': {'name': '축농증 수술', 'claims': 0, 'adjustments': 0, 'kdrg_changes': 0},
        'G08': {'name': '서혜부 및 대퇴부 탈장수술', 'claims': 0, 'adjustments': 0, 'kdrg_changes': 0},
        'H06': {'name': '담낭절제술', 'claims': 0, 'adjustments': 0, 'kdrg_changes': 0},
        'I09': {'name': '항문수술', 'claims': 0, 'adjustments': 0, 'kdrg_changes': 0},
        'L08': {'name': '요로결석 체외충격파쇄석술', 'claims': 0, 'adjustments': 0, 'kdrg_changes': 0},
        'O01': {'name': '제왕절개술', 'claims': 0, 'adjustments': 0, 'kdrg_changes': 0},
        'O60': {'name': '질식분만', 'claims': 0, 'adjustments': 0, 'kdrg_changes': 0},
        'OTHER': {'name': '기타 (행위별)', 'claims': 0, 'adjustments': 0, 'kdrg_changes': 0},
    }
    
    for file_id, data in uploaded_files.items():
        for record in data.get('records', []):
            # KDRG 코드 추출
            kdrg = (
                record.get('claimed_kdrg') or 
                record.get('original_kdrg') or 
                record.get('kdrg') or ''
            )
            
            # 7개 DRG군 분류
            drg_code = 'OTHER'
            for code in ['D12', 'D13', 'G08', 'H06', 'I09', 'L08', 'O01', 'O60']:
                if kdrg.startswith(code):
                    drg_code = code
                    break
            
            drg7_stats[drg_code]['claims'] += 1
            drg7_stats[drg_code]['adjustments'] += record.get('adjustment_amount', 0)
            
            # KDRG 변경 체크
            original = record.get('original_kdrg', '')
            reviewed = record.get('reviewed_kdrg', '')
            if original and reviewed and original != reviewed:
                drg7_stats[drg_code]['kdrg_changes'] += 1
    
    return {
        'success': True,
        'drg7_summary': drg7_stats
    }


@router.post("/reparse/{file_id}")
async def reparse_file(
    file_id: str,
    sheet_name: Optional[str] = Query(None, description="엑셀 시트명")
):
    """
    파일 재파싱 (다른 시트 선택 등)
    """
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    
    data = uploaded_files[file_id]
    content = data.get('content')
    
    if not content:
        raise HTTPException(status_code=400, detail="원본 파일이 없습니다.")
    
    # 재파싱
    result = feedback_parser.parse_bytes(content, data.get('file_name', ''), sheet_name)
    
    # 업데이트
    uploaded_files[file_id].update({
        **result,
        'reparsed_at': datetime.now().isoformat(),
    })
    
    return {
        'success': True,
        'message': '파일이 재파싱되었습니다.',
        'data_type': result['data_type'],
        'total_records': result['total_records'],
        'summary': result['summary'],
    }


# ===== 요양기관업무포털 자동 다운로드 API =====

class PortalLoginRequest(BaseModel):
    """포털 로그인 요청"""
    hospital_code: str = Field(..., description="요양기관번호")
    user_id: str = Field(..., description="사용자 ID")
    password: str = Field(..., description="비밀번호")
    login_method: str = Field("id_password", description="로그인 방법 (id_password, certificate, simple_auth)")


class PortalConfigRequest(BaseModel):
    """자동 다운로드 설정 요청"""
    enabled: bool = Field(True, description="활성화 여부")
    schedule_time: str = Field("06:00", description="실행 시간 (HH:MM)")
    download_path: str = Field("./downloads/feedback", description="다운로드 경로")
    file_types: Optional[List[str]] = Field(None, description="파일 유형 (None이면 모두)")
    days_to_keep: int = Field(90, description="파일 보관 기간")
    auto_parse: bool = Field(True, description="자동 파싱 여부")


class PortalFileRequest(BaseModel):
    """파일 목록 조회 요청"""
    start_date: Optional[str] = Field(None, description="시작일 (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="종료일 (YYYY-MM-DD)")
    file_type: Optional[str] = Field(None, description="파일 유형 필터")


class PortalDownloadRequest(BaseModel):
    """파일 다운로드 요청"""
    file_ids: List[str] = Field(..., description="다운로드할 파일 ID 목록")


@router.post("/portal/login")
async def portal_login(request: PortalLoginRequest):
    """
    요양기관업무포털 로그인
    
    심평원 요양기관업무포털(biz.hira.or.kr)에 로그인합니다.
    현재는 시뮬레이션 모드로 동작합니다.
    """
    try:
        # 로그인 방법 변환
        login_method_map = {
            "id_password": PortalLoginMethod.ID_PASSWORD,
            "certificate": PortalLoginMethod.CERTIFICATE,
            "simple_auth": PortalLoginMethod.SIMPLE_AUTH,
        }
        login_method = login_method_map.get(request.login_method, PortalLoginMethod.ID_PASSWORD)
        
        # 자격증명 설정
        credentials = PortalCredentials(
            hospital_code=request.hospital_code,
            user_id=request.user_id,
            password=request.password,
            login_method=login_method,
        )
        hira_portal_service.set_credentials(credentials)
        
        # 로그인 시도
        success, message = await hira_portal_service.login()
        
        return {
            "success": success,
            "message": message,
            "hospital_code": request.hospital_code,
            "is_simulation": True,  # 현재 시뮬레이션 모드
        }
        
    except Exception as e:
        logger.error(f"Portal login error: {e}")
        raise HTTPException(status_code=500, detail=f"로그인 처리 중 오류: {str(e)}")


@router.post("/portal/logout")
async def portal_logout():
    """
    요양기관업무포털 로그아웃
    """
    try:
        await hira_portal_service.logout()
        return {
            "success": True,
            "message": "로그아웃되었습니다.",
        }
    except Exception as e:
        logger.error(f"Portal logout error: {e}")
        raise HTTPException(status_code=500, detail=f"로그아웃 처리 중 오류: {str(e)}")


@router.get("/portal/files")
async def get_portal_files(
    start_date: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    file_type: Optional[str] = Query(None, description="파일 유형 필터"),
):
    """
    요양기관업무포털 환류파일 목록 조회
    
    포털에 로그인된 상태에서 환류파일 목록을 조회합니다.
    """
    try:
        if not hira_portal_service.is_logged_in:
            raise HTTPException(status_code=401, detail="포털에 먼저 로그인하세요.")
        
        files = await hira_portal_service.get_feedback_file_list(
            start_date=start_date,
            end_date=end_date,
            file_type=file_type,
        )
        
        return {
            "success": True,
            "total": len(files),
            "files": [
                {
                    "file_id": f.file_id,
                    "file_name": f.file_name,
                    "file_date": f.file_date,
                    "file_type": f.file_type,
                    "file_size": f.file_size,
                    "is_new": f.is_new,
                    "downloaded": f.downloaded,
                }
                for f in files
            ],
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get portal files error: {e}")
        raise HTTPException(status_code=500, detail=f"파일 목록 조회 중 오류: {str(e)}")


@router.post("/portal/download")
async def download_portal_files(request: PortalDownloadRequest, background_tasks: BackgroundTasks):
    """
    요양기관업무포털 환류파일 다운로드
    
    지정된 파일들을 다운로드합니다.
    """
    try:
        if not hira_portal_service.is_logged_in:
            raise HTTPException(status_code=401, detail="포털에 먼저 로그인하세요.")
        
        # 파일 목록 조회
        all_files = await hira_portal_service.get_feedback_file_list()
        
        # 요청된 파일만 필터
        files_to_download = [f for f in all_files if f.file_id in request.file_ids]
        
        if not files_to_download:
            raise HTTPException(status_code=404, detail="다운로드할 파일을 찾을 수 없습니다.")
        
        # 다운로드 실행
        results = []
        for file_info in files_to_download:
            result = await hira_portal_service.download_file(file_info)
            results.append({
                "file_id": file_info.file_id,
                "file_name": file_info.file_name,
                "success": result.success,
                "local_path": result.local_path,
                "error": result.error_message,
                "download_time": result.download_time,
            })
        
        success_count = sum(1 for r in results if r["success"])
        
        return {
            "success": True,
            "message": f"{success_count}/{len(results)}개 파일 다운로드 완료",
            "results": results,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download portal files error: {e}")
        raise HTTPException(status_code=500, detail=f"파일 다운로드 중 오류: {str(e)}")


@router.post("/portal/auto-download")
async def auto_download_portal_files():
    """
    요양기관업무포털 신규 파일 자동 다운로드
    
    설정된 자격증명으로 로그인하여 신규 환류파일을 자동으로 다운로드합니다.
    """
    try:
        # 자동 다운로드 실행
        result = await hira_portal_service.auto_download_and_parse()
        
        return {
            "success": result["success"],
            "message": "자동 다운로드 완료" if result["success"] else "자동 다운로드 실패",
            "timestamp": result["timestamp"],
            "downloaded_count": len(result["downloaded_files"]),
            "downloaded_files": result["downloaded_files"],
            "parsed_files": result["parsed_files"],
            "errors": result["errors"],
        }
        
    except Exception as e:
        logger.error(f"Auto download error: {e}")
        raise HTTPException(status_code=500, detail=f"자동 다운로드 중 오류: {str(e)}")


@router.get("/portal/status")
async def get_portal_status():
    """
    요양기관업무포털 서비스 상태 조회
    """
    try:
        status = hira_portal_service.get_status()
        return {
            "success": True,
            **status,
        }
    except Exception as e:
        logger.error(f"Get portal status error: {e}")
        raise HTTPException(status_code=500, detail=f"상태 조회 중 오류: {str(e)}")


@router.post("/portal/config")
async def set_portal_config(request: PortalConfigRequest):
    """
    자동 다운로드 설정
    """
    try:
        config = AutoDownloadConfig(
            enabled=request.enabled,
            schedule_time=request.schedule_time,
            download_path=request.download_path,
            file_types=request.file_types,
            days_to_keep=request.days_to_keep,
            auto_parse=request.auto_parse,
        )
        hira_portal_service.set_config(config)
        
        return {
            "success": True,
            "message": "설정이 저장되었습니다.",
            "config": {
                "enabled": config.enabled,
                "schedule_time": config.schedule_time,
                "download_path": config.download_path,
                "file_types": config.file_types,
                "days_to_keep": config.days_to_keep,
                "auto_parse": config.auto_parse,
            },
        }
        
    except Exception as e:
        logger.error(f"Set portal config error: {e}")
        raise HTTPException(status_code=500, detail=f"설정 저장 중 오류: {str(e)}")


@router.get("/portal/config")
async def get_portal_config():
    """
    자동 다운로드 설정 조회
    """
    try:
        status = hira_portal_service.get_status()
        return {
            "success": True,
            "config": status.get("config", {}),
        }
    except Exception as e:
        logger.error(f"Get portal config error: {e}")
        raise HTTPException(status_code=500, detail=f"설정 조회 중 오류: {str(e)}")


@router.get("/portal/history")
async def get_download_history(
    limit: int = Query(50, ge=1, le=500, description="조회할 이력 수")
):
    """
    다운로드 이력 조회
    """
    try:
        history = hira_portal_service.get_download_history(limit=limit)
        return {
            "success": True,
            "total": len(history),
            "history": history,
        }
    except Exception as e:
        logger.error(f"Get download history error: {e}")
        raise HTTPException(status_code=500, detail=f"이력 조회 중 오류: {str(e)}")
