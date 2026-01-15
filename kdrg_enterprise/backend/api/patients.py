"""
환자 관리 API 라우터
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import date
import pandas as pd
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from services.privacy_service import privacy_protector
from services.profit_service import profit_optimizer, OptimizationRecommendation, LossAlert
from api.auth import require_auth, UserInfo

router = APIRouter()


# 모델 정의
class PatientCreate(BaseModel):
    patient_id: str
    patient_name: str
    gender: Optional[str] = None
    age: Optional[int] = None
    department: Optional[str] = None
    admission_date: Optional[date] = None
    discharge_date: Optional[date] = None
    primary_diagnosis_code: Optional[str] = None
    diagnosis_name: Optional[str] = None
    kdrg_code: Optional[str] = None
    aadrg_code: Optional[str] = None
    claim_amount: Optional[float] = None


class PatientResponse(BaseModel):
    id: int
    masked_patient_id: str
    masked_name: str
    gender: Optional[str] = None
    age: Optional[int] = None
    age_group: Optional[str] = None
    department: Optional[str] = None
    admission_date: Optional[date] = None
    discharge_date: Optional[date] = None
    length_of_stay: Optional[int] = None
    primary_diagnosis_code: Optional[str] = None
    diagnosis_name: Optional[str] = None
    kdrg_code: Optional[str] = None
    aadrg_code: Optional[str] = None
    drg_group: Optional[str] = None
    claim_amount: Optional[float] = None


class PatientListResponse(BaseModel):
    success: bool
    total: int
    page: int
    per_page: int
    patients: List[PatientResponse]


class ImportResult(BaseModel):
    success: bool
    message: str
    total_imported: int
    errors: List[str]


# 인메모리 환자 저장소 (프로덕션에서는 DB 사용)
PATIENTS_DB: List[Dict] = []
PATIENT_ID_COUNTER = 0


def get_drg_group(aadrg_code: str) -> str:
    """7개 DRG군 분류"""
    if not aadrg_code:
        return "미분류"
    
    drg_groups = {
        'T01': '편도/축농증',
        'T03': '수혈',
        'X04': '망막/백내장',
        'X05': '결석',
        'T05': '중이염',
        'T11': '모낭염',
        'T12': '치핵'
    }
    
    for code, name in drg_groups.items():
        if aadrg_code.startswith(code):
            return f"{code} - {name}"
    
    return "기타 DRG"


@router.get("/", response_model=PatientListResponse)
async def list_patients(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    department: Optional[str] = None,
    drg_group: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    user: UserInfo = Depends(require_auth)
):
    """환자 목록 조회 (마스킹된 정보)"""
    filtered = PATIENTS_DB.copy()
    
    # 필터링
    if department:
        filtered = [p for p in filtered if p.get('department') == department]
    
    if drg_group:
        filtered = [p for p in filtered if p.get('drg_group') == drg_group]
    
    if date_from:
        filtered = [p for p in filtered if p.get('admission_date') and p['admission_date'] >= date_from]
    
    if date_to:
        filtered = [p for p in filtered if p.get('admission_date') and p['admission_date'] <= date_to]
    
    # 페이징
    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = filtered[start:end]
    
    # 응답 변환
    patients = [
        PatientResponse(
            id=p['id'],
            masked_patient_id=p.get('masked_patient_id', '****'),
            masked_name=p.get('masked_name', '***'),
            gender=p.get('gender'),
            age=p.get('age'),
            age_group=p.get('age_group'),
            department=p.get('department'),
            admission_date=p.get('admission_date'),
            discharge_date=p.get('discharge_date'),
            length_of_stay=p.get('length_of_stay'),
            primary_diagnosis_code=p.get('primary_diagnosis_code'),
            diagnosis_name=p.get('diagnosis_name'),
            kdrg_code=p.get('kdrg_code'),
            aadrg_code=p.get('aadrg_code'),
            drg_group=p.get('drg_group'),
            claim_amount=p.get('claim_amount')
        )
        for p in paginated
    ]
    
    return PatientListResponse(
        success=True,
        total=total,
        page=page,
        per_page=per_page,
        patients=patients
    )


@router.post("/", response_model=PatientResponse)
async def create_patient(
    patient: PatientCreate,
    user: UserInfo = Depends(require_auth)
):
    """환자 등록"""
    global PATIENT_ID_COUNTER
    PATIENT_ID_COUNTER += 1
    
    # 재원일수 계산
    length_of_stay = None
    if patient.admission_date and patient.discharge_date:
        length_of_stay = (patient.discharge_date - patient.admission_date).days
    
    # 개인정보 처리
    patient_data = patient.dict()
    encrypted_data = privacy_protector.encrypt_patient_data(patient_data)
    
    # 저장할 데이터
    db_patient = {
        'id': PATIENT_ID_COUNTER,
        **encrypted_data,
        'gender': patient.gender,
        'age': patient.age,
        'age_group': f"{(patient.age // 10) * 10}대" if patient.age else None,
        'department': patient.department,
        'admission_date': patient.admission_date,
        'discharge_date': patient.discharge_date,
        'length_of_stay': length_of_stay,
        'primary_diagnosis_code': patient.primary_diagnosis_code,
        'diagnosis_name': patient.diagnosis_name,
        'kdrg_code': patient.kdrg_code,
        'aadrg_code': patient.aadrg_code,
        'drg_group': get_drg_group(patient.aadrg_code),
        'claim_amount': patient.claim_amount
    }
    
    PATIENTS_DB.append(db_patient)
    
    return PatientResponse(
        id=db_patient['id'],
        masked_patient_id=db_patient.get('masked_patient_id', '****'),
        masked_name=db_patient.get('masked_name', '***'),
        gender=db_patient.get('gender'),
        age=db_patient.get('age'),
        age_group=db_patient.get('age_group'),
        department=db_patient.get('department'),
        admission_date=db_patient.get('admission_date'),
        discharge_date=db_patient.get('discharge_date'),
        length_of_stay=db_patient.get('length_of_stay'),
        primary_diagnosis_code=db_patient.get('primary_diagnosis_code'),
        diagnosis_name=db_patient.get('diagnosis_name'),
        kdrg_code=db_patient.get('kdrg_code'),
        aadrg_code=db_patient.get('aadrg_code'),
        drg_group=db_patient.get('drg_group'),
        claim_amount=db_patient.get('claim_amount')
    )


@router.get("/{patient_id}")
async def get_patient(
    patient_id: int,
    user: UserInfo = Depends(require_auth)
):
    """환자 상세 조회"""
    patient = next((p for p in PATIENTS_DB if p['id'] == patient_id), None)
    
    if not patient:
        raise HTTPException(status_code=404, detail="환자를 찾을 수 없습니다.")
    
    return {
        "success": True,
        "patient": PatientResponse(
            id=patient['id'],
            masked_patient_id=patient.get('masked_patient_id', '****'),
            masked_name=patient.get('masked_name', '***'),
            gender=patient.get('gender'),
            age=patient.get('age'),
            age_group=patient.get('age_group'),
            department=patient.get('department'),
            admission_date=patient.get('admission_date'),
            discharge_date=patient.get('discharge_date'),
            length_of_stay=patient.get('length_of_stay'),
            primary_diagnosis_code=patient.get('primary_diagnosis_code'),
            diagnosis_name=patient.get('diagnosis_name'),
            kdrg_code=patient.get('kdrg_code'),
            aadrg_code=patient.get('aadrg_code'),
            drg_group=patient.get('drg_group'),
            claim_amount=patient.get('claim_amount')
        )
    }


@router.post("/import", response_model=ImportResult)
async def import_patients(
    file: UploadFile = File(...),
    user: UserInfo = Depends(require_auth)
):
    """CSV/Excel 파일에서 환자 데이터 가져오기"""
    global PATIENT_ID_COUNTER
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일이 필요합니다.")
    
    # 파일 저장
    file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
    
    try:
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # 파일 읽기
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file_path, encoding='utf-8')
        elif file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path)
        else:
            raise HTTPException(status_code=400, detail="CSV 또는 Excel 파일만 지원합니다.")
        
        errors = []
        imported_count = 0
        
        for idx, row in df.iterrows():
            try:
                PATIENT_ID_COUNTER += 1
                
                # 컬럼 매핑 (유연하게)
                patient_id = str(row.get('patient_id', row.get('환자번호', row.get('등록번호', ''))))
                patient_name = str(row.get('patient_name', row.get('환자명', row.get('이름', ''))))
                
                if not patient_id or not patient_name:
                    errors.append(f"행 {idx + 1}: 환자번호 또는 환자명 누락")
                    continue
                
                # 개인정보 암호화
                patient_data = {
                    'patient_id': patient_id,
                    'patient_name': patient_name
                }
                encrypted_data = privacy_protector.encrypt_patient_data(patient_data)
                
                # 날짜 파싱
                admission_date = None
                discharge_date = None
                
                try:
                    ad = row.get('admission_date', row.get('입원일'))
                    if pd.notna(ad):
                        admission_date = pd.to_datetime(ad).date()
                except:
                    pass
                
                try:
                    dd = row.get('discharge_date', row.get('퇴원일'))
                    if pd.notna(dd):
                        discharge_date = pd.to_datetime(dd).date()
                except:
                    pass
                
                # 재원일수
                length_of_stay = None
                if admission_date and discharge_date:
                    length_of_stay = (discharge_date - admission_date).days
                
                # 나이
                age = None
                try:
                    age_val = row.get('age', row.get('나이'))
                    if pd.notna(age_val):
                        age = int(age_val)
                except:
                    pass
                
                aadrg_code = str(row.get('aadrg_code', row.get('AADRG', '')))
                
                db_patient = {
                    'id': PATIENT_ID_COUNTER,
                    **encrypted_data,
                    'gender': str(row.get('gender', row.get('성별', ''))) or None,
                    'age': age,
                    'age_group': f"{(age // 10) * 10}대" if age else None,
                    'department': str(row.get('department', row.get('진료과', ''))) or None,
                    'admission_date': admission_date,
                    'discharge_date': discharge_date,
                    'length_of_stay': length_of_stay,
                    'primary_diagnosis_code': str(row.get('primary_diagnosis_code', row.get('주진단코드', ''))) or None,
                    'diagnosis_name': str(row.get('diagnosis_name', row.get('진단명', ''))) or None,
                    'kdrg_code': str(row.get('kdrg_code', row.get('KDRG', ''))) or None,
                    'aadrg_code': aadrg_code or None,
                    'drg_group': get_drg_group(aadrg_code) if aadrg_code else None,
                    'claim_amount': float(row.get('claim_amount', row.get('청구금액', 0)) or 0)
                }
                
                PATIENTS_DB.append(db_patient)
                imported_count += 1
                
            except Exception as e:
                errors.append(f"행 {idx + 1}: {str(e)}")
        
        return ImportResult(
            success=True,
            message=f"{imported_count}명의 환자 데이터를 가져왔습니다.",
            total_imported=imported_count,
            errors=errors[:10]  # 최대 10개 오류만 반환
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 처리 오류: {str(e)}")
    finally:
        # 업로드된 파일 삭제
        if os.path.exists(file_path):
            os.remove(file_path)


@router.get("/stats/summary")
async def get_patient_stats(user: UserInfo = Depends(require_auth)):
    """환자 통계 요약"""
    if not PATIENTS_DB:
        return {
            "success": True,
            "stats": {
                "total_patients": 0,
                "by_department": {},
                "by_drg_group": {},
                "avg_length_of_stay": 0,
                "total_claim_amount": 0
            }
        }
    
    # 부서별 통계
    by_department = {}
    for p in PATIENTS_DB:
        dept = p.get('department', '미지정')
        by_department[dept] = by_department.get(dept, 0) + 1
    
    # DRG군별 통계
    by_drg_group = {}
    for p in PATIENTS_DB:
        drg = p.get('drg_group', '미분류')
        by_drg_group[drg] = by_drg_group.get(drg, 0) + 1
    
    # 평균 재원일수
    los_values = [p.get('length_of_stay', 0) for p in PATIENTS_DB if p.get('length_of_stay')]
    avg_los = sum(los_values) / len(los_values) if los_values else 0
    
    # 총 청구금액
    total_claim = sum(p.get('claim_amount', 0) for p in PATIENTS_DB)
    
    return {
        "success": True,
        "stats": {
            "total_patients": len(PATIENTS_DB),
            "by_department": by_department,
            "by_drg_group": by_drg_group,
            "avg_length_of_stay": round(avg_los, 1),
            "total_claim_amount": total_claim
        }
    }
