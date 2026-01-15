"""
KDRG Pre-Grouper API 라우터
- 병원 내 KDRG 사전 분류 API
- 청구 전 KDRG 예측 및 검증
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from dataclasses import asdict
import logging
import io
import pandas as pd

from config import settings
from services.pregrouper_service import (
    KDRGPreGrouper,
    pre_grouper,
    GrouperInput,
    GrouperResult,
    PatientInfo,
    DiagnosisInfo,
    ProcedureInfo,
)
from services.grouping_store import grouping_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Pre-Grouper"])


# ===== Pydantic Models =====

class PatientInput(BaseModel):
    """환자 정보 입력"""
    patient_id: str = Field(..., description="환자 ID")
    age: int = Field(..., ge=0, le=120, description="나이")
    sex: str = Field(..., pattern="^[MF]$", description="성별 (M/F)")
    admission_date: str = Field(..., description="입원일 (YYYY-MM-DD)")
    discharge_date: str = Field(..., description="퇴원일 (YYYY-MM-DD)")
    los: int = Field(..., ge=0, description="재원일수")
    birth_weight: Optional[int] = Field(None, description="신생아 출생체중 (g)")
    discharge_status: str = Field("alive", description="퇴원 상태 (alive/dead/transfer)")


class DiagnosisInput(BaseModel):
    """진단 정보 입력"""
    main_diagnosis: str = Field(..., description="주진단 코드 (ICD-10)")
    sub_diagnoses: List[str] = Field(default_factory=list, description="부진단 코드 목록")
    admission_diagnosis: Optional[str] = Field(None, description="입원 시 진단")


class ProcedureInput(BaseModel):
    """수술/처치 정보 입력"""
    procedures: List[str] = Field(default_factory=list, description="수술/처치 코드 목록")
    main_procedure: Optional[str] = Field(None, description="주수술 코드")


class GroupingRequest(BaseModel):
    """그루핑 요청"""
    patient: PatientInput
    diagnosis: DiagnosisInput
    procedure: ProcedureInput = Field(default_factory=ProcedureInput)
    claim_id: Optional[str] = Field(None, description="청구 ID")


class SimpleGroupingRequest(BaseModel):
    """간편 그루핑 요청"""
    patient_id: str
    age: int
    sex: str
    admission_date: str
    discharge_date: str
    los: int
    main_diagnosis: str
    sub_diagnoses: List[str] = Field(default_factory=list)
    procedures: List[str] = Field(default_factory=list)
    claim_id: Optional[str] = None


class BatchGroupingRequest(BaseModel):
    """배치 그루핑 요청"""
    records: List[SimpleGroupingRequest]


# ===== 저장소 (SQLite via grouping_store) =====


# ===== API Endpoints =====

@router.post("/group")
async def group_single(request: GroupingRequest):
    """
    단건 KDRG 그루핑
    
    환자 정보, 진단 정보, 수술/처치 정보를 입력받아 KDRG 코드를 생성합니다.
    """
    try:
        # 입력 데이터 변환
        patient = PatientInfo(
            patient_id=request.patient.patient_id,
            age=request.patient.age,
            sex=request.patient.sex,
            admission_date=request.patient.admission_date,
            discharge_date=request.patient.discharge_date,
            los=request.patient.los,
            birth_weight=request.patient.birth_weight,
            discharge_status=request.patient.discharge_status,
        )
        
        diagnosis = DiagnosisInfo(
            main_diagnosis=request.diagnosis.main_diagnosis,
            sub_diagnoses=request.diagnosis.sub_diagnoses,
            admission_diagnosis=request.diagnosis.admission_diagnosis,
        )
        
        procedure = ProcedureInfo(
            procedures=request.procedure.procedures,
            main_procedure=request.procedure.main_procedure,
        )
        
        input_data = GrouperInput(
            patient=patient,
            diagnosis=diagnosis,
            procedure=procedure,
            claim_id=request.claim_id,
        )
        
        # 그루핑 실행
        result = pre_grouper.group(input_data)
        
        # 히스토리 저장 (SQLite)
        history_id = f"grp_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        created_at = datetime.now().isoformat()
        payload = {
            'history_id': history_id,
            'created_at': created_at,
            'input': {
                'patient_id': request.patient.patient_id,
                'main_diagnosis': request.diagnosis.main_diagnosis,
            },
            'result': asdict(result),
        }
        await grouping_store.save_history(history_id, "single", payload)
        
        return {
            'success': True,
            'history_id': history_id,
            'result': asdict(result),
        }
        
    except Exception as e:
        logger.error(f"그루핑 오류: {e}")
        raise HTTPException(status_code=500, detail=f"그루핑 중 오류 발생: {str(e)}")


@router.post("/group-simple")
async def group_simple(request: SimpleGroupingRequest):
    """
    간편 KDRG 그루핑
    
    플랫 구조로 데이터를 입력받아 KDRG 코드를 생성합니다.
    """
    try:
        data = {
            'patient_id': request.patient_id,
            'age': request.age,
            'sex': request.sex,
            'admission_date': request.admission_date,
            'discharge_date': request.discharge_date,
            'los': request.los,
            'main_diagnosis': request.main_diagnosis,
            'sub_diagnoses': request.sub_diagnoses,
            'procedures': request.procedures,
            'claim_id': request.claim_id,
        }
        
        result = pre_grouper.group_from_dict(data)
        
        return {
            'success': True,
            'result': asdict(result),
        }
        
    except Exception as e:
        logger.error(f"간편 그루핑 오류: {e}")
        raise HTTPException(status_code=500, detail=f"그루핑 중 오류 발생: {str(e)}")


@router.post("/group-batch")
async def group_batch(request: BatchGroupingRequest):
    """
    배치 KDRG 그루핑
    
    여러 건의 데이터를 한 번에 그루핑합니다.
    """
    try:
        results = []
        errors = []
        
        for idx, record in enumerate(request.records):
            try:
                data = {
                    'patient_id': record.patient_id,
                    'age': record.age,
                    'sex': record.sex,
                    'admission_date': record.admission_date,
                    'discharge_date': record.discharge_date,
                    'los': record.los,
                    'main_diagnosis': record.main_diagnosis,
                    'sub_diagnoses': record.sub_diagnoses,
                    'procedures': record.procedures,
                    'claim_id': record.claim_id,
                }
                result = pre_grouper.group_from_dict(data)
                results.append(asdict(result))
            except Exception as e:
                errors.append({
                    'index': idx,
                    'patient_id': record.patient_id,
                    'error': str(e),
                })
        
        # 배치 결과 저장
        batch_id = f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        created_at = datetime.now().isoformat()
        payload = {
            'history_id': batch_id,
            'created_at': created_at,
            'type': 'batch',
            'total': len(request.records),
            'success_count': len(results),
            'error_count': len(errors),
            'results': results,
            'errors': errors,
        }
        await grouping_store.save_history(batch_id, "batch", payload)
        
        return {
            'success': True,
            'batch_id': batch_id,
            'total': len(request.records),
            'success_count': len(results),
            'error_count': len(errors),
            'results': results,
            'errors': errors if errors else None,
        }
        
    except Exception as e:
        logger.error(f"배치 그루핑 오류: {e}")
        raise HTTPException(status_code=500, detail=f"배치 그루핑 중 오류 발생: {str(e)}")


@router.post("/upload")
async def upload_and_group(
    file: UploadFile = File(..., description="CSV 또는 Excel 파일")
):
    """
    파일 업로드 후 일괄 그루핑
    
    CSV 또는 Excel 파일을 업로드하면 자동으로 그루핑합니다.
    
    필수 컬럼:
    - patient_id: 환자 ID
    - age: 나이
    - sex: 성별 (M/F)
    - admission_date: 입원일
    - discharge_date: 퇴원일
    - los: 재원일수
    - main_diagnosis: 주진단
    
    선택 컬럼:
    - sub_diagnoses: 부진단 (쉼표로 구분)
    - procedures: 수술/처치 코드 (쉼표로 구분)
    """
    try:
        # 파일 읽기 (크기 제한)
        max_bytes = settings.MAX_UPLOAD_BYTES
        content = await file.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise HTTPException(status_code=413, detail=f"파일 크기가 제한({settings.MAX_UPLOAD_SIZE_MB}MB)를 초과했습니다.")

        filename = file.filename.lower()
        
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content), encoding='utf-8-sig')
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise HTTPException(status_code=400, detail="지원하지 않는 파일 형식입니다. CSV 또는 Excel 파일만 가능합니다.")
        
        # 행 수 제한
        if len(df) > settings.MAX_UPLOAD_ROWS:
            raise HTTPException(status_code=413, detail=f"업로드 건수가 제한({settings.MAX_UPLOAD_ROWS}건)를 초과했습니다.")
        
        # 필수 컬럼 확인
        required_cols = ['patient_id', 'age', 'sex', 'admission_date', 'discharge_date', 'los', 'main_diagnosis']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            raise HTTPException(
                status_code=400, 
                detail=f"필수 컬럼이 누락되었습니다: {', '.join(missing_cols)}"
            )
        
        results = []
        errors = []
        
        for idx, row in df.iterrows():
            try:
                # 부진단 처리
                sub_diagnoses = []
                if 'sub_diagnoses' in df.columns and pd.notna(row.get('sub_diagnoses')):
                    sub_dx = str(row['sub_diagnoses'])
                    sub_diagnoses = [s.strip() for s in sub_dx.split(',') if s.strip()]
                
                # 수술/처치 처리
                procedures = []
                if 'procedures' in df.columns and pd.notna(row.get('procedures')):
                    procs = str(row['procedures'])
                    procedures = [p.strip() for p in procs.split(',') if p.strip()]
                
                data = {
                    'patient_id': str(row['patient_id']),
                    'age': int(row['age']),
                    'sex': str(row['sex']).upper(),
                    'admission_date': str(row['admission_date'])[:10],
                    'discharge_date': str(row['discharge_date'])[:10],
                    'los': int(row['los']),
                    'main_diagnosis': str(row['main_diagnosis']),
                    'sub_diagnoses': sub_diagnoses,
                    'procedures': procedures,
                    'claim_id': str(row.get('claim_id', '')),
                }
                
                result = pre_grouper.group_from_dict(data)
                results.append(asdict(result))
                
            except Exception as e:
                errors.append({
                    'row': idx + 2,  # 헤더 + 0-인덱스
                    'patient_id': str(row.get('patient_id', 'unknown')),
                    'error': str(e),
                })
        
        # 업로드 결과 저장
        upload_id = f"upload_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        created_at = datetime.now().isoformat()
        payload = {
            'history_id': upload_id,
            'created_at': created_at,
            'type': 'upload',
            'filename': file.filename,
            'total': len(df),
            'success_count': len(results),
            'error_count': len(errors),
            'results': results,
            'errors': errors,
        }
        await grouping_store.save_history(upload_id, "upload", payload)
        
        # DRG군별 통계
        drg_stats = {}
        for r in results:
            drg_type = r.get('drg_type', '행위별')
            if drg_type not in drg_stats:
                drg_stats[drg_type] = {'count': 0, 'total_amount': 0}
            drg_stats[drg_type]['count'] += 1
            drg_stats[drg_type]['total_amount'] += r.get('estimated_amount', 0)
        
        return {
            'success': True,
            'upload_id': upload_id,
            'filename': file.filename,
            'total': len(df),
            'success_count': len(results),
            'error_count': len(errors),
            'drg_statistics': drg_stats,
            'results': results[:settings.MAX_RESULT_PREVIEW],
            'errors': errors[:settings.MAX_ERROR_PREVIEW] if errors else None,
            'message': f"총 {len(df)}건 중 {len(results)}건 그루핑 완료"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"파일 업로드 그루핑 오류: {e}")
        raise HTTPException(status_code=500, detail=f"파일 처리 중 오류 발생: {str(e)}")


@router.get("/history")
async def get_grouping_history(
    limit: int = Query(50, ge=1, le=200, description="조회 건수")
):
    """
    그루핑 히스토리 조회 (SQLite)
    """
    return await grouping_store.list_history(limit)


@router.get("/history/{history_id}")
async def get_grouping_result(history_id: str):
    """
    특정 그루핑 결과 상세 조회
    """
    result = await grouping_store.get_history(history_id)
    if not result:
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")
    
    return {
        'success': True,
        **result,
    }


@router.post("/optimize")
async def get_optimization(request: SimpleGroupingRequest):
    """
    KDRG 최적화 추천
    
    현재 KDRG 분류 결과에서 개선 가능한 항목을 분석합니다.
    """
    try:
        data = {
            'patient_id': request.patient_id,
            'age': request.age,
            'sex': request.sex,
            'admission_date': request.admission_date,
            'discharge_date': request.discharge_date,
            'los': request.los,
            'main_diagnosis': request.main_diagnosis,
            'sub_diagnoses': request.sub_diagnoses,
            'procedures': request.procedures,
            'claim_id': request.claim_id,
        }
        
        result = pre_grouper.group_from_dict(data)
        optimization = pre_grouper.estimate_optimization(result)
        
        return {
            'success': True,
            'grouping_result': asdict(result),
            'optimization': optimization,
        }
        
    except Exception as e:
        logger.error(f"최적화 분석 오류: {e}")
        raise HTTPException(status_code=500, detail=f"최적화 분석 중 오류 발생: {str(e)}")


@router.get("/drg7-info")
async def get_drg7_info():
    """
    7개 DRG군 정보 조회
    """
    drg7_info = []
    for code, info in KDRGPreGrouper.DRG7_SURGERY_CODES.items():
        drg7_info.append({
            'code': code,
            'name': info['name'],
            'procedures': info['procedures'],
            'diagnoses': info['diagnoses'],
            'base_weight': info['base_weight'],
            'los_lower': info['los_range'][0],
            'los_upper': info['los_range'][1],
        })
    
    return {
        'success': True,
        'total': len(drg7_info),
        'drg7': drg7_info,
    }


@router.get("/mdc-info")
async def get_mdc_info():
    """
    MDC (주진단범주) 정보 조회
    """
    mdc_info = []
    for code, (name, prefixes) in KDRGPreGrouper.MDC_DEFINITIONS.items():
        mdc_info.append({
            'code': code,
            'name': name,
            'diagnosis_prefixes': prefixes,
        })
    
    return {
        'success': True,
        'total': len(mdc_info),
        'mdc': mdc_info,
    }


@router.get("/cc-codes")
async def get_cc_codes():
    """
    CC/MCC 코드 목록 조회
    """
    return {
        'success': True,
        'mcc': KDRGPreGrouper.CC_CODES['MCC'],
        'cc': KDRGPreGrouper.CC_CODES['CC'],
    }


@router.delete("/history/{history_id}")
async def delete_history(history_id: str):
    """
    그루핑 히스토리 삭제
    """
    deleted = await grouping_store.delete_history(history_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")
    
    return {
        'success': True,
        'message': '히스토리가 삭제되었습니다.',
    }


@router.get("/statistics")
async def get_grouping_statistics():
    """
    전체 그루핑 통계 조회
    """
    return await grouping_store.get_statistics()
