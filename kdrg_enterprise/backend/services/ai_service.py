"""
AI/ML API 연동 서비스 모듈

OpenAI GPT 및 Anthropic Claude API를 통한 DRG 분석 보조
- DRG 코드 추천
- 진단명-DRG 매핑 제안
- 청구 최적화 분석
"""

import httpx
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class AIProvider(Enum):
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"


@dataclass
class AIAnalysisResult:
    """AI 분석 결과"""
    success: bool
    provider: str
    analysis_type: str
    result: Dict[str, Any]
    confidence: float
    raw_response: str
    tokens_used: int = 0


class AIService:
    """AI/ML 분석 서비스"""
    
    def __init__(
        self,
        openai_key: Optional[str] = None,
        claude_key: Optional[str] = None,
        gemini_key: Optional[str] = None,
    ):
        self.openai_key = openai_key
        self.claude_key = claude_key
        self.gemini_key = gemini_key
        
        self.openai_base_url = "https://api.openai.com/v1"
        self.claude_base_url = "https://api.anthropic.com/v1"
        self.gemini_base_url = "https://generativelanguage.googleapis.com/v1beta"
        
        self.timeout = 60.0
        
        # DRG 도메인 지식 (프롬프트에 활용)
        self.drg_context = """
        KDRG(Korean Diagnosis Related Groups)는 한국의 진단관련군 분류체계입니다.
        
        주요 구조:
        - MDC(주진단범주): 25개 대분류
        - AADRG(인접진단관련군): 3자리 코드
        - KDRG(한국형진단관련군): 5자리 코드 (AADRG + CC등급)
        
        7개 포괄수가 DRG군:
        - T01: 편도/축농증 수술
        - T03: 수혈 관련
        - X04: 망막/백내장 수술
        - X05: 결석 수술
        - T05: 중이염 수술
        - T11: 모낭염/농양 절개
        - T12: 치핵 수술
        
        CC(Complication/Comorbidity) 등급:
        - CC 등급이 높을수록 상대가치점수가 높아 수가가 증가함
        - 0: CC 없음, 1-4: CC 등급 (높을수록 중증)
        """
    
    def set_openai_key(self, key: str):
        """OpenAI API 키 설정"""
        self.openai_key = key
    
    def set_claude_key(self, key: str):
        """Claude API 키 설정"""
        self.claude_key = key
    
    def set_gemini_key(self, key: str):
        """Gemini API 키 설정"""
        self.gemini_key = key
    
    def _get_available_provider(self) -> Optional[AIProvider]:
        """사용 가능한 AI 제공자 반환"""
        if self.claude_key:
            return AIProvider.CLAUDE
        if self.openai_key:
            return AIProvider.OPENAI
        if self.gemini_key:
            return AIProvider.GEMINI
        return None
    
    # ========================
    # OpenAI API 호출
    # ========================
    
    async def _call_openai(self, 
                           messages: List[Dict],
                           model: str = "gpt-4o-mini",
                           temperature: float = 0.3,
                           max_tokens: int = 2000) -> Dict:
        """OpenAI API 호출"""
        if not self.openai_key:
            return {"error": "OpenAI API 키가 설정되지 않았습니다."}
        
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.openai_base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    return {"error": f"OpenAI API 오류: {response.status_code} - {response.text}"}
                
                return response.json()
                
        except Exception as e:
            logger.error(f"OpenAI API 오류: {e}")
            return {"error": str(e)}
    
    # ========================
    # Claude API 호출
    # ========================
    
    async def _call_claude(self,
                           messages: List[Dict],
                           model: str = "claude-sonnet-4-20250514",
                           temperature: float = 0.3,
                           max_tokens: int = 2000,
                           system_prompt: str = None) -> Dict:
        """Claude API 호출"""
        if not self.claude_key:
            return {"error": "Claude API 키가 설정되지 않았습니다."}
        
        headers = {
            "x-api-key": self.claude_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.claude_base_url}/messages",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    return {"error": f"Claude API 오류: {response.status_code} - {response.text}"}
                
                return response.json()
                
        except Exception as e:
            logger.error(f"Claude API 오류: {e}")
            return {"error": str(e)}
    
    # ========================
    # Gemini API 호출
    # ========================
    
    async def _call_gemini(
        self,
        messages: List[Dict],
        model: str = "gemini-1.5-flash",
        temperature: float = 0.3,
        max_tokens: int = 2000,
        system_prompt: str = None,
    ) -> Dict:
        """Gemini API 호출"""
        if not self.gemini_key:
            return {"error": "Gemini API 키가 설정되지 않았습니다."}
        
        # Gemini는 content 배열을 사용하므로 메시지를 단일 텍스트로 합칩니다.
        prompt_parts = []
        if system_prompt:
            prompt_parts.append(system_prompt)
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"{role.upper()}: {content}")
        prompt_text = "\n\n".join(prompt_parts)
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt_text}],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.gemini_base_url}/models/{model}:generateContent",
                    params={"key": self.gemini_key},
                    json=payload,
                )
                if response.status_code != 200:
                    return {"error": f"Gemini API 오류: {response.status_code} - {response.text}"}
                return response.json()
        except Exception as e:
            logger.error(f"Gemini API 오류: {e}")
            return {"error": str(e)}
    
    # ========================
    # DRG 분석 기능
    # ========================
    
    async def analyze_drg_recommendation(self, patient_data: Dict) -> AIAnalysisResult:
        """환자 데이터 기반 DRG 코드 추천 분석
        
        Args:
            patient_data: 환자 정보 (진단코드, 수술명, 재원일수 등)
        
        Returns:
            AIAnalysisResult with recommended DRG codes
        """
        provider = self._get_available_provider()
        if not provider:
            return AIAnalysisResult(
                success=False,
                provider="none",
                analysis_type="drg_recommendation",
                result={"error": "AI API 키가 설정되지 않았습니다."},
                confidence=0,
                raw_response=""
            )
        
        prompt = f"""
        다음 환자 정보를 분석하여 적절한 KDRG 코드를 추천해주세요.
        
        {self.drg_context}
        
        환자 정보:
        - 주진단코드: {patient_data.get('primary_diagnosis_code', 'N/A')}
        - 진단명: {patient_data.get('diagnosis_name', 'N/A')}
        - 현재 KDRG: {patient_data.get('kdrg_code', 'N/A')}
        - 현재 AADRG: {patient_data.get('aadrg_code', 'N/A')}
        - 수술명: {patient_data.get('surgery_name', 'N/A')}
        - 재원일수: {patient_data.get('length_of_stay', 'N/A')}일
        - 동반질환: {patient_data.get('comorbidities', 'N/A')}
        - 합병증: {patient_data.get('complications', 'N/A')}
        
        다음 JSON 형식으로 응답해주세요:
        {{
            "recommended_kdrg": "추천 KDRG 코드",
            "recommended_aadrg": "추천 AADRG 코드", 
            "cc_level": "추천 CC 등급 (0-4)",
            "reason": "추천 이유",
            "confidence": 0.0-1.0 사이의 신뢰도,
            "alternatives": ["대안1", "대안2"],
            "considerations": "고려사항"
        }}
        """
        
        messages = [{"role": "user", "content": prompt}]
        
        if provider == AIProvider.CLAUDE:
            response = await self._call_claude(
                messages, 
                system_prompt="당신은 의료 DRG 분류 전문가입니다. 정확하고 객관적인 분석을 제공하세요."
            )
            raw_text = response.get('content', [{}])[0].get('text', '') if 'content' in response else ''
            tokens = response.get('usage', {}).get('input_tokens', 0) + response.get('usage', {}).get('output_tokens', 0)
        elif provider == AIProvider.GEMINI:
            response = await self._call_gemini(
                messages,
                system_prompt="당신은 의료 DRG 분류 전문가입니다. 정확하고 객관적인 분석을 제공하세요."
            )
            raw_text = (
                response.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                if isinstance(response, dict)
                else ""
            )
            usage = response.get("usageMetadata", {}) if isinstance(response, dict) else {}
            tokens = usage.get("promptTokenCount", 0) + usage.get("candidatesTokenCount", 0)
        else:
            messages.insert(0, {
                "role": "system", 
                "content": "당신은 의료 DRG 분류 전문가입니다. 정확하고 객관적인 분석을 제공하세요."
            })
            response = await self._call_openai(messages)
            raw_text = response.get('choices', [{}])[0].get('message', {}).get('content', '') if 'choices' in response else ''
            tokens = response.get('usage', {}).get('total_tokens', 0)
        
        if 'error' in response:
            return AIAnalysisResult(
                success=False,
                provider=provider.value,
                analysis_type="drg_recommendation",
                result={"error": response['error']},
                confidence=0,
                raw_response=str(response)
            )
        
        # JSON 파싱 시도
        try:
            # JSON 블록 추출
            json_start = raw_text.find('{')
            json_end = raw_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(raw_text[json_start:json_end])
            else:
                result = {"raw_analysis": raw_text}
        except json.JSONDecodeError:
            result = {"raw_analysis": raw_text}
        
        return AIAnalysisResult(
            success=True,
            provider=provider.value,
            analysis_type="drg_recommendation",
            result=result,
            confidence=result.get('confidence', 0.7) if isinstance(result, dict) else 0.7,
            raw_response=raw_text,
            tokens_used=tokens
        )
    
    async def analyze_claim_optimization(self, 
                                         patient_data: Dict,
                                         kdrg_alternatives: List[Dict] = None) -> AIAnalysisResult:
        """청구 최적화 분석
        
        현재 DRG 코드와 대안 코드들을 비교하여 최적의 청구 방안 제안
        """
        provider = self._get_available_provider()
        if not provider:
            return AIAnalysisResult(
                success=False,
                provider="none",
                analysis_type="claim_optimization",
                result={"error": "AI API 키가 설정되지 않았습니다."},
                confidence=0,
                raw_response=""
            )
        
        alternatives_text = ""
        if kdrg_alternatives:
            alternatives_text = "\n".join([
                f"- {alt.get('kdrg_code')}: 상대가치 {alt.get('relative_weight', 'N/A')}"
                for alt in kdrg_alternatives
            ])
        
        prompt = f"""
        다음 환자의 DRG 청구 최적화 방안을 분석해주세요.
        
        {self.drg_context}
        
        환자 정보:
        - 현재 KDRG: {patient_data.get('kdrg_code', 'N/A')}
        - 현재 상대가치: {patient_data.get('relative_weight', 'N/A')}
        - 주진단: {patient_data.get('primary_diagnosis_code', 'N/A')}
        - 수술: {patient_data.get('surgery_name', 'N/A')}
        - 재원일수: {patient_data.get('length_of_stay', 'N/A')}일
        
        대안 KDRG 코드들:
        {alternatives_text if alternatives_text else '없음'}
        
        다음 JSON 형식으로 응답해주세요:
        {{
            "optimal_kdrg": "최적 KDRG 코드",
            "expected_benefit": "예상 수익 증가 (% 또는 금액)",
            "action_items": ["필요한 조치1", "필요한 조치2"],
            "documentation_needs": ["필요한 문서/기록1", "필요한 문서/기록2"],
            "risk_factors": ["위험요소1", "위험요소2"],
            "confidence": 0.0-1.0 사이의 신뢰도
        }}
        """
        
        messages = [{"role": "user", "content": prompt}]
        
        if provider == AIProvider.CLAUDE:
            response = await self._call_claude(
                messages,
                system_prompt="당신은 의료 청구 및 DRG 최적화 전문가입니다. 합법적이고 윤리적인 최적화 방안만 제안하세요."
            )
            raw_text = response.get('content', [{}])[0].get('text', '') if 'content' in response else ''
            tokens = response.get('usage', {}).get('input_tokens', 0) + response.get('usage', {}).get('output_tokens', 0)
        elif provider == AIProvider.GEMINI:
            response = await self._call_gemini(
                messages,
                system_prompt="당신은 의료 청구 및 DRG 최적화 전문가입니다. 합법적이고 윤리적인 최적화 방안만 제안하세요."
            )
            raw_text = (
                response.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                if isinstance(response, dict)
                else ""
            )
            usage = response.get("usageMetadata", {}) if isinstance(response, dict) else {}
            tokens = usage.get("promptTokenCount", 0) + usage.get("candidatesTokenCount", 0)
        else:
            messages.insert(0, {
                "role": "system",
                "content": "당신은 의료 청구 및 DRG 최적화 전문가입니다. 합법적이고 윤리적인 최적화 방안만 제안하세요."
            })
            response = await self._call_openai(messages)
            raw_text = response.get('choices', [{}])[0].get('message', {}).get('content', '') if 'choices' in response else ''
            tokens = response.get('usage', {}).get('total_tokens', 0)
        
        if 'error' in response:
            return AIAnalysisResult(
                success=False,
                provider=provider.value,
                analysis_type="claim_optimization",
                result={"error": response['error']},
                confidence=0,
                raw_response=str(response)
            )
        
        try:
            json_start = raw_text.find('{')
            json_end = raw_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(raw_text[json_start:json_end])
            else:
                result = {"raw_analysis": raw_text}
        except json.JSONDecodeError:
            result = {"raw_analysis": raw_text}
        
        return AIAnalysisResult(
            success=True,
            provider=provider.value,
            analysis_type="claim_optimization",
            result=result,
            confidence=result.get('confidence', 0.7) if isinstance(result, dict) else 0.7,
            raw_response=raw_text,
            tokens_used=tokens
        )
    
    async def analyze_diagnosis_drg_mapping(self, 
                                            diagnosis_code: str,
                                            diagnosis_name: str = None) -> AIAnalysisResult:
        """진단코드-DRG 매핑 분석
        
        KCD 진단코드를 입력받아 가능한 DRG 코드들을 분석
        """
        provider = self._get_available_provider()
        if not provider:
            return AIAnalysisResult(
                success=False,
                provider="none",
                analysis_type="diagnosis_mapping",
                result={"error": "AI API 키가 설정되지 않았습니다."},
                confidence=0,
                raw_response=""
            )
        
        prompt = f"""
        다음 진단코드에 해당할 수 있는 KDRG 코드들을 분석해주세요.
        
        {self.drg_context}
        
        진단 정보:
        - KCD 진단코드: {diagnosis_code}
        - 진단명: {diagnosis_name or '미제공'}
        
        다음 JSON 형식으로 응답해주세요:
        {{
            "mdc_code": "해당 MDC 코드",
            "mdc_name": "MDC 명칭",
            "possible_aadrg": [
                {{"code": "AADRG1", "name": "명칭1", "probability": 0.8}},
                {{"code": "AADRG2", "name": "명칭2", "probability": 0.6}}
            ],
            "is_7drg": true/false,
            "drg_7_type": "7개 DRG군 해당 시 유형 (T01, T03 등)",
            "notes": "참고사항"
        }}
        """
        
        messages = [{"role": "user", "content": prompt}]
        
        if provider == AIProvider.CLAUDE:
            response = await self._call_claude(messages)
            raw_text = response.get('content', [{}])[0].get('text', '') if 'content' in response else ''
            tokens = response.get('usage', {}).get('input_tokens', 0) + response.get('usage', {}).get('output_tokens', 0)
        elif provider == AIProvider.GEMINI:
            response = await self._call_gemini(messages)
            raw_text = (
                response.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                if isinstance(response, dict)
                else ""
            )
            usage = response.get("usageMetadata", {}) if isinstance(response, dict) else {}
            tokens = usage.get("promptTokenCount", 0) + usage.get("candidatesTokenCount", 0)
        else:
            response = await self._call_openai(messages)
            raw_text = response.get('choices', [{}])[0].get('message', {}).get('content', '') if 'choices' in response else ''
            tokens = response.get('usage', {}).get('total_tokens', 0)
        
        if 'error' in response:
            return AIAnalysisResult(
                success=False,
                provider=provider.value,
                analysis_type="diagnosis_mapping",
                result={"error": response['error']},
                confidence=0,
                raw_response=str(response)
            )
        
        try:
            json_start = raw_text.find('{')
            json_end = raw_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(raw_text[json_start:json_end])
            else:
                result = {"raw_analysis": raw_text}
        except json.JSONDecodeError:
            result = {"raw_analysis": raw_text}
        
        return AIAnalysisResult(
            success=True,
            provider=provider.value,
            analysis_type="diagnosis_mapping",
            result=result,
            confidence=0.75,
            raw_response=raw_text,
            tokens_used=tokens
        )
    
    async def generate_audit_report(self, 
                                    patients_summary: Dict,
                                    optimization_results: List[Dict] = None) -> AIAnalysisResult:
        """심사 대비 보고서 생성
        
        DRG 청구 현황을 분석하여 심사 대비 보고서 초안 생성
        """
        provider = self._get_available_provider()
        if not provider:
            return AIAnalysisResult(
                success=False,
                provider="none",
                analysis_type="audit_report",
                result={"error": "AI API 키가 설정되지 않았습니다."},
                confidence=0,
                raw_response=""
            )
        
        prompt = f"""
        다음 DRG 청구 현황을 바탕으로 심평원 심사 대비 보고서 초안을 작성해주세요.
        
        청구 현황 요약:
        - 총 환자 수: {patients_summary.get('total_patients', 'N/A')}명
        - 총 청구 금액: {patients_summary.get('total_claim', 'N/A')}원
        - 평균 재원일수: {patients_summary.get('avg_los', 'N/A')}일
        - 7개 DRG군 환자 비율: {patients_summary.get('drg7_ratio', 'N/A')}%
        
        최적화 추천 건수: {len(optimization_results) if optimization_results else 0}건
        
        다음 구조로 보고서를 작성해주세요:
        
        1. 요약
        2. 주요 지표 분석
        3. 7개 DRG군 현황
        4. 개선 권고사항
        5. 심사 대비 체크리스트
        """
        
        messages = [{"role": "user", "content": prompt}]
        
        if provider == AIProvider.CLAUDE:
            response = await self._call_claude(
                messages,
                max_tokens=4000,
                system_prompt="당신은 의료 DRG 심사 및 청구 전문가입니다. 전문적이고 체계적인 보고서를 작성하세요."
            )
            raw_text = response.get('content', [{}])[0].get('text', '') if 'content' in response else ''
            tokens = response.get('usage', {}).get('input_tokens', 0) + response.get('usage', {}).get('output_tokens', 0)
        elif provider == AIProvider.GEMINI:
            response = await self._call_gemini(
                messages,
                max_tokens=4000,
                system_prompt="당신은 의료 DRG 심사 및 청구 전문가입니다. 전문적이고 체계적인 보고서를 작성하세요."
            )
            raw_text = (
                response.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                if isinstance(response, dict)
                else ""
            )
            usage = response.get("usageMetadata", {}) if isinstance(response, dict) else {}
            tokens = usage.get("promptTokenCount", 0) + usage.get("candidatesTokenCount", 0)
        else:
            messages.insert(0, {
                "role": "system",
                "content": "당신은 의료 DRG 심사 및 청구 전문가입니다. 전문적이고 체계적인 보고서를 작성하세요."
            })
            response = await self._call_openai(messages, max_tokens=4000)
            raw_text = response.get('choices', [{}])[0].get('message', {}).get('content', '') if 'choices' in response else ''
            tokens = response.get('usage', {}).get('total_tokens', 0)
        
        if 'error' in response:
            return AIAnalysisResult(
                success=False,
                provider=provider.value,
                analysis_type="audit_report",
                result={"error": response['error']},
                confidence=0,
                raw_response=str(response)
            )
        
        return AIAnalysisResult(
            success=True,
            provider=provider.value,
            analysis_type="audit_report",
            result={"report": raw_text},
            confidence=0.85,
            raw_response=raw_text,
            tokens_used=tokens
        )


