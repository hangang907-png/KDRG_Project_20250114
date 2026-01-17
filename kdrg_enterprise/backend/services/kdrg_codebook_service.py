"""
KDRG 코드북 동기화 서비스
- 심평원 API에서 KDRG 데이터 가져오기
- SQLite DB에 저장 및 조회
"""

import sqlite3
import os
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# DB 경로
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'kdrg.db')


@dataclass
class KDRGCodebookEntry:
    """KDRG 코드북 엔트리"""
    kdrg_code: str
    kdrg_name: str
    aadrg_code: str
    aadrg_name: Optional[str] = None
    mdc_code: Optional[str] = None
    mdc_name: Optional[str] = None
    cc_level: Optional[str] = None
    relative_weight: float = 0.0
    geometric_mean_los: float = 0.0
    arithmetic_mean_los: float = 0.0
    low_trim: int = 0
    high_trim: int = 0
    version: str = "V4.6"
    synced_at: Optional[str] = None


class KDRGCodebookService:
    """KDRG 코드북 관리 서비스"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._ensure_table()
    
    def _get_connection(self) -> sqlite3.Connection:
        """DB 연결 반환"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_table(self):
        """코드북 테이블 생성"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # KDRG 코드북 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS kdrg_codebook (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kdrg_code TEXT NOT NULL UNIQUE,
                    kdrg_name TEXT NOT NULL,
                    aadrg_code TEXT,
                    aadrg_name TEXT,
                    mdc_code TEXT,
                    mdc_name TEXT,
                    cc_level TEXT,
                    relative_weight REAL DEFAULT 0,
                    geometric_mean_los REAL DEFAULT 0,
                    arithmetic_mean_los REAL DEFAULT 0,
                    low_trim INTEGER DEFAULT 0,
                    high_trim INTEGER DEFAULT 0,
                    version TEXT DEFAULT 'V4.6',
                    synced_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 동기화 메타데이터 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_type TEXT NOT NULL,
                    last_sync_at TEXT,
                    total_records INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'success',
                    message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 인덱스 생성
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_kdrg_code ON kdrg_codebook(kdrg_code)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_aadrg_code ON kdrg_codebook(aadrg_code)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_mdc_code ON kdrg_codebook(mdc_code)')
            
            conn.commit()
    
    def save_codebook_entries(self, entries: List[Dict]) -> int:
        """코드북 엔트리 저장 (UPSERT)"""
        if not entries:
            return 0
        
        synced_at = datetime.now().isoformat()
        saved_count = 0
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            for entry in entries:
                try:
                    cursor.execute('''
                        INSERT INTO kdrg_codebook (
                            kdrg_code, kdrg_name, aadrg_code, aadrg_name,
                            mdc_code, mdc_name, cc_level, relative_weight,
                            geometric_mean_los, arithmetic_mean_los,
                            low_trim, high_trim, version, synced_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(kdrg_code) DO UPDATE SET
                            kdrg_name = excluded.kdrg_name,
                            aadrg_code = excluded.aadrg_code,
                            aadrg_name = excluded.aadrg_name,
                            mdc_code = excluded.mdc_code,
                            mdc_name = excluded.mdc_name,
                            cc_level = excluded.cc_level,
                            relative_weight = excluded.relative_weight,
                            geometric_mean_los = excluded.geometric_mean_los,
                            arithmetic_mean_los = excluded.arithmetic_mean_los,
                            low_trim = excluded.low_trim,
                            high_trim = excluded.high_trim,
                            version = excluded.version,
                            synced_at = excluded.synced_at,
                            updated_at = excluded.updated_at
                    ''', (
                        entry.get('kdrg_code', ''),
                        entry.get('kdrg_name', ''),
                        entry.get('aadrg_code', ''),
                        entry.get('aadrg_name', ''),
                        entry.get('mdc_code', ''),
                        entry.get('mdc_name', ''),
                        entry.get('cc_level', ''),
                        float(entry.get('relative_weight', 0) or 0),
                        float(entry.get('geometric_mean_los', 0) or 0),
                        float(entry.get('arithmetic_mean_los', 0) or 0),
                        int(entry.get('low_trim', 0) or 0),
                        int(entry.get('high_trim', 0) or 0),
                        entry.get('version', 'V4.6'),
                        synced_at,
                        synced_at
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Error saving entry {entry.get('kdrg_code')}: {e}")
            
            conn.commit()
        
        return saved_count
    
    def update_sync_metadata(self, sync_type: str, total_records: int, status: str = 'success', message: str = None):
        """동기화 메타데이터 업데이트"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sync_metadata (sync_type, last_sync_at, total_records, status, message)
                VALUES (?, ?, ?, ?, ?)
            ''', (sync_type, datetime.now().isoformat(), total_records, status, message))
            conn.commit()
    
    def get_sync_status(self) -> Dict:
        """동기화 상태 조회"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 마지막 동기화 정보
            cursor.execute('''
                SELECT * FROM sync_metadata
                WHERE sync_type = 'kdrg_codebook'
                ORDER BY created_at DESC LIMIT 1
            ''')
            last_sync = cursor.fetchone()
            
            # 코드북 통계
            cursor.execute('SELECT COUNT(*) as total FROM kdrg_codebook')
            total = cursor.fetchone()['total']
            
            return {
                'has_codebook': total > 0,
                'total_codes': total,
                'last_sync': dict(last_sync) if last_sync else None
            }
    
    def get_codebook(
        self,
        page: int = 1,
        per_page: int = 50,
        search: str = None,
        aadrg: str = None,
        mdc: str = None
    ) -> Dict:
        """코드북 조회"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 기본 쿼리
            query = 'SELECT * FROM kdrg_codebook WHERE 1=1'
            params = []
            
            if search:
                query += ' AND (kdrg_code LIKE ? OR kdrg_name LIKE ?)'
                params.extend([f'%{search}%', f'%{search}%'])
            
            if aadrg:
                query += ' AND aadrg_code LIKE ?'
                params.append(f'{aadrg}%')
            
            if mdc:
                query += ' AND mdc_code = ?'
                params.append(mdc)
            
            # 카운트
            count_query = query.replace('SELECT *', 'SELECT COUNT(*) as total')
            cursor.execute(count_query, params)
            total = cursor.fetchone()['total']
            
            # 페이징
            query += ' ORDER BY kdrg_code LIMIT ? OFFSET ?'
            params.extend([per_page, (page - 1) * per_page])
            
            cursor.execute(query, params)
            codes = [dict(row) for row in cursor.fetchall()]
            
            return {
                'total': total,
                'page': page,
                'per_page': per_page,
                'codes': codes
            }
    
    def get_kdrg_info(self, kdrg_code: str) -> Optional[Dict]:
        """특정 KDRG 코드 정보 조회"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM kdrg_codebook WHERE kdrg_code = ?', (kdrg_code.upper(),))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def search_kdrg(self, query: str, limit: int = 50) -> List[Dict]:
        """KDRG 검색"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM kdrg_codebook
                WHERE kdrg_code LIKE ? OR kdrg_name LIKE ? OR aadrg_name LIKE ?
                LIMIT ?
            ''', (f'%{query}%', f'%{query}%', f'%{query}%', limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def validate_kdrg_code(self, kdrg_code: str) -> Dict:
        """KDRG 코드 유효성 검증"""
        info = self.get_kdrg_info(kdrg_code)
        
        if info:
            return {
                'valid': True,
                'kdrg_code': kdrg_code,
                'message': '유효한 KDRG 코드입니다.',
                'kdrg_info': info
            }
        
        # 코드북에 데이터가 있는지 확인
        status = self.get_sync_status()
        if not status['has_codebook']:
            return {
                'valid': True,  # 코드북이 없으면 형식만 검증
                'kdrg_code': kdrg_code,
                'message': '코드북이 동기화되지 않아 형식만 검증되었습니다.',
                'kdrg_info': None
            }
        
        return {
            'valid': False,
            'kdrg_code': kdrg_code,
            'message': '코드북에서 해당 KDRG 코드를 찾을 수 없습니다.',
            'kdrg_info': None
        }
    
    def get_alternatives(self, kdrg_code: str) -> List[Dict]:
        """동일 AADRG 내 대안 KDRG 조회"""
        info = self.get_kdrg_info(kdrg_code)
        if not info:
            return []
        
        aadrg_code = info.get('aadrg_code', '')[:3]  # 앞 3자리로 그룹핑
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM kdrg_codebook
                WHERE aadrg_code LIKE ? AND kdrg_code != ?
                ORDER BY relative_weight DESC
            ''', (f'{aadrg_code}%', kdrg_code))
            return [dict(row) for row in cursor.fetchall()]


# 전역 서비스 인스턴스
codebook_service = KDRGCodebookService()
