import { useState, useEffect, useCallback } from 'react';
import {
  Upload,
  FileSpreadsheet,
  Trash2,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  TrendingDown,
  TrendingUp,
  BarChart3,
  FileText,
  Search,
  X,
  ChevronLeft,
  ChevronRight,
  Download,
  GitCompare,
  FileUp,
  Info,
  Cloud,
  LogIn,
  LogOut,
  Settings,
  Clock,
  FolderDown,
  History,
} from 'lucide-react';
import api, { portalAPI } from '../services/api';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import ErrorMessage from '../components/ErrorMessage';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import Tooltip from '../components/Tooltip';

interface FeedbackFile {
  file_id: string;
  file_name: string;
  data_type: string;
  total_records: number;
  uploaded_at: string;
  summary: {
    total_claimed_amount?: number;
    total_reviewed_amount?: number;
    total_adjustment?: number;
    adjustment_rate?: number;
    kdrg_change_count?: number;
    drg_distribution?: Record<string, number>;
    date_range?: { start: string; end: string };
  };
}

interface FileRecord {
  claim_id?: string;
  patient_id?: string;
  patient_name?: string;
  admission_date?: string;
  discharge_date?: string;
  claimed_kdrg?: string;
  original_kdrg?: string;
  reviewed_kdrg?: string;
  claimed_amount?: number;
  original_amount?: number;
  reviewed_amount?: number;
  adjustment_amount?: number;
  adjustment_reason?: string;
  is_adjusted?: boolean;
}

const DATA_TYPE_LABELS: Record<string, string> = {
  drg_claim: 'DRG 청구내역',
  review_result: '심사결과',
  kdrg_grouper: 'KDRG 그루퍼 결과',
  payment: '지급결과',
  return_detail: '반송/보완',
  unknown: '알 수 없음',
};

const COLORS = [
  '#3B82F6',
  '#10B981',
  '#F59E0B',
  '#EF4444',
  '#8B5CF6',
  '#EC4899',
  '#06B6D4',
  '#84CC16',
];

