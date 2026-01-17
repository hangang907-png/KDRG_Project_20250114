import { useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { hiraAPI, aiAPI, kdrgAPI } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import {
  Settings,
  Key,
  CheckCircle,
  XCircle,
  Save,
  Eye,
  EyeOff,
  RefreshCw,
  Clock,
  AlertCircle,
  Database,
  Upload,
  FileSpreadsheet,
} from 'lucide-react';
import clsx from 'clsx';
import { checkSyncStatus, setLastSyncDate, formatDate } from '../services/updateService';

export default function SettingsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'api' | 'privacy' | 'system'>('api');

  // API Keys
  const [hiraKey, setHiraKey] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');
  const [claudeKey, setClaudeKey] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [showKeys, setShowKeys] = useState(false);

  // Sync state
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<'success' | 'error' | null>(null);
  const [syncError, setSyncError] = useState<string>('');
  const syncStatus = checkSyncStatus();

  // File upload state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadVersion, setUploadVersion] = useState('V4.6');
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{ success: boolean; message: string } | null>(
    null
  );
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: hiraStatus } = useQuery({
    queryKey: ['hiraStatus'],
    queryFn: () => hiraAPI.status().then(res => res.data),
  });

  const { data: aiStatus } = useQuery({
    queryKey: ['aiStatus'],
    queryFn: () => aiAPI.status().then(res => res.data),
  });

  const hiraKeyMutation = useMutation({
    mutationFn: (key: string) => hiraAPI.setApiKey(key),
  });

  const aiKeyMutation = useMutation({
    mutationFn: ({ provider, key }: { provider: string; key: string }) =>
      aiAPI.setApiKey(provider, key),
  });

  const handleSaveHiraKey = () => {
    if (hiraKey.trim()) {
      hiraKeyMutation.mutate(hiraKey.trim());
    }
  };

  const handleSaveAIKey = (provider: 'openai' | 'claude' | 'gemini') => {
    const key = provider === 'openai' ? openaiKey : provider === 'claude' ? claudeKey : geminiKey;
    if (key.trim()) {
      aiKeyMutation.mutate({ provider, key: key.trim() });
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    setSyncError('');

    try {
      // 실제 KDRG 코드북 동기화 API 호출
      const response = await hiraAPI.sync();

      if (response.data.success) {
        // 동기화 성공 시 날짜 저장
        setLastSyncDate();
        setSyncResult('success');

        // 쿼리 캐시 무효화
        queryClient.invalidateQueries({ queryKey: ['hiraStatus'] });
        queryClient.invalidateQueries({ queryKey: ['kdrgCodebook'] });
      } else {
        setSyncResult('error');
        setSyncError(response.data.message || 'KDRG 기준정보 동기화에 실패했습니다.');
      }
    } catch (error) {
      console.error('Sync failed:', error);
      setSyncResult('error');
      setSyncError(
        'KDRG 기준정보 동기화에 실패했습니다. API 키 설정을 확인하거나 나중에 다시 시도해주세요.'
      );
    } finally {
      setSyncing(false);
    }
  };

  const handleFileUpload = async () => {
    if (!uploadFile) return;

    setUploading(true);
    setUploadResult(null);

    try {
      const response = await kdrgAPI.uploadCodebook(uploadFile, uploadVersion);

      if (response.data.success) {
        setUploadResult({
          success: true,
          message:
            response.data.message || `${response.data.total_codes}개 코드가 업로드되었습니다.`,
        });
        setUploadFile(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        // 쿼리 캐시 무효화
        queryClient.invalidateQueries({ queryKey: ['hiraStatus'] });
        queryClient.invalidateQueries({ queryKey: ['kdrgCodebook'] });
        // 동기화 날짜 업데이트
        setLastSyncDate();
      } else {
        setUploadResult({
          success: false,
          message: response.data.message || '업로드에 실패했습니다.',
        });
      }
    } catch (error: unknown) {
      console.error('Upload failed:', error);
      const errorMessage =
        error instanceof Error
          ? error.message
          : (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            '파일 업로드에 실패했습니다.';
      setUploadResult({
        success: false,
        message: errorMessage,
      });
    } finally {
      setUploading(false);
    }
  };

  const isAdmin = user?.role === 'admin';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">설정</h1>
        <p className="mt-1 text-gray-600">시스템 설정 및 API 연동 관리</p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-8">
          {[
            { id: 'api', label: 'API 연동', icon: Key },
            { id: 'privacy', label: '개인정보 보호', icon: Settings },
            { id: 'system', label: '시스템', icon: Settings },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={clsx(
                'flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors',
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              )}
            >
              <tab.icon className="h-5 w-5" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Content */}
      {activeTab === 'api' && (
        <div className="space-y-6">
          {/* HIRA API */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">심평원 API (공공데이터포털)</h3>
                <p className="text-sm text-gray-600">KDRG 기준정보 조회 및 검증에 사용됩니다</p>
              </div>
              <div className="flex items-center gap-2">
                {hiraStatus?.api_configured ? (
                  <>
                    <CheckCircle className="h-5 w-5 text-success-500" />
                    <span className="text-sm text-success-600">연결됨</span>
                  </>
                ) : (
                  <>
                    <XCircle className="h-5 w-5 text-gray-400" />
                    <span className="text-sm text-gray-500">미설정</span>
                  </>
                )}
              </div>
            </div>

            {isAdmin ? (
              <div className="flex gap-3">
                <div className="relative flex-1">
                  <input
                    type={showKeys ? 'text' : 'password'}
                    value={hiraKey}
                    onChange={e => setHiraKey(e.target.value)}
                    placeholder="공공데이터포털 API 키 입력"
                    className="input pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKeys(!showKeys)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400"
                  >
                    {showKeys ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
                <button
                  onClick={handleSaveHiraKey}
                  disabled={!hiraKey.trim() || hiraKeyMutation.isPending}
                  className="btn-primary flex items-center gap-2"
                >
                  <Save className="h-4 w-4" />
                  {hiraKeyMutation.isPending ? '저장 중...' : '저장'}
                </button>
              </div>
            ) : (
              <p className="text-sm text-gray-500">API 키 설정은 관리자만 가능합니다.</p>
            )}
            {hiraKeyMutation.isSuccess && (
              <p className="mt-2 text-sm text-success-600">API 키가 저장되었습니다.</p>
            )}
          </div>

          {/* AI API */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">AI API</h3>
                <p className="text-sm text-gray-600">DRG 추천 및 분석에 AI가 사용됩니다</p>
              </div>
              <div className="flex items-center gap-2">
                {aiStatus?.ready ? (
                  <>
                    <CheckCircle className="h-5 w-5 text-success-500" />
                    <span className="text-sm text-success-600">
                      {aiStatus.available_provider} 연결됨
                    </span>
                  </>
                ) : (
                  <>
                    <XCircle className="h-5 w-5 text-gray-400" />
                    <span className="text-sm text-gray-500">미설정</span>
                  </>
                )}
              </div>
            </div>

            {isAdmin ? (
              <div className="space-y-4">
                {/* OpenAI */}
                <div>
                  <label className="label">OpenAI API Key</label>
                  <div className="flex gap-3">
                    <input
                      type={showKeys ? 'text' : 'password'}
                      value={openaiKey}
                      onChange={e => setOpenaiKey(e.target.value)}
                      placeholder="sk-..."
                      className="input flex-1"
                    />
                    <button
                      onClick={() => handleSaveAIKey('openai')}
                      disabled={!openaiKey.trim() || aiKeyMutation.isPending}
                      className="btn-secondary"
                    >
                      저장
                    </button>
                  </div>
                </div>

                {/* Claude */}
                <div>
                  <label className="label">Claude API Key</label>
                  <div className="flex gap-3">
                    <input
                      type={showKeys ? 'text' : 'password'}
                      value={claudeKey}
                      onChange={e => setClaudeKey(e.target.value)}
                      placeholder="sk-ant-..."
                      className="input flex-1"
                    />
                    <button
                      onClick={() => handleSaveAIKey('claude')}
                      disabled={!claudeKey.trim() || aiKeyMutation.isPending}
                      className="btn-secondary"
                    >
                      저장
                    </button>
                  </div>
                </div>

                {/* Gemini */}
                <div>
                  <label className="label">Gemini API Key</label>
                  <div className="flex gap-3">
                    <input
                      type={showKeys ? 'text' : 'password'}
                      value={geminiKey}
                      onChange={e => setGeminiKey(e.target.value)}
                      placeholder="AIza..."
                      className="input flex-1"
                    />
                    <button
                      onClick={() => handleSaveAIKey('gemini')}
                      disabled={!geminiKey.trim() || aiKeyMutation.isPending}
                      className="btn-secondary"
                    >
                      저장
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500">API 키 설정은 관리자만 가능합니다.</p>
            )}
          </div>

          {/* API Guide */}
          <div className="card bg-primary-50 border-primary-200">
            <h3 className="font-semibold text-primary-900 mb-2">API 키 발급 방법</h3>
            <div className="text-sm text-primary-800 space-y-2">
              <p>
                <strong>심평원 API:</strong> 공공데이터포털(data.go.kr) 회원가입 후
                신포괄기준정보조회서비스 활용신청
              </p>
              <p>
                <strong>OpenAI:</strong> platform.openai.com에서 API 키 발급
              </p>
              <p>
                <strong>Claude:</strong> console.anthropic.com에서 API 키 발급
              </p>
              <p>
                <strong>Gemini:</strong> aistudio.google.com에서 API 키 발급 후 `.env`의
                `GEMINI_API_KEY` 혹은 설정 화면에 입력
              </p>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'privacy' && (
        <div className="space-y-6">
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">개인정보 보호 설정</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between py-3 border-b border-gray-100">
                <div>
                  <p className="font-medium text-gray-900">환자명 마스킹</p>
                  <p className="text-sm text-gray-600">환자 이름을 홍*동 형태로 표시</p>
                </div>
                <span className="badge-success">활성화됨</span>
              </div>
              <div className="flex items-center justify-between py-3 border-b border-gray-100">
                <div>
                  <p className="font-medium text-gray-900">환자번호 마스킹</p>
                  <p className="text-sm text-gray-600">등록번호 일부를 *** 로 표시</p>
                </div>
                <span className="badge-success">활성화됨</span>
              </div>
              <div className="flex items-center justify-between py-3">
                <div>
                  <p className="font-medium text-gray-900">데이터 암호화</p>
                  <p className="text-sm text-gray-600">민감 정보 AES-256 암호화 저장</p>
                </div>
                <span className="badge-success">활성화됨</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'system' && (
        <div className="space-y-6">
          {/* KDRG 기준정보 동기화 */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary-100 rounded-lg">
                  <Database className="h-5 w-5 text-primary-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">KDRG 기준정보 동기화</h3>
                  <p className="text-sm text-gray-600">
                    심평원 공공데이터포털에서 최신 KDRG 기준정보를 확인합니다
                  </p>
                </div>
              </div>
            </div>

            {/* 동기화 상태 */}
            <div className="bg-gray-50 rounded-lg p-4 mb-4">
              <div className="flex items-center gap-3 mb-3">
                <Clock className="h-5 w-5 text-gray-500" />
                <div>
                  <p className="text-sm font-medium text-gray-700">마지막 동기화</p>
                  <p className="text-sm text-gray-600">
                    {formatDate(syncStatus.lastSyncDate)}
                    {syncStatus.daysSinceSync !== null && syncStatus.daysSinceSync > 0 && (
                      <span
                        className={clsx(
                          'ml-2',
                          syncStatus.daysSinceSync >= 7 ? 'text-warning-600' : 'text-gray-500'
                        )}
                      >
                        ({syncStatus.daysSinceSync}일 전)
                      </span>
                    )}
                    {syncStatus.daysSinceSync === 0 && (
                      <span className="ml-2 text-success-600">(오늘)</span>
                    )}
                  </p>
                </div>
              </div>
              {/* 코드북 상태 표시 */}
              {hiraStatus?.codebook_status && (
                <div className="flex items-center gap-3 pt-3 border-t border-gray-200">
                  <Database className="h-5 w-5 text-gray-500" />
                  <div>
                    <p className="text-sm font-medium text-gray-700">코드북 상태</p>
                    <p className="text-sm text-gray-600">
                      {hiraStatus.codebook_status.has_codebook ? (
                        <span className="text-success-600">
                          {hiraStatus.codebook_status.total_codes.toLocaleString()}개 KDRG 코드
                          로드됨
                        </span>
                      ) : (
                        <span className="text-warning-600">코드북이 로드되지 않았습니다</span>
                      )}
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* 동기화 결과 메시지 */}
            {syncResult === 'success' && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
                <div className="flex items-center gap-3">
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  <p className="text-sm font-medium text-green-800">기준정보가 최신 상태입니다.</p>
                </div>
              </div>
            )}

            {syncResult === 'error' && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
                  <p className="text-sm text-red-700">{syncError}</p>
                </div>
              </div>
            )}

            {/* 동기화 권장 알림 */}
            {syncStatus.needsReminder && !syncResult && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="h-5 w-5 text-yellow-600 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-yellow-800">업데이트 확인 권장</p>
                    <p className="text-sm text-yellow-700 mt-1">
                      {syncStatus.lastSyncDate
                        ? '마지막 동기화 이후 7일이 지났습니다.'
                        : '아직 기준정보를 동기화한 적이 없습니다.'}{' '}
                      정확한 DRG 분류를 위해 동기화를 진행해주세요.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* 동기화 버튼 */}
            <button
              onClick={handleSync}
              disabled={syncing || !hiraStatus?.api_configured}
              className="btn-primary flex items-center gap-2"
            >
              <RefreshCw className={clsx('h-4 w-4', syncing && 'animate-spin')} />
              {syncing ? '동기화 중...' : '지금 동기화'}
            </button>

            {!hiraStatus?.api_configured && (
              <p className="mt-2 text-sm text-gray-500">
                동기화하려면 먼저 'API 연동' 탭에서 심평원 API 키를 설정해주세요.
              </p>
            )}
          </div>

          {/* KDRG 코드북 파일 업로드 */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <FileSpreadsheet className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">KDRG 코드북 파일 업로드</h3>
                  <p className="text-sm text-gray-600">
                    심평원에서 다운로드한 KDRG 코드북 파일(CSV/Excel)을 업로드합니다
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              {/* 버전 선택 */}
              <div>
                <label className="label">KDRG 버전</label>
                <select
                  value={uploadVersion}
                  onChange={e => setUploadVersion(e.target.value)}
                  className="input w-48"
                >
                  <option value="V4.6">V4.6 (2024)</option>
                  <option value="V4.5">V4.5</option>
                  <option value="V4.4">V4.4</option>
                  <option value="V4.3">V4.3</option>
                </select>
              </div>

              {/* 파일 선택 */}
              <div>
                <label className="label">코드북 파일</label>
                <div className="flex items-center gap-3">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv,.xlsx,.xls,.pdf"
                    onChange={e => setUploadFile(e.target.files?.[0] || null)}
                    className="input flex-1"
                  />
                  <button
                    onClick={handleFileUpload}
                    disabled={!uploadFile || uploading}
                    className="btn-primary flex items-center gap-2"
                  >
                    <Upload className={clsx('h-4 w-4', uploading && 'animate-pulse')} />
                    {uploading ? '업로드 중...' : '업로드'}
                  </button>
                </div>
                {uploadFile && (
                  <p className="mt-1 text-sm text-gray-500">
                    선택된 파일: {uploadFile.name} ({(uploadFile.size / 1024).toFixed(1)} KB)
                  </p>
                )}
              </div>

              {/* 업로드 결과 메시지 */}
              {uploadResult && (
                <div
                  className={clsx(
                    'rounded-lg p-4',
                    uploadResult.success
                      ? 'bg-green-50 border border-green-200'
                      : 'bg-red-50 border border-red-200'
                  )}
                >
                  <div className="flex items-center gap-3">
                    {uploadResult.success ? (
                      <CheckCircle className="h-5 w-5 text-green-500" />
                    ) : (
                      <AlertCircle className="h-5 w-5 text-red-500" />
                    )}
                    <p
                      className={clsx(
                        'text-sm font-medium',
                        uploadResult.success ? 'text-green-800' : 'text-red-700'
                      )}
                    >
                      {uploadResult.message}
                    </p>
                  </div>
                </div>
              )}

              {/* 안내 메시지 */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="h-5 w-5 text-blue-600 flex-shrink-0" />
                  <div className="text-sm text-blue-800">
                    <p className="font-medium mb-1">코드북 파일 형식 안내</p>
                    <ul className="list-disc list-inside space-y-1 text-blue-700">
                      <li>CSV, Excel(.xlsx, .xls), PDF 파일 지원</li>
                      <li>필수 컬럼: KDRG (코드)</li>
                      <li>권장 컬럼: KDRG명, AADRG, AADRG명, MDC, 상대가치, 평균재원일수</li>
                      <li>심평원 포털에서 다운로드한 원본 파일 사용 권장</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 시스템 정보 */}
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">시스템 정보</h3>
            <div className="space-y-3">
              <div className="flex justify-between py-2">
                <span className="text-gray-600">앱 이름</span>
                <span className="font-medium text-gray-900">KDRG Enterprise</span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-gray-600">버전</span>
                <span className="font-medium text-gray-900">1.0.0</span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-gray-600">현재 사용자</span>
                <span className="font-medium text-gray-900">{user?.username}</span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-gray-600">권한</span>
                <span
                  className={clsx(
                    'badge',
                    user?.role === 'admin' ? 'badge-primary' : 'bg-gray-100 text-gray-600'
                  )}
                >
                  {user?.role === 'admin' ? '관리자' : '일반 사용자'}
                </span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-gray-600">소속</span>
                <span className="font-medium text-gray-900">{user?.department || '-'}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
