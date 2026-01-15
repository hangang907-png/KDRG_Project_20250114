"""
예측 vs 실제 KDRG 비교 분석 테스트
"""

import sys
sys.path.insert(0, '/home/qk/kdrg_enterprise/backend')

from services.comparison_service import KDRGComparisonService, MismatchType
from services.feedback_parser_service import FeedbackParserService

def test_comparison():
    print("=== 예측 vs 실제 KDRG 비교 분석 테스트 ===\n")
    
    # 1. 파서로 데이터 로드
    parser = FeedbackParserService()
    
    claim_file = '/home/qk/kdrg_enterprise/data/sample_claim_data.xlsx'
    review_file = '/home/qk/kdrg_enterprise/data/sample_review_result.xlsx'
    
    print("1. 데이터 로드")
    claim_data = parser.parse_file(claim_file)
    review_data = parser.parse_file(review_file)
    print(f"   - 청구 데이터: {len(claim_data['records'])}건")
    print(f"   - 심사 결과: {len(review_data['records'])}건")
    print()
    
    # 2. 비교 분석 실행
    print("2. 비교 분석 실행")
    service = KDRGComparisonService()
    
    comparisons = service.compare_records(
        claim_data['records'],
        review_data['records']
    )
    print(f"   - 비교 건수: {len(comparisons)}건")
    print()
    
    # 3. 통계 계산
    print("3. 통계 분석")
    stats = service.calculate_statistics()
    print(f"   - 전체 정확도: {stats.accuracy_rate}%")
    print(f"   - 중증도 정확도: {stats.severity_accuracy}%")
    print(f"   - AADRG 정확도: {stats.aadrg_accuracy}%")
    print()
    print(f"   불일치 유형별:")
    print(f"     * 정확 일치: {stats.exact_matches}건")
    print(f"     * 중증도 차이: {stats.severity_mismatches}건")
    print(f"     * AADRG 차이: {stats.aadrg_mismatches}건")
    print(f"     * MDC 차이: {stats.mdc_mismatches}건")
    print()
    print(f"   금액:")
    print(f"     * 총 예측 금액: {stats.total_predicted_amount:,.0f}원")
    print(f"     * 총 실제 금액: {stats.total_actual_amount:,.0f}원")
    print(f"     * 차이: {stats.total_difference:,.0f}원")
    print()
    
    # 4. 원인 분석
    print("4. 불일치 원인 분포")
    for cause, count in stats.cause_distribution.items():
        print(f"   - {cause}: {count}건")
    print()
    
    # 5. 주요 불일치 패턴
    print("5. 주요 불일치 패턴 (상위 5개)")
    for pattern in stats.drg_mismatch_patterns[:5]:
        print(f"   - {pattern['pattern']}: {pattern['count']}건 (차이: {pattern['total_diff']:,.0f}원)")
    print()
    
    # 6. 7개 DRG군 분석
    print("6. 7개 DRG군별 정확도")
    drg7 = service.get_drg7_analysis()
    for code in ['D12', 'D13', 'G08', 'H06', 'I09', 'L08', 'O01', 'O60']:
        data = drg7.get(code, {})
        if data.get('total', 0) > 0:
            print(f"   - {code}: {data['accuracy']}% ({data['matches']}/{data['total']}건)")
    print()
    
    # 7. 개선 권고사항
    print("7. 개선 권고사항")
    recommendations = service.generate_improvement_recommendations()
    for rec in recommendations[:3]:
        print(f"   [{rec.priority.upper()}] {rec.category}")
        print(f"     문제: {rec.issue}")
        print(f"     권고: {rec.recommendation}")
        print()
    
    # 8. 상세 비교 예시
    print("8. 불일치 건 상세 (상위 5건)")
    mismatches = [c for c in comparisons if not c.is_match][:5]
    for m in mismatches:
        print(f"   [{m.claim_id}]")
        print(f"     예측: {m.predicted_kdrg} → 실제: {m.actual_kdrg}")
        print(f"     유형: {m.mismatch_type}, 원인: {', '.join(m.mismatch_causes)}")
        print(f"     금액차이: {m.amount_difference:,.0f}원, 위험도: {m.risk_score}")
        print(f"     권고: {m.recommendation}")
        print()
    
    print("=== 테스트 완료 ===")
    return True


if __name__ == '__main__':
    test_comparison()
