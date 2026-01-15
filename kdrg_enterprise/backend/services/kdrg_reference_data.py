"""
KDRG 기준정보 데이터
- 전체 MDC별 KDRG 코드, 상대가치점수, 수가 정보
- 2024년 기준 (심평원 공개 자료 기반)

참고: 실제 운영 시에는 심평원 API나 DB에서 최신 데이터를 가져와야 함
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class MDCCode(Enum):
    """주진단범주 (Major Diagnostic Category)"""
    A = ("A", "신경계 질환")
    B = ("B", "눈 질환")
    C = ("C", "귀, 코, 입, 인후 질환")
    D = ("D", "호흡기계 질환")
    E = ("E", "순환기계 질환")
    F = ("F", "소화기계 질환")
    G = ("G", "간담도계 및 췌장 질환")
    H = ("H", "근골격계 및 결합조직 질환")
    I = ("I", "피부, 피하조직 및 유방 질환")
    J = ("J", "내분비, 영양 및 대사 질환")
    K = ("K", "신장 및 요로계 질환")
    L = ("L", "남성생식기계 질환")
    M = ("M", "여성생식기계 질환")
    N = ("N", "임신, 출산 및 산욕")
    O = ("O", "주산기 질환")
    P = ("P", "혈액 및 조혈기관 질환")
    Q = ("Q", "골수증식 질환")
    R = ("R", "감염 및 기생충 질환")
    S = ("S", "정신 질환")
    T = ("T", "알코올/약물 사용")
    U = ("U", "손상, 중독 및 약물 독성효과")
    V = ("V", "화상")
    W = ("W", "기타")
    X = ("X", "기타 악성신생물")
    Y = ("Y", "HIV 감염")
    Z = ("Z", "다발성 외상")

    def __init__(self, code: str, name: str):
        self._code = code
        self._name = name
    
    @property
    def code(self) -> str:
        return self._code
    
    @property
    def mdc_name(self) -> str:
        return self._name


@dataclass
class KDRGInfo:
    """KDRG 코드 정보"""
    kdrg_code: str  # 5자리 KDRG 코드
    aadrg_code: str  # 4자리 AADRG 코드
    mdc: str  # MDC 코드 (A-Z)
    severity: int  # 중증도 (0-4)
    name: str  # KDRG 명칭
    relative_weight: float  # 상대가치점수
    base_amount: float  # 기준수가 (원)
    los_lower: int  # 재원일수 하한
    los_upper: int  # 재원일수 상한
    los_outlier_per_diem: float  # 장기재원 일당 수가
    is_surgical: bool  # 수술/처치 여부
    drg7_code: Optional[str] = None  # 7개 DRG군 해당시 코드


# 2024년 기준 1점당 수가 (원)
BASE_RATE_2024 = 87000


# 전체 KDRG 기준정보 (주요 KDRG만 포함, 실제 운영 시 전체 데이터 필요)
KDRG_REFERENCE_DATA: Dict[str, KDRGInfo] = {
    # ====== 7개 포괄수가 DRG ======
    
    # D12 - 편도 및 아데노이드 절제술
    "D1210": KDRGInfo("D1210", "D121", "D", 0, "편도 및 아데노이드 절제술 - 중증도 없음", 0.72, 62640, 1, 3, 26100, True, "D12"),
    "D1211": KDRGInfo("D1211", "D121", "D", 1, "편도 및 아데노이드 절제술 - 경도", 0.80, 69600, 1, 4, 26100, True, "D12"),
    "D1212": KDRGInfo("D1212", "D121", "D", 2, "편도 및 아데노이드 절제술 - 중등도", 0.92, 80040, 2, 5, 26100, True, "D12"),
    "D1213": KDRGInfo("D1213", "D121", "D", 3, "편도 및 아데노이드 절제술 - 고도", 1.15, 100050, 2, 7, 26100, True, "D12"),
    
    # D13 - 축농증 수술
    "D1310": KDRGInfo("D1310", "D131", "D", 0, "축농증 수술 - 중증도 없음", 0.95, 82650, 2, 4, 27600, True, "D13"),
    "D1311": KDRGInfo("D1311", "D131", "D", 1, "축농증 수술 - 경도", 1.05, 91350, 2, 5, 27600, True, "D13"),
    "D1312": KDRGInfo("D1312", "D131", "D", 2, "축농증 수술 - 중등도", 1.18, 102660, 3, 6, 27600, True, "D13"),
    "D1313": KDRGInfo("D1313", "D131", "D", 3, "축농증 수술 - 고도", 1.45, 126150, 3, 8, 27600, True, "D13"),
    
    # G08 - 서혜부 및 대퇴부 탈장수술
    "G0810": KDRGInfo("G0810", "G081", "G", 0, "서혜부/대퇴부 탈장수술 - 중증도 없음", 0.85, 73950, 1, 3, 24600, True, "G08"),
    "G0811": KDRGInfo("G0811", "G081", "G", 1, "서혜부/대퇴부 탈장수술 - 경도", 0.95, 82650, 1, 4, 24600, True, "G08"),
    "G0812": KDRGInfo("G0812", "G081", "G", 2, "서혜부/대퇴부 탈장수술 - 중등도", 1.10, 95700, 2, 5, 24600, True, "G08"),
    "G0813": KDRGInfo("G0813", "G081", "G", 3, "서혜부/대퇴부 탈장수술 - 고도", 1.40, 121800, 3, 7, 24600, True, "G08"),
    
    # H06 - 담낭절제술
    "H0610": KDRGInfo("H0610", "H061", "H", 0, "담낭절제술 - 중증도 없음", 1.10, 95700, 3, 5, 31900, True, "H06"),
    "H0611": KDRGInfo("H0611", "H061", "H", 1, "담낭절제술 - 경도", 1.25, 108750, 3, 6, 31900, True, "H06"),
    "H0612": KDRGInfo("H0612", "H061", "H", 2, "담낭절제술 - 중등도", 1.45, 126150, 4, 8, 31900, True, "H06"),
    "H0613": KDRGInfo("H0613", "H061", "H", 3, "담낭절제술 - 고도", 1.85, 160950, 5, 12, 31900, True, "H06"),
    
    # I09 - 항문수술
    "I0910": KDRGInfo("I0910", "I091", "I", 0, "항문수술 - 중증도 없음", 0.55, 47850, 1, 2, 15900, True, "I09"),
    "I0911": KDRGInfo("I0911", "I091", "I", 1, "항문수술 - 경도", 0.62, 53940, 1, 3, 15900, True, "I09"),
    "I0912": KDRGInfo("I0912", "I091", "I", 2, "항문수술 - 중등도", 0.72, 62640, 2, 4, 15900, True, "I09"),
    "I0913": KDRGInfo("I0913", "I091", "I", 3, "항문수술 - 고도", 0.92, 80040, 2, 6, 15900, True, "I09"),
    
    # L08 - 요로결석 체외충격파쇄석술
    "L0810": KDRGInfo("L0810", "L081", "L", 0, "요로결석 체외충격파쇄석술 - 중증도 없음", 0.65, 56550, 1, 2, 18800, True, "L08"),
    "L0811": KDRGInfo("L0811", "L081", "L", 1, "요로결석 체외충격파쇄석술 - 경도", 0.72, 62640, 1, 2, 18800, True, "L08"),
    "L0812": KDRGInfo("L0812", "L081", "L", 2, "요로결석 체외충격파쇄석술 - 중등도", 0.82, 71340, 1, 3, 18800, True, "L08"),
    "L0813": KDRGInfo("L0813", "L081", "L", 3, "요로결석 체외충격파쇄석술 - 고도", 1.05, 91350, 2, 4, 18800, True, "L08"),
    
    # O01 - 제왕절개술
    "O0110": KDRGInfo("O0110", "O011", "O", 0, "제왕절개술 - 중증도 없음", 1.35, 117450, 4, 6, 39100, True, "O01"),
    "O0111": KDRGInfo("O0111", "O011", "O", 1, "제왕절개술 - 경도", 1.50, 130500, 4, 7, 39100, True, "O01"),
    "O0112": KDRGInfo("O0112", "O011", "O", 2, "제왕절개술 - 중등도", 1.75, 152250, 5, 8, 39100, True, "O01"),
    "O0113": KDRGInfo("O0113", "O011", "O", 3, "제왕절개술 - 고도", 2.20, 191400, 5, 10, 39100, True, "O01"),
    
    # O60 - 질식분만
    "O6010": KDRGInfo("O6010", "O601", "O", 0, "질식분만 - 중증도 없음", 0.90, 78300, 2, 3, 26100, False, "O60"),
    "O6011": KDRGInfo("O6011", "O601", "O", 1, "질식분만 - 경도", 1.00, 87000, 2, 4, 26100, False, "O60"),
    "O6012": KDRGInfo("O6012", "O601", "O", 2, "질식분만 - 중등도", 1.15, 100050, 3, 5, 26100, False, "O60"),
    "O6013": KDRGInfo("O6013", "O601", "O", 3, "질식분만 - 고도", 1.45, 126150, 3, 7, 26100, False, "O60"),
    
    # ====== 주요 일반 KDRG (행위별 참조용) ======
    
    # A - 신경계
    "A0110": KDRGInfo("A0110", "A011", "A", 0, "두개강 내 수술 - 중증도 없음", 3.50, 304500, 7, 14, 43500, True, None),
    "A0111": KDRGInfo("A0111", "A011", "A", 1, "두개강 내 수술 - 경도", 4.20, 365400, 8, 18, 43500, True, None),
    "A0112": KDRGInfo("A0112", "A011", "A", 2, "두개강 내 수술 - 중등도", 5.10, 443700, 10, 25, 43500, True, None),
    "A0113": KDRGInfo("A0113", "A011", "A", 3, "두개강 내 수술 - 고도", 6.50, 565500, 14, 35, 43500, True, None),
    "A6010": KDRGInfo("A6010", "A601", "A", 0, "뇌졸중 - 중증도 없음", 1.20, 104400, 5, 10, 34800, False, None),
    "A6011": KDRGInfo("A6011", "A601", "A", 1, "뇌졸중 - 경도", 1.45, 126150, 7, 14, 34800, False, None),
    "A6012": KDRGInfo("A6012", "A601", "A", 2, "뇌졸중 - 중등도", 1.85, 160950, 10, 21, 34800, False, None),
    "A6013": KDRGInfo("A6013", "A601", "A", 3, "뇌졸중 - 고도", 2.50, 217500, 14, 30, 34800, False, None),
    
    # E - 순환기계
    "E0110": KDRGInfo("E0110", "E011", "E", 0, "관상동맥 우회술 - 중증도 없음", 4.80, 417600, 10, 18, 46400, True, None),
    "E0111": KDRGInfo("E0111", "E011", "E", 1, "관상동맥 우회술 - 경도", 5.60, 487200, 12, 21, 46400, True, None),
    "E0112": KDRGInfo("E0112", "E011", "E", 2, "관상동맥 우회술 - 중등도", 6.80, 591600, 14, 28, 46400, True, None),
    "E0113": KDRGInfo("E0113", "E011", "E", 3, "관상동맥 우회술 - 고도", 8.50, 739500, 18, 40, 46400, True, None),
    "E0210": KDRGInfo("E0210", "E021", "E", 0, "심장판막 수술 - 중증도 없음", 5.50, 478500, 12, 20, 47800, True, None),
    "E0211": KDRGInfo("E0211", "E021", "E", 1, "심장판막 수술 - 경도", 6.50, 565500, 14, 24, 47800, True, None),
    "E0212": KDRGInfo("E0212", "E021", "E", 2, "심장판막 수술 - 중등도", 8.00, 696000, 16, 30, 47800, True, None),
    "E0213": KDRGInfo("E0213", "E021", "E", 3, "심장판막 수술 - 고도", 10.50, 913500, 20, 45, 47800, True, None),
    "E6010": KDRGInfo("E6010", "E601", "E", 0, "심부전 - 중증도 없음", 0.85, 73950, 4, 8, 24600, False, None),
    "E6011": KDRGInfo("E6011", "E601", "E", 1, "심부전 - 경도", 1.05, 91350, 5, 10, 24600, False, None),
    "E6012": KDRGInfo("E6012", "E601", "E", 2, "심부전 - 중등도", 1.35, 117450, 7, 14, 24600, False, None),
    "E6013": KDRGInfo("E6013", "E601", "E", 3, "심부전 - 고도", 1.80, 156600, 10, 21, 24600, False, None),
    
    # F - 소화기계
    "F0110": KDRGInfo("F0110", "F011", "F", 0, "위절제술 - 중증도 없음", 2.20, 191400, 7, 12, 38400, True, None),
    "F0111": KDRGInfo("F0111", "F011", "F", 1, "위절제술 - 경도", 2.60, 226200, 8, 14, 38400, True, None),
    "F0112": KDRGInfo("F0112", "F011", "F", 2, "위절제술 - 중등도", 3.20, 278400, 10, 18, 38400, True, None),
    "F0113": KDRGInfo("F0113", "F011", "F", 3, "위절제술 - 고도", 4.20, 365400, 14, 28, 38400, True, None),
    "F6010": KDRGInfo("F6010", "F601", "F", 0, "위장관 출혈 - 중증도 없음", 0.75, 65250, 3, 6, 21700, False, None),
    "F6011": KDRGInfo("F6011", "F601", "F", 1, "위장관 출혈 - 경도", 0.92, 80040, 4, 8, 21700, False, None),
    "F6012": KDRGInfo("F6012", "F601", "F", 2, "위장관 출혈 - 중등도", 1.18, 102660, 5, 10, 21700, False, None),
    "F6013": KDRGInfo("F6013", "F601", "F", 3, "위장관 출혈 - 고도", 1.55, 134850, 7, 14, 21700, False, None),
    
    # H - 근골격계
    "H0110": KDRGInfo("H0110", "H011", "H", 0, "고관절 치환술 - 중증도 없음", 2.80, 243600, 10, 16, 40600, True, None),
    "H0111": KDRGInfo("H0111", "H011", "H", 1, "고관절 치환술 - 경도", 3.30, 287100, 12, 18, 40600, True, None),
    "H0112": KDRGInfo("H0112", "H011", "H", 2, "고관절 치환술 - 중등도", 4.00, 348000, 14, 24, 40600, True, None),
    "H0113": KDRGInfo("H0113", "H011", "H", 3, "고관절 치환술 - 고도", 5.20, 452400, 18, 35, 40600, True, None),
    "H0210": KDRGInfo("H0210", "H021", "H", 0, "슬관절 치환술 - 중증도 없음", 2.50, 217500, 10, 14, 36200, True, None),
    "H0211": KDRGInfo("H0211", "H021", "H", 1, "슬관절 치환술 - 경도", 2.90, 252300, 11, 16, 36200, True, None),
    "H0212": KDRGInfo("H0212", "H021", "H", 2, "슬관절 치환술 - 중등도", 3.50, 304500, 13, 20, 36200, True, None),
    "H0213": KDRGInfo("H0213", "H021", "H", 3, "슬관절 치환술 - 고도", 4.50, 391500, 16, 28, 36200, True, None),
    
    # K - 신장 및 요로계
    "K0110": KDRGInfo("K0110", "K011", "K", 0, "신장절제술 - 중증도 없음", 2.40, 208800, 7, 12, 34800, True, None),
    "K0111": KDRGInfo("K0111", "K011", "K", 1, "신장절제술 - 경도", 2.85, 247950, 8, 14, 34800, True, None),
    "K0112": KDRGInfo("K0112", "K011", "K", 2, "신장절제술 - 중등도", 3.50, 304500, 10, 18, 34800, True, None),
    "K0113": KDRGInfo("K0113", "K011", "K", 3, "신장절제술 - 고도", 4.60, 400200, 14, 28, 34800, True, None),
    "K6010": KDRGInfo("K6010", "K601", "K", 0, "신부전 - 중증도 없음", 0.95, 82650, 4, 8, 27500, False, None),
    "K6011": KDRGInfo("K6011", "K601", "K", 1, "신부전 - 경도", 1.20, 104400, 5, 10, 27500, False, None),
    "K6012": KDRGInfo("K6012", "K601", "K", 2, "신부전 - 중등도", 1.55, 134850, 7, 14, 27500, False, None),
    "K6013": KDRGInfo("K6013", "K601", "K", 3, "신부전 - 고도", 2.10, 182700, 10, 21, 27500, False, None),
    
    # R - 감염
    "R6010": KDRGInfo("R6010", "R601", "R", 0, "패혈증 - 중증도 없음", 1.30, 113100, 5, 10, 37700, False, None),
    "R6011": KDRGInfo("R6011", "R601", "R", 1, "패혈증 - 경도", 1.65, 143550, 7, 14, 37700, False, None),
    "R6012": KDRGInfo("R6012", "R601", "R", 2, "패혈증 - 중등도", 2.20, 191400, 10, 21, 37700, False, None),
    "R6013": KDRGInfo("R6013", "R601", "R", 3, "패혈증 - 고도", 3.20, 278400, 14, 35, 37700, False, None),
}


def get_kdrg_info(kdrg_code: str) -> Optional[KDRGInfo]:
    """KDRG 코드로 정보 조회"""
    return KDRG_REFERENCE_DATA.get(kdrg_code.upper())


def get_kdrg_by_aadrg(aadrg_code: str) -> List[KDRGInfo]:
    """AADRG로 관련 KDRG 목록 조회"""
    aadrg = aadrg_code.upper()[:4]
    return [
        info for info in KDRG_REFERENCE_DATA.values()
        if info.aadrg_code.startswith(aadrg[:3])
    ]


def get_kdrg_by_mdc(mdc: str) -> List[KDRGInfo]:
    """MDC로 관련 KDRG 목록 조회"""
    return [
        info for info in KDRG_REFERENCE_DATA.values()
        if info.mdc == mdc.upper()
    ]


def get_drg7_kdrgss() -> List[KDRGInfo]:
    """7개 DRG군 KDRG 목록 조회"""
    return [
        info for info in KDRG_REFERENCE_DATA.values()
        if info.drg7_code is not None
    ]


def get_alternative_kdrgss(current_kdrg: str) -> List[KDRGInfo]:
    """현재 KDRG의 대안 KDRG 목록 (같은 AADRG 내 다른 중증도)"""
    current = get_kdrg_info(current_kdrg)
    if not current:
        return []
    
    return [
        info for info in KDRG_REFERENCE_DATA.values()
        if info.aadrg_code == current.aadrg_code and info.kdrg_code != current.kdrg_code
    ]


def calculate_revenue_difference(kdrg1: str, kdrg2: str) -> Tuple[float, float, float]:
    """두 KDRG 간 수익 차이 계산
    
    Returns:
        Tuple[기준수가 차이, 상대가치 차이, 차이 비율(%)]
    """
    info1 = get_kdrg_info(kdrg1)
    info2 = get_kdrg_info(kdrg2)
    
    if not info1 or not info2:
        return (0.0, 0.0, 0.0)
    
    amount_diff = info2.base_amount - info1.base_amount
    weight_diff = info2.relative_weight - info1.relative_weight
    
    if info1.base_amount > 0:
        pct_diff = (amount_diff / info1.base_amount) * 100
    else:
        pct_diff = 0.0
    
    return (amount_diff, weight_diff, round(pct_diff, 2))


def get_severity_options(aadrg: str) -> List[Dict]:
    """AADRG의 모든 중증도 옵션 반환"""
    alternatives = []
    
    for severity in range(4):
        kdrg_code = aadrg[:4] + str(severity)
        info = get_kdrg_info(kdrg_code)
        if info:
            alternatives.append({
                'kdrg_code': info.kdrg_code,
                'severity': info.severity,
                'name': info.name,
                'relative_weight': info.relative_weight,
                'base_amount': info.base_amount,
            })
    
    return alternatives


# MDC별 주요 진단코드-KDRG 매핑 (최적화 제안용)
MDC_DIAGNOSIS_MAPPING = {
    'A': {
        'G20': ['A601', 'A602'],  # 파킨슨병
        'G35': ['A601', 'A602'],  # 다발성 경화증
        'G40': ['A603', 'A604'],  # 간질
        'I60': ['A011', 'A012'],  # 뇌출혈
        'I61': ['A011', 'A012'],  
        'I63': ['A601', 'A602'],  # 뇌경색
    },
    'E': {
        'I20': ['E601', 'E602'],  # 협심증
        'I21': ['E011', 'E012'],  # 급성 심근경색
        'I25': ['E601', 'E602'],  # 만성 허혈성 심질환
        'I50': ['E601', 'E602'],  # 심부전
    },
    'F': {
        'K25': ['F601', 'F011'],  # 위궤양
        'K26': ['F601', 'F011'],  # 십이지장궤양
        'K35': ['F011', 'F012'],  # 급성 충수염
        'K80': ['H061', 'G081'],  # 담석
    },
    'H': {
        'M16': ['H011', 'H012'],  # 고관절증
        'M17': ['H021', 'H022'],  # 슬관절증
        'S72': ['H011', 'H012'],  # 대퇴골 골절
    },
}


def get_mdc_diagnosis_mapping(mdc: str) -> Dict:
    """MDC별 진단-KDRG 매핑 조회"""
    return MDC_DIAGNOSIS_MAPPING.get(mdc.upper(), {})
