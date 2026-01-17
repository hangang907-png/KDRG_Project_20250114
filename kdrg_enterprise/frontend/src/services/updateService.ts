/**
 * KDRG 업데이트 알림 서비스
 * - localStorage를 통한 마지막 동기화 날짜 관리
 * - 7일 주기 업데이트 알림
 */

const STORAGE_KEY = 'kdrg_last_sync_date';
const REMINDER_DISMISSED_KEY = 'kdrg_reminder_dismissed_date';
const DEFAULT_REMINDER_DAYS = 7;

export interface SyncStatus {
  lastSyncDate: string | null;
  daysSinceSync: number | null;
  needsReminder: boolean;
}

/**
 * 마지막 동기화 날짜 가져오기
 */
export function getLastSyncDate(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/**
 * 마지막 동기화 날짜 저장
 */
export function setLastSyncDate(date?: string): void {
  try {
    const syncDate = date || new Date().toISOString().split('T')[0];
    localStorage.setItem(STORAGE_KEY, syncDate);
    // 동기화하면 dismissed 초기화
    localStorage.removeItem(REMINDER_DISMISSED_KEY);
  } catch {
    console.error('Failed to save sync date');
  }
}

/**
 * 알림을 나중에 보기로 설정
 */
export function dismissReminder(): void {
  try {
    const today = new Date().toISOString().split('T')[0];
    localStorage.setItem(REMINDER_DISMISSED_KEY, today);
  } catch {
    console.error('Failed to dismiss reminder');
  }
}

/**
 * 오늘 이미 알림을 닫았는지 확인
 */
export function isReminderDismissedToday(): boolean {
  try {
    const dismissedDate = localStorage.getItem(REMINDER_DISMISSED_KEY);
    if (!dismissedDate) return false;

    const today = new Date().toISOString().split('T')[0];
    return dismissedDate === today;
  } catch {
    return false;
  }
}

/**
 * 동기화 상태 확인
 */
export function checkSyncStatus(reminderDays: number = DEFAULT_REMINDER_DAYS): SyncStatus {
  const lastSyncDate = getLastSyncDate();

  if (!lastSyncDate) {
    return {
      lastSyncDate: null,
      daysSinceSync: null,
      needsReminder: true, // 한번도 동기화한 적 없으면 알림 필요
    };
  }

  try {
    const lastSync = new Date(lastSyncDate);
    const today = new Date();
    const diffTime = today.getTime() - lastSync.getTime();
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

    // 오늘 이미 닫았으면 알림 불필요
    if (isReminderDismissedToday()) {
      return {
        lastSyncDate,
        daysSinceSync: diffDays,
        needsReminder: false,
      };
    }

    return {
      lastSyncDate,
      daysSinceSync: diffDays,
      needsReminder: diffDays >= reminderDays,
    };
  } catch {
    return {
      lastSyncDate,
      daysSinceSync: null,
      needsReminder: true,
    };
  }
}

/**
 * 동기화 상태 초기화 (테스트/디버그용)
 */
export function resetSyncStatus(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(REMINDER_DISMISSED_KEY);
  } catch {
    console.error('Failed to reset sync status');
  }
}

/**
 * 날짜를 한국어 형식으로 포맷
 */
export function formatDate(dateString: string | null): string {
  if (!dateString) return '없음';

  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch {
    return dateString;
  }
}