# 전역 인스턴스
ai_service = AIService()


# 테스트 함수
async def test_ai_service():
    """AI 서비스 테스트"""
    import os
    
    openai_key = os.environ.get('OPENAI_API_KEY')
    claude_key = os.environ.get('CLAUDE_API_KEY')
    gemini_key = os.environ.get('GEMINI_API_KEY')
    
    if not openai_key and not claude_key and not gemini_key:
        print("AI API 키가 설정되지 않았습니다.")
        print("OPENAI_API_KEY, CLAUDE_API_KEY 또는 GEMINI_API_KEY 환경변수를 설정하세요.")
        return
    
    service = AIService(openai_key=openai_key, claude_key=claude_key, gemini_key=gemini_key)
    
    # 테스트 환자 데이터
    test_patient = {
        'primary_diagnosis_code': 'J35.0',
        'diagnosis_name': '만성 편도염',
        'kdrg_code': 'T0110',
        'aadrg_code': 'T01',
        'surgery_name': '편도절제술',
        'length_of_stay': 3,
        'comorbidities': '고혈압',
        'complications': '없음'
    }
    
    print("\n=== DRG 추천 분석 테스트 ===")
    result = await service.analyze_drg_recommendation(test_patient)
    print(f"성공: {result.success}")
    print(f"제공자: {result.provider}")
    print(f"결과: {result.result}")
    print(f"토큰 사용: {result.tokens_used}")


if __name__ == "__main__":
    asyncio.run(test_ai_service())
