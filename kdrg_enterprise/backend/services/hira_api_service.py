"""
심평원 API 연동 서비스 모듈

공공데이터포털(data.go.kr) API를 통해 심평원 데이터 조회
- 신포괄기준정보조회서비스: data.go.kr/data/15040343
- 병원정보서비스: data.go.kr/data/15001698
"""

import httpx
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class APIResponseStatus(Enum):
    SUCCESS = "00"
    APPLICATION_ERROR = "01"
    DB_ERROR = "02"
    NO_DATA = "03"
    HTTP_ERROR = "04"
    SERVICE_TIMEOUT = "05"
    INVALID_REQUEST = "10"
    NO_PERMISSION = "20"
    KEY_EXPIRED = "21"
    TRAFFIC_EXCEEDED = "22"


@dataclass
class APIResponse:
    """API 응답 결과"""
    success: bool
    status_code: str
    message: str
    data: Any = None
    total_count: int = 0
    page_no: int = 1
    num_of_rows: int = 10


@dataclass
class KDRGInfo:
    """KDRG 기준정보"""
    kdrg_code: str
    kdrg_name: str
    aadrg_code: str
    aadrg_name: str
    mdc_code: str
    mdc_name: str
    cc_level: str
    relative_weight: float
    geometric_mean_los: float
    arithmetic_mean_los: float
    low_trim: int
    high_trim: int


@dataclass
class HospitalInfo:
    """병원 정보"""
    hospital_code: str
    hospital_name: str
    address: str
    tel: str
    hospital_type: str
    sido: str
    sigungu: str


