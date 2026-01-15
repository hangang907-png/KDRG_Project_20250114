"""
환류 데이터 파서 테스트
"""

import sys
sys.path.insert(0, '/home/qk/kdrg_enterprise/backend')

from services.feedback_parser_service import FeedbackParserService, FeedbackDataType

def test_parser():
    parser = FeedbackParserService()
    
    print("=== 환류 데이터 파서 테스트 ===\n")
    
    # 1. 청구 데이터 파싱 테스트
    print("1. 청구 데이터 파싱 테스트")
    claim_file = '/home/qk/kdrg_enterprise/data/sample_claim_data.xlsx'
    
    result = parser.parse_file(claim_file)
    print(f"   - 데이터 유형: {result['data_type']}")
    print(f"   - 총 레코드: {result['total_records']}건")
    print(f"   - 컬럼: {result['columns'][:5]}...")
    print(f"   - 요약:")
    summary = result['summary']
    print(f"     * 총 청구액: {summary.get('total_claimed_amount', 0):,.0f}원")
    print(f"     * DRG 분포: {summary.get('drg_distribution', {})}")
    
    # 첫 번째 레코드 출력
    if result['records']:
        print(f"   - 첫 번째 레코드: {result['records'][0]}")
    print()
    
    # 2. 심사 결과 파싱 테스트
    print("2. 심사 결과 파싱 테스트")
    review_file = '/home/qk/kdrg_enterprise/data/sample_review_result.xlsx'
    
    result2 = parser.parse_file(review_file)
    print(f"   - 데이터 유형: {result2['data_type']}")
    print(f"   - 총 레코드: {result2['total_records']}건")
    summary2 = result2['summary']
    print(f"   - 요약:")
    print(f"     * 총 청구액: {summary2.get('total_claimed_amount', 0):,.0f}원")
    print(f"     * 심사금액: {summary2.get('total_reviewed_amount', 0):,.0f}원")
    print(f"     * 조정금액: {summary2.get('total_adjustment', 0):,.0f}원")
    print(f"     * 조정률: {summary2.get('adjustment_rate', 0)}%")
    print(f"     * KDRG 변경: {summary2.get('kdrg_change_count', 0)}건")
    print(f"     * 주요 조정사유: {summary2.get('top_adjustments', [])}")
    print()
    
    # 3. 비교 분석 테스트
    print("3. 청구 vs 심사 비교 분석 테스트")
    comparison = parser.compare_claim_vs_review(result, result2)
    print(f"   - 총 청구: {comparison['total_claims']}건")
    print(f"   - 매칭됨: {comparison['matched']}건")
    print(f"   - KDRG 변경: {len(comparison['kdrg_changed'])}건")
    print(f"   - 금액 조정: {len(comparison['amount_adjusted'])}건")
    print(f"   - 통계:")
    stats = comparison['statistics']
    print(f"     * 총 청구액: {stats['total_claimed']:,.0f}원")
    print(f"     * 총 심사액: {stats['total_reviewed']:,.0f}원")
    print(f"     * 총 조정액: {stats['total_adjustment']:,.0f}원")
    print(f"     * 평균 조정률: {stats['avg_adjustment_rate']}%")
    
    # KDRG 변경 상세
    if comparison['kdrg_changed']:
        print(f"\n   KDRG 변경 상세 (상위 5건):")
        for item in comparison['kdrg_changed'][:5]:
            print(f"     * {item['claim_id']}: {item['original_kdrg']} → {item['reviewed_kdrg']}")
    
    print("\n=== 테스트 완료 ===")
    return True


if __name__ == '__main__':
    test_parser()
