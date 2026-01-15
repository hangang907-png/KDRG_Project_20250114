"""
심평원 요양기관업무포털 자동화 서비스
- 요양기관업무포털(biz.hira.or.kr) 자동 로그인
- 환류데이터 자동 다운로드
- 다운로드된 파일 자동 파싱

주의: 실제 운영 시에는 심평원 정책 및 이용약관을 준수해야 함
     공동인증서 로그인은 복잡한 보안 절차가 필요하므로,
     현재 구현은 ID/PW 로그인 및 시뮬레이션 기반
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class PortalLoginMethod(Enum):
    """로그인 방법"""
    ID_PASSWORD = "id_password"  # 아이디/비밀번호
    CERTIFICATE = "certificate"  # 공동인증서
    SIMPLE_AUTH = "simple_auth"  # 간편인증 (카카오, 네이버 등)


class DownloadStatus(Enum):
    """다운로드 상태"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PortalCredentials:
    """포털 로그인 자격증명"""
    hospital_code: str  # 요양기관번호
    user_id: str  # 사용자 ID
    password: str  # 비밀번호
    login_method: PortalLoginMethod = PortalLoginMethod.ID_PASSWORD
    certificate_path: Optional[str] = None  # 공동인증서 경로
    certificate_password: Optional[str] = None  # 인증서 비밀번호


@dataclass
class FeedbackFileInfo:
    """환류파일 정보"""
    file_id: str
    file_name: str
    file_date: str  # 생성일
    file_type: str  # 파일 유형 (청구환류, 심사환류 등)
    file_size: int  # 바이트
    download_url: str
    is_new: bool  # 신규 파일 여부
    downloaded: bool = False
    local_path: Optional[str] = None


@dataclass
class DownloadResult:
    """다운로드 결과"""
    success: bool
    file_info: FeedbackFileInfo
    local_path: Optional[str]
    error_message: Optional[str] = None
    download_time: float = 0.0  # 소요 시간 (초)


@dataclass
class AutoDownloadConfig:
    """자동 다운로드 설정"""
    enabled: bool = False
    schedule_time: str = "06:00"  # 매일 실행 시간
    download_path: str = "./downloads/feedback"
    file_types: List[str] = None  # 다운로드할 파일 유형 (None이면 모두)
    days_to_keep: int = 90  # 파일 보관 기간
    notify_on_download: bool = True  # 다운로드 완료 알림
    auto_parse: bool = True  # 다운로드 후 자동 파싱
    
    def __post_init__(self):
        if self.file_types is None:
            self.file_types = ["청구환류", "심사환류", "전산매체환류"]


