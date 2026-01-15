"""
KDRG Pre-Grouper 서비스
- 병원 내 KDRG 사전 분류 엔진
- 심평원 KDRG 그루퍼 로직 시뮬레이션
- 청구 전 KDRG 예측 및 검증

참고: 실제 심평원 KDRG 그루퍼는 비공개이므로,
      공개된 KDRG 분류 기준을 기반으로 구현
"""

import re
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Severity(Enum):
    """중증도 레벨"""
    NONE = 0  # 중증도 없음
    MINOR = 1  # 경도
    MODERATE = 2  # 중등도
    MAJOR = 3  # 고도
    EXTREME = 4  # 극고도


class PatientType(Enum):
    """환자 유형"""
    INPATIENT = "inpatient"  # 입원
    OUTPATIENT = "outpatient"  # 외래
    DAY_SURGERY = "day_surgery"  # 당일 수술


@dataclass
class PatientInfo:
    """환자 정보"""
    patient_id: str
    age: int
    sex: str  # M/F
    admission_date: str
    discharge_date: str
    los: int  # 재원일수
    birth_weight: Optional[int] = None  # 신생아 출생체중 (g)
    discharge_status: str = "alive"  # alive/dead/transfer


@dataclass
class DiagnosisInfo:
    """진단 정보"""
    main_diagnosis: str  # 주진단 (ICD-10)
    sub_diagnoses: List[str] = field(default_factory=list)  # 부진단
    admission_diagnosis: Optional[str] = None  # 입원 시 진단
    
    def all_diagnoses(self) -> List[str]:
        """모든 진단 코드 반환"""
        return [self.main_diagnosis] + self.sub_diagnoses


@dataclass
class ProcedureInfo:
    """수술/처치 정보"""
    procedures: List[str] = field(default_factory=list)  # 수술/처치 코드
    main_procedure: Optional[str] = None  # 주수술
    or_procedures: List[str] = field(default_factory=list)  # 수술실 수술


@dataclass
class GrouperInput:
    """Pre-Grouper 입력"""
    patient: PatientInfo
    diagnosis: DiagnosisInfo
    procedure: ProcedureInfo
    claim_id: Optional[str] = None


@dataclass
class GrouperResult:
    """Pre-Grouper 결과"""
    claim_id: str
    patient_id: str
    
    # 분류 결과
    mdc: str  # 주진단범주 (A-Z)
    mdc_name: str
    aadrg: str  # AADRG (4자리)
    kdrg: str  # KDRG (5자리)
    severity: int  # 중증도 (0-4)
    
    # 가중치 및 금액
    relative_weight: float  # 상대가치점수
    base_amount: float  # 기준수가
    estimated_amount: float  # 예상 청구액
    
    # 재원일수
    los: int
    los_lower: int  # 하한
    los_upper: int  # 상한
    los_outlier: str  # normal/short/long
    
    # 상세 정보
    drg_type: str  # 7개 DRG군 or 행위별
    grouper_path: List[str]  # 분류 경로
    warnings: List[str]  # 경고 메시지
    confidence: float  # 신뢰도 (0-100)


