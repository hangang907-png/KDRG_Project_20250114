import pandas as pd
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class OptimizationRecommendation:
    """DRG 최적화 추천 결과"""
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
    alert_level: AlertLevel


@dataclass
class LossAlert:
    """청구 손실 경고"""
    patient_id: str
    alert_type: str
    current_value: str
    expected_value: str
    estimated_loss: float
    description: str
    alert_level: AlertLevel


class ProfitOptimizer:
    """병원 이익 극대화 모듈"""
    
    def __init__(self, kdrg_database: pd.DataFrame = None):
        self.kdrg_db = kdrg_database
        self.seven_drg_codes = {
            'T01': {'name': '편도/축농증', 'base_weight': 0.8},
            'T03': {'name': '수혈', 'base_weight': 0.6},
            'X04': {'name': '망막/백내장', 'base_weight': 1.2},
            'X05': {'name': '결석', 'base_weight': 1.0},
            'T05': {'name': '중이염', 'base_weight': 0.7},
            'T11': {'name': '모낭염', 'base_weight': 0.5},
            'T12': {'name': '치핵', 'base_weight': 0.9}
        }
        
        # 기본 점수 단가 (원) - 실제 값으로 업데이트 필요
        self.base_point_value = 81.4  # 2024년 기준 예시
    
    def set_kdrg_database(self, kdrg_db: pd.DataFrame):
        """KDRG 데이터베이스 설정"""
        self.kdrg_db = kdrg_db
    
    # ========================
    # DRG 코드 최적화 추천
    # ========================
    
    def analyze_kdrg_optimization(self, patient_data: dict) -> Optional[OptimizationRecommendation]:
        """환자별 KDRG 코드 최적화 분석
        
        CC(합병증/동반질환) 여부, 수술 여부 등을 분석하여
        더 적절한 KDRG 코드가 있는지 확인
        """
        current_kdrg = patient_data.get('kdrg_code', '')
        current_aadrg = patient_data.get('aadrg_code', '')
        diagnosis_code = patient_data.get('primary_diagnosis_code', '')
        
        if not current_kdrg or not current_aadrg:
            return None
        
        # AADRG 내 다른 KDRG 코드 조회
        alternative_codes = self._find_alternative_kdrg(current_aadrg, current_kdrg)
        
        if not alternative_codes:
            return None
        
        # 최적 코드 선택
        best_alternative = self._select_best_alternative(
            patient_data, current_kdrg, alternative_codes
        )
        
        if not best_alternative:
            return None
        
        # 수익 차이 계산
        current_payment = self._calculate_payment(current_kdrg)
        potential_payment = self._calculate_payment(best_alternative['kdrg'])
        
        if potential_payment <= current_payment:
            return None
        
        return OptimizationRecommendation(
            patient_id=patient_data.get('patient_hash', ''),
            current_kdrg=current_kdrg,
            current_aadrg=current_aadrg,
            recommended_kdrg=best_alternative['kdrg'],
            recommended_aadrg=best_alternative['aadrg'],
            current_payment=current_payment,
            potential_payment=potential_payment,
            payment_difference=potential_payment - current_payment,
            confidence_score=best_alternative.get('confidence', 0.8),
            reason=best_alternative.get('reason', 'CC 등급 재검토 권장'),
            alert_level=AlertLevel.INFO
        )
    
    def _find_alternative_kdrg(self, aadrg: str, current_kdrg: str) -> List[dict]:
        """동일 AADRG 내 대안 KDRG 코드 조회"""
        if self.kdrg_db is None:
            return []
        
        alternatives = []
        
        # AADRG 첫 3자리 기준으로 관련 코드 조회
        aadrg_prefix = aadrg[:3] if len(aadrg) >= 3 else aadrg
        
        for _, row in self.kdrg_db.iterrows():
            row_aadrg = str(row.get('AADRG', ''))
            row_kdrg = str(row.get('KDRG', ''))
            
            if row_aadrg.startswith(aadrg_prefix) and row_kdrg != current_kdrg:
                alternatives.append({
                    'aadrg': row_aadrg,
                    'kdrg': row_kdrg,
                    'cc': row.get('CC', ''),
                    'weight': row.get('상대가치', 1.0)
                })
        
        return alternatives
    
    def _select_best_alternative(self, patient_data: dict, current_kdrg: str, 
                                  alternatives: List[dict]) -> Optional[dict]:
        """환자 데이터 기반 최적 대안 선택"""
        if not alternatives:
            return None
        
        # CC 등급이 높은 코드 우선 선택 (더 높은 수가)
        # 실제로는 환자의 합병증/동반질환 분석 필요
        
        best = None
        best_weight = 0
        
        for alt in alternatives:
            weight = float(alt.get('weight', 1.0)) if alt.get('weight') else 1.0
            if weight > best_weight:
                best_weight = weight
                best = alt
        
        if best:
            best['confidence'] = 0.75
            best['reason'] = 'CC 등급 상향 가능성 검토 (합병증/동반질환 확인 필요)'
        
        return best
    
    def _calculate_payment(self, kdrg_code: str) -> float:
        """KDRG 코드 기반 예상 청구 금액 계산"""
        if self.kdrg_db is None:
            return 0.0
        
        # 코드북에서 상대가치 조회
        for _, row in self.kdrg_db.iterrows():
            if str(row.get('KDRG', '')) == kdrg_code:
                weight = float(row.get('상대가치', 1.0)) if row.get('상대가치') else 1.0
                return weight * self.base_point_value * 1000  # 천원 단위
        
        return 0.0
    
    # ========================
    # 청구 손실 감지/경고
    # ========================
    
    def detect_claim_losses(self, patient_data: dict) -> List[LossAlert]:
        """청구 손실 감지"""
        alerts = []
        
        # 1. KDRG 코드 미입력 검사
        if not patient_data.get('kdrg_code'):
            alerts.append(LossAlert(
                patient_id=patient_data.get('patient_hash', ''),
                alert_type='KDRG_MISSING',
                current_value='',
                expected_value='필수 입력',
                estimated_loss=500000,  # 예상 손실 (임의값)
                description='KDRG 코드가 입력되지 않아 DRG 청구가 불가능합니다.',
                alert_level=AlertLevel.CRITICAL
            ))
        
        # 2. 7개 DRG군 해당 여부 검사
        aadrg = patient_data.get('aadrg_code', '')
        for drg_code, drg_info in self.seven_drg_codes.items():
            if aadrg.startswith(drg_code):
                # 7개 DRG군에 해당하지만 필수 정보 누락 시
                alerts.extend(self._check_7drg_requirements(patient_data, drg_code, drg_info))
                break
        
        # 3. 재원일수 이상 검사
        los_alert = self._check_length_of_stay(patient_data)
        if los_alert:
            alerts.append(los_alert)
        
        # 4. CC 등급 누락 검사
        cc_alert = self._check_cc_classification(patient_data)
        if cc_alert:
            alerts.append(cc_alert)
        
        return alerts
    
    def _check_7drg_requirements(self, patient_data: dict, drg_code: str, 
                                  drg_info: dict) -> List[LossAlert]:
        """7개 DRG군별 필수 요건 검사"""
        alerts = []
        patient_id = patient_data.get('patient_hash', '')
        
        requirements = {
            'T01': ['수술일자', '수술명'],
            'T03': ['수혈일자', '혈액형'],
            'X04': ['수술일자', '수술명'],
            'X05': ['수술일자', '결석위치'],
            'T05': ['수술일자', '수술명'],
            'T11': ['처치일자'],
            'T12': ['수술일자', '수술명']
        }
        
        required_fields = requirements.get(drg_code, [])
        
        for field in required_fields:
            if not patient_data.get(field):
                alerts.append(LossAlert(
                    patient_id=patient_id,
                    alert_type=f'7DRG_{drg_code}_MISSING',
                    current_value='미입력',
                    expected_value=field,
                    estimated_loss=drg_info['base_weight'] * 100000,
                    description=f'{drg_info["name"]} DRG군 청구 시 {field} 정보가 필요합니다.',
                    alert_level=AlertLevel.WARNING
                ))
        
        return alerts
    
    def _check_length_of_stay(self, patient_data: dict) -> Optional[LossAlert]:
        """재원일수 이상 검사"""
        los = patient_data.get('length_of_stay', 0)
        aadrg = patient_data.get('aadrg_code', '')
        
        # 표준 재원일수 대비 검사 (예시 기준)
        standard_los = {
            'T01': 3, 'T03': 2, 'X04': 2, 'X05': 3,
            'T05': 3, 'T11': 2, 'T12': 3
        }
        
        for drg_code, std_los in standard_los.items():
            if aadrg.startswith(drg_code):
                if los and los > std_los * 2:
                    return LossAlert(
                        patient_id=patient_data.get('patient_hash', ''),
                        alert_type='LOS_EXCESSIVE',
                        current_value=str(los),
                        expected_value=f'{std_los}일 이하',
                        estimated_loss=(los - std_los) * 50000,
                        description=f'재원일수({los}일)가 표준({std_los}일)을 크게 초과합니다. DRG 수익성 검토 필요.',
                        alert_level=AlertLevel.WARNING
                    )
                break
        
        return None
    
    def _check_cc_classification(self, patient_data: dict) -> Optional[LossAlert]:
        """CC(합병증/동반질환) 분류 검사"""
        kdrg = patient_data.get('kdrg_code', '')
        diagnosis_code = patient_data.get('primary_diagnosis_code', '')
        
        # KDRG 마지막 자리가 CC 등급을 나타냄 (0: 없음, 1-4: CC 등급)
        if kdrg and len(kdrg) >= 5:
            cc_level = kdrg[-1]
            if cc_level == '0':
                return LossAlert(
                    patient_id=patient_data.get('patient_hash', ''),
                    alert_type='CC_REVIEW',
                    current_value='CC 없음',
                    expected_value='CC 등급 검토',
                    estimated_loss=100000,
                    description='합병증/동반질환(CC) 등급이 0입니다. 환자 상태 재검토 시 상향 가능성이 있습니다.',
                    alert_level=AlertLevel.INFO
                )
        
        return None
    
    # ========================
    # 수익 분석/시각화
    # ========================
    
    def analyze_revenue(self, patients_df: pd.DataFrame) -> Dict:
        """수익 분석"""
        if patients_df is None or len(patients_df) == 0:
            return {}
        
        analysis = {
            'summary': {},
            'by_department': {},
            'by_drg': {},
            'by_month': {},
            'optimization_potential': {},
            'loss_summary': {}
        }
        
        # 전체 요약
        analysis['summary'] = {
            'total_patients': len(patients_df),
            'total_claim': patients_df['claim_amount'].sum() if 'claim_amount' in patients_df.columns else 0,
            'avg_claim': patients_df['claim_amount'].mean() if 'claim_amount' in patients_df.columns else 0,
            'avg_los': patients_df['length_of_stay'].mean() if 'length_of_stay' in patients_df.columns else 0
        }
        
        # 진료과별 분석
        if 'department' in patients_df.columns:
            dept_analysis = patients_df.groupby('department').agg({
                'patient_hash': 'count',
                'claim_amount': ['sum', 'mean'] if 'claim_amount' in patients_df.columns else 'count'
            }).reset_index()
            analysis['by_department'] = dept_analysis.to_dict('records')
        
        # DRG군별 분석
        if 'aadrg_code' in patients_df.columns:
            # 7개 DRG군 분류
            def classify_drg(aadrg):
                if not aadrg:
                    return '기타'
                for code, info in self.seven_drg_codes.items():
                    if str(aadrg).startswith(code):
                        return f"{code} - {info['name']}"
                return '기타 DRG'
            
            patients_df['drg_group'] = patients_df['aadrg_code'].apply(classify_drg)
            
            drg_analysis = patients_df.groupby('drg_group').agg({
                'patient_hash': 'count'
            }).reset_index()
            drg_analysis.columns = ['drg_group', 'patient_count']
            analysis['by_drg'] = drg_analysis.to_dict('records')
        
        return analysis
    
    def calculate_optimization_potential(self, patients_df: pd.DataFrame) -> Dict:
        """전체 최적화 가능 금액 계산"""
        total_current = 0
        total_potential = 0
        optimization_count = 0
        
        for _, row in patients_df.iterrows():
            patient_data = row.to_dict()
            recommendation = self.analyze_kdrg_optimization(patient_data)
            
            if recommendation:
                total_current += recommendation.current_payment
                total_potential += recommendation.potential_payment
                optimization_count += 1
        
        return {
            'optimization_count': optimization_count,
            'total_current_payment': total_current,
            'total_potential_payment': total_potential,
            'total_potential_gain': total_potential - total_current,
            'optimization_rate': (optimization_count / len(patients_df) * 100) if len(patients_df) > 0 else 0
        }


# 전역 인스턴스
profit_optimizer = ProfitOptimizer()
