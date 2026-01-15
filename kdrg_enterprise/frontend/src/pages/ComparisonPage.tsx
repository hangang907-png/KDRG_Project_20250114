import { useState, useEffect, useCallback } from 'react';
import {
  GitCompare,
  Target,
  AlertTriangle,
  CheckCircle,
  XCircle,
  TrendingUp,
  TrendingDown,
  BarChart3,
  FileText,
  RefreshCw,
  ChevronRight,
  Info,
  Lightbulb,
  Download,
  Filter,
} from 'lucide-react';
import api from '../services/api';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
} from 'recharts';

interface FeedbackFile {
  file_id: string;
  file_name: string;
  data_type: string;
  total_records: number;
}

interface ComparisonResult {
  result_id: string;
  created_at: string;
  predicted_file: string;
  actual_file: string;
  total_cases: number;
  accuracy_rate: number;
}

interface ComparisonDetail {
  claim_id: string;
  patient_id: string;
  predicted_kdrg: string;
  actual_kdrg: string;
  is_match: boolean;
  mismatch_type: string;
  mismatch_causes: string[];
  amount_difference: number;
  risk_score: number;
  recommendation: string;
}

interface Recommendation {
  priority: string;
  category: string;
  issue: string;
  recommendation: string;
  affected_cases: number;
  potential_impact: number;
}

const MISMATCH_TYPE_LABELS: Record<string, { label: string; color: string; icon: any }> = {
  exact_match: { label: '정확히 일치', color: 'text-green-600 bg-green-50', icon: CheckCircle },
  severity_diff: { label: '중증도 차이', color: 'text-yellow-600 bg-yellow-50', icon: AlertTriangle },
  aadrg_diff: { label: 'AADRG 차이', color: 'text-orange-600 bg-orange-50', icon: AlertTriangle },
  mdc_diff: { label: 'MDC 차이', color: 'text-red-600 bg-red-50', icon: XCircle },
};

const CAUSE_LABELS: Record<string, string> = {
  diagnosis_coding: '진단 코딩',
  procedure_coding: '수술 코딩',
  severity_assessment: '중증도 평가',
  complication: '합병증/동반질환',
  documentation: '의무기록',
  rule_change: '급여기준 변경',
  unknown: '원인 불명',
};

const COLORS = ['#10B981', '#F59E0B', '#F97316', '#EF4444', '#8B5CF6', '#3B82F6'];

