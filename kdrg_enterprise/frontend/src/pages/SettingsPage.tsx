import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { hiraAPI, aiAPI } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { Settings, Key, CheckCircle, XCircle, Save, Eye, EyeOff } from 'lucide-react';
import clsx from 'clsx';

export default function SettingsPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'api' | 'privacy' | 'system'>('api');
  
  // API Keys
  const [hiraKey, setHiraKey] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');
  const [claudeKey, setClaudeKey] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [showKeys, setShowKeys] = useState(false);

  const { data: hiraStatus } = useQuery({
    queryKey: ['hiraStatus'],
    queryFn: () => hiraAPI.status().then((res) => res.data),
  });

  const { data: aiStatus } = useQuery({
    queryKey: ['aiStatus'],
    queryFn: () => aiAPI.status().then((res) => res.data),
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
    const key =
      provider === 'openai' ? openaiKey : provider === 'claude' ? claudeKey : geminiKey;
    if (key.trim()) {
      aiKeyMutation.mutate({ provider, key: key.trim() });
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
          ].map((tab) => (
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
                <h3 className="text-lg font-semibold text-gray-900">
                  심평원 API (공공데이터포털)
                </h3>
                <p className="text-sm text-gray-600">
                  KDRG 기준정보 조회 및 검증에 사용됩니다
                </p>
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
                    onChange={(e) => setHiraKey(e.target.value)}
                    placeholder="공공데이터포털 API 키 입력"
                    className="input pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKeys(!showKeys)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400"
                  >
                    {showKeys ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
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
              <p className="text-sm text-gray-500">
                API 키 설정은 관리자만 가능합니다.
              </p>
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
                <p className="text-sm text-gray-600">
                  DRG 추천 및 분석에 AI가 사용됩니다
                </p>
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
                      onChange={(e) => setOpenaiKey(e.target.value)}
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
                      onChange={(e) => setClaudeKey(e.target.value)}
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
                      onChange={(e) => setGeminiKey(e.target.value)}
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
              <p className="text-sm text-gray-500">
                API 키 설정은 관리자만 가능합니다.
              </p>
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
                <strong>Gemini:</strong> aistudio.google.com에서 API 키 발급 후 `.env`의 `GEMINI_API_KEY` 혹은 설정 화면에 입력
              </p>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'privacy' && (
        <div className="space-y-6">
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              개인정보 보호 설정
            </h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between py-3 border-b border-gray-100">
                <div>
                  <p className="font-medium text-gray-900">환자명 마스킹</p>
                  <p className="text-sm text-gray-600">
                    환자 이름을 홍*동 형태로 표시
                  </p>
                </div>
                <span className="badge-success">활성화됨</span>
              </div>
              <div className="flex items-center justify-between py-3 border-b border-gray-100">
                <div>
                  <p className="font-medium text-gray-900">환자번호 마스킹</p>
                  <p className="text-sm text-gray-600">
                    등록번호 일부를 *** 로 표시
                  </p>
                </div>
                <span className="badge-success">활성화됨</span>
              </div>
              <div className="flex items-center justify-between py-3">
                <div>
                  <p className="font-medium text-gray-900">데이터 암호화</p>
                  <p className="text-sm text-gray-600">
                    민감 정보 AES-256 암호화 저장
                  </p>
                </div>
                <span className="badge-success">활성화됨</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'system' && (
        <div className="space-y-6">
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
                <span className="font-medium text-gray-900">
                  {user?.department || '-'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