class HIRAAPIService:
    """심평원 공공데이터 API 서비스"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "http://apis.data.go.kr/B551182"
        self.timeout = 30.0
        
        # 서비스별 엔드포인트
        self.endpoints = {
            # 신포괄기준정보조회서비스
            'kdrg_info': '/NdrgStdInfoService/getNdrgPayList',
            'kdrg_detail': '/NdrgStdInfoService/getNdrgPayList', # 상세 기능이 하나뿐이므로 동일하게 설정
            'kdrg_weight': '/NdrgStdInfoService/getNdrgPayList',
            
            # 병원정보서비스
            'hospital_list': '/hospInfoServicev2/getHospBasisList',
            'hospital_detail': '/hospInfoServicev2/getHospBasisInfo',
            
            # DRG 수가정보서비스 (예시)
            'drg_fee': '/drgFeeInfoService/getDrgFeeInfo'
        }
    
    def set_api_key(self, api_key: str):
        """API 키 설정"""
        self.api_key = api_key
    
    async def _make_request(self, endpoint: str, params: Dict = None) -> APIResponse:
        """API 요청 실행"""
        if not self.api_key:
            return APIResponse(
                success=False,
                status_code="99",
                message="API 키가 설정되지 않았습니다.",
                data=None
            )
        
        url = f"{self.base_url}{endpoint}"
        request_params = {
            'serviceKey': self.api_key,
            **(params or {})
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=request_params)
                
                if response.status_code != 200:
                    return APIResponse(
                        success=False,
                        status_code="04",
                        message=f"HTTP 오류: {response.status_code}",
                        data=None
                    )
                
                # XML 응답 파싱
                return self._parse_xml_response(response.text)
                
        except httpx.TimeoutException:
            logger.error(f"API 요청 타임아웃: {url}")
            return APIResponse(
                success=False,
                status_code="05",
                message="API 요청 시간 초과",
                data=None
            )
        except Exception as e:
            logger.error(f"API 요청 오류: {e}")
            return APIResponse(
                success=False,
                status_code="01",
                message=str(e),
                data=None
            )
    
    def _parse_xml_response(self, xml_text: str) -> APIResponse:
        """XML 응답 파싱"""
        try:
            root = ET.fromstring(xml_text)
            
            # 응답 헤더 파싱
            header = root.find('.//header')
            result_code = header.find('resultCode').text if header and header.find('resultCode') is not None else "00"
            result_msg = header.find('resultMsg').text if header and header.find('resultMsg') is not None else ""
            
            if result_code != "00":
                return APIResponse(
                    success=False,
                    status_code=result_code,
                    message=result_msg,
                    data=None
                )
            
            # 응답 바디 파싱
            body = root.find('.//body')
            if body is None:
                return APIResponse(
                    success=True,
                    status_code="00",
                    message="Success",
                    data=[],
                    total_count=0
                )
            
            # 페이징 정보
            total_count = int(body.find('totalCount').text) if body.find('totalCount') is not None else 0
            page_no = int(body.find('pageNo').text) if body.find('pageNo') is not None else 1
            num_of_rows = int(body.find('numOfRows').text) if body.find('numOfRows') is not None else 10
            
            # 아이템 목록 파싱
            items = []
            items_elem = body.find('.//items')
            if items_elem is not None:
                for item in items_elem.findall('item'):
                    item_dict = {}
                    for child in item:
                        item_dict[child.tag] = child.text
                    items.append(item_dict)
            
            return APIResponse(
                success=True,
                status_code="00",
                message="Success",
                data=items,
                total_count=total_count,
                page_no=page_no,
                num_of_rows=num_of_rows
            )
            
        except ET.ParseError as e:
            logger.error(f"XML 파싱 오류: {e}")
            return APIResponse(
                success=False,
                status_code="01",
                message=f"XML 파싱 오류: {e}",
                data=None
            )
    
    # ========================
    # 신포괄기준정보 조회
    # ========================
    
    async def get_kdrg_info(self, 
                           kdrg_code: str = None,
                           aadrg_code: str = None,
                           mdc_code: str = None,
                           page_no: int = 1,
                           num_of_rows: int = 100) -> APIResponse:
        """KDRG 기준정보 조회
        
        Args:
            kdrg_code: KDRG 코드 (5자리)
            aadrg_code: AADRG 코드 (3자리)
            mdc_code: MDC 코드
            page_no: 페이지 번호
            num_of_rows: 페이지당 행 수
        
        Returns:
            APIResponse with KDRGInfo list
        """
        params = {
            'pageNo': page_no,
            'numOfRows': num_of_rows
        }
        
        if kdrg_code:
            params['kdrg_cd'] = kdrg_code
        if aadrg_code:
            params['aadrg_cd'] = aadrg_code
        if mdc_code:
            params['mdc_cd'] = mdc_code
        
        response = await self._make_request(self.endpoints['kdrg_info'], params)
        
        if response.success and response.data:
            # KDRGInfo 객체로 변환
            kdrg_list = []
            for item in response.data:
                kdrg_list.append(KDRGInfo(
                    kdrg_code=item.get('kdrgCd', ''),
                    kdrg_name=item.get('kdrgNm', ''),
                    aadrg_code=item.get('aadrgCd', ''),
                    aadrg_name=item.get('aadrgNm', ''),
                    mdc_code=item.get('mdcCd', ''),
                    mdc_name=item.get('mdcNm', ''),
                    cc_level=item.get('ccLvl', ''),
                    relative_weight=float(item.get('relWght', 0) or 0),
                    geometric_mean_los=float(item.get('geoAvgLos', 0) or 0),
                    arithmetic_mean_los=float(item.get('ariAvgLos', 0) or 0),
                    low_trim=int(item.get('lowTrim', 0) or 0),
                    high_trim=int(item.get('highTrim', 0) or 0)
                ))
            response.data = kdrg_list
        
        return response
    
    async def get_kdrg_weight(self,
                              year: str = None,
                              kdrg_code: str = None,
                              page_no: int = 1,
                              num_of_rows: int = 100) -> APIResponse:
        """KDRG 상대가치점수 조회
        
        Args:
            year: 적용 연도 (예: "2024")
            kdrg_code: KDRG 코드
            page_no: 페이지 번호
            num_of_rows: 페이지당 행 수
        """
        params = {
            'pageNo': page_no,
            'numOfRows': num_of_rows
        }
        
        if year:
            params['aplcYr'] = year
        if kdrg_code:
            params['kdrg_cd'] = kdrg_code
        
        return await self._make_request(self.endpoints['kdrg_weight'], params)
    
    # ========================
    # 병원 정보 조회
    # ========================
    
    async def get_hospital_list(self,
                                sido: str = None,
                                sigungu: str = None,
                                hospital_name: str = None,
                                hospital_type: str = None,
                                page_no: int = 1,
                                num_of_rows: int = 100) -> APIResponse:
        """병원 목록 조회
        
        Args:
            sido: 시/도 코드
            sigungu: 시/군/구 코드
            hospital_name: 병원명 (검색)
            hospital_type: 병원 종류 코드
            page_no: 페이지 번호
            num_of_rows: 페이지당 행 수
        """
        params = {
            'pageNo': page_no,
            'numOfRows': num_of_rows
        }
        
        if sido:
            params['sidoCd'] = sido
        if sigungu:
            params['sgguCd'] = sigungu
        if hospital_name:
            params['yadmNm'] = hospital_name
        if hospital_type:
            params['clCd'] = hospital_type
        
        response = await self._make_request(self.endpoints['hospital_list'], params)
        
        if response.success and response.data:
            hospital_list = []
            for item in response.data:
                hospital_list.append(HospitalInfo(
                    hospital_code=item.get('ykiho', ''),
                    hospital_name=item.get('yadmNm', ''),
                    address=item.get('addr', ''),
                    tel=item.get('telno', ''),
                    hospital_type=item.get('clCdNm', ''),
                    sido=item.get('sidoCdNm', ''),
                    sigungu=item.get('sgguCdNm', '')
                ))
            response.data = hospital_list
        
        return response
    
    async def get_hospital_detail(self, hospital_code: str) -> APIResponse:
        """병원 상세정보 조회
        
        Args:
            hospital_code: 요양기관번호
        """
        params = {'ykiho': hospital_code}
        return await self._make_request(self.endpoints['hospital_detail'], params)
    
    # ========================
    # 7개 DRG군 관련 조회
    # ========================
    
    async def get_7drg_info(self) -> APIResponse:
        """7개 DRG군 기준정보 조회
        
        포괄2차 적용 7개 DRG:
        - T01: 편도/축농증
        - T03: 수혈
        - X04: 망막/백내장
        - X05: 결석
        - T05: 중이염  
        - T11: 모낭염
        - T12: 치핵
        """
        seven_drg_codes = ['T01', 'T03', 'X04', 'X05', 'T05', 'T11', 'T12']
        all_results = []
        
        for code in seven_drg_codes:
            response = await self.get_kdrg_info(aadrg_code=code, num_of_rows=50)
            if response.success and response.data:
                all_results.extend(response.data)
        
        return APIResponse(
            success=True,
            status_code="00",
            message="7개 DRG군 정보 조회 완료",
            data=all_results,
            total_count=len(all_results)
        )
    
    # ========================
    # 유틸리티 메서드
    # ========================
    
    async def validate_kdrg_code(self, kdrg_code: str) -> Dict:
        """KDRG 코드 유효성 검증
        
        Returns:
            {
                'valid': bool,
                'kdrg_info': KDRGInfo or None,
                'message': str
            }
        """
        if not kdrg_code or len(kdrg_code) != 5:
            return {
                'valid': False,
                'kdrg_info': None,
                'message': 'KDRG 코드는 5자리여야 합니다.'
            }
        
        response = await self.get_kdrg_info(kdrg_code=kdrg_code)
        
        if response.success and response.data:
            return {
                'valid': True,
                'kdrg_info': response.data[0] if response.data else None,
                'message': 'KDRG 코드가 유효합니다.'
            }
        else:
            return {
                'valid': False,
                'kdrg_info': None,
                'message': f'KDRG 코드를 찾을 수 없습니다. ({response.message})'
            }
    
    async def get_kdrg_comparison(self, 
                                   current_kdrg: str, 
                                   alternative_kdrg: str) -> Dict:
        """두 KDRG 코드 비교
        
        수익성 차이 분석에 활용
        """
        current_resp = await self.get_kdrg_info(kdrg_code=current_kdrg)
        alt_resp = await self.get_kdrg_info(kdrg_code=alternative_kdrg)
        
        result = {
            'current': None,
            'alternative': None,
            'weight_difference': 0,
            'recommendation': ''
        }
        
        if current_resp.success and current_resp.data:
            result['current'] = current_resp.data[0]
        
        if alt_resp.success and alt_resp.data:
            result['alternative'] = alt_resp.data[0]
        
        if result['current'] and result['alternative']:
            current_weight = result['current'].relative_weight
            alt_weight = result['alternative'].relative_weight
            result['weight_difference'] = alt_weight - current_weight
            
            if result['weight_difference'] > 0:
                result['recommendation'] = f"대안 KDRG({alternative_kdrg})가 상대가치 {result['weight_difference']:.4f} 높음"
            elif result['weight_difference'] < 0:
                result['recommendation'] = f"현재 KDRG({current_kdrg})가 더 적합함"
            else:
                result['recommendation'] = "상대가치 동일"
        
        return result


# 전역 인스턴스
hira_api_service = HIRAAPIService()


# 테스트 함수
async def test_hira_api():
    """HIRA API 테스트 (API 키 필요)"""
    import os
    api_key = os.environ.get('DATA_GO_KR_API_KEY')
    
    if not api_key:
        print("API 키가 설정되지 않았습니다. DATA_GO_KR_API_KEY 환경변수를 설정하세요.")
        return
    
    service = HIRAAPIService(api_key)
    
    # KDRG 정보 조회 테스트
    print("\n=== KDRG 기준정보 조회 테스트 ===")
    response = await service.get_kdrg_info(aadrg_code="T01", num_of_rows=5)
    print(f"성공: {response.success}")
    print(f"데이터 수: {response.total_count}")
    if response.data:
        for item in response.data[:3]:
            print(f"  - {item.kdrg_code}: {item.kdrg_name} (상대가치: {item.relative_weight})")
    
    # 7개 DRG군 조회 테스트
    print("\n=== 7개 DRG군 조회 테스트 ===")
    response = await service.get_7drg_info()
    print(f"성공: {response.success}")
    print(f"데이터 수: {response.total_count}")


if __name__ == "__main__":
    asyncio.run(test_hira_api())