export default function ComparisonPage() {
  const [files, setFiles] = useState<FeedbackFile[]>([]);
  const [results, setResults] = useState<ComparisonResult[]>([]);
  const [selectedResult, setSelectedResult] = useState<any>(null);
  const [details, setDetails] = useState<ComparisonDetail[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [drg7Analysis, setDrg7Analysis] = useState<any>(null);
  
  const [predictedFile, setPredictedFile] = useState('');
  const [actualFile, setActualFile] = useState('');
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [activeTab, setActiveTab] = useState<'analyze' | 'results' | 'details'>('analyze');
  const [mismatchFilter, setMismatchFilter] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  // 파일 목록 및 결과 조회
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [filesRes, resultsRes] = await Promise.all([
        api.get('/feedback/files'),
        api.get('/comparison/results'),
      ]);
      setFiles(filesRes.data.files || []);
      setResults(resultsRes.data.results || []);
    } catch (err) {
      console.error('데이터 조회 실패:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // 비교 분석 실행
  const handleAnalyze = async () => {
    if (!predictedFile || !actualFile) {
      setError('청구 데이터와 심사 결과 파일을 모두 선택해주세요.');
      return;
    }

    setAnalyzing(true);
    setError(null);

    try {
      const response = await api.post('/comparison/analyze', null, {
        params: {
          predicted_file_id: predictedFile,
          actual_file_id: actualFile,
        },
      });

      if (response.data.success) {
        setSelectedResult(response.data);
        setActiveTab('results');
        fetchData(); // 결과 목록 갱신
        
        // 상세 데이터 로드
        await loadResultDetails(response.data.result_id);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '분석에 실패했습니다.');
    } finally {
      setAnalyzing(false);
    }
  };

  // 결과 상세 로드
  const loadResultDetails = async (resultId: string) => {
    try {
      const [detailsRes, recsRes, drg7Res] = await Promise.all([
        api.get(`/comparison/results/${resultId}/details`, { params: { page_size: 100 } }),
        api.get(`/comparison/results/${resultId}/recommendations`),
        api.get(`/comparison/results/${resultId}/drg7`),
      ]);
      
      setDetails(detailsRes.data.records || []);
      setRecommendations(recsRes.data.recommendations || []);
      setDrg7Analysis(drg7Res.data.drg7_analysis || {});
    } catch (err) {
      console.error('상세 데이터 로드 실패:', err);
    }
  };

  // 결과 선택
  const handleSelectResult = async (result: ComparisonResult) => {
    try {
      const response = await api.get(`/comparison/results/${result.result_id}`);
      setSelectedResult(response.data);
      await loadResultDetails(result.result_id);
      setActiveTab('results');
    } catch (err) {
      setError('결과를 불러오는데 실패했습니다.');
    }
  };

  // 금액 포맷
  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat('ko-KR', { style: 'currency', currency: 'KRW' }).format(amount);
  };

  // 불일치 유형별 차트 데이터
  const getMismatchChartData = () => {
    if (!selectedResult?.mismatch_breakdown) return [];
    const breakdown = selectedResult.mismatch_breakdown;
    return [
      { name: '일치', value: breakdown.exact_matches, color: '#10B981' },
      { name: '중증도', value: breakdown.severity_mismatches, color: '#F59E0B' },
      { name: 'AADRG', value: breakdown.aadrg_mismatches, color: '#F97316' },
      { name: 'MDC', value: breakdown.mdc_mismatches, color: '#EF4444' },
    ].filter(d => d.value > 0);
  };

  // 원인 분포 차트 데이터
  const getCauseChartData = () => {
    if (!selectedResult?.cause_distribution) return [];
    return Object.entries(selectedResult.cause_distribution).map(([cause, count]) => ({
      name: CAUSE_LABELS[cause] || cause,
      value: count as number,
    }));
  };

  // 필터된 상세 데이터
  const filteredDetails = mismatchFilter
    ? details.filter(d => d.mismatch_type === mismatchFilter)
    : details;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">예측 vs 실제 KDRG 비교 분석</h1>
        <p className="text-gray-600 mt-1">청구(예측) KDRG와 심사(실제) 결과 비교 및 정확도 분석</p>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {/* 탭 네비게이션 */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-4">
          {[
            { id: 'analyze', label: '분석 실행', icon: GitCompare },
            { id: 'results', label: '분석 결과', icon: BarChart3 },
            { id: 'details', label: '상세 비교', icon: FileText },
          ].map((tab) => (
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

      {/* 분석 실행 탭 */}
      {activeTab === 'analyze' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 분석 설정 */}
          <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
            <h2 className="font-semibold text-lg mb-4">비교 분석 설정</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  청구 데이터 (예측)
                </label>
                <select
                  value={predictedFile}
                  onChange={(e) => setPredictedFile(e.target.value)}
                  className="w-full border rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">파일 선택...</option>
                  {files.filter(f => f.data_type === 'drg_claim').map(f => (
                    <option key={f.file_id} value={f.file_id}>
                      {f.file_name} ({f.total_records}건)
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 mt-1">병원에서 청구한 KDRG 코드</p>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  심사 결과 (실제)
                </label>
                <select
                  value={actualFile}
                  onChange={(e) => setActualFile(e.target.value)}
                  className="w-full border rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">파일 선택...</option>
                  {files.filter(f => f.data_type === 'review_result').map(f => (
                    <option key={f.file_id} value={f.file_id}>
                      {f.file_name} ({f.total_records}건)
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 mt-1">심평원 심사 후 확정된 KDRG 코드</p>
              </div>
            </div>

            <button
              onClick={handleAnalyze}
              disabled={analyzing || !predictedFile || !actualFile}
              className={`w-full py-3 rounded-lg font-medium flex items-center justify-center gap-2 ${
                analyzing || !predictedFile || !actualFile
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              {analyzing ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  분석 중...
                </>
              ) : (
                <>
                  <GitCompare className="w-5 h-5" />
                  비교 분석 실행
                </>
              )}
            </button>

            <div className="mt-6 p-4 bg-blue-50 rounded-lg">
              <div className="flex gap-2">
                <Info className="w-5 h-5 text-blue-600 flex-shrink-0" />
                <div className="text-sm text-blue-800">
                  <p className="font-medium mb-1">비교 분석 항목</p>
                  <ul className="list-disc list-inside space-y-1 text-blue-700">
                    <li>전체 정확도 (KDRG 일치율)</li>
                    <li>중증도 정확도 (AADRG 일치율)</li>
                    <li>불일치 유형 분류 및 원인 분석</li>
                    <li>7개 DRG군별 정확도</li>
                    <li>개선 권고사항</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

          {/* 이전 분석 결과 */}
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="font-semibold mb-4">이전 분석 결과</h3>
            {results.length === 0 ? (
              <p className="text-gray-500 text-center py-8">분석 결과가 없습니다</p>
            ) : (
              <div className="space-y-2 max-h-[400px] overflow-y-auto">
                {results.map((result) => (
                  <div
                    key={result.result_id}
                    onClick={() => handleSelectResult(result)}
                    className="p-3 border rounded-lg cursor-pointer hover:border-blue-500 transition-colors"
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="font-medium text-sm">{result.total_cases}건 분석</p>
                        <p className="text-xs text-gray-500">
                          {new Date(result.created_at).toLocaleString('ko-KR')}
                        </p>
                      </div>
                      <div className={`text-lg font-bold ${
                        result.accuracy_rate >= 80 ? 'text-green-600' :
                        result.accuracy_rate >= 60 ? 'text-yellow-600' : 'text-red-600'
                      }`}>
                        {result.accuracy_rate}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 분석 결과 탭 */}
      {activeTab === 'results' && selectedResult && (
        <div className="space-y-6">
          {/* 요약 카드 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center gap-2 text-gray-500 mb-1">
                <Target className="w-4 h-4" />
                <span className="text-sm">전체 정확도</span>
              </div>
              <p className={`text-3xl font-bold ${
                selectedResult.summary?.accuracy_rate >= 80 ? 'text-green-600' :
                selectedResult.summary?.accuracy_rate >= 60 ? 'text-yellow-600' : 'text-red-600'
              }`}>
                {selectedResult.summary?.accuracy_rate || 0}%
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center gap-2 text-gray-500 mb-1">
                <BarChart3 className="w-4 h-4" />
                <span className="text-sm">중증도 정확도</span>
              </div>
              <p className="text-3xl font-bold text-blue-600">
                {selectedResult.summary?.severity_accuracy || 0}%
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center gap-2 text-gray-500 mb-1">
                <FileText className="w-4 h-4" />
                <span className="text-sm">분석 건수</span>
              </div>
              <p className="text-3xl font-bold text-gray-900">
                {selectedResult.summary?.total_cases || 0}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center gap-2 text-gray-500 mb-1">
                {(selectedResult.summary?.total_difference || 0) > 0 ? (
                  <TrendingDown className="w-4 h-4 text-red-500" />
                ) : (
                  <TrendingUp className="w-4 h-4 text-green-500" />
                )}
                <span className="text-sm">금액 차이</span>
              </div>
              <p className={`text-2xl font-bold ${
                (selectedResult.summary?.total_difference || 0) > 0 ? 'text-red-600' : 'text-green-600'
              }`}>
                {formatAmount(Math.abs(selectedResult.summary?.total_difference || 0))}
              </p>
            </div>
          </div>

          {/* 차트 영역 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 불일치 유형 분포 */}
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold mb-4">불일치 유형 분포</h3>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={getMismatchChartData()}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  >
                    {getMismatchChartData().map((entry, idx) => (
                      <Cell key={idx} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* 원인 분포 */}
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold mb-4">불일치 원인 분포</h3>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={getCauseChartData()} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis type="category" dataKey="name" width={100} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#3B82F6" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 7개 DRG군 분석 */}
          {drg7Analysis && (
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold mb-4">7개 DRG군별 정확도</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {Object.entries(drg7Analysis)
                  .filter(([code]) => code !== 'OTHER')
                  .map(([code, data]: [string, any]) => (
                    <div key={code} className="p-3 border rounded-lg">
                      <div className="flex justify-between items-start mb-2">
                        <span className="font-mono font-bold">{code}</span>
                        <span className={`text-lg font-bold ${
                          data.accuracy >= 80 ? 'text-green-600' :
                          data.accuracy >= 60 ? 'text-yellow-600' : 'text-red-600'
                        }`}>
                          {data.accuracy}%
                        </span>
                      </div>
                      <p className="text-xs text-gray-500">
                        {data.total}건 중 {data.matches}건 일치
                      </p>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* 개선 권고사항 */}
          {recommendations.length > 0 && (
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold mb-4 flex items-center gap-2">
                <Lightbulb className="w-5 h-5 text-yellow-500" />
                개선 권고사항
              </h3>
              <div className="space-y-3">
                {recommendations.map((rec, idx) => (
                  <div
                    key={idx}
                    className={`p-4 rounded-lg border-l-4 ${
                      rec.priority === 'high' ? 'border-red-500 bg-red-50' :
                      rec.priority === 'medium' ? 'border-yellow-500 bg-yellow-50' :
                      'border-blue-500 bg-blue-50'
                    }`}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <span className={`text-xs font-medium px-2 py-1 rounded ${
                          rec.priority === 'high' ? 'bg-red-200 text-red-800' :
                          rec.priority === 'medium' ? 'bg-yellow-200 text-yellow-800' :
                          'bg-blue-200 text-blue-800'
                        }`}>
                          {rec.priority === 'high' ? '높음' : rec.priority === 'medium' ? '중간' : '낮음'}
                        </span>
                        <span className="ml-2 text-sm font-medium">{rec.category}</span>
                      </div>
                      <span className="text-sm text-gray-500">{rec.affected_cases}건 영향</span>
                    </div>
                    <p className="mt-2 text-sm text-gray-700">{rec.issue}</p>
                    <p className="mt-1 text-sm font-medium text-gray-900">{rec.recommendation}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 주요 불일치 패턴 */}
          {selectedResult.top_mismatch_patterns?.length > 0 && (
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold mb-4">주요 불일치 패턴</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left">변경 패턴</th>
                      <th className="px-4 py-2 text-right">건수</th>
                      <th className="px-4 py-2 text-right">총 금액 차이</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {selectedResult.top_mismatch_patterns.map((pattern: any, idx: number) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-4 py-2 font-mono">{pattern.pattern}</td>
                        <td className="px-4 py-2 text-right">{pattern.count}건</td>
                        <td className="px-4 py-2 text-right text-red-600">
                          {formatAmount(pattern.total_diff)}
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

      {/* 상세 비교 탭 */}
      {activeTab === 'details' && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-4 border-b flex items-center justify-between">
            <h3 className="font-semibold">상세 비교 데이터</h3>
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-gray-400" />
              <select
                value={mismatchFilter}
                onChange={(e) => setMismatchFilter(e.target.value)}
                className="border rounded px-3 py-1 text-sm"
              >
                <option value="">전체</option>
                <option value="exact_match">일치만</option>
                <option value="severity_diff">중증도 차이</option>
                <option value="aadrg_diff">AADRG 차이</option>
                <option value="mdc_diff">MDC 차이</option>
              </select>
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left">청구번호</th>
                  <th className="px-3 py-2 text-left">예측 KDRG</th>
                  <th className="px-3 py-2 text-left">실제 KDRG</th>
                  <th className="px-3 py-2 text-center">결과</th>
                  <th className="px-3 py-2 text-left">원인</th>
                  <th className="px-3 py-2 text-right">금액차이</th>
                  <th className="px-3 py-2 text-center">위험도</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filteredDetails.slice(0, 50).map((detail, idx) => {
                  const typeInfo = MISMATCH_TYPE_LABELS[detail.mismatch_type];
                  return (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-3 py-2">{detail.claim_id}</td>
                      <td className="px-3 py-2 font-mono">{detail.predicted_kdrg}</td>
                      <td className={`px-3 py-2 font-mono ${!detail.is_match ? 'text-red-600 font-semibold' : ''}`}>
                        {detail.actual_kdrg}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs ${typeInfo?.color}`}>
                          {typeInfo?.label}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        {detail.mismatch_causes.map(c => CAUSE_LABELS[c] || c).join(', ')}
                      </td>
                      <td className={`px-3 py-2 text-right ${detail.amount_difference > 0 ? 'text-red-600' : ''}`}>
                        {formatAmount(detail.amount_difference)}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${
                              detail.risk_score >= 70 ? 'bg-red-500' :
                              detail.risk_score >= 40 ? 'bg-yellow-500' : 'bg-green-500'
                            }`}
                            style={{ width: `${detail.risk_score}%` }}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          
          {filteredDetails.length === 0 && (
            <div className="p-8 text-center text-gray-500">
              데이터가 없습니다. 먼저 분석을 실행해주세요.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
