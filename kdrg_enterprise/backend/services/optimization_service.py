"""
전역 KDRG 최적화 서비스
- 전체 MDC에 대한 KDRG 수익성 분석
- 대안 KDRG 제안 및 코딩 개선 권고
- 수익성 시뮬레이션
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import logging

from .kdrg_reference_data import (
    KDRGInfo,
    get_kdrg_info,
    get_kdrg_by_aadrg,
    get_kdrg_by_mdc,
    get_alternative_kdrgss,
    calculate_revenue_difference,
    get_severity_options,
    MDCCode,
    KDRG_REFERENCE_DATA,
    BASE_RATE_2024,
)
from .pregrouper_service import pre_grouper, PatientInfo, DiagnosisInfo, ProcedureInfo, GrouperInput

logger = logging.getLogger(__name__)


class OptimizationType(Enum):
    """최적화 유형"""
    SEVERITY_UPGRADE = "severity_upgrade"  # 중증도 상향
    DIAGNOSIS_CODING = "diagnosis_coding"  # 진단 코딩 개선
    PROCEDURE_CODING = "procedure_coding"  # 수술/처치 코딩 개선
    COMPLICATION_ADD = "complication_add"  # 합병증/동반질환 추가
    DRG7_CONVERSION = "drg7_conversion"  # 7개 DRG군 전환


class RiskLevel(Enum):
    """위험 수준"""
    LOW = "low"  # 합법적 코딩 개선
    MEDIUM = "medium"  # 검토 필요
    HIGH = "high"  # 심사 위험


@dataclass
class OptimizationSuggestion:
    """최적화 제안"""
    suggestion_id: str
    optimization_type: str
    current_kdrg: str
    suggested_kdrg: str
    current_amount: float
    suggested_amount: float
    revenue_difference: float
    revenue_change_pct: float
    required_actions: List[str]
    risk_level: str
    confidence: float
    rationale: str


@dataclass
class PatientOptimizationResult:
    """환자별 최적화 분석 결과"""
    patient_id: str
    claim_id: str
    current_kdrg: str
    current_mdc: str
    current_severity: int
    current_amount: float
    main_diagnosis: str
    procedures: List[str]
    los: int
    
    # 최적화 결과
    suggestions: List[OptimizationSuggestion]
    total_optimization_potential: float
    best_suggestion: Optional[OptimizationSuggestion]
    analysis_timestamp: str


@dataclass
class MDCOptimizationSummary:
    """MDC별 최적화 요약"""
    mdc: str
    mdc_name: str
    total_cases: int
    total_current_revenue: float
    total_potential_revenue: float
    optimization_potential: float
    optimization_rate: float  # 최적화 가능 케이스 비율
    top_suggestions: List[Dict]


@dataclass
class GlobalOptimizationReport:
    """전역 최적화 보고서"""
    report_id: str
    generated_at: str
    total_cases_analyzed: int
    total_current_revenue: float
    total_potential_revenue: float
    total_optimization_potential: float
    optimization_rate: float
    mdc_summaries: List[MDCOptimizationSummary]
    top_opportunities: List[PatientOptimizationResult]
    risk_distribution: Dict[str, int]


class GlobalKDRGOptimizationService:
    """전역 KDRG 최적화 서비스"""
    
    # 중증도 상향에 필요한 CC 코드 (예시)
    CC_UPGRADE_CODES = {
        'MCC': [
            ('J96.0', '급성 호흡부전', ['폐렴', '호흡기 질환']),
            ('I50.0', '울혈성 심부전', ['순환기 질환']),
            ('N17.0', '급성 신부전', ['신장 질환']),
            ('E11.65', '당뇨병성 고혈당 위기', ['당뇨 환자']),
            ('A41.9', '패혈증', ['감염 환자']),
        ],
        'CC': [
            ('E11.9', '당뇨병', ['혈당 이상 환자']),
            ('I10', '본태성 고혈압', ['혈압 이상 환자']),
            ('J44.1', '만성폐쇄성폐질환', ['흡연자, 호흡기 질환']),
            ('N18.3', '만성 신장병 3기', ['신기능 저하']),
        ],
    }
    
    def __init__(self):
        self.report_counter = 0
    
    def analyze_patient_optimization(
        self, 
        patient_data: Dict[str, Any]
    ) -> PatientOptimizationResult:
        """개별 환자 최적화 분석"""
        
        patient_id = str(patient_data.get('patient_id', ''))
        claim_id = str(patient_data.get('claim_id', ''))
        current_kdrg = str(patient_data.get('kdrg', '')).upper()
        main_diagnosis = str(patient_data.get('main_diagnosis', ''))
        sub_diagnoses = patient_data.get('sub_diagnoses', [])
        procedures = patient_data.get('procedures', [])
        los = int(patient_data.get('los', 0))
        age = int(patient_data.get('age', 0))
        
        # 현재 KDRG 정보 조회
        current_info = get_kdrg_info(current_kdrg)
        
        if not current_info:
            # KDRG 정보가 없으면 Pre-Grouper로 추정
            grouper_result = pre_grouper.group_from_dict(patient_data)
            current_kdrg = grouper_result.kdrg
            current_info = get_kdrg_info(current_kdrg)
        
        current_mdc = current_info.mdc if current_info else current_kdrg[0] if current_kdrg else 'W'
        current_severity = current_info.severity if current_info else 0
        current_amount = current_info.base_amount if current_info else 0.0
        
        suggestions = []
        
        # 1. 중증도 상향 가능성 분석
        severity_suggestions = self._analyze_severity_upgrade(
            current_kdrg, current_info, sub_diagnoses, age, los
        )
        suggestions.extend(severity_suggestions)
        
        # 2. 합병증/동반질환 추가 가능성
        complication_suggestions = self._analyze_complication_opportunities(
            current_info, main_diagnosis, sub_diagnoses
        )
        suggestions.extend(complication_suggestions)
        
        # 3. 7개 DRG군 전환 가능성
        drg7_suggestions = self._analyze_drg7_conversion(
            current_info, main_diagnosis, procedures
        )
        suggestions.extend(drg7_suggestions)
        
        # 4. 진단 코딩 개선
        diagnosis_suggestions = self._analyze_diagnosis_coding(
            current_info, main_diagnosis, sub_diagnoses, procedures
        )
        suggestions.extend(diagnosis_suggestions)
        
        # 수익 차이 기준으로 정렬
        suggestions.sort(key=lambda x: x.revenue_difference, reverse=True)
        
        # 총 최적화 잠재력 계산
        total_potential = sum(s.revenue_difference for s in suggestions if s.revenue_difference > 0)
        
        best_suggestion = suggestions[0] if suggestions else None
        
        return PatientOptimizationResult(
            patient_id=patient_id,
            claim_id=claim_id,
            current_kdrg=current_kdrg,
            current_mdc=current_mdc,
            current_severity=current_severity,
            current_amount=current_amount,
            main_diagnosis=main_diagnosis,
            procedures=procedures if isinstance(procedures, list) else [procedures] if procedures else [],
            los=los,
            suggestions=suggestions,
            total_optimization_potential=total_potential,
            best_suggestion=best_suggestion,
            analysis_timestamp=datetime.now().isoformat(),
        )
    
    def _analyze_severity_upgrade(
        self,
        current_kdrg: str,
        current_info: Optional[KDRGInfo],
        sub_diagnoses: List[str],
        age: int,
        los: int
    ) -> List[OptimizationSuggestion]:
        """중증도 상향 가능성 분석"""
        suggestions = []
        
        if not current_info or current_info.severity >= 3:
            return suggestions
        
        # 상위 중증도 옵션 조회
        alternatives = get_alternative_kdrgss(current_kdrg)
        higher_severity = [
            alt for alt in alternatives 
            if alt.severity > current_info.severity
        ]
        
        for alt in higher_severity:
            revenue_diff = alt.base_amount - current_info.base_amount
            if revenue_diff <= 0:
                continue
            
            # 필요한 조치 결정
            required_actions = []
            risk_level = RiskLevel.LOW
            confidence = 70.0
            
            severity_gap = alt.severity - current_info.severity
            
            if severity_gap == 1:
                required_actions.append("합병증/동반질환(CC) 코드 추가 검토")
                required_actions.append("의무기록에 기록된 동반질환 누락 여부 확인")
                confidence = 75.0
            elif severity_gap >= 2:
                required_actions.append("주요 합병증(MCC) 코드 추가 필요")
                required_actions.append("중환자실 기록, 주요 시술 기록 확인")
                risk_level = RiskLevel.MEDIUM
                confidence = 50.0
            
            # 고령자나 장기 재원의 경우 신뢰도 상향
            if age >= 70:
                confidence += 5
                required_actions.append("고령 환자 - CC 코드 누락 가능성 높음")
            if los > current_info.los_upper:
                confidence += 5
                required_actions.append("장기 재원 - 합병증 발생 가능성 확인")
            
            pct_change = (revenue_diff / current_info.base_amount * 100) if current_info.base_amount > 0 else 0
            
            suggestions.append(OptimizationSuggestion(
                suggestion_id=f"sev_{current_kdrg}_{alt.kdrg_code}",
                optimization_type=OptimizationType.SEVERITY_UPGRADE.value,
                current_kdrg=current_kdrg,
                suggested_kdrg=alt.kdrg_code,
                current_amount=current_info.base_amount,
                suggested_amount=alt.base_amount,
                revenue_difference=revenue_diff,
                revenue_change_pct=round(pct_change, 2),
                required_actions=required_actions,
                risk_level=risk_level.value,
                confidence=min(confidence, 95.0),
                rationale=f"중증도 {current_info.severity} → {alt.severity} 상향 시 수익 {revenue_diff:,.0f}원 증가 예상",
            ))
        
        return suggestions
    
    def _analyze_complication_opportunities(
        self,
        current_info: Optional[KDRGInfo],
        main_diagnosis: str,
        sub_diagnoses: List[str]
    ) -> List[OptimizationSuggestion]:
        """합병증/동반질환 추가 기회 분석"""
        suggestions = []
        
        if not current_info:
            return suggestions
        
        existing_codes = set([main_diagnosis.upper()] + [d.upper() for d in sub_diagnoses])
        
        # CC 코드 추가 가능성 검토
        cc_level = 'CC' if current_info.severity < 2 else 'MCC'
        potential_codes = self.CC_UPGRADE_CODES.get(cc_level, [])
        
        for code, name, conditions in potential_codes[:3]:  # 상위 3개만
            if code.upper() in existing_codes:
                continue
            
            # 잠재적 수익 증가 계산
            target_severity = current_info.severity + (2 if cc_level == 'MCC' else 1)
            target_kdrg = current_info.aadrg_code[:4] + str(min(target_severity, 4))
            target_info = get_kdrg_info(target_kdrg)
            
            if not target_info:
                continue
            
            revenue_diff = target_info.base_amount - current_info.base_amount
            if revenue_diff <= 0:
                continue
            
            pct_change = (revenue_diff / current_info.base_amount * 100) if current_info.base_amount > 0 else 0
            
            suggestions.append(OptimizationSuggestion(
                suggestion_id=f"cc_{code}_{current_info.kdrg_code}",
                optimization_type=OptimizationType.COMPLICATION_ADD.value,
                current_kdrg=current_info.kdrg_code,
                suggested_kdrg=target_kdrg,
                current_amount=current_info.base_amount,
                suggested_amount=target_info.base_amount,
                revenue_difference=revenue_diff,
                revenue_change_pct=round(pct_change, 2),
                required_actions=[
                    f"'{name}' ({code}) 코드 추가 검토",
                    f"해당 조건: {', '.join(conditions)}",
                    "의무기록에 해당 진단 기록 확인",
                ],
                risk_level=RiskLevel.MEDIUM.value,
                confidence=45.0,
                rationale=f"{name} 코드 추가 시 수익 {revenue_diff:,.0f}원 증가 가능",
            ))
        
        return suggestions
    
    def _analyze_drg7_conversion(
        self,
        current_info: Optional[KDRGInfo],
        main_diagnosis: str,
        procedures: List[str]
    ) -> List[OptimizationSuggestion]:
        """7개 DRG군 전환 가능성 분석"""
        suggestions = []
        
        if not current_info:
            return suggestions
        
        # 이미 7개 DRG군이면 스킵
        if current_info.drg7_code:
            return suggestions
        
        # 7개 DRG군 매핑 확인
        drg7_mapping = {
            'D12': {'diagnoses': ['J35', 'J36', 'J03'], 'procedures': ['Q216', 'Q217']},
            'D13': {'diagnoses': ['J32', 'J33', 'J34'], 'procedures': ['Q213', 'Q214']},
            'G08': {'diagnoses': ['K40', 'K41'], 'procedures': ['Q289', 'Q290']},
            'H06': {'diagnoses': ['K80', 'K81', 'K82'], 'procedures': ['Q765', 'Q766']},
            'I09': {'diagnoses': ['K60', 'K61', 'K62', 'K64'], 'procedures': ['Q297', 'Q298']},
            'L08': {'diagnoses': ['N20', 'N21', 'N22', 'N23'], 'procedures': ['R391']},
            'O01': {'diagnoses': ['O82', 'O84'], 'procedures': ['R450', 'R451']},
            'O60': {'diagnoses': ['O80', 'O81', 'O83'], 'procedures': []},
        }
        
        dx_upper = main_diagnosis.upper()[:3]
        proc_prefixes = [p.upper()[:4] for p in procedures]
        
        for drg7, info in drg7_mapping.items():
            dx_match = any(dx_upper.startswith(d[:3]) for d in info['diagnoses'])
            proc_match = not info['procedures'] or any(
                any(p.startswith(pr[:4]) for pr in proc_prefixes)
                for p in info['procedures']
            )
            
            if dx_match and not proc_match and info['procedures']:
                # 수술 추가하면 7개 DRG군 가능
                drg7_kdrg = drg7 + "10"  # 기본 중증도
                drg7_info = get_kdrg_info(drg7_kdrg)
                
                if drg7_info:
                    revenue_diff = drg7_info.base_amount - current_info.base_amount
                    if revenue_diff > 0:
                        pct_change = (revenue_diff / current_info.base_amount * 100) if current_info.base_amount > 0 else 0
                        
                        suggestions.append(OptimizationSuggestion(
                            suggestion_id=f"drg7_{drg7}_{current_info.kdrg_code}",
                            optimization_type=OptimizationType.DRG7_CONVERSION.value,
                            current_kdrg=current_info.kdrg_code,
                            suggested_kdrg=drg7_kdrg,
                            current_amount=current_info.base_amount,
                            suggested_amount=drg7_info.base_amount,
                            revenue_difference=revenue_diff,
                            revenue_change_pct=round(pct_change, 2),
                            required_actions=[
                                f"7개 포괄수가 DRG '{drg7_info.name}' 전환 가능",
                                "해당 수술/처치 코드 기록 확인",
                                "포괄수가 적용 시 재원일수 관리 중요",
                            ],
                            risk_level=RiskLevel.LOW.value,
                            confidence=60.0,
                            rationale=f"7개 DRG군 전환 시 포괄수가 적용으로 수익 {revenue_diff:,.0f}원 증가 예상",
                        ))
        
        return suggestions
    
    def _analyze_diagnosis_coding(
        self,
        current_info: Optional[KDRGInfo],
        main_diagnosis: str,
        sub_diagnoses: List[str],
        procedures: List[str]
    ) -> List[OptimizationSuggestion]:
        """진단 코딩 개선 분석"""
        suggestions = []
        
        if not current_info:
            return suggestions
        
        # 주진단 변경 가능성 (부진단 중 더 높은 수가의 진단이 있는지)
        # 이 분석은 실제 환경에서는 더 정교해야 함
        
        # 간단한 예: 동일 MDC 내에서 수술 KDRG가 더 유리한 경우
        if not current_info.is_surgical and procedures:
            # 수술이 있는데 비수술 KDRG로 분류된 경우
            surgical_kdrgss = [
                info for info in get_kdrg_by_mdc(current_info.mdc)
                if info.is_surgical and info.base_amount > current_info.base_amount
            ]
            
            if surgical_kdrgss:
                best_surgical = max(surgical_kdrgss, key=lambda x: x.base_amount)
                revenue_diff = best_surgical.base_amount - current_info.base_amount
                pct_change = (revenue_diff / current_info.base_amount * 100) if current_info.base_amount > 0 else 0
                
                suggestions.append(OptimizationSuggestion(
                    suggestion_id=f"diag_{current_info.kdrg_code}_{best_surgical.kdrg_code}",
                    optimization_type=OptimizationType.DIAGNOSIS_CODING.value,
                    current_kdrg=current_info.kdrg_code,
                    suggested_kdrg=best_surgical.kdrg_code,
                    current_amount=current_info.base_amount,
                    suggested_amount=best_surgical.base_amount,
                    revenue_difference=revenue_diff,
                    revenue_change_pct=round(pct_change, 2),
                    required_actions=[
                        "수술/처치 코드가 KDRG 분류에 반영되었는지 확인",
                        "주진단과 수술의 관련성 검토",
                        f"수술 KDRG '{best_surgical.name}'로 변경 가능 여부 검토",
                    ],
                    risk_level=RiskLevel.MEDIUM.value,
                    confidence=55.0,
                    rationale="수술 기록이 있으나 비수술 DRG로 분류됨 - 코딩 검토 필요",
                ))
        
        return suggestions
    
    def analyze_batch_optimization(
        self,
        patients_data: List[Dict[str, Any]],
        mdc_filter: Optional[str] = None,
        min_potential: float = 0
    ) -> GlobalOptimizationReport:
        """배치 최적화 분석"""
        
        self.report_counter += 1
        report_id = f"OPT-{datetime.now().strftime('%Y%m%d')}-{self.report_counter:04d}"
        
        results: List[PatientOptimizationResult] = []
        mdc_stats: Dict[str, Dict] = {}
        risk_counts = {'low': 0, 'medium': 0, 'high': 0}
        
        for patient in patients_data:
            # MDC 필터 적용
            if mdc_filter:
                patient_mdc = str(patient.get('kdrg', ''))[:1].upper()
                if patient_mdc != mdc_filter.upper():
                    continue
            
            result = self.analyze_patient_optimization(patient)
            
            if result.total_optimization_potential >= min_potential:
                results.append(result)
                
                # MDC별 통계 수집
                mdc = result.current_mdc
                if mdc not in mdc_stats:
                    mdc_stats[mdc] = {
                        'cases': 0,
                        'current_revenue': 0,
                        'potential_revenue': 0,
                        'suggestions': [],
                    }
                
                mdc_stats[mdc]['cases'] += 1
                mdc_stats[mdc]['current_revenue'] += result.current_amount
                mdc_stats[mdc]['potential_revenue'] += result.current_amount + result.total_optimization_potential
                
                if result.best_suggestion:
                    mdc_stats[mdc]['suggestions'].append(result.best_suggestion)
                    risk_counts[result.best_suggestion.risk_level] += 1
        
        # MDC 요약 생성
        mdc_summaries = []
        for mdc, stats in sorted(mdc_stats.items()):
            try:
                mdc_name = MDCCode[mdc].mdc_name
            except KeyError:
                mdc_name = f"MDC {mdc}"
            
            optimization_potential = stats['potential_revenue'] - stats['current_revenue']
            
            mdc_summaries.append(MDCOptimizationSummary(
                mdc=mdc,
                mdc_name=mdc_name,
                total_cases=stats['cases'],
                total_current_revenue=stats['current_revenue'],
                total_potential_revenue=stats['potential_revenue'],
                optimization_potential=optimization_potential,
                optimization_rate=round(len(stats['suggestions']) / stats['cases'] * 100, 2) if stats['cases'] > 0 else 0,
                top_suggestions=[asdict(s) for s in stats['suggestions'][:5]],
            ))
        
        # 최적화 기회 상위 케이스
        results.sort(key=lambda x: x.total_optimization_potential, reverse=True)
        top_opportunities = results[:20]
        
        # 전체 통계
        total_current = sum(r.current_amount for r in results)
        total_potential = sum(r.current_amount + r.total_optimization_potential for r in results)
        
        return GlobalOptimizationReport(
            report_id=report_id,
            generated_at=datetime.now().isoformat(),
            total_cases_analyzed=len(results),
            total_current_revenue=total_current,
            total_potential_revenue=total_potential,
            total_optimization_potential=total_potential - total_current,
            optimization_rate=round(len([r for r in results if r.total_optimization_potential > 0]) / len(results) * 100, 2) if results else 0,
            mdc_summaries=mdc_summaries,
            top_opportunities=top_opportunities,
            risk_distribution=risk_counts,
        )
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """최적화 서비스 요약 정보"""
        return {
            'service_name': 'Global KDRG Optimization Service',
            'version': '1.0.0',
            'supported_mdc': [m.code for m in MDCCode],
            'total_kdrg_codes': len(KDRG_REFERENCE_DATA),
            'optimization_types': [t.value for t in OptimizationType],
            'risk_levels': [r.value for r in RiskLevel],
            'base_rate_2024': BASE_RATE_2024,
        }
    
    def simulate_optimization(
        self,
        patient_data: Dict[str, Any],
        target_kdrg: str
    ) -> Dict[str, Any]:
        """최적화 시뮬레이션"""
        
        current_kdrg = str(patient_data.get('kdrg', ''))
        current_info = get_kdrg_info(current_kdrg)
        target_info = get_kdrg_info(target_kdrg)
        
        if not current_info or not target_info:
            return {
                'success': False,
                'error': 'Invalid KDRG code',
            }
        
        revenue_diff, weight_diff, pct_diff = calculate_revenue_difference(current_kdrg, target_kdrg)
        
        return {
            'success': True,
            'current': {
                'kdrg': current_info.kdrg_code,
                'name': current_info.name,
                'severity': current_info.severity,
                'relative_weight': current_info.relative_weight,
                'base_amount': current_info.base_amount,
            },
            'target': {
                'kdrg': target_info.kdrg_code,
                'name': target_info.name,
                'severity': target_info.severity,
                'relative_weight': target_info.relative_weight,
                'base_amount': target_info.base_amount,
            },
            'difference': {
                'amount': revenue_diff,
                'weight': weight_diff,
                'percentage': pct_diff,
            },
            'feasibility': self._assess_feasibility(current_info, target_info),
        }
    
    def _assess_feasibility(
        self,
        current: KDRGInfo,
        target: KDRGInfo
    ) -> Dict[str, Any]:
        """전환 가능성 평가"""
        
        feasibility = {
            'possible': True,
            'difficulty': 'low',
            'requirements': [],
            'warnings': [],
        }
        
        # 같은 AADRG 내 중증도 변경
        if current.aadrg_code == target.aadrg_code:
            severity_diff = target.severity - current.severity
            if severity_diff == 1:
                feasibility['requirements'].append("CC 코드 1개 이상 추가 필요")
                feasibility['difficulty'] = 'low'
            elif severity_diff == 2:
                feasibility['requirements'].append("MCC 코드 또는 CC 코드 2개 이상 필요")
                feasibility['difficulty'] = 'medium'
            elif severity_diff >= 3:
                feasibility['requirements'].append("다수의 MCC 코드 필요")
                feasibility['difficulty'] = 'high'
                feasibility['warnings'].append("심사 위험 주의")
        
        # 다른 AADRG로 변경
        elif current.mdc == target.mdc:
            feasibility['requirements'].append("주수술 또는 주진단 변경 필요")
            feasibility['difficulty'] = 'medium'
            feasibility['warnings'].append("KDRG 분류 로직 재검토 필요")
        
        # 다른 MDC로 변경
        else:
            feasibility['requirements'].append("주진단 변경 필요")
            feasibility['difficulty'] = 'high'
            feasibility['warnings'].append("주진단 변경은 심사 위험 높음")
            feasibility['possible'] = False
        
        return feasibility


# 서비스 인스턴스
global_optimization_service = GlobalKDRGOptimizationService()