class HIRAPortalService:
    """심평원 요양기관업무포털 서비스"""
    
    PORTAL_BASE_URL = "https://biz.hira.or.kr"
    LOGIN_URL = f"{PORTAL_BASE_URL}/login.do"
    FEEDBACK_LIST_URL = f"{PORTAL_BASE_URL}/portal/feedback/list.do"
    FEEDBACK_DOWNLOAD_URL = f"{PORTAL_BASE_URL}/portal/feedback/download.do"
    
    def __init__(self, download_dir: str = "./downloads/feedback"):
        self.download_dir = download_dir
        self.session = None
        self.is_logged_in = False
        self.credentials: Optional[PortalCredentials] = None
        self.config = AutoDownloadConfig()
        self._ensure_download_dir()
    
    def _ensure_download_dir(self):
        """다운로드 디렉토리 생성"""
        Path(self.download_dir).mkdir(parents=True, exist_ok=True)
    
    def set_credentials(self, credentials: PortalCredentials) -> bool:
        """자격증명 설정"""
        self.credentials = credentials
        logger.info(f"Portal credentials set for hospital: {credentials.hospital_code}")
        return True
    
    def set_config(self, config: AutoDownloadConfig):
        """자동 다운로드 설정"""
        self.config = config
        self.download_dir = config.download_path
        self._ensure_download_dir()
    
    async def login(self) -> Tuple[bool, str]:
        """포털 로그인
        
        주의: 실제 구현 시 Selenium 또는 Playwright 사용 필요
        현재는 시뮬레이션 모드
        """
        if not self.credentials:
            return (False, "자격증명이 설정되지 않았습니다.")
        
        try:
            logger.info(f"Attempting portal login for: {self.credentials.hospital_code}")
            
            # 실제 구현 시:
            # 1. Selenium WebDriver 초기화
            # 2. 로그인 페이지 접속
            # 3. ID/PW 입력 또는 공동인증서 선택
            # 4. 로그인 버튼 클릭
            # 5. 로그인 성공 여부 확인
            
            # 시뮬레이션: 로그인 성공 가정
            await asyncio.sleep(0.5)  # 네트워크 지연 시뮬레이션
            
            if self.credentials.login_method == PortalLoginMethod.CERTIFICATE:
                # 공동인증서 로그인은 추가 구현 필요
                return (False, "공동인증서 로그인은 아직 지원되지 않습니다. ID/PW 로그인을 사용하세요.")
            
            # 로그인 성공 시뮬레이션
            self.is_logged_in = True
            logger.info("Portal login successful (simulation mode)")
            
            return (True, "로그인 성공")
            
        except Exception as e:
            logger.error(f"Portal login failed: {e}")
            return (False, f"로그인 실패: {str(e)}")
    
    async def logout(self) -> bool:
        """포털 로그아웃"""
        if self.session:
            # 세션 정리
            pass
        self.is_logged_in = False
        logger.info("Portal logged out")
        return True
    
    async def get_feedback_file_list(
        self, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        file_type: Optional[str] = None
    ) -> List[FeedbackFileInfo]:
        """환류파일 목록 조회
        
        Args:
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            file_type: 파일 유형 필터
            
        Returns:
            환류파일 목록
        """
        if not self.is_logged_in:
            logger.warning("Not logged in. Please login first.")
            return []
        
        try:
            # 기본 날짜 범위: 최근 30일
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            
            logger.info(f"Fetching feedback files: {start_date} ~ {end_date}")
            
            # 실제 구현 시: 
            # 1. 환류데이터 목록 페이지 접속
            # 2. 검색 조건 설정 (날짜, 유형 등)
            # 3. 목록 파싱
            
            # 시뮬레이션: 예시 파일 목록 반환
            await asyncio.sleep(0.3)
            
            # 시뮬레이션 데이터
            sample_files = [
                FeedbackFileInfo(
                    file_id="FB2025010001",
                    file_name="청구환류_2025년01월_외래.xlsx",
                    file_date="2025-01-10",
                    file_type="청구환류",
                    file_size=1024 * 500,  # 500KB
                    download_url=f"{self.FEEDBACK_DOWNLOAD_URL}?id=FB2025010001",
                    is_new=True,
                ),
                FeedbackFileInfo(
                    file_id="FB2025010002",
                    file_name="심사환류_2025년01월_입원.xlsx",
                    file_date="2025-01-08",
                    file_type="심사환류",
                    file_size=1024 * 800,  # 800KB
                    download_url=f"{self.FEEDBACK_DOWNLOAD_URL}?id=FB2025010002",
                    is_new=True,
                ),
                FeedbackFileInfo(
                    file_id="FB2024120001",
                    file_name="전산매체환류_2024년12월.xlsx",
                    file_date="2024-12-20",
                    file_type="전산매체환류",
                    file_size=1024 * 300,  # 300KB
                    download_url=f"{self.FEEDBACK_DOWNLOAD_URL}?id=FB2024120001",
                    is_new=False,
                ),
            ]
            
            # 파일 유형 필터
            if file_type:
                sample_files = [f for f in sample_files if f.file_type == file_type]
            
            # 날짜 필터
            sample_files = [
                f for f in sample_files
                if start_date <= f.file_date <= end_date
            ]
            
            return sample_files
            
        except Exception as e:
            logger.error(f"Failed to get feedback file list: {e}")
            return []
    
    async def download_file(self, file_info: FeedbackFileInfo) -> DownloadResult:
        """환류파일 다운로드
        
        Args:
            file_info: 다운로드할 파일 정보
            
        Returns:
            다운로드 결과
        """
        if not self.is_logged_in:
            return DownloadResult(
                success=False,
                file_info=file_info,
                local_path=None,
                error_message="로그인이 필요합니다.",
            )
        
        start_time = datetime.now()
        
        try:
            logger.info(f"Downloading file: {file_info.file_name}")
            
            # 실제 구현 시:
            # 1. 다운로드 URL 접속
            # 2. 파일 다운로드
            # 3. 로컬 저장
            
            # 시뮬레이션: 파일 다운로드
            await asyncio.sleep(0.5)  # 다운로드 시뮬레이션
            
            # 로컬 파일 경로
            local_path = os.path.join(
                self.download_dir, 
                f"{datetime.now().strftime('%Y%m%d')}_{file_info.file_name}"
            )
            
            # 시뮬레이션: 빈 파일 생성 (실제로는 다운로드된 파일)
            # with open(local_path, 'wb') as f:
            #     f.write(b"")  # 실제 파일 내용
            
            download_time = (datetime.now() - start_time).total_seconds()
            
            file_info.downloaded = True
            file_info.local_path = local_path
            
            logger.info(f"Download complete: {file_info.file_name} ({download_time:.2f}s)")
            
            return DownloadResult(
                success=True,
                file_info=file_info,
                local_path=local_path,
                download_time=download_time,
            )
            
        except Exception as e:
            logger.error(f"Download failed: {file_info.file_name} - {e}")
            return DownloadResult(
                success=False,
                file_info=file_info,
                local_path=None,
                error_message=str(e),
            )
    
    async def download_all_new_files(self) -> List[DownloadResult]:
        """모든 신규 파일 다운로드"""
        if not self.is_logged_in:
            # 자동 로그인 시도
            success, message = await self.login()
            if not success:
                return []
        
        # 파일 목록 조회
        files = await self.get_feedback_file_list()
        new_files = [f for f in files if f.is_new and not f.downloaded]
        
        if not new_files:
            logger.info("No new files to download")
            return []
        
        # 설정된 파일 유형만 다운로드
        if self.config.file_types:
            new_files = [f for f in new_files if f.file_type in self.config.file_types]
        
        results = []
        for file_info in new_files:
            result = await self.download_file(file_info)
            results.append(result)
        
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Downloaded {success_count}/{len(results)} files")
        
        return results
    
    async def auto_download_and_parse(self) -> Dict[str, Any]:
        """자동 다운로드 및 파싱 (스케줄러용)"""
        if not self.config.enabled:
            return {"success": False, "message": "자동 다운로드가 비활성화되어 있습니다."}
        
        results = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "downloaded_files": [],
            "parsed_files": [],
            "errors": [],
        }
        
        try:
            # 로그인
            login_success, login_message = await self.login()
            if not login_success:
                results["success"] = False
                results["errors"].append(login_message)
                return results
            
            # 다운로드
            download_results = await self.download_all_new_files()
            
            for dr in download_results:
                if dr.success:
                    results["downloaded_files"].append({
                        "file_name": dr.file_info.file_name,
                        "local_path": dr.local_path,
                        "download_time": dr.download_time,
                    })
                    
                    # 자동 파싱
                    if self.config.auto_parse and dr.local_path:
                        # feedback_parser_service 호출
                        # parsed = feedback_parser.parse_file(dr.local_path)
                        results["parsed_files"].append(dr.file_info.file_name)
                else:
                    results["errors"].append(dr.error_message)
            
            # 로그아웃
            await self.logout()
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))
        
        return results
    
    def get_download_history(self, limit: int = 50) -> List[Dict]:
        """다운로드 이력 조회"""
        history_file = os.path.join(self.download_dir, "download_history.json")
        
        if not os.path.exists(history_file):
            return []
        
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            return history[-limit:]
        except Exception:
            return []
    
    def _save_download_history(self, result: DownloadResult):
        """다운로드 이력 저장"""
        history_file = os.path.join(self.download_dir, "download_history.json")
        
        try:
            history = []
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            
            history.append({
                "file_id": result.file_info.file_id,
                "file_name": result.file_info.file_name,
                "file_type": result.file_info.file_type,
                "downloaded_at": datetime.now().isoformat(),
                "success": result.success,
                "local_path": result.local_path,
                "error": result.error_message,
            })
            
            # 최근 1000개만 유지
            history = history[-1000:]
            
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save download history: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """서비스 상태 조회"""
        return {
            "is_logged_in": self.is_logged_in,
            "credentials_set": self.credentials is not None,
            "hospital_code": self.credentials.hospital_code if self.credentials else None,
            "config": {
                "enabled": self.config.enabled,
                "schedule_time": self.config.schedule_time,
                "download_path": self.config.download_path,
                "auto_parse": self.config.auto_parse,
            },
            "download_dir": self.download_dir,
            "download_dir_exists": os.path.exists(self.download_dir),
        }


# 서비스 인스턴스
hira_portal_service = HIRAPortalService()
