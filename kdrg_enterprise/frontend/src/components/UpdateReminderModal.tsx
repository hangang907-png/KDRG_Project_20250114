import { useState } from 'react';
import { RefreshCw, Clock, X, AlertCircle, CheckCircle } from 'lucide-react';
import Modal from './Modal';
import { hiraAPI } from '../services/api';
import {
  checkSyncStatus,
  setLastSyncDate,
  dismissReminder,
  formatDate,
  SyncStatus,
} from '../services/updateService';

interface UpdateReminderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSyncComplete?: () => void;
}

export default function UpdateReminderModal({
  isOpen,
  onClose,
  onSyncComplete,
}: UpdateReminderModalProps) {
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<'success' | 'error' | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>('');

  const syncStatus = checkSyncStatus();

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    setErrorMessage('');

    try {
      // 실제 KDRG 코드북 동기화 API 호출
      const response = await hiraAPI.sync();

      if (response.data.success) {
        // 동기화 성공 시 날짜 저장
        setLastSyncDate();
        setSyncResult('success');

        // 잠시 후 모달 닫기
        setTimeout(() => {
          onSyncComplete?.();
          onClose();
        }, 1500);
      } else {
        setSyncResult('error');
        setErrorMessage(response.data.message || 'KDRG 기준정보 동기화에 실패했습니다.');
      }
    } catch (error) {
      console.error('Sync failed:', error);
      setSyncResult('error');
      setErrorMessage(
        'KDRG 기준정보 확인에 실패했습니다. 네트워크 연결을 확인하거나 나중에 다시 시도해주세요.'
      );
    } finally {
      setSyncing(false);
    }
  };

  const handleDismiss = () => {
    dismissReminder();
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="KDRG 기준정보 업데이트 확인" size="md">
      <div className="space-y-4">
        {/* Status Info */}
        <div className="bg-blue-50 border border-blue-100 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <Clock className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-blue-900">마지막 동기화 날짜</p>
              <p className="text-sm text-blue-700 mt-1">
                {formatDate(syncStatus.lastSyncDate)}
                {syncStatus.daysSinceSync !== null && (
                  <span className="ml-2 text-blue-500">({syncStatus.daysSinceSync}일 전)</span>
                )}
              </p>
            </div>
          </div>
        </div>

        {/* Description */}
        <div className="text-sm text-gray-600">
          <p>
            심평원 KDRG 기준정보가 변경되었을 수 있습니다. 정확한 DRG 분류와 수가 계산을 위해
            주기적인 업데이트 확인을 권장합니다.
          </p>
        </div>

        {/* Sync Result */}
        {syncResult === 'success' && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <p className="text-sm font-medium text-green-800">기준정보가 최신 상태입니다.</p>
            </div>
          </div>
        )}

        {syncResult === 'error' && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
              <p className="text-sm text-red-700">{errorMessage}</p>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-4 border-t border-gray-100">
          <button
            onClick={handleDismiss}
            disabled={syncing}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
          >
            나중에
          </button>
          <button
            onClick={handleSync}
            disabled={syncing || syncResult === 'success'}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? '확인 중...' : '지금 확인'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