class KDRGPreGrouper:
    """KDRG Pre-Grouper 엔진"""
    
    # MDC (Major Diagnostic Category) 정의
    MDC_DEFINITIONS = {
        'A': ('신경계 질환', ['G', 'F0', 'R40', 'R41']),
        'B': ('눈 질환', ['H0', 'H1', 'H2', 'H3', 'H4', 'H5']),
        'C': ('귀, 코, 입, 인후 질환', ['H6', 'H7', 'H8', 'H9', 'J0', 'J1', 'J2', 'J3']),
        'D': ('호흡기계 질환', ['J4', 'J5', 'J6', 'J7', 'J8', 'J9']),
        'E': ('순환기계 질환', ['I']),
        'F': ('소화기계 질환', ['K']),
        'G': ('간담도계 및 췌장 질환', ['K7', 'K8']),
        'H': ('근골격계 및 결합조직 질환', ['M']),
        'I': ('피부, 피하조직 및 유방 질환', ['L', 'C50']),
        'J': ('내분비, 영양 및 대사 질환', ['E']),
        'K': ('신장 및 요로계 질환', ['N0', 'N1', 'N2', 'N3', 'N4']),
        'L': ('남성생식기계 질환', ['N40', 'N41', 'N42', 'N43', 'N44', 'N45', 'N46', 'N47', 'N48', 'N49', 'N50', 'N51']),
        'M': ('여성생식기계 질환', ['N6', 'N7', 'N8', 'N9']),
        'N': ('임신, 출산 및 산욕', ['O']),
        'O': ('주산기 질환', ['P']),
        'P': ('혈액 및 조혈기관 질환', ['D5', 'D6', 'D7', 'D8']),
        'Q': ('골수증식 질환', ['C81', 'C82', 'C83', 'C84', 'C85', 'C86', 'C88', 'C90', 'C91', 'C92', 'C93', 'C94', 'C95', 'C96']),
        'R': ('감염 및 기생충 질환', ['A', 'B']),
        'S': ('정신 질환', ['F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9']),
        'T': ('알코올/약물 사용', ['F10', 'F11', 'F12', 'F13', 'F14', 'F15', 'F16', 'F17', 'F18', 'F19']),
        'U': ('손상, 중독 및 약물 독성효과', ['S', 'T']),
        'V': ('화상', ['T20', 'T21', 'T22', 'T23', 'T24', 'T25', 'T26', 'T27', 'T28', 'T29', 'T30', 'T31']),
        'W': ('기타', []),
        'X': ('기타 악성신생물', ['C']),
        'Y': ('HIV 감염', ['B20', 'B21', 'B22', 'B23', 'B24']),
        'Z': ('다발성 외상', ['T07']),
    }
    
    # 7개 DRG군 수술 코드 매핑
    DRG7_SURGERY_CODES = {
        'D12': {
            'name': '편도 및 아데노이드 절제술',
            'procedures': ['Q2161', 'Q2162', 'Q2163', 'Q2164', 'Q2171', 'Q2172'],
            'diagnoses': ['J35', 'J36', 'J03'],
            'base_weight': 0.8,
            'los_range': (1, 3),
        },
        'D13': {
            'name': '축농증 수술',
            'procedures': ['Q2131', 'Q2132', 'Q2133', 'Q2134', 'Q2141', 'Q2142'],
            'diagnoses': ['J32', 'J33', 'J34'],
            'base_weight': 1.0,
            'los_range': (2, 5),
        },
        'G08': {
            'name': '서혜부 및 대퇴부 탈장수술',
            'procedures': ['Q2891', 'Q2892', 'Q2893', 'Q2894', 'Q2901', 'Q2902'],
            'diagnoses': ['K40', 'K41'],
            'base_weight': 0.9,
            'los_range': (1, 4),
        },
        'H06': {
            'name': '담낭절제술',
            'procedures': ['Q7651', 'Q7652', 'Q7653', 'Q7654', 'Q7661', 'Q7662'],
            'diagnoses': ['K80', 'K81', 'K82'],
            'base_weight': 1.2,
            'los_range': (3, 7),
        },
        'I09': {
            'name': '항문수술',
            'procedures': ['Q2971', 'Q2972', 'Q2973', 'Q2981', 'Q2982'],
            'diagnoses': ['K60', 'K61', 'K62', 'K64'],
            'base_weight': 0.6,
            'los_range': (1, 3),
        },
        'L08': {
            'name': '요로결석 체외충격파쇄석술',
            'procedures': ['R3911', 'R3912', 'R3913', 'R3914', 'R3915'],
            'diagnoses': ['N20', 'N21', 'N22', 'N23'],
            'base_weight': 0.7,
            'los_range': (1, 2),
        },
        'O01': {
            'name': '제왕절개술',
            'procedures': ['R4507', 'R4508', 'R4509', 'R4510', 'R4511'],
            'diagnoses': ['O82', 'O84'],
            'base_weight': 1.5,
            'los_range': (4, 7),
        },
        'O60': {
            'name': '질식분만',
            'procedures': [],  # 수술 없음
            'diagnoses': ['O80', 'O81', 'O83'],
            'base_weight': 1.0,
            'los_range': (2, 4),
        },
    }
    
    # 중증도 판정 CC (Complication/Comorbidity) 코드
    CC_CODES = {
        'MCC': [  # Major CC
            'J96', 'I50', 'N17', 'K72', 'E10.1', 'E11.1', 'A41', 'R57',
            'I21', 'I22', 'J80', 'K70.4', 'K71.1', 'G93.1', 'G93.4',
        ],
        'CC': [  # CC
            'E11', 'I10', 'I25', 'J44', 'J45', 'N18', 'E78', 'K21',
            'M81', 'F32', 'G40', 'K25', 'K26', 'K27', 'K29', 'D50',
        ],
    }
    
    # 기준 수가 (2024년 기준, 원)
    BASE_RATE_2024 = 87000  # 1점당 수가
    
    def __init__(self):
        self.grouper_version = "PreGrouper-1.0"
    
    def determine_mdc(self, main_diagnosis: str) -> Tuple[str, str]:
        """주진단으로 MDC 결정"""
        dx = main_diagnosis.upper().replace('.', '')
        
        for mdc_code, (mdc_name, prefixes) in self.MDC_DEFINITIONS.items():
            for prefix in prefixes:
                if dx.startswith(prefix.replace('.', '')):
                    return (mdc_code, mdc_name)
        
        return ('W', '기타')
    
    def check_drg7(self, diagnosis: DiagnosisInfo, procedure: ProcedureInfo) -> Optional[str]:
        """7개 DRG군 해당 여부 확인"""
        main_dx = diagnosis.main_diagnosis.upper()
        
        for drg_code, drg_info in self.DRG7_SURGERY_CODES.items():
            # 진단 확인
            dx_match = any(
                main_dx.startswith(dx.replace('.', '')) 
                for dx in drg_info['diagnoses']
            )
            
            # 수술 확인 (O60 질식분만은 수술 없음)
            if drg_info['procedures']:
                proc_match = any(
                    proc.upper() in [p.upper() for p in procedure.procedures]
                    for proc in drg_info['procedures']
                )
            else:
                # 질식분만: 진단만으로 판단
                proc_match = dx_match
            
            if dx_match and proc_match:
                return drg_code
        
        return None
    
    def calculate_severity(self, diagnosis: DiagnosisInfo, patient: PatientInfo) -> int:
        """중증도 계산"""
        severity = 0
        
        all_dx = diagnosis.all_diagnoses()
        
        # MCC 체크
        for dx in all_dx:
            dx_clean = dx.upper().replace('.', '')
            for mcc in self.CC_CODES['MCC']:
                if dx_clean.startswith(mcc.replace('.', '')):
                    severity = max(severity, 3)
                    break
        
        # CC 체크
        if severity < 3:
            for dx in all_dx:
                dx_clean = dx.upper().replace('.', '')
                for cc in self.CC_CODES['CC']:
                    if dx_clean.startswith(cc.replace('.', '')):
                        severity = max(severity, 2)
                        break
        
        # 나이 보정
        if patient.age >= 70:
            severity = min(severity + 1, 4)
        elif patient.age < 1:
            severity = min(severity + 1, 4)
        
        # 재원일수 보정
        if patient.los > 14:
            severity = min(severity + 1, 4)
        
        return severity
    
    def calculate_relative_weight(self, aadrg: str, severity: int, 
                                   patient: PatientInfo) -> float:
        """상대가치점수 계산"""
        # 7개 DRG군 기준 가중치
        drg_code = aadrg[:3] if len(aadrg) >= 3 else aadrg
        
        if drg_code in self.DRG7_SURGERY_CODES:
            base_weight = self.DRG7_SURGERY_CODES[drg_code]['base_weight']
        else:
            base_weight = 1.0
        
        # 중증도 보정
        severity_multiplier = {
            0: 0.9,
            1: 1.0,
            2: 1.1,
            3: 1.25,
            4: 1.5,
        }
        weight = base_weight * severity_multiplier.get(severity, 1.0)
        
        # 재원일수 보정
        if patient.los > 7:
            weight *= 1.1
        elif patient.los < 2:
            weight *= 0.95
        
        return round(weight, 4)
    
    def determine_los_outlier(self, los: int, aadrg: str) -> Tuple[int, int, str]:
        """재원일수 이상치 판정"""
        drg_code = aadrg[:3] if len(aadrg) >= 3 else aadrg
        
        if drg_code in self.DRG7_SURGERY_CODES:
            los_lower, los_upper = self.DRG7_SURGERY_CODES[drg_code]['los_range']
        else:
            los_lower, los_upper = 3, 10
        
        if los < los_lower:
            outlier = 'short'
        elif los > los_upper:
            outlier = 'long'
        else:
            outlier = 'normal'
        
        return (los_lower, los_upper, outlier)
    
    def generate_aadrg(self, mdc: str, drg7_code: Optional[str], 
                        procedure: ProcedureInfo) -> str:
        """AADRG 생성"""
        if drg7_code:
            return drg7_code + '1'
        
        # 수술 여부에 따라 분류
        if procedure.procedures:
            return f"{mdc}01A"  # 수술 있음
        else:
            return f"{mdc}60A"  # 수술 없음 (내과)
    
    def generate_kdrg(self, aadrg: str, severity: int) -> str:
        """KDRG 생성 (5자리)"""
        return aadrg[:4] + str(min(severity, 4))
    
    def validate_input(self, input_data: GrouperInput) -> List[str]:
        """입력 데이터 검증"""
        warnings = []
        
        # 주진단 필수
        if not input_data.diagnosis.main_diagnosis:
            warnings.append("주진단 코드가 없습니다.")
        
        # 날짜 검증
        try:
            adm = datetime.strptime(input_data.patient.admission_date, '%Y-%m-%d')
            dis = datetime.strptime(input_data.patient.discharge_date, '%Y-%m-%d')
            if dis < adm:
                warnings.append("퇴원일이 입원일보다 이전입니다.")
        except:
            warnings.append("날짜 형식 오류 (YYYY-MM-DD)")
        
        # 나이 검증
        if input_data.patient.age < 0 or input_data.patient.age > 120:
            warnings.append(f"나이 이상치: {input_data.patient.age}")
        
        # 재원일수 검증
        if input_data.patient.los < 0:
            warnings.append("재원일수가 음수입니다.")
        elif input_data.patient.los > 365:
            warnings.append(f"장기 재원: {input_data.patient.los}일")
        
        return warnings
    
    def group(self, input_data: GrouperInput) -> GrouperResult:
        """KDRG 그루핑 실행"""
        warnings = self.validate_input(input_data)
        grouper_path = []
        
        patient = input_data.patient
        diagnosis = input_data.diagnosis
        procedure = input_data.procedure
        
        # 1. MDC 결정
        mdc, mdc_name = self.determine_mdc(diagnosis.main_diagnosis)
        grouper_path.append(f"MDC: {mdc} ({mdc_name})")
        
        # 2. 7개 DRG군 확인
        drg7_code = self.check_drg7(diagnosis, procedure)
        if drg7_code:
            drg_type = self.DRG7_SURGERY_CODES[drg7_code]['name']
            grouper_path.append(f"7개 DRG군: {drg7_code} ({drg_type})")
        else:
            drg_type = '행위별'
            grouper_path.append("7개 DRG군 해당 없음 (행위별)")
        
        # 3. 중증도 계산
        severity = self.calculate_severity(diagnosis, patient)
        grouper_path.append(f"중증도: {severity}")
        
        # 4. AADRG 생성
        aadrg = self.generate_aadrg(mdc, drg7_code, procedure)
        grouper_path.append(f"AADRG: {aadrg}")
        
        # 5. KDRG 생성
        kdrg = self.generate_kdrg(aadrg, severity)
        grouper_path.append(f"KDRG: {kdrg}")
        
        # 6. 상대가치점수
        relative_weight = self.calculate_relative_weight(aadrg, severity, patient)
        
        # 7. 재원일수 이상치
        los_lower, los_upper, los_outlier = self.determine_los_outlier(patient.los, aadrg)
        if los_outlier != 'normal':
            warnings.append(f"재원일수 이상치: {los_outlier} ({patient.los}일, 기준: {los_lower}-{los_upper}일)")
        
        # 8. 예상 금액
        base_amount = relative_weight * self.BASE_RATE_2024
        
        # 재원일수 보정
        if los_outlier == 'short':
            estimated_amount = base_amount * 0.9
        elif los_outlier == 'long':
            # 장기 재원 일당 추가
            extra_days = patient.los - los_upper
            estimated_amount = base_amount + (extra_days * self.BASE_RATE_2024 * 0.3)
        else:
            estimated_amount = base_amount
        
        # 9. 신뢰도 계산
        confidence = 100.0
        if not drg7_code:
            confidence -= 20  # 7개 DRG군 아님
        if len(warnings) > 0:
            confidence -= len(warnings) * 5
        if not procedure.procedures:
            confidence -= 10  # 수술 정보 없음
        confidence = max(30, confidence)
        
        return GrouperResult(
            claim_id=input_data.claim_id or '',
            patient_id=patient.patient_id,
            mdc=mdc,
            mdc_name=mdc_name,
            aadrg=aadrg,
            kdrg=kdrg,
            severity=severity,
            relative_weight=relative_weight,
            base_amount=base_amount,
            estimated_amount=round(estimated_amount, 0),
            los=patient.los,
            los_lower=los_lower,
            los_upper=los_upper,
            los_outlier=los_outlier,
            drg_type=drg_type,
            grouper_path=grouper_path,
            warnings=warnings,
            confidence=confidence,
        )
    
    def group_batch(self, inputs: List[GrouperInput]) -> List[GrouperResult]:
        """배치 그루핑"""
        return [self.group(inp) for inp in inputs]
    
    def group_from_dict(self, data: Dict[str, Any]) -> GrouperResult:
        """딕셔너리에서 그루핑"""
        patient = PatientInfo(
            patient_id=str(data.get('patient_id', '')),
            age=int(data.get('age', 0)),
            sex=str(data.get('sex', 'M')),
            admission_date=str(data.get('admission_date', '')),
            discharge_date=str(data.get('discharge_date', '')),
            los=int(data.get('los', 0)),
        )
        
        diagnosis = DiagnosisInfo(
            main_diagnosis=str(data.get('main_diagnosis', '')),
            sub_diagnoses=data.get('sub_diagnoses', []) if isinstance(data.get('sub_diagnoses'), list) else [],
        )
        
        procedures = data.get('procedures', [])
        if isinstance(procedures, str):
            procedures = [p.strip() for p in procedures.split(',') if p.strip()]
        
        procedure = ProcedureInfo(
            procedures=procedures,
            main_procedure=procedures[0] if procedures else None,
        )
        
        input_data = GrouperInput(
            patient=patient,
            diagnosis=diagnosis,
            procedure=procedure,
            claim_id=str(data.get('claim_id', '')),
        )
        
        return self.group(input_data)
    
    def estimate_optimization(self, result: GrouperResult, 
                               original_kdrg: str = None) -> Dict[str, Any]:
        """KDRG 최적화 추정"""
        suggestions = []
        
        # 중증도 향상 가능성
        if result.severity < 2:
            suggestions.append({
                'type': 'severity',
                'current': result.severity,
                'potential': result.severity + 1,
                'action': '합병증/동반질환 코딩 검토',
                'impact': result.estimated_amount * 0.1,
            })
        
        # 재원일수 최적화
        if result.los_outlier == 'short':
            suggestions.append({
                'type': 'los',
                'current': result.los,
                'optimal': result.los_lower,
                'action': '재원일수 하한 미달 - 조기 퇴원 검토',
                'impact': result.estimated_amount * -0.1,
            })
        elif result.los_outlier == 'long':
            suggestions.append({
                'type': 'los',
                'current': result.los,
                'optimal': result.los_upper,
                'action': '재원일수 상한 초과 - 효율적 퇴원 계획 필요',
                'impact': 0,
            })
        
        # 7개 DRG군 전환 가능성
        if result.drg_type == '행위별':
            suggestions.append({
                'type': 'drg7',
                'current': result.drg_type,
                'action': '7개 포괄 DRG군 전환 가능성 검토',
                'impact': 0,
            })
        
        return {
            'kdrg': result.kdrg,
            'estimated_amount': result.estimated_amount,
            'suggestions': suggestions,
            'optimization_potential': sum(s.get('impact', 0) for s in suggestions),
        }


# 서비스 인스턴스
pre_grouper = KDRGPreGrouper()
