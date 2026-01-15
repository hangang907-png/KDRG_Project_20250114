import hashlib
import re
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from typing import Optional
import os


class PrivacyProtector:
    """개인정보 보호 모듈 - 익명화 및 암호화"""
    
    def __init__(self, encryption_key: str = None):
        self.encryption_key = encryption_key or os.environ.get('ENCRYPTION_KEY', 'default-key-32-bytes-needed!!')
        self._fernet = self._create_fernet()
    
    def _create_fernet(self) -> Fernet:
        """Fernet 암호화 객체 생성"""
        # Derive a proper key from the encryption key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'kdrg_enterprise_salt',
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.encryption_key.encode()))
        return Fernet(key)
    
    # ========================
    # 익명화 (Masking) 기능
    # ========================
    
    def mask_name(self, name: str) -> str:
        """환자 이름 마스킹
        
        예시:
        - 홍길동 → 홍*동
        - 김철수 → 김*수
        - John Doe → J*** D**
        """
        if not name or len(name) < 2:
            return "***"
        
        # 한글 이름 처리
        if re.match(r'^[가-힣]+$', name):
            if len(name) == 2:
                return name[0] + "*"
            elif len(name) == 3:
                return name[0] + "*" + name[2]
            else:
                return name[0] + "*" * (len(name) - 2) + name[-1]
        
        # 영문 이름 처리
        parts = name.split()
        masked_parts = []
        for part in parts:
            if len(part) <= 1:
                masked_parts.append("*")
            else:
                masked_parts.append(part[0] + "*" * (len(part) - 1))
        return " ".join(masked_parts)
    
    def mask_patient_id(self, patient_id: str) -> str:
        """환자 등록번호 마스킹
        
        예시:
        - P00123456 → P00***456
        - 12345678 → 1234****
        """
        if not patient_id or len(patient_id) < 4:
            return "****"
        
        length = len(patient_id)
        visible_start = length // 3
        visible_end = length // 3
        mask_length = length - visible_start - visible_end
        
        return patient_id[:visible_start] + "*" * mask_length + patient_id[-visible_end:]
    
    def mask_phone(self, phone: str) -> str:
        """전화번호 마스킹
        
        예시:
        - 010-1234-5678 → 010-****-5678
        """
        if not phone:
            return "***-****-****"
        
        # 숫자만 추출
        digits = re.sub(r'\D', '', phone)
        
        if len(digits) == 11:
            return f"{digits[:3]}-****-{digits[-4:]}"
        elif len(digits) == 10:
            return f"{digits[:2]}-****-{digits[-4:]}"
        else:
            return "***-****-****"
    
    def mask_ssn(self, ssn: str) -> str:
        """주민등록번호 마스킹
        
        예시:
        - 901010-1234567 → 901010-*******
        """
        if not ssn:
            return "******-*******"
        
        # 숫자와 하이픈만 추출
        cleaned = re.sub(r'[^\d-]', '', ssn)
        
        if '-' in cleaned:
            parts = cleaned.split('-')
            if len(parts) == 2:
                return f"{parts[0]}-*******"
        
        if len(cleaned) >= 6:
            return f"{cleaned[:6]}-*******"
        
        return "******-*******"
    
    def hash_patient_id(self, patient_id: str) -> str:
        """환자 등록번호를 해시로 변환 (일방향)
        
        동일한 환자를 식별할 수 있지만 원본 복구 불가
        """
        if not patient_id:
            return ""
        
        salted = f"kdrg_salt_{patient_id}_enterprise"
        return hashlib.sha256(salted.encode()).hexdigest()
    
    # ========================
    # 암호화 (Encryption) 기능
    # ========================
    
    def encrypt(self, data: str) -> str:
        """데이터 암호화 (복호화 가능)"""
        if not data:
            return ""
        
        encrypted = self._fernet.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """데이터 복호화"""
        if not encrypted_data:
            return ""
        
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self._fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"복호화 실패: {e}")
    
    def encrypt_patient_data(self, patient_data: dict) -> dict:
        """환자 데이터 암호화 처리
        
        민감 필드는 암호화하고, 표시용 필드는 마스킹
        """
        result = patient_data.copy()
        
        # 암호화할 필드
        if 'patient_id' in result:
            result['encrypted_patient_id'] = self.encrypt(result['patient_id'])
            result['patient_hash'] = self.hash_patient_id(result['patient_id'])
            result['masked_patient_id'] = self.mask_patient_id(result['patient_id'])
            del result['patient_id']
        
        if 'patient_name' in result:
            result['encrypted_patient_name'] = self.encrypt(result['patient_name'])
            result['masked_name'] = self.mask_name(result['patient_name'])
            del result['patient_name']
        
        if 'phone' in result:
            result['encrypted_phone'] = self.encrypt(result['phone'])
            result['masked_phone'] = self.mask_phone(result['phone'])
            del result['phone']
        
        if 'ssn' in result:
            result['encrypted_ssn'] = self.encrypt(result['ssn'])
            result['masked_ssn'] = self.mask_ssn(result['ssn'])
            del result['ssn']
        
        return result
    
    def decrypt_patient_data(self, encrypted_data: dict) -> dict:
        """암호화된 환자 데이터 복호화"""
        result = encrypted_data.copy()
        
        if 'encrypted_patient_id' in result:
            result['patient_id'] = self.decrypt(result['encrypted_patient_id'])
        
        if 'encrypted_patient_name' in result:
            result['patient_name'] = self.decrypt(result['encrypted_patient_name'])
        
        if 'encrypted_phone' in result:
            result['phone'] = self.decrypt(result['encrypted_phone'])
        
        if 'encrypted_ssn' in result:
            result['ssn'] = self.decrypt(result['encrypted_ssn'])
        
        return result
    
    # ========================
    # 데이터 익명화 레벨
    # ========================
    
    def anonymize_for_analysis(self, patient_data: dict) -> dict:
        """분석용 익명화 데이터 생성
        
        개인 식별 정보를 제거하고 분석에 필요한 데이터만 반환
        """
        # 분석에 사용할 필드만 선택
        analysis_fields = [
            'department', 'primary_diagnosis_code', 'kdrg_code', 'aadrg_code',
            'admission_date', 'discharge_date', 'length_of_stay',
            'gender', 'age', 'discharge_result', 'claim_amount'
        ]
        
        result = {}
        for field in analysis_fields:
            if field in patient_data:
                result[field] = patient_data[field]
        
        # 연령대로 변환 (k-익명성)
        if 'age' in result and result['age']:
            age = result['age']
            result['age_group'] = f"{(age // 10) * 10}대"
        
        return result
    
    def anonymize_for_report(self, patient_data: dict) -> dict:
        """리포트용 익명화 데이터 생성
        
        마스킹된 이름과 ID를 포함
        """
        result = self.anonymize_for_analysis(patient_data)
        
        # 마스킹된 정보 추가
        if 'masked_name' in patient_data:
            result['patient_name'] = patient_data['masked_name']
        
        if 'masked_patient_id' in patient_data:
            result['patient_id'] = patient_data['masked_patient_id']
        
        return result


# 전역 인스턴스
privacy_protector = PrivacyProtector()
