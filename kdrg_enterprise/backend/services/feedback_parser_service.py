"""
심평원 환류 데이터 파서 서비스
- 요양기관업무포털(biz.hira.or.kr)에서 다운로드한 환류 데이터 파싱
- 지원 형식: Excel (.xlsx, .xls), CSV
- DRG 청구내역, 심사결과, 조정내역 등 파싱
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class FeedbackDataType(Enum):
    """환류 데이터 유형"""
    DRG_CLAIM = "drg_claim"  # DRG 청구내역
    REVIEW_RESULT = "review_result"  # 심사결과
    ADJUSTMENT = "adjustment"  # 조정내역
    KDRG_GROUPER = "kdrg_grouper"  # KDRG 그루퍼 결과
    PAYMENT = "payment"  # 지급결과
    RETURN_DETAIL = "return_detail"  # 반송/보완 상세
    UNKNOWN = "unknown"


@dataclass
class ClaimRecord:
    """DRG 청구 레코드"""
    claim_id: str  # 청구번호
    patient_id: str  # 환자번호
    patient_name: str  # 환자명 (마스킹 처리)
    admission_date: str  # 입원일
    discharge_date: str  # 퇴원일
    los: int  # 재원일수
    main_diagnosis: str  # 주진단
    sub_diagnoses: List[str]  # 부진단
    procedures: List[str]  # 수술/처치
    claimed_kdrg: str  # 청구 KDRG
    claimed_aadrg: str  # 청구 AADRG
    claimed_amount: float  # 청구금액
    mdc: str  # MDC
    drg_type: str  # DRG 유형 (7개 DRG군)
    age: int  # 나이
    sex: str  # 성별
    severity: str  # 중증도


@dataclass
class ReviewResult:
    """심사 결과 레코드"""
    claim_id: str  # 청구번호
    review_date: str  # 심사일
    original_kdrg: str  # 원청구 KDRG
    reviewed_kdrg: str  # 심사 후 KDRG
    original_amount: float  # 원청구금액
    reviewed_amount: float  # 심사금액
    adjustment_amount: float  # 조정금액
    adjustment_reason: str  # 조정사유
    review_opinion: str  # 심사의견
    is_adjusted: bool  # 조정여부
    adjustment_type: str  # 조정유형 (삭감/증액/변경없음)


@dataclass
class KDRGGrouperResult:
    """KDRG 그루퍼 결과"""
    claim_id: str
    patient_id: str
    mdc: str  # 주진단범주
    aadrg: str  # AADRG (4자리)
    kdrg: str  # KDRG (5자리)
    severity_level: str  # 중증도 (0-4)
    weight: float  # 상대가치점수
    los_lower: int  # 재원일수 하한
    los_upper: int  # 재원일수 상한
    base_rate: float  # 기준수가
    calculated_amount: float  # 산정금액
    grouper_version: str  # 그루퍼 버전


@dataclass
class FeedbackSummary:
    """환류 데이터 요약"""
    file_name: str
    data_type: str
    total_records: int
    date_range: Dict[str, str]
    total_claimed_amount: float
    total_reviewed_amount: float
    total_adjustment: float
    adjustment_rate: float  # 조정률
    kdrg_change_count: int  # KDRG 변경 건수
    drg_distribution: Dict[str, int]  # DRG 유형별 분포
    top_adjustments: List[Dict]  # 주요 조정 사유


class FeedbackParserService:
    """심평원 환류 데이터 파서 서비스"""
    
    # 7개 DRG군 코드
    DRG7_CODES = {
        'D12': '편도 및 아데노이드 절제술',
        'D13': '축농증 수술',
        'G08': '서혜부 및 대퇴부 탈장수술',
        'H06': '담낭절제술',
        'I09': '항문수술',
        'L08': '요로결석 체외충격파쇄석술',
        'O01': '제왕절개술',
        'O60': '질식분만',
    }
    
    # 컬럼 매핑 (심평원 엑셀 → 내부 필드)
    COLUMN_MAPPINGS = {
        'claim': {
            '청구번호': 'claim_id',
            '청구관리번호': 'claim_id',
            '환자번호': 'patient_id',
            '등록번호': 'patient_id',
            '환자명': 'patient_name',
            '성명': 'patient_name',
            '입원일': 'admission_date',
            '입원일자': 'admission_date',
            '퇴원일': 'discharge_date',
            '퇴원일자': 'discharge_date',
            '재원일수': 'los',
            '입원일수': 'los',
            '주진단': 'main_diagnosis',
            '주상병': 'main_diagnosis',
            '주진단코드': 'main_diagnosis',
            '부진단': 'sub_diagnoses',
            '부상병': 'sub_diagnoses',
            '수술': 'procedures',
            '처치': 'procedures',
            '수술코드': 'procedures',
            'KDRG': 'claimed_kdrg',
            'KDRG코드': 'claimed_kdrg',
            '청구KDRG': 'claimed_kdrg',
            'AADRG': 'claimed_aadrg',
            'AADRG코드': 'claimed_aadrg',
            '청구금액': 'claimed_amount',
            '총청구액': 'claimed_amount',
            'MDC': 'mdc',
            '주진단범주': 'mdc',
            'DRG유형': 'drg_type',
            'DRG군': 'drg_type',
            '나이': 'age',
            '연령': 'age',
            '성별': 'sex',
            '중증도': 'severity',
        },
        'review': {
            '청구번호': 'claim_id',
            '청구관리번호': 'claim_id',
            '심사일': 'review_date',
            '심사일자': 'review_date',
            '원청구KDRG': 'original_kdrg',
            '청구KDRG': 'original_kdrg',
            '심사KDRG': 'reviewed_kdrg',
            '결정KDRG': 'reviewed_kdrg',
            '원청구금액': 'original_amount',
            '청구금액': 'original_amount',
            '심사금액': 'reviewed_amount',
            '결정금액': 'reviewed_amount',
            '조정금액': 'adjustment_amount',
            '삭감금액': 'adjustment_amount',
            '조정사유': 'adjustment_reason',
            '삭감사유': 'adjustment_reason',
            '심사의견': 'review_opinion',
            '의견': 'review_opinion',
        },
        'grouper': {
            '청구번호': 'claim_id',
            '환자번호': 'patient_id',
            'MDC': 'mdc',
            '주진단범주': 'mdc',
            'AADRG': 'aadrg',
            'KDRG': 'kdrg',
            '중증도': 'severity_level',
            '상대가치점수': 'weight',
            '가중치': 'weight',
            '재원일수하한': 'los_lower',
            '재원일수상한': 'los_upper',
            '기준수가': 'base_rate',
            '산정금액': 'calculated_amount',
            '그루퍼버전': 'grouper_version',
        }
    }

    def __init__(self):
        self.parsed_data: Dict[str, List] = {}
        self.summary: Optional[FeedbackSummary] = None

    def detect_file_type(self, file_path: str) -> str:
        """파일 확장자 감지"""
        ext = file_path.lower().split('.')[-1]
        if ext in ['xlsx', 'xls']:
            return 'excel'
        elif ext == 'csv':
            return 'csv'
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {ext}")

    def detect_data_type(self, df: pd.DataFrame) -> FeedbackDataType:
        """데이터 유형 자동 감지"""
        columns = set(df.columns.str.strip())
        
        # 심사결과 (조정금액, 심사KDRG 등이 있으면)
        review_keywords = {'심사금액', '결정금액', '조정금액', '삭감금액', '심사KDRG', '결정KDRG'}
        if review_keywords & columns:
            return FeedbackDataType.REVIEW_RESULT
        
        # KDRG 그루퍼 결과
        grouper_keywords = {'상대가치점수', '가중치', '재원일수하한', '재원일수상한', '그루퍼버전'}
        if grouper_keywords & columns:
            return FeedbackDataType.KDRG_GROUPER
        
        # 지급결과
        payment_keywords = {'지급금액', '지급일', '지급결정액'}
        if payment_keywords & columns:
            return FeedbackDataType.PAYMENT
        
        # 반송/보완
        return_keywords = {'반송사유', '보완요청', '반송일'}
        if return_keywords & columns:
            return FeedbackDataType.RETURN_DETAIL
        
        # DRG 청구내역 (기본)
        claim_keywords = {'청구금액', 'KDRG', '주진단', '입원일', '퇴원일'}
        if claim_keywords & columns:
            return FeedbackDataType.DRG_CLAIM
        
        return FeedbackDataType.UNKNOWN

    def read_file(self, file_path: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
        """파일 읽기"""
        file_type = self.detect_file_type(file_path)
        
        try:
            if file_type == 'excel':
                if sheet_name:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                else:
                    # 첫 번째 시트 읽기
                    df = pd.read_excel(file_path)
            else:
                # CSV - 인코딩 자동 감지
                for encoding in ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise ValueError("파일 인코딩을 감지할 수 없습니다.")
            
            # 컬럼명 정리
            df.columns = df.columns.str.strip()
            
            return df
            
        except Exception as e:
            logger.error(f"파일 읽기 오류: {e}")
            raise

    def read_file_from_bytes(self, file_content: bytes, file_name: str, 
                              sheet_name: Optional[str] = None) -> pd.DataFrame:
        """바이트 데이터에서 파일 읽기 (업로드용)"""
        import io
        
        ext = file_name.lower().split('.')[-1]
        
        try:
            if ext in ['xlsx', 'xls']:
                if sheet_name:
                    df = pd.read_excel(io.BytesIO(file_content), sheet_name=sheet_name)
                else:
                    df = pd.read_excel(io.BytesIO(file_content))
            else:
                # CSV
                for encoding in ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']:
                    try:
                        df = pd.read_csv(io.BytesIO(file_content), encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise ValueError("파일 인코딩을 감지할 수 없습니다.")
            
            df.columns = df.columns.str.strip()
            return df
            
        except Exception as e:
            logger.error(f"파일 읽기 오류: {e}")
            raise

    def normalize_columns(self, df: pd.DataFrame, data_type: FeedbackDataType) -> pd.DataFrame:
        """컬럼명 정규화"""
        if data_type == FeedbackDataType.DRG_CLAIM:
            mapping = self.COLUMN_MAPPINGS['claim']
        elif data_type == FeedbackDataType.REVIEW_RESULT:
            mapping = self.COLUMN_MAPPINGS['review']
        elif data_type == FeedbackDataType.KDRG_GROUPER:
            mapping = self.COLUMN_MAPPINGS['grouper']
        else:
            return df
        
        # 컬럼 매핑 적용
        rename_map = {}
        for col in df.columns:
            if col in mapping:
                rename_map[col] = mapping[col]
        
        return df.rename(columns=rename_map)

    def parse_date(self, date_val: Any) -> str:
        """날짜 파싱"""
        if pd.isna(date_val):
            return ""
        
        if isinstance(date_val, datetime):
            return date_val.strftime('%Y-%m-%d')
        
        date_str = str(date_val).strip()
        
        # 다양한 날짜 형식 처리
        patterns = [
            (r'(\d{4})-(\d{2})-(\d{2})', '%Y-%m-%d'),
            (r'(\d{4})\.(\d{2})\.(\d{2})', '%Y.%m.%d'),
            (r'(\d{4})/(\d{2})/(\d{2})', '%Y/%m/%d'),
            (r'(\d{8})', '%Y%m%d'),
        ]
        
        for pattern, fmt in patterns:
            if re.match(pattern, date_str):
                try:
                    if fmt == '%Y%m%d':
                        return datetime.strptime(date_str[:8], fmt).strftime('%Y-%m-%d')
                    return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
                except:
                    pass
        
        return date_str

    def parse_amount(self, amount_val: Any) -> float:
        """금액 파싱"""
        if pd.isna(amount_val):
            return 0.0
        
        if isinstance(amount_val, (int, float)):
            return float(amount_val)
        
        # 문자열에서 숫자만 추출
        amount_str = str(amount_val).replace(',', '').replace('원', '').strip()
        try:
            return float(amount_str)
        except:
            return 0.0

    def parse_list_field(self, value: Any) -> List[str]:
        """리스트 필드 파싱 (부진단, 수술 등)"""
        if pd.isna(value):
            return []
        
        value_str = str(value).strip()
        
        # 구분자로 분리
        for sep in [',', ';', '/', '|']:
            if sep in value_str:
                return [v.strip() for v in value_str.split(sep) if v.strip()]
        
        return [value_str] if value_str else []

    def parse_claim_records(self, df: pd.DataFrame) -> List[ClaimRecord]:
        """청구 레코드 파싱"""
        df = self.normalize_columns(df, FeedbackDataType.DRG_CLAIM)
        records = []
        
        for _, row in df.iterrows():
            try:
                record = ClaimRecord(
                    claim_id=str(row.get('claim_id', '')).strip(),
                    patient_id=str(row.get('patient_id', '')).strip(),
                    patient_name=str(row.get('patient_name', '')).strip(),
                    admission_date=self.parse_date(row.get('admission_date')),
                    discharge_date=self.parse_date(row.get('discharge_date')),
                    los=int(row.get('los', 0)) if pd.notna(row.get('los')) else 0,
                    main_diagnosis=str(row.get('main_diagnosis', '')).strip(),
                    sub_diagnoses=self.parse_list_field(row.get('sub_diagnoses')),
                    procedures=self.parse_list_field(row.get('procedures')),
                    claimed_kdrg=str(row.get('claimed_kdrg', '')).strip(),
                    claimed_aadrg=str(row.get('claimed_aadrg', '')).strip(),
                    claimed_amount=self.parse_amount(row.get('claimed_amount')),
                    mdc=str(row.get('mdc', '')).strip(),
                    drg_type=str(row.get('drg_type', '')).strip(),
                    age=int(row.get('age', 0)) if pd.notna(row.get('age')) else 0,
                    sex=str(row.get('sex', '')).strip(),
                    severity=str(row.get('severity', '')).strip(),
                )
                records.append(record)
            except Exception as e:
                logger.warning(f"청구 레코드 파싱 오류: {e}")
                continue
        
        return records

    def parse_review_results(self, df: pd.DataFrame) -> List[ReviewResult]:
        """심사 결과 파싱"""
        df = self.normalize_columns(df, FeedbackDataType.REVIEW_RESULT)
        records = []
        
        for _, row in df.iterrows():
            try:
                original_amount = self.parse_amount(row.get('original_amount'))
                reviewed_amount = self.parse_amount(row.get('reviewed_amount'))
                adjustment_amount = self.parse_amount(row.get('adjustment_amount'))
                
                # 조정금액이 없으면 계산
                if adjustment_amount == 0 and original_amount > 0:
                    adjustment_amount = original_amount - reviewed_amount
                
                # 조정유형 판단
                if adjustment_amount > 0:
                    adjustment_type = '삭감'
                elif adjustment_amount < 0:
                    adjustment_type = '증액'
                else:
                    adjustment_type = '변경없음'
                
                original_kdrg = str(row.get('original_kdrg', '')).strip()
                reviewed_kdrg = str(row.get('reviewed_kdrg', '')).strip()
                
                record = ReviewResult(
                    claim_id=str(row.get('claim_id', '')).strip(),
                    review_date=self.parse_date(row.get('review_date')),
                    original_kdrg=original_kdrg,
                    reviewed_kdrg=reviewed_kdrg,
                    original_amount=original_amount,
                    reviewed_amount=reviewed_amount,
                    adjustment_amount=adjustment_amount,
                    adjustment_reason=str(row.get('adjustment_reason', '')).strip(),
                    review_opinion=str(row.get('review_opinion', '')).strip(),
                    is_adjusted=adjustment_amount != 0 or original_kdrg != reviewed_kdrg,
                    adjustment_type=adjustment_type,
                )
                records.append(record)
            except Exception as e:
                logger.warning(f"심사결과 레코드 파싱 오류: {e}")
                continue
        
        return records

    def parse_grouper_results(self, df: pd.DataFrame) -> List[KDRGGrouperResult]:
        """KDRG 그루퍼 결과 파싱"""
        df = self.normalize_columns(df, FeedbackDataType.KDRG_GROUPER)
        records = []
        
        for _, row in df.iterrows():
            try:
                record = KDRGGrouperResult(
                    claim_id=str(row.get('claim_id', '')).strip(),
                    patient_id=str(row.get('patient_id', '')).strip(),
                    mdc=str(row.get('mdc', '')).strip(),
                    aadrg=str(row.get('aadrg', '')).strip(),
                    kdrg=str(row.get('kdrg', '')).strip(),
                    severity_level=str(row.get('severity_level', '')).strip(),
                    weight=float(row.get('weight', 0)) if pd.notna(row.get('weight')) else 0.0,
                    los_lower=int(row.get('los_lower', 0)) if pd.notna(row.get('los_lower')) else 0,
                    los_upper=int(row.get('los_upper', 0)) if pd.notna(row.get('los_upper')) else 0,
                    base_rate=self.parse_amount(row.get('base_rate')),
                    calculated_amount=self.parse_amount(row.get('calculated_amount')),
                    grouper_version=str(row.get('grouper_version', '')).strip(),
                )
                records.append(record)
            except Exception as e:
                logger.warning(f"그루퍼 결과 파싱 오류: {e}")
                continue
        
        return records

    def parse_file(self, file_path: str, sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """파일 파싱 메인 함수"""
        df = self.read_file(file_path, sheet_name)
        data_type = self.detect_data_type(df)
        
        result = {
            'file_path': file_path,
            'data_type': data_type.value,
            'total_records': len(df),
            'columns': list(df.columns),
            'records': [],
            'raw_data': df.to_dict('records'),
        }
        
        if data_type == FeedbackDataType.DRG_CLAIM:
            records = self.parse_claim_records(df)
            result['records'] = [asdict(r) for r in records]
        elif data_type == FeedbackDataType.REVIEW_RESULT:
            records = self.parse_review_results(df)
            result['records'] = [asdict(r) for r in records]
        elif data_type == FeedbackDataType.KDRG_GROUPER:
            records = self.parse_grouper_results(df)
            result['records'] = [asdict(r) for r in records]
        
        # 요약 생성
        result['summary'] = self.generate_summary(df, data_type, file_path)
        
        return result

    def parse_bytes(self, file_content: bytes, file_name: str, 
                    sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """바이트 데이터 파싱 (업로드용)"""
        df = self.read_file_from_bytes(file_content, file_name, sheet_name)
        data_type = self.detect_data_type(df)
        
        result = {
            'file_name': file_name,
            'data_type': data_type.value,
            'total_records': len(df),
            'columns': list(df.columns),
            'records': [],
            'raw_data': df.to_dict('records'),
        }
        
        if data_type == FeedbackDataType.DRG_CLAIM:
            records = self.parse_claim_records(df)
            result['records'] = [asdict(r) for r in records]
        elif data_type == FeedbackDataType.REVIEW_RESULT:
            records = self.parse_review_results(df)
            result['records'] = [asdict(r) for r in records]
        elif data_type == FeedbackDataType.KDRG_GROUPER:
            records = self.parse_grouper_results(df)
            result['records'] = [asdict(r) for r in records]
        
        result['summary'] = self.generate_summary(df, data_type, file_name)
        
        return result

    def generate_summary(self, df: pd.DataFrame, data_type: FeedbackDataType, 
                         file_name: str) -> Dict[str, Any]:
        """환류 데이터 요약 생성"""
        df = self.normalize_columns(df.copy(), data_type)
        
        summary = {
            'file_name': file_name,
            'data_type': data_type.value,
            'total_records': len(df),
            'date_range': {},
            'total_claimed_amount': 0,
            'total_reviewed_amount': 0,
            'total_adjustment': 0,
            'adjustment_rate': 0,
            'kdrg_change_count': 0,
            'drg_distribution': {},
            'top_adjustments': [],
        }
        
        # 날짜 범위
        date_cols = ['admission_date', 'discharge_date', 'review_date']
        for col in date_cols:
            if col in df.columns:
                dates = pd.to_datetime(df[col], errors='coerce').dropna()
                if len(dates) > 0:
                    summary['date_range'] = {
                        'start': dates.min().strftime('%Y-%m-%d'),
                        'end': dates.max().strftime('%Y-%m-%d'),
                    }
                    break
        
        # 금액 통계
        if data_type == FeedbackDataType.DRG_CLAIM:
            if 'claimed_amount' in df.columns:
                summary['total_claimed_amount'] = df['claimed_amount'].apply(
                    lambda x: self.parse_amount(x)).sum()
        
        elif data_type == FeedbackDataType.REVIEW_RESULT:
            if 'original_amount' in df.columns:
                summary['total_claimed_amount'] = df['original_amount'].apply(
                    lambda x: self.parse_amount(x)).sum()
            if 'reviewed_amount' in df.columns:
                summary['total_reviewed_amount'] = df['reviewed_amount'].apply(
                    lambda x: self.parse_amount(x)).sum()
            
            summary['total_adjustment'] = (
                summary['total_claimed_amount'] - summary['total_reviewed_amount']
            )
            
            if summary['total_claimed_amount'] > 0:
                summary['adjustment_rate'] = round(
                    summary['total_adjustment'] / summary['total_claimed_amount'] * 100, 2
                )
            
            # KDRG 변경 건수
            if 'original_kdrg' in df.columns and 'reviewed_kdrg' in df.columns:
                kdrg_changes = df[df['original_kdrg'] != df['reviewed_kdrg']]
                summary['kdrg_change_count'] = len(kdrg_changes)
            
            # 주요 조정 사유
            if 'adjustment_reason' in df.columns:
                reason_counts = df['adjustment_reason'].value_counts().head(5)
                summary['top_adjustments'] = [
                    {'reason': reason, 'count': int(count)}
                    for reason, count in reason_counts.items()
                    if reason and str(reason).strip()
                ]
        
        # DRG 분포
        kdrg_col = None
        for col in ['claimed_kdrg', 'kdrg', 'KDRG']:
            if col in df.columns:
                kdrg_col = col
                break
        
        if kdrg_col:
            # 7개 DRG군별 분류
            for code, name in self.DRG7_CODES.items():
                count = len(df[df[kdrg_col].str.startswith(code, na=False)])
                if count > 0:
                    summary['drg_distribution'][f"{code} ({name})"] = count
            
            # 기타
            other_count = len(df) - sum(summary['drg_distribution'].values())
            if other_count > 0:
                summary['drg_distribution']['기타 (행위별)'] = other_count
        
        return summary

    def compare_claim_vs_review(self, claim_data: Dict, review_data: Dict) -> Dict[str, Any]:
        """청구 vs 심사 결과 비교 분석"""
        claim_records = {r['claim_id']: r for r in claim_data.get('records', [])}
        review_records = {r['claim_id']: r for r in review_data.get('records', [])}
        
        comparison = {
            'total_claims': len(claim_records),
            'total_reviews': len(review_records),
            'matched': 0,
            'kdrg_changed': [],
            'amount_adjusted': [],
            'statistics': {
                'total_claimed': 0,
                'total_reviewed': 0,
                'total_adjustment': 0,
                'avg_adjustment_rate': 0,
            }
        }
        
        for claim_id, claim in claim_records.items():
            if claim_id in review_records:
                review = review_records[claim_id]
                comparison['matched'] += 1
                
                # KDRG 변경
                if claim.get('claimed_kdrg') != review.get('reviewed_kdrg'):
                    comparison['kdrg_changed'].append({
                        'claim_id': claim_id,
                        'original_kdrg': claim.get('claimed_kdrg'),
                        'reviewed_kdrg': review.get('reviewed_kdrg'),
                        'patient_id': claim.get('patient_id'),
                    })
                
                # 금액 조정
                if review.get('adjustment_amount', 0) != 0:
                    comparison['amount_adjusted'].append({
                        'claim_id': claim_id,
                        'original_amount': claim.get('claimed_amount', 0),
                        'reviewed_amount': review.get('reviewed_amount', 0),
                        'adjustment': review.get('adjustment_amount', 0),
                        'reason': review.get('adjustment_reason', ''),
                    })
                
                comparison['statistics']['total_claimed'] += claim.get('claimed_amount', 0)
                comparison['statistics']['total_reviewed'] += review.get('reviewed_amount', 0)
        
        comparison['statistics']['total_adjustment'] = (
            comparison['statistics']['total_claimed'] - 
            comparison['statistics']['total_reviewed']
        )
        
        if comparison['statistics']['total_claimed'] > 0:
            comparison['statistics']['avg_adjustment_rate'] = round(
                comparison['statistics']['total_adjustment'] / 
                comparison['statistics']['total_claimed'] * 100, 2
            )
        
        return comparison

    def get_excel_sheets(self, file_content: bytes, file_name: str) -> List[str]:
        """엑셀 파일의 시트 목록 조회"""
        import io
        
        ext = file_name.lower().split('.')[-1]
        if ext not in ['xlsx', 'xls']:
            return []
        
        try:
            xl = pd.ExcelFile(io.BytesIO(file_content))
            return xl.sheet_names
        except Exception as e:
            logger.error(f"시트 목록 조회 오류: {e}")
            return []


# 서비스 인스턴스
feedback_parser = FeedbackParserService()