export default function FeedbackPage() {
  const [files, setFiles] = useState<FeedbackFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<FeedbackFile | null>(null);
  const [fileRecords, setFileRecords] = useState<FileRecord[]>([]);
  const [recordsPage, setRecordsPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [statistics, setStatistics] = useState<any>(null);
  const [drg7Summary, setDrg7Summary] = useState<any>(null);
  const [kdrChanges, setKdrgChanges] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'files' | 'analysis' | 'compare' | 'portal'>('files');
  const [compareFiles, setCompareFiles] = useState<{ claim: string; review: string }>({
    claim: '',
    review: '',
  });
  const [compareResult, setCompareResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // 포털 관련 state
  const [portalStatus, setPortalStatus] = useState<any>(null);
  const [portalFiles, setPortalFiles] = useState<any[]>([]);
  const [portalLoading, setPortalLoading] = useState(false);
  const [loginForm, setLoginForm] = useState({ hospital_code: '', user_id: '', password: '' });
  const [selectedPortalFiles, setSelectedPortalFiles] = useState<string[]>([]);
  const [downloadHistory, setDownloadHistory] = useState<any[]>([]);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [portalConfig, setPortalConfig] = useState({
    enabled: false,
    schedule_time: '06:00',
    download_path: './downloads/feedback',
    days_to_keep: 90,
    auto_parse: true,
  });

  // 파일 목록 조회
  const fetchFiles = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get('/feedback/files');
      setFiles(response.data.files || []);
    } catch (err: any) {
      setError('파일 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  // 통계 조회
  const fetchStatistics = useCallback(async () => {
    try {
      const [statsRes, drg7Res, changesRes] = await Promise.all([
        api.get('/feedback/statistics'),
        api.get('/feedback/analysis/drg7-summary'),
        api.get('/feedback/analysis/kdrg-changes'),
      ]);
      setStatistics(statsRes.data);
      setDrg7Summary(drg7Res.data.drg7_summary);
      setKdrgChanges(changesRes.data);
    } catch (err) {
      console.error('통계 조회 실패:', err);
    }
  }, []);

  useEffect(() => {
    fetchFiles();
    fetchStatistics();
    fetchPortalStatus();
  }, [fetchFiles, fetchStatistics]);

  // 포털 상태 조회
  const fetchPortalStatus = async () => {
    try {
      const response = await portalAPI.getStatus();
      setPortalStatus(response.data);
      if (response.data.config) {
        setPortalConfig(response.data.config);
      }
    } catch (err) {
      console.error('포털 상태 조회 실패:', err);
    }
  };

  // 포털 로그인
  const handlePortalLogin = async () => {
    if (!loginForm.hospital_code || !loginForm.user_id || !loginForm.password) {
      setError('모든 로그인 정보를 입력해주세요.');
      return;
    }

    setPortalLoading(true);
    try {
      const response = await portalAPI.login(loginForm);
      if (response.data.success) {
        await fetchPortalStatus();
        await fetchPortalFiles();
        alert('포털 로그인 성공! (시뮬레이션 모드)');
      } else {
        setError(response.data.message || '로그인에 실패했습니다.');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '포털 로그인에 실패했습니다.');
    } finally {
      setPortalLoading(false);
    }
  };

  // 포털 로그아웃
  const handlePortalLogout = async () => {
    try {
      await portalAPI.logout();
      await fetchPortalStatus();
      setPortalFiles([]);
    } catch (err) {
      console.error('포털 로그아웃 실패:', err);
    }
  };

  // 포털 파일 목록 조회
  const fetchPortalFiles = async () => {
    setPortalLoading(true);
    try {
      const response = await portalAPI.getFiles();
      setPortalFiles(response.data.files || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || '파일 목록 조회에 실패했습니다.');
    } finally {
      setPortalLoading(false);
    }
  };

  // 포털 파일 다운로드
  const handlePortalDownload = async () => {
    if (selectedPortalFiles.length === 0) {
      setError('다운로드할 파일을 선택해주세요.');
      return;
    }

    setPortalLoading(true);
    try {
      const response = await portalAPI.download(selectedPortalFiles);
      if (response.data.success) {
        alert(response.data.message);
        setSelectedPortalFiles([]);
        fetchDownloadHistory();
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '파일 다운로드에 실패했습니다.');
    } finally {
      setPortalLoading(false);
    }
  };

  // 자동 다운로드 실행
  const handleAutoDownload = async () => {
    setPortalLoading(true);
    try {
      const response = await portalAPI.autoDownload();
      if (response.data.success) {
        alert(`자동 다운로드 완료!\n다운로드: ${response.data.downloaded_count}개 파일`);
        fetchDownloadHistory();
      } else {
        setError(response.data.message || '자동 다운로드에 실패했습니다.');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '자동 다운로드에 실패했습니다.');
    } finally {
      setPortalLoading(false);
    }
  };

  // 다운로드 이력 조회
  const fetchDownloadHistory = async () => {
    try {
      const response = await portalAPI.getHistory(20);
      setDownloadHistory(response.data.history || []);
    } catch (err) {
      console.error('다운로드 이력 조회 실패:', err);
    }
  };

  // 포털 설정 저장
  const handleSaveConfig = async () => {
    try {
      await portalAPI.setConfig(portalConfig);
      setShowConfigModal(false);
      alert('설정이 저장되었습니다.');
    } catch (err: any) {
      setError(err.response?.data?.detail || '설정 저장에 실패했습니다.');
    }
  };

  // 파일 업로드
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post('/feedback/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      if (response.data.success) {
        fetchFiles();
        fetchStatistics();
        alert(
          `파일 업로드 성공!\n- 데이터 유형: ${DATA_TYPE_LABELS[response.data.data_type]}\n- 총 ${response.data.total_records}건`
        );
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '파일 업로드에 실패했습니다.');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  // 파일 상세 조회
  const handleFileSelect = async (file: FeedbackFile) => {
    setSelectedFile(file);
    setRecordsPage(1);
    await fetchFileRecords(file.file_id, 1);
  };

  const fetchFileRecords = async (fileId: string, page: number) => {
    try {
      const response = await api.get(`/feedback/files/${fileId}`, {
        params: { page, page_size: 20 },
      });
      setFileRecords(response.data.records || []);
      setTotalPages(response.data.total_pages || 1);
    } catch (err) {
      setError('데이터를 불러오는데 실패했습니다.');
    }
  };

  // 파일 삭제
  const handleFileDelete = async (fileId: string) => {
    if (!confirm('이 파일을 삭제하시겠습니까?')) return;

    try {
      await api.delete(`/feedback/files/${fileId}`);
      fetchFiles();
      fetchStatistics();
      if (selectedFile?.file_id === fileId) {
        setSelectedFile(null);
        setFileRecords([]);
      }
    } catch (err) {
      setError('파일 삭제에 실패했습니다.');
    }
  };

  // 비교 분석
  const handleCompare = async () => {
    if (!compareFiles.claim || !compareFiles.review) {
      setError('청구 데이터와 심사 결과 파일을 모두 선택해주세요.');
      return;
    }

    try {
      const response = await api.post('/feedback/compare', null, {
        params: {
          claim_file_id: compareFiles.claim,
          review_file_id: compareFiles.review,
        },
      });
      setCompareResult(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || '비교 분석에 실패했습니다.');
    }
  };

  // 금액 포맷
  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat('ko-KR', { style: 'currency', currency: 'KRW' }).format(amount);
  };

  // DRG 분포 차트 데이터
  const getDrgChartData = () => {
    if (!statistics?.drg_distribution) return [];
    return Object.entries(statistics.drg_distribution).map(([name, value]) => ({
      name: name.split('(')[0].trim(),
      value: value as number,
    }));
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">환류 데이터 관리</h1>
        <p className="text-gray-600 mt-1">심평원 환류 데이터 업로드, 분석 및 비교</p>
      </div>

      {error && (
        <ErrorMessage
          title="오류가 발생했습니다"
          message={error}
          onDismiss={() => setError(null)}
          onRetry={() => {
            setError(null);
            fetchFiles();
            fetchStatistics();
          }}
        />
      )}

      {/* 탭 네비게이션 */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-4">
          {[
            { id: 'files', label: '파일 관리', icon: FileSpreadsheet },
            { id: 'analysis', label: '분석', icon: BarChart3 },
            { id: 'compare', label: '비교 분석', icon: GitCompare },
            { id: 'portal', label: '자동 다운로드', icon: Cloud },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* 파일 관리 탭 */}
      {activeTab === 'files' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 파일 목록 */}
          <div className="lg:col-span-1 bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-900">업로드된 파일</h2>
              <label className="cursor-pointer">
                <input
                  type="file"
                  accept=".xlsx,.xls,.csv"
                  onChange={handleFileUpload}
                  className="hidden"
                  disabled={uploading}
                />
                <span
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${
                    uploading
                      ? 'bg-gray-100 text-gray-400'
                      : 'bg-blue-500 text-white hover:bg-blue-600'
                  }`}
                >
                  {uploading ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Upload className="w-4 h-4" />
                  )}
                  업로드
                </span>
              </label>
            </div>

            {loading ? (
              <div className="flex justify-center py-8">
                <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
              </div>
            ) : files.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <FileSpreadsheet className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>업로드된 파일이 없습니다</p>
                <p className="text-sm mt-1">Excel 또는 CSV 파일을 업로드하세요</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[500px] overflow-y-auto">
                {files.map(file => (
                  <div
                    key={file.file_id}
                    onClick={() => handleFileSelect(file)}
                    className={`p-3 rounded-lg cursor-pointer border transition-colors ${
                      selectedFile?.file_id === file.file_id
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm text-gray-900 truncate">
                          {file.file_name}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          {DATA_TYPE_LABELS[file.data_type]} · {file.total_records}건
                        </p>
                        {file.summary.adjustment_rate !== undefined && (
                          <p
                            className={`text-xs mt-1 ${
                              file.summary.adjustment_rate > 0 ? 'text-red-600' : 'text-green-600'
                            }`}
                          >
                            조정률: {file.summary.adjustment_rate}%
                          </p>
                        )}
                      </div>
                      <button
                        onClick={e => {
                          e.stopPropagation();
                          handleFileDelete(file.file_id);
                        }}
                        className="p-1 text-gray-400 hover:text-red-500"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 파일 상세 */}
          <div className="lg:col-span-2 bg-white rounded-lg shadow p-4">
            {selectedFile ? (
              <>
                <div className="mb-4">
                  <h2 className="font-semibold text-gray-900">{selectedFile.file_name}</h2>
                  <div className="flex flex-wrap gap-4 mt-2 text-sm text-gray-600">
                    <span>유형: {DATA_TYPE_LABELS[selectedFile.data_type]}</span>
                    <span>레코드: {selectedFile.total_records}건</span>
                    {selectedFile.summary.date_range && (
                      <span>
                        기간: {selectedFile.summary.date_range.start} ~{' '}
                        {selectedFile.summary.date_range.end}
                      </span>
                    )}
                  </div>
                </div>

                {/* 요약 정보 */}
                {selectedFile.data_type === 'review_result' && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div className="p-3 bg-blue-50 rounded-lg">
                      <p className="text-xs text-blue-600">총 청구액</p>
                      <p className="text-lg font-semibold text-blue-700">
                        {formatAmount(selectedFile.summary.total_claimed_amount || 0)}
                      </p>
                    </div>
                    <div className="p-3 bg-green-50 rounded-lg">
                      <p className="text-xs text-green-600">심사 금액</p>
                      <p className="text-lg font-semibold text-green-700">
                        {formatAmount(selectedFile.summary.total_reviewed_amount || 0)}
                      </p>
                    </div>
                    <div className="p-3 bg-red-50 rounded-lg">
                      <p className="text-xs text-red-600">조정 금액</p>
                      <p className="text-lg font-semibold text-red-700">
                        {formatAmount(selectedFile.summary.total_adjustment || 0)}
                      </p>
                    </div>
                    <div className="p-3 bg-yellow-50 rounded-lg">
                      <p className="text-xs text-yellow-600">KDRG 변경</p>
                      <p className="text-lg font-semibold text-yellow-700">
                        {selectedFile.summary.kdrg_change_count || 0}건
                      </p>
                    </div>
                  </div>
                )}

                {/* 데이터 테이블 */}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left">청구번호</th>
                        <th className="px-3 py-2 text-left">환자ID</th>
                        {selectedFile.data_type === 'drg_claim' && (
                          <>
                            <th className="px-3 py-2 text-left">입원일</th>
                            <th className="px-3 py-2 text-left">KDRG</th>
                            <th className="px-3 py-2 text-right">청구액</th>
                          </>
                        )}
                        {selectedFile.data_type === 'review_result' && (
                          <>
                            <th className="px-3 py-2 text-left">원 KDRG</th>
                            <th className="px-3 py-2 text-left">심사 KDRG</th>
                            <th className="px-3 py-2 text-right">조정액</th>
                            <th className="px-3 py-2 text-left">조정사유</th>
                          </>
                        )}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {fileRecords.map((record, idx) => (
                        <tr key={idx} className="hover:bg-gray-50">
                          <td className="px-3 py-2">{record.claim_id}</td>
                          <td className="px-3 py-2">{record.patient_id}</td>
                          {selectedFile.data_type === 'drg_claim' && (
                            <>
                              <td className="px-3 py-2">{record.admission_date}</td>
                              <td className="px-3 py-2 font-mono">{record.claimed_kdrg}</td>
                              <td className="px-3 py-2 text-right">
                                {formatAmount(record.claimed_amount || 0)}
                              </td>
                            </>
                          )}
                          {selectedFile.data_type === 'review_result' && (
                            <>
                              <td className="px-3 py-2 font-mono">{record.original_kdrg}</td>
                              <td
                                className={`px-3 py-2 font-mono ${
                                  record.original_kdrg !== record.reviewed_kdrg
                                    ? 'text-red-600 font-semibold'
                                    : ''
                                }`}
                              >
                                {record.reviewed_kdrg}
                              </td>
                              <td
                                className={`px-3 py-2 text-right ${
                                  (record.adjustment_amount || 0) > 0 ? 'text-red-600' : ''
                                }`}
                              >
                                {formatAmount(record.adjustment_amount || 0)}
                              </td>
                              <td
                                className="px-3 py-2 max-w-[200px] truncate"
                                title={record.adjustment_reason}
                              >
                                {record.adjustment_reason}
                              </td>
                            </>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* 페이지네이션 */}
                <div className="flex items-center justify-between mt-4">
                  <span className="text-sm text-gray-600">
                    페이지 {recordsPage} / {totalPages}
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        setRecordsPage(p => p - 1);
                        fetchFileRecords(selectedFile.file_id, recordsPage - 1);
                      }}
                      disabled={recordsPage <= 1}
                      className="p-2 rounded border disabled:opacity-50"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => {
                        setRecordsPage(p => p + 1);
                        fetchFileRecords(selectedFile.file_id, recordsPage + 1);
                      }}
                      disabled={recordsPage >= totalPages}
                      className="p-2 rounded border disabled:opacity-50"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-gray-500">
                <FileText className="w-16 h-16 mb-4 opacity-50" />
                <p>파일을 선택하여 상세 내용을 확인하세요</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 분석 탭 */}
      {activeTab === 'analysis' && (
        <div className="space-y-6">
          {/* 통계 카드 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">총 파일</p>
              <p className="text-2xl font-bold">{statistics?.total_files || 0}개</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">총 레코드</p>
              <p className="text-2xl font-bold">
                {statistics?.total_records?.toLocaleString() || 0}건
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">총 청구액</p>
              <p className="text-2xl font-bold text-blue-600">
                {formatAmount(statistics?.total_claimed_amount || 0)}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">전체 조정률</p>
              <p
                className={`text-2xl font-bold ${
                  (statistics?.overall_adjustment_rate || 0) > 0 ? 'text-red-600' : 'text-green-600'
                }`}
              >
                {statistics?.overall_adjustment_rate || 0}%
              </p>
            </div>
          </div>

          {/* 차트 영역 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* DRG 분포 */}
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold mb-4">DRG 분포</h3>
              {getDrgChartData().length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={getDrgChartData()}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    >
                      {getDrgChartData().map((_, idx) => (
                        <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                      ))}
                    </Pie>
                    <RechartsTooltip />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-[300px] text-gray-500">
                  데이터가 없습니다
                </div>
              )}
            </div>

            {/* 7개 DRG군 현황 */}
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold mb-4">7개 DRG군 현황</h3>
              {drg7Summary ? (
                <div className="space-y-3 max-h-[300px] overflow-y-auto">
                  {Object.entries(drg7Summary)
                    .filter(([code]) => code !== 'OTHER')
                    .map(([code, data]: [string, any]) => (
                      <div
                        key={code}
                        className="flex items-center justify-between p-2 bg-gray-50 rounded"
                      >
                        <div>
                          <span className="font-mono font-semibold">{code}</span>
                          <span className="text-sm text-gray-600 ml-2">{data.name}</span>
                        </div>
                        <div className="text-right text-sm">
                          <span className="text-gray-600">{data.claims}건</span>
                          {data.kdrg_changes > 0 && (
                            <span className="text-red-500 ml-2">변경 {data.kdrg_changes}</span>
                          )}
                        </div>
                      </div>
                    ))}
                </div>
              ) : (
                <div className="flex items-center justify-center h-[300px] text-gray-500">
                  데이터가 없습니다
                </div>
              )}
            </div>
          </div>

          {/* KDRG 변경 패턴 */}
          {kdrChanges && kdrChanges.top_patterns?.length > 0 && (
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold mb-4">주요 KDRG 변경 패턴</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left">변경 패턴</th>
                      <th className="px-4 py-2 text-right">건수</th>
                      <th className="px-4 py-2 text-right">총 조정액</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {kdrChanges.top_patterns.slice(0, 10).map((pattern: any, idx: number) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-4 py-2 font-mono">{pattern.pattern}</td>
                        <td className="px-4 py-2 text-right">{pattern.count}건</td>
                        <td className="px-4 py-2 text-right text-red-600">
                          {formatAmount(pattern.total_adjustment)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 비교 분석 탭 */}
      {activeTab === 'compare' && (
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="font-semibold mb-4">청구 vs 심사 결과 비교</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  청구 데이터 파일
                </label>
                <select
                  value={compareFiles.claim}
                  onChange={e => setCompareFiles(prev => ({ ...prev, claim: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="">선택하세요</option>
                  {files
                    .filter(f => f.data_type === 'drg_claim')
                    .map(f => (
                      <option key={f.file_id} value={f.file_id}>
                        {f.file_name}
                      </option>
                    ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  심사 결과 파일
                </label>
                <select
                  value={compareFiles.review}
                  onChange={e => setCompareFiles(prev => ({ ...prev, review: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="">선택하세요</option>
                  {files
                    .filter(f => f.data_type === 'review_result')
                    .map(f => (
                      <option key={f.file_id} value={f.file_id}>
                        {f.file_name}
                      </option>
                    ))}
                </select>
              </div>
            </div>
            <button
              onClick={handleCompare}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 flex items-center gap-2"
            >
              <GitCompare className="w-4 h-4" />
              비교 분석 실행
            </button>
          </div>

          {compareResult && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="font-semibold mb-4">비교 결과</h3>

              {/* 요약 */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="p-3 bg-blue-50 rounded-lg">
                  <p className="text-xs text-blue-600">총 청구</p>
                  <p className="text-lg font-semibold">{compareResult.total_claims}건</p>
                </div>
                <div className="p-3 bg-green-50 rounded-lg">
                  <p className="text-xs text-green-600">매칭됨</p>
                  <p className="text-lg font-semibold">{compareResult.matched}건</p>
                </div>
                <div className="p-3 bg-yellow-50 rounded-lg">
                  <p className="text-xs text-yellow-600">KDRG 변경</p>
                  <p className="text-lg font-semibold">
                    {compareResult.kdrg_changed?.length || 0}건
                  </p>
                </div>
                <div className="p-3 bg-red-50 rounded-lg">
                  <p className="text-xs text-red-600">조정률</p>
                  <p className="text-lg font-semibold">
                    {compareResult.statistics?.avg_adjustment_rate || 0}%
                  </p>
                </div>
              </div>

              {/* KDRG 변경 목록 */}
              {compareResult.kdrg_changed?.length > 0 && (
                <div className="mb-6">
                  <h4 className="font-medium mb-2">KDRG 변경 건</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-3 py-2 text-left">청구번호</th>
                          <th className="px-3 py-2 text-left">환자ID</th>
                          <th className="px-3 py-2 text-left">원 KDRG</th>
                          <th className="px-3 py-2 text-left">심사 KDRG</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {compareResult.kdrg_changed.slice(0, 20).map((item: any, idx: number) => (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="px-3 py-2">{item.claim_id}</td>
                            <td className="px-3 py-2">{item.patient_id}</td>
                            <td className="px-3 py-2 font-mono">{item.original_kdrg}</td>
                            <td className="px-3 py-2 font-mono text-red-600">
                              {item.reviewed_kdrg}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 자동 다운로드(포털) 탭 */}
      {activeTab === 'portal' && (
        <div className="space-y-6">
          {/* 포털 상태 및 로그인 */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <Cloud className="w-6 h-6 text-blue-600" />
                <h2 className="font-semibold text-gray-900">요양기관업무포털 연동</h2>
                {portalStatus?.is_simulation && (
                  <span className="px-2 py-0.5 text-xs bg-yellow-100 text-yellow-700 rounded">
                    시뮬레이션 모드
                  </span>
                )}
              </div>
              <button
                onClick={() => setShowConfigModal(true)}
                className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 border rounded-lg"
              >
                <Settings className="w-4 h-4" />
                설정
              </button>
            </div>

            {portalStatus?.is_logged_in ? (
              <div className="flex items-center justify-between p-4 bg-green-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <div>
                    <p className="font-medium text-green-800">포털 연결됨</p>
                    <p className="text-sm text-green-600">
                      요양기관: {portalStatus?.hospital_code || '-'}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={fetchPortalFiles}
                    disabled={portalLoading}
                    className="px-3 py-2 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 flex items-center gap-1"
                  >
                    <RefreshCw className={`w-4 h-4 ${portalLoading ? 'animate-spin' : ''}`} />
                    새로고침
                  </button>
                  <button
                    onClick={handleAutoDownload}
                    disabled={portalLoading}
                    className="px-3 py-2 text-sm bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 flex items-center gap-1"
                  >
                    <FolderDown className="w-4 h-4" />
                    자동 다운로드
                  </button>
                  <button
                    onClick={handlePortalLogout}
                    className="px-3 py-2 text-sm border text-gray-600 rounded-lg hover:bg-gray-50 flex items-center gap-1"
                  >
                    <LogOut className="w-4 h-4" />
                    로그아웃
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="p-4 bg-blue-50 rounded-lg">
                  <p className="text-sm text-blue-700">
                    <Info className="w-4 h-4 inline mr-1" />
                    심평원 요양기관업무포털(biz.hira.or.kr)에 로그인하여 환류파일을 자동으로
                    다운로드할 수 있습니다.
                  </p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      요양기관번호
                    </label>
                    <input
                      type="text"
                      value={loginForm.hospital_code}
                      onChange={e =>
                        setLoginForm(prev => ({ ...prev, hospital_code: e.target.value }))
                      }
                      placeholder="12345678"
                      className="w-full border rounded-lg px-3 py-2"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      사용자 ID
                    </label>
                    <input
                      type="text"
                      value={loginForm.user_id}
                      onChange={e => setLoginForm(prev => ({ ...prev, user_id: e.target.value }))}
                      placeholder="user_id"
                      className="w-full border rounded-lg px-3 py-2"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">비밀번호</label>
                    <input
                      type="password"
                      value={loginForm.password}
                      onChange={e => setLoginForm(prev => ({ ...prev, password: e.target.value }))}
                      placeholder="••••••••"
                      className="w-full border rounded-lg px-3 py-2"
                    />
                  </div>
                </div>
                <button
                  onClick={handlePortalLogin}
                  disabled={portalLoading}
                  className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 flex items-center gap-2"
                >
                  {portalLoading ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <LogIn className="w-4 h-4" />
                  )}
                  포털 로그인
                </button>
              </div>
            )}
          </div>

          {/* 포털 파일 목록 */}
          {portalStatus?.is_logged_in && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-gray-900">환류파일 목록</h3>
                {selectedPortalFiles.length > 0 && (
                  <button
                    onClick={handlePortalDownload}
                    disabled={portalLoading}
                    className="px-3 py-2 text-sm bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 flex items-center gap-1"
                  >
                    <Download className="w-4 h-4" />
                    선택 다운로드 ({selectedPortalFiles.length})
                  </button>
                )}
              </div>

              {portalLoading ? (
                <div className="flex justify-center py-8">
                  <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
                </div>
              ) : portalFiles.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <FileSpreadsheet className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>다운로드 가능한 파일이 없습니다</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left">
                          <input
                            type="checkbox"
                            checked={selectedPortalFiles.length === portalFiles.length}
                            onChange={e => {
                              if (e.target.checked) {
                                setSelectedPortalFiles(portalFiles.map(f => f.file_id));
                              } else {
                                setSelectedPortalFiles([]);
                              }
                            }}
                            className="rounded"
                          />
                        </th>
                        <th className="px-3 py-2 text-left">파일명</th>
                        <th className="px-3 py-2 text-left">유형</th>
                        <th className="px-3 py-2 text-left">생성일</th>
                        <th className="px-3 py-2 text-right">크기</th>
                        <th className="px-3 py-2 text-center">상태</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {portalFiles.map(file => (
                        <tr key={file.file_id} className="hover:bg-gray-50">
                          <td className="px-3 py-2">
                            <input
                              type="checkbox"
                              checked={selectedPortalFiles.includes(file.file_id)}
                              onChange={e => {
                                if (e.target.checked) {
                                  setSelectedPortalFiles(prev => [...prev, file.file_id]);
                                } else {
                                  setSelectedPortalFiles(prev =>
                                    prev.filter(id => id !== file.file_id)
                                  );
                                }
                              }}
                              className="rounded"
                            />
                          </td>
                          <td className="px-3 py-2 font-medium">{file.file_name}</td>
                          <td className="px-3 py-2">{file.file_type}</td>
                          <td className="px-3 py-2">{file.file_date}</td>
                          <td className="px-3 py-2 text-right">
                            {(file.file_size / 1024).toFixed(0)} KB
                          </td>
                          <td className="px-3 py-2 text-center">
                            {file.is_new ? (
                              <span className="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded">
                                신규
                              </span>
                            ) : file.downloaded ? (
                              <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
                                다운로드됨
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded">
                                대기
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* 다운로드 이력 */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <History className="w-5 h-5 text-gray-600" />
                <h3 className="font-semibold text-gray-900">다운로드 이력</h3>
              </div>
              <button
                onClick={fetchDownloadHistory}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                새로고침
              </button>
            </div>

            {downloadHistory.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <Clock className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>다운로드 이력이 없습니다</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[300px] overflow-y-auto">
                {downloadHistory.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      {item.success ? (
                        <CheckCircle className="w-5 h-5 text-green-600" />
                      ) : (
                        <AlertCircle className="w-5 h-5 text-red-600" />
                      )}
                      <div>
                        <p className="font-medium text-sm">{item.file_name}</p>
                        <p className="text-xs text-gray-500">{item.file_type}</p>
                      </div>
                    </div>
                    <div className="text-right text-xs text-gray-500">
                      {new Date(item.downloaded_at).toLocaleString('ko-KR')}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 설정 모달 */}
      {showConfigModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-lg">자동 다운로드 설정</h3>
              <button
                onClick={() => setShowConfigModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-gray-700">자동 다운로드 활성화</label>
                <button
                  onClick={() => setPortalConfig(prev => ({ ...prev, enabled: !prev.enabled }))}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    portalConfig.enabled ? 'bg-blue-600' : 'bg-gray-200'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
                      portalConfig.enabled ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">실행 시간</label>
                <input
                  type="time"
                  value={portalConfig.schedule_time}
                  onChange={e =>
                    setPortalConfig(prev => ({ ...prev, schedule_time: e.target.value }))
                  }
                  className="w-full border rounded-lg px-3 py-2"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  다운로드 경로
                </label>
                <input
                  type="text"
                  value={portalConfig.download_path}
                  onChange={e =>
                    setPortalConfig(prev => ({ ...prev, download_path: e.target.value }))
                  }
                  className="w-full border rounded-lg px-3 py-2"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  파일 보관 기간 (일)
                </label>
                <input
                  type="number"
                  value={portalConfig.days_to_keep}
                  onChange={e =>
                    setPortalConfig(prev => ({
                      ...prev,
                      days_to_keep: parseInt(e.target.value) || 90,
                    }))
                  }
                  min="1"
                  max="365"
                  className="w-full border rounded-lg px-3 py-2"
                />
              </div>

              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-gray-700">다운로드 후 자동 파싱</label>
                <button
                  onClick={() =>
                    setPortalConfig(prev => ({ ...prev, auto_parse: !prev.auto_parse }))
                  }
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    portalConfig.auto_parse ? 'bg-blue-600' : 'bg-gray-200'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
                      portalConfig.auto_parse ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowConfigModal(false)}
                className="flex-1 px-4 py-2 border text-gray-700 rounded-lg hover:bg-gray-50"
              >
                취소
              </button>
              <button
                onClick={handleSaveConfig}
                className="flex-1 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
              >
                저장
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
