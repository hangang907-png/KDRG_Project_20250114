"""
예측 vs 실제 KDRG 비교 분석 서비스
- 병원 내 사전 KDRG 분류(예측)와 심평원 심사 결과(실제) 비교
- 불일치 원인 분석 및 패턴 추출
- 예측 정확도 향상을 위한 피드백 제공
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict
import logging
import json

logger = logging.getLogger(__name__)


class MismatchType(Enum):
    """불일치 유형"""
    EXACT_MATCH = "exact_match"  # 정확히 일치
    SEVERITY_DIFF = "severity_diff"  # 중증도만 다름 (AADRG 동일)
    AADRG_DIFF = "aadrg_diff"  # AADRG 다름 (MDC 동일)
    MDC_DIFF = "mdc_diff"  # MDC 다름 (완전히 다른 분류)


class MismatchCause(Enum):
    """불일치 추정 원인"""
    DIAGNOSIS_CODING = "diagnosis_coding"  # 진단 코딩 오류
    PROCEDURE_CODING = "procedure_coding"  # 수술/처치 코딩 오류
    SEVERITY_ASSESSMENT = "severity_assessment"  # 중증도 평가 차이
    COMPLICATION = "complication"  # 합병증/동반질환 누락
    GROUPER_VERSION = "grouper_version"  # 그루퍼 버전 차이
    DOCUMENTATION = "documentation"  # 의무기록 불충분
    RULE_CHANGE = "rule_change"  # 급여기준 변경
    UNKNOWN = "unknown"  # 원인 불명


@dataclass
class KDRGComparison:
    """KDRG 비교 결과"""
    claim_id: str
    patient_id: str
    admission_date: str
    discharge_date: str
    los: int
    main_diagnosis: str
    
    # 예측 (병원 청구)
    predicted_kdrg: str
    predicted_aadrg: str
    predicted_mdc: str
    predicted_severity: str
    predicted_amount: float
    
    # 실제 (심평원 심사)
    actual_kdrg: str
    actual_aadrg: str
    actual_mdc: str
    actual_severity: str
    actual_amount: float
    
    # 비교 결과
    is_match: bool
    mismatch_type: str
    mismatch_causes: List[str]
    amount_difference: float
    adjustment_reason: str
    
    # 분석
    risk_score: float  # 불일치 위험 점수 (0-100)
    recommendation: str  # 개선 권고사항


@dataclass
class ComparisonStatistics:
    """비교 통계"""
    total_cases: int = 0
    exact_matches: int = 0
    severity_mismatches: int = 0
    aadrg_mismatches: int = 0
    mdc_mismatches: int = 0
    
    accuracy_rate: float = 0.0  # 정확도
    severity_accuracy: float = 0.0  # 중증도 정확도
    aadrg_accuracy: float = 0.0  # AADRG 정확도
    
    total_predicted_amount: float = 0.0
    total_actual_amount: float = 0.0
    total_difference: float = 0.0
    
    cause_distribution: Dict[str, int] = field(default_factory=dict)
    drg_mismatch_patterns: List[Dict] = field(default_factory=list)
    monthly_accuracy: Dict[str, float] = field(default_factory=dict)


@dataclass
class ImprovementRecommendation:
    """개선 권고사항"""
    priority: str  # high, medium, low
    category: str  # 진단코딩, 수술코딩, 중증도, 문서화 등
    issue: str  # 문제점
    recommendation: str  # 권고사항
    affected_cases: int  # 영향받는 건수
    potential_impact: float  # 잠재적 금액 영향


class KDRGComparisonService:
    """예측 vs 실제 KDRG 비교 분석 서비스"""
    
    # 7개 DRG군 코드
    DRG7_CODES = ['D12', 'D13', 'G08', 'H06', 'I09', 'L08', 'O01', 'O60']
    
    # 불일치 원인 키워드 매핑
    CAUSE_KEYWORDS = {
        MismatchCause.DIAGNOSIS_CODING: ['진단', '상병', '주진단', '부진단', 'ICD'],
        MismatchCause.PROCEDURE_CODING: ['수술', '처치', '시술', '코드'],
        MismatchCause.SEVERITY_ASSESSMENT: ['중증', '경증', 'CC', 'MCC', '합병증점수'],
        MismatchCause.COMPLICATION: ['합병증', '동반질환', '부상병'],
        MismatchCause.DOCUMENTATION: ['기록', '문서', '누락', '미비'],
        MismatchCause.RULE_CHANGE: ['기준', '변경', '고시', '개정'],
    }
    
    def __init__(self):
        self.comparisons: List[KDRGComparison] = []
        self.statistics: Optional[ComparisonStatistics] = None
    
    def parse_kdrg(self, kdrg: str) -> Tuple[str, str, str]:
        """KDRG 코드 파싱 -> (MDC, AADRG, 중증도)"""
        if not kdrg or len(kdrg) < 4:
            return ('', '', '')
        
        kdrg = kdrg.strip().upper()
        mdc = kdrg[0]
        aadrg = kdrg[:4] if len(kdrg) >= 4 else kdrg
        severity = kdrg[4] if len(kdrg) >= 5 else '0'
        
        return (mdc, aadrg, severity)
    
    def determine_mismatch_type(self, predicted: str, actual: str) -> MismatchType:
        """불일치 유형 판별"""
        if predicted == actual:
            return MismatchType.EXACT_MATCH
        
        pred_mdc, pred_aadrg, pred_sev = self.parse_kdrg(predicted)
        act_mdc, act_aadrg, act_sev = self.parse_kdrg(actual)
        
        if pred_aadrg == act_aadrg:
            return MismatchType.SEVERITY_DIFF
        elif pred_mdc == act_mdc:
            return MismatchType.AADRG_DIFF
        else:
            return MismatchType.MDC_DIFF
    
    def infer_mismatch_causes(self, mismatch_type: MismatchType, 
                               adjustment_reason: str = "") -> List[str]:
        """불일치 원인 추정"""
        causes = []
        reason_lower = adjustment_reason.lower() if adjustment_reason else ""
        
        # 조정사유에서 키워드 추출
        for cause, keywords in self.CAUSE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in reason_lower:
                    causes.append(cause.value)
                    break
        
        # 불일치 유형에 따른 추가 추정
        if mismatch_type == MismatchType.SEVERITY_DIFF:
            if MismatchCause.SEVERITY_ASSESSMENT.value not in causes:
                causes.append(MismatchCause.SEVERITY_ASSESSMENT.value)
        elif mismatch_type == MismatchType.AADRG_DIFF:
            if not causes:
                causes.append(MismatchCause.PROCEDURE_CODING.value)
        elif mismatch_type == MismatchType.MDC_DIFF:
            if not causes:
                causes.append(MismatchCause.DIAGNOSIS_CODING.value)
        
        if not causes:
            causes.append(MismatchCause.UNKNOWN.value)
        
        return causes
    
    def calculate_risk_score(self, mismatch_type: MismatchType, 
                             amount_diff: float, los: int) -> float:
        """불일치 위험 점수 계산 (0-100)"""
        score = 0.0
        
        # 불일치 유형에 따른 기본 점수
        type_scores = {
            MismatchType.EXACT_MATCH: 0,
            MismatchType.SEVERITY_DIFF: 30,
            MismatchType.AADRG_DIFF: 60,
            MismatchType.MDC_DIFF: 90,
        }
        score += type_scores.get(mismatch_type, 50)
        
        # 금액 차이에 따른 추가 점수
        if abs(amount_diff) > 500000:
            score += 10
        elif abs(amount_diff) > 200000:
            score += 5
        
        # 재원일수 이상치
        if los > 14:
            score += 5
        
        return min(100, score)
    
    def generate_recommendation(self, mismatch_type: MismatchType,
                                 causes: List[str], kdrg_pred: str, 
                                 kdrg_actual: str) -> str:
        """개선 권고사항 생성"""
        recommendations = []
        
        if mismatch_type == MismatchType.SEVERITY_DIFF:
            recommendations.append(f"중증도 평가 재검토 필요: {kdrg_pred} → {kdrg_actual}")
            recommendations.append("합병증/동반질환 코딩 누락 여부 확인")
        
        elif mismatch_type == MismatchType.AADRG_DIFF:
            recommendations.append(f"AADRG 분류 재검토: {kdrg_pred[:4]} → {kdrg_actual[:4]}")
            recommendations.append("수술/처치 코드 정확성 확인")
        
        elif mismatch_type == MismatchType.MDC_DIFF:
            recommendations.append(f"주진단 분류 재검토: MDC {kdrg_pred[0]} → {kdrg_actual[0]}")
            recommendations.append("주진단 선택 원칙 교육 필요")
        
        if MismatchCause.DOCUMENTATION.value in causes:
            recommendations.append("의무기록 작성 충실도 향상 필요")
        
        return " | ".join(recommendations) if recommendations else "추가 분석 필요"
    
    def compare_records(self, predicted_data: List[Dict], 
                        actual_data: List[Dict]) -> List[KDRGComparison]:
        """예측 데이터와 실제 데이터 비교"""
        # 청구번호로 인덱싱
        actual_by_id = {r.get('claim_id', ''): r for r in actual_data}
        
        comparisons = []
        
        for pred in predicted_data:
            claim_id = pred.get('claim_id', '')
            if not claim_id:
                continue
            
            actual = actual_by_id.get(claim_id)
            if not actual:
                continue
            
            # KDRG 코드 추출
            predicted_kdrg = pred.get('claimed_kdrg', '') or pred.get('kdrg', '')
            actual_kdrg = actual.get('reviewed_kdrg', '') or actual.get('kdrg', '')
            
            pred_mdc, pred_aadrg, pred_sev = self.parse_kdrg(predicted_kdrg)
            act_mdc, act_aadrg, act_sev = self.parse_kdrg(actual_kdrg)
            
            # 불일치 분석
            mismatch_type = self.determine_mismatch_type(predicted_kdrg, actual_kdrg)
            is_match = mismatch_type == MismatchType.EXACT_MATCH
            
            adjustment_reason = actual.get('adjustment_reason', '')
            causes = self.infer_mismatch_causes(mismatch_type, adjustment_reason)
            
            # 금액 계산
            predicted_amount = float(pred.get('claimed_amount', 0) or 0)
            actual_amount = float(actual.get('reviewed_amount', 0) or actual.get('original_amount', 0) or 0)
            amount_diff = predicted_amount - actual_amount
            
            los = int(pred.get('los', 0) or 0)
            risk_score = self.calculate_risk_score(mismatch_type, amount_diff, los)
            recommendation = self.generate_recommendation(
                mismatch_type, causes, predicted_kdrg, actual_kdrg
            )
            
            comparison = KDRGComparison(
                claim_id=claim_id,
                patient_id=pred.get('patient_id', ''),
                admission_date=pred.get('admission_date', ''),
                discharge_date=pred.get('discharge_date', ''),
                los=los,
                main_diagnosis=pred.get('main_diagnosis', ''),
                
                predicted_kdrg=predicted_kdrg,
                predicted_aadrg=pred_aadrg,
                predicted_mdc=pred_mdc,
                predicted_severity=pred_sev,
                predicted_amount=predicted_amount,
                
                actual_kdrg=actual_kdrg,
                actual_aadrg=act_aadrg,
                actual_mdc=act_mdc,
                actual_severity=act_sev,
                actual_amount=actual_amount,
                
                is_match=is_match,
                mismatch_type=mismatch_type.value,
                mismatch_causes=causes,
                amount_difference=amount_diff,
                adjustment_reason=adjustment_reason,
                
                risk_score=risk_score,
                recommendation=recommendation,
            )
            comparisons.append(comparison)
        
        self.comparisons = comparisons
        return comparisons
    
    def calculate_statistics(self) -> ComparisonStatistics:
        """비교 통계 계산"""
        if not self.comparisons:
            return ComparisonStatistics()
        
        stats = ComparisonStatistics()
        stats.total_cases = len(self.comparisons)
        
        cause_counts = defaultdict(int)
        mismatch_patterns = defaultdict(lambda: {'count': 0, 'total_diff': 0})
        monthly_matches = defaultdict(lambda: {'total': 0, 'matches': 0})
        
        for comp in self.comparisons:
            # 일치 유형별 카운트
            if comp.mismatch_type == MismatchType.EXACT_MATCH.value:
                stats.exact_matches += 1
            elif comp.mismatch_type == MismatchType.SEVERITY_DIFF.value:
                stats.severity_mismatches += 1
            elif comp.mismatch_type == MismatchType.AADRG_DIFF.value:
                stats.aadrg_mismatches += 1
            elif comp.mismatch_type == MismatchType.MDC_DIFF.value:
                stats.mdc_mismatches += 1
            
            # 금액 합계
            stats.total_predicted_amount += comp.predicted_amount
            stats.total_actual_amount += comp.actual_amount
            stats.total_difference += comp.amount_difference
            
            # 원인 분포
            for cause in comp.mismatch_causes:
                cause_counts[cause] += 1
            
            # 불일치 패턴
            if not comp.is_match:
                pattern = f"{comp.predicted_kdrg} → {comp.actual_kdrg}"
                mismatch_patterns[pattern]['count'] += 1
                mismatch_patterns[pattern]['total_diff'] += comp.amount_difference
            
            # 월별 정확도
            if comp.admission_date:
                month = comp.admission_date[:7]  # YYYY-MM
                monthly_matches[month]['total'] += 1
                if comp.is_match:
                    monthly_matches[month]['matches'] += 1
        
        # 정확도 계산
        if stats.total_cases > 0:
            stats.accuracy_rate = round(stats.exact_matches / stats.total_cases * 100, 2)
            stats.severity_accuracy = round(
                (stats.exact_matches + stats.severity_mismatches) / stats.total_cases * 100, 2
            )
            stats.aadrg_accuracy = round(
                (stats.total_cases - stats.mdc_mismatches) / stats.total_cases * 100, 2
            )
        
        stats.cause_distribution = dict(cause_counts)
        
        # 상위 불일치 패턴
        stats.drg_mismatch_patterns = sorted(
            [{'pattern': k, **v} for k, v in mismatch_patterns.items()],
            key=lambda x: x['count'],
            reverse=True
        )[:20]
        
        # 월별 정확도
        stats.monthly_accuracy = {
            month: round(data['matches'] / data['total'] * 100, 2) if data['total'] > 0 else 0
            for month, data in sorted(monthly_matches.items())
        }
        
        self.statistics = stats
        return stats
    
    def generate_improvement_recommendations(self) -> List[ImprovementRecommendation]:
        """개선 권고사항 목록 생성"""
        if not self.statistics:
            self.calculate_statistics()
        
        recommendations = []
        
        # 원인별 권고사항
        cause_recommendations = {
            MismatchCause.DIAGNOSIS_CODING.value: {
                'category': '진단코딩',
                'recommendation': '주진단 선택 원칙 교육 및 코딩 가이드라인 재정비',
            },
            MismatchCause.PROCEDURE_CODING.value: {
                'category': '수술코딩',
                'recommendation': '수술/처치 코드 매핑 테이블 점검 및 업데이트',
            },
            MismatchCause.SEVERITY_ASSESSMENT.value: {
                'category': '중증도평가',
                'recommendation': '합병증/동반질환 코딩 체크리스트 도입',
            },
            MismatchCause.COMPLICATION.value: {
                'category': '합병증관리',
                'recommendation': '부진단 누락 방지를 위한 자동 알림 시스템 구축',
            },
            MismatchCause.DOCUMENTATION.value: {
                'category': '의무기록',
                'recommendation': '의무기록 작성 충실도 모니터링 및 피드백 체계 구축',
            },
        }
        
        for cause, count in sorted(
            self.statistics.cause_distribution.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            if cause in cause_recommendations:
                info = cause_recommendations[cause]
                # 영향도에 따른 우선순위
                if count >= 10:
                    priority = 'high'
                elif count >= 5:
                    priority = 'medium'
                else:
                    priority = 'low'
                
                recommendations.append(ImprovementRecommendation(
                    priority=priority,
                    category=info['category'],
                    issue=f"{cause} 관련 불일치 {count}건 발생",
                    recommendation=info['recommendation'],
                    affected_cases=count,
                    potential_impact=0,  # 추후 계산
                ))
        
        # 정확도 기반 권고
        if self.statistics.accuracy_rate < 80:
            recommendations.insert(0, ImprovementRecommendation(
                priority='high',
                category='전체 프로세스',
                issue=f"전체 정확도 {self.statistics.accuracy_rate}%로 목표(80%) 미달",
                recommendation='KDRG 분류 프로세스 전면 재검토 및 Pre-Grouper 도입 검토',
                affected_cases=self.statistics.total_cases - self.statistics.exact_matches,
                potential_impact=abs(self.statistics.total_difference),
            ))
        
        return recommendations
    
    def get_drg7_analysis(self) -> Dict[str, Any]:
        """7개 DRG군별 정확도 분석"""
        drg7_stats = {}
        
        for drg_code in self.DRG7_CODES:
            drg7_stats[drg_code] = {
                'total': 0,
                'matches': 0,
                'accuracy': 0,
                'total_diff': 0,
                'mismatches': [],
            }
        
        drg7_stats['OTHER'] = {
            'total': 0,
            'matches': 0,
            'accuracy': 0,
            'total_diff': 0,
            'mismatches': [],
        }
        
        for comp in self.comparisons:
            # DRG군 분류
            drg_code = 'OTHER'
            for code in self.DRG7_CODES:
                if comp.predicted_kdrg.startswith(code):
                    drg_code = code
                    break
            
            drg7_stats[drg_code]['total'] += 1
            if comp.is_match:
                drg7_stats[drg_code]['matches'] += 1
            else:
                drg7_stats[drg_code]['mismatches'].append({
                    'claim_id': comp.claim_id,
                    'predicted': comp.predicted_kdrg,
                    'actual': comp.actual_kdrg,
                    'diff': comp.amount_difference,
                })
            drg7_stats[drg_code]['total_diff'] += comp.amount_difference
        
        # 정확도 계산
        for code in drg7_stats:
            total = drg7_stats[code]['total']
            if total > 0:
                drg7_stats[code]['accuracy'] = round(
                    drg7_stats[code]['matches'] / total * 100, 2
                )
            # 상위 5개만 유지
            drg7_stats[code]['mismatches'] = drg7_stats[code]['mismatches'][:5]
        
        return drg7_stats
    
    def get_trend_analysis(self) -> Dict[str, Any]:
        """추세 분석"""
        if not self.statistics:
            self.calculate_statistics()
        
        return {
            'monthly_accuracy': self.statistics.monthly_accuracy,
            'improvement_trend': self._calculate_trend(self.statistics.monthly_accuracy),
        }
    
    def _calculate_trend(self, monthly_data: Dict[str, float]) -> str:
        """추세 계산"""
        if len(monthly_data) < 2:
            return 'insufficient_data'
        
        values = list(monthly_data.values())
        first_half_avg = sum(values[:len(values)//2]) / (len(values)//2) if values[:len(values)//2] else 0
        second_half_avg = sum(values[len(values)//2:]) / (len(values) - len(values)//2) if values[len(values)//2:] else 0
        
        if second_half_avg > first_half_avg + 5:
            return 'improving'
        elif second_half_avg < first_half_avg - 5:
            return 'declining'
        else:
            return 'stable'
    
    def export_report(self) -> Dict[str, Any]:
        """종합 보고서 생성"""
        if not self.statistics:
            self.calculate_statistics()
        
        recommendations = self.generate_improvement_recommendations()
        drg7_analysis = self.get_drg7_analysis()
        trend = self.get_trend_analysis()
        
        return {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_cases': self.statistics.total_cases,
                'accuracy_rate': self.statistics.accuracy_rate,
                'severity_accuracy': self.statistics.severity_accuracy,
                'aadrg_accuracy': self.statistics.aadrg_accuracy,
                'total_difference': self.statistics.total_difference,
            },
            'mismatch_breakdown': {
                'exact_matches': self.statistics.exact_matches,
                'severity_mismatches': self.statistics.severity_mismatches,
                'aadrg_mismatches': self.statistics.aadrg_mismatches,
                'mdc_mismatches': self.statistics.mdc_mismatches,
            },
            'cause_distribution': self.statistics.cause_distribution,
            'top_mismatch_patterns': self.statistics.drg_mismatch_patterns[:10],
            'drg7_analysis': drg7_analysis,
            'trend_analysis': trend,
            'recommendations': [asdict(r) for r in recommendations],
            'detailed_comparisons': [asdict(c) for c in self.comparisons[:100]],
        }


# 서비스 인스턴스
kdrg_comparison_service = KDRGComparisonService()
