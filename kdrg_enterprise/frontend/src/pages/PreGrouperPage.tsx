import { useState, useEffect, useCallback } from 'react';
import {
  Calculator,
  Upload,
  FileSpreadsheet,
  History,
  RefreshCw,
  AlertTriangle,
  Info,
  Download,
  ChevronRight,
  Lightbulb,
  Activity,
  TrendingUp,
} from 'lucide-react';
import api from '../services/api';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';

interface GrouperResult {
  claim_id: string;
  patient_id: string;
  mdc: string;
  mdc_name: string;
  aadrg: string;
  kdrg: string;
  severity: number;
  relative_weight: number;
  base_amount: number;
  estimated_amount: number;
  los: number;
  los_lower: number;
  los_upper: number;
  los_outlier: string;
  drg_type: string;
  grouper_path: string[];
  warnings: string[];
  confidence: number;
}

interface DRG7Info {
  code: string;
  name: string;
  procedures: string[];
  diagnoses: string[];
  base_weight: number;
  los_lower: number;
  los_upper: number;
}

interface OptimizationSuggestion {
  type: string;
  current: any;
  potential?: any;
  optimal?: any;
  action: string;
  impact: number;
}

const COLORS = [
  '#10B981',
  '#3B82F6',
  '#F59E0B',
  '#EF4444',
  '#8B5CF6',
  '#EC4899',
  '#06B6D4',
  '#84CC16',
];

const SEVERITY_LABELS: Record<number, { label: string; color: string }> = {
  0: { label: '없음', color: 'bg-gray-100 text-gray-700' },
  1: { label: '경도', color: 'bg-green-100 text-green-700' },
  2: { label: '중등도', color: 'bg-yellow-100 text-yellow-700' },
  3: { label: '고도', color: 'bg-orange-100 text-orange-700' },
  4: { label: '극고도', color: 'bg-red-100 text-red-700' },
};

const LOS_OUTLIER_LABELS: Record<string, { label: string; color: string }> = {
  normal: { label: '정상', color: 'text-green-600' },
  short: { label: '단기', color: 'text-yellow-600' },
  long: { label: '장기', color: 'text-red-600' },
};

export default function PreGrouperPage() {
  const [activeTab, setActiveTab] = useState<'single' | 'batch' | 'history' | 'info'>('single');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GrouperResult | null>(null);
  const [batchResults, setBatchResults] = useState<GrouperResult[]>([]);
  const [optimization, setOptimization] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [drg7Info, setDrg7Info] = useState<DRG7Info[]>([]);
  const [statistics, setStatistics] = useState<any>(null);

  // 단건 입력 폼
  const [formData, setFormData] = useState({
    patient_id: '',
    age: '',
    sex: 'M',
    admission_date: '',
    discharge_date: '',
    los: '',
    main_diagnosis: '',
    sub_diagnoses: '',
    procedures: '',
  });

  // 데이터 로드
  const fetchData = useCallback(async () => {
    try {
      const [historyRes, drg7Res, statsRes] = await Promise.all([
        api.get('/pregrouper/history'),
        api.get('/pregrouper/drg7-info'),
        api.get('/pregrouper/statistics'),
      ]);
      setHistory(historyRes.data.history || []);
      setDrg7Info(drg7Res.data.drg7 || []);
      setStatistics(statsRes.data);
    } catch (err) {
      console.error('데이터 로드 실패:', err);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // 폼 입력 핸들러
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));

    // 재원일수 자동 계산
    if (name === 'admission_date' || name === 'discharge_date') {
      const admDate = name === 'admission_date' ? value : formData.admission_date;
      const disDate = name === 'discharge_date' ? value : formData.discharge_date;
      if (admDate && disDate) {
        const los = Math.ceil(
          (new Date(disDate).getTime() - new Date(admDate).getTime()) / (1000 * 60 * 60 * 24)
        );
        if (los >= 0) {
          setFormData(prev => ({ ...prev, los: String(los) }));
        }
      }
    }
  };

  // 단건 그루핑 실행
  const handleSingleGroup = async () => {
    if (
      !formData.patient_id ||
      !formData.main_diagnosis ||
      !formData.admission_date ||
      !formData.discharge_date
    ) {
      setError('환자ID, 주진단, 입원일, 퇴원일은 필수입니다.');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setOptimization(null);

    try {
      const response = await api.post('/pregrouper/group-simple', {
        patient_id: formData.patient_id,
        age: parseInt(formData.age) || 0,
        sex: formData.sex,
        admission_date: formData.admission_date,
        discharge_date: formData.discharge_date,
        los: parseInt(formData.los) || 0,
        main_diagnosis: formData.main_diagnosis,
        sub_diagnoses: formData.sub_diagnoses
          .split(',')
          .map(s => s.trim())
          .filter(s => s),
        procedures: formData.procedures
          .split(',')
          .map(s => s.trim())
          .filter(s => s),
      });

      if (response.data.success) {
        setResult(response.data.result);

        // 최적화 분석
        const optRes = await api.post('/pregrouper/optimize', {
          patient_id: formData.patient_id,
          age: parseInt(formData.age) || 0,
          sex: formData.sex,
          admission_date: formData.admission_date,
          discharge_date: formData.discharge_date,
          los: parseInt(formData.los) || 0,
          main_diagnosis: formData.main_diagnosis,
          sub_diagnoses: formData.sub_diagnoses
            .split(',')
            .map(s => s.trim())
            .filter(s => s),
          procedures: formData.procedures
            .split(',')
            .map(s => s.trim())
            .filter(s => s),
        });
        setOptimization(optRes.data.optimization);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '그루핑에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  // 파일 업로드
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setError(null);
    setBatchResults([]);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await api.post('/pregrouper/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      if (response.data.success) {
        setBatchResults(response.data.results || []);
        fetchData(); // 히스토리 갱신
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '파일 업로드에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  // 금액 포맷
  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat('ko-KR', { style: 'currency', currency: 'KRW' }).format(amount);
  };

  // 배치 결과 통계
  const getBatchStats = () => {
    if (!batchResults.length) return null;

    const drgTypeCount: Record<string, number> = {};
    let totalAmount = 0;

    batchResults.forEach(r => {
      drgTypeCount[r.drg_type] = (drgTypeCount[r.drg_type] || 0) + 1;
      totalAmount += r.estimated_amount;
    });

    return {
      total: batchResults.length,
      drgTypeCount,
      totalAmount,
      chartData: Object.entries(drgTypeCount).map(([name, value]) => ({ name, value })),
    };
  };

  const batchStats = getBatchStats();

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">KDRG Pre-Grouper</h1>
        <p className="text-gray-600 mt-1">청구 전 KDRG 코드 사전 분류 및 예측</p>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-start gap-2">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* 탭 네비게이션 */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-4">
          {[
            { id: 'single', label: '단건 그루핑', icon: Calculator },
            { id: 'batch', label: '일괄 그루핑', icon: FileSpreadsheet },
            { id: 'history', label: '그루핑 이력', icon: History },
            { id: 'info', label: 'DRG 정보', icon: Info },
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

      {/* 단건 그루핑 탭 */}
      {activeTab === 'single' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 입력 폼 */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="font-semibold text-lg mb-4">환자 정보 입력</h2>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">환자 ID *</label>
                  <input
                    type="text"
                    name="patient_id"
                    value={formData.patient_id}
                    onChange={handleInputChange}
                    className="w-full border rounded-lg px-3 py-2"
                    placeholder="12345678"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">나이</label>
                  <input
                    type="number"
                    name="age"
                    value={formData.age}
                    onChange={handleInputChange}
                    className="w-full border rounded-lg px-3 py-2"
                    placeholder="55"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">성별</label>
                  <select
                    name="sex"
                    value={formData.sex}
                    onChange={handleInputChange}
                    className="w-full border rounded-lg px-3 py-2"
                  >
                    <option value="M">남</option>
                    <option value="F">여</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">입원일 *</label>
                  <input
                    type="date"
                    name="admission_date"
                    value={formData.admission_date}
                    onChange={handleInputChange}
                    className="w-full border rounded-lg px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">퇴원일 *</label>
                  <input
                    type="date"
                    name="discharge_date"
                    value={formData.discharge_date}
                    onChange={handleInputChange}
                    className="w-full border rounded-lg px-3 py-2"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  재원일수 (자동 계산)
                </label>
                <input
                  type="number"
                  name="los"
                  value={formData.los}
                  onChange={handleInputChange}
                  className="w-full border rounded-lg px-3 py-2 bg-gray-50"
                  placeholder="0"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  주진단 (ICD-10) *
                </label>
                <input
                  type="text"
                  name="main_diagnosis"
                  value={formData.main_diagnosis}
                  onChange={handleInputChange}
                  className="w-full border rounded-lg px-3 py-2 font-mono"
                  placeholder="K80.1"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  부진단 (쉼표로 구분)
                </label>
                <input
                  type="text"
                  name="sub_diagnoses"
                  value={formData.sub_diagnoses}
                  onChange={handleInputChange}
                  className="w-full border rounded-lg px-3 py-2 font-mono"
                  placeholder="E11.9, I10, K21.0"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  수술/처치코드 (쉼표로 구분)
                </label>
                <input
                  type="text"
                  name="procedures"
                  value={formData.procedures}
                  onChange={handleInputChange}
                  className="w-full border rounded-lg px-3 py-2 font-mono"
                  placeholder="Q7651, Q7652"
                />
              </div>

              <button
                onClick={handleSingleGroup}
                disabled={loading}
                className={`w-full py-3 rounded-lg font-medium flex items-center justify-center gap-2 ${
                  loading
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    그루핑 중...
                  </>
                ) : (
                  <>
                    <Calculator className="w-5 h-5" />
                    KDRG 그루핑 실행
                  </>
                )}
              </button>
            </div>
          </div>

          {/* 결과 표시 */}
          <div className="space-y-4">
            {result && (
              <>
                {/* KDRG 결과 */}
                <div className="bg-white rounded-lg shadow p-6">
                  <div className="flex justify-between items-start mb-4">
                    <h2 className="font-semibold text-lg">그루핑 결과</h2>
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        result.confidence >= 80
                          ? 'bg-green-100 text-green-700'
                          : result.confidence >= 60
                            ? 'bg-yellow-100 text-yellow-700'
                            : 'bg-red-100 text-red-700'
                      }`}
                    >
                      신뢰도 {result.confidence}%
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div className="p-4 bg-blue-50 rounded-lg text-center">
                      <p className="text-xs text-gray-500 mb-1">KDRG 코드</p>
                      <p className="text-3xl font-bold font-mono text-blue-600">{result.kdrg}</p>
                    </div>
                    <div className="p-4 bg-gray-50 rounded-lg text-center">
                      <p className="text-xs text-gray-500 mb-1">AADRG</p>
                      <p className="text-2xl font-bold font-mono text-gray-700">{result.aadrg}</p>
                    </div>
                  </div>

                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between py-2 border-b">
                      <span className="text-gray-500">MDC (주진단범주)</span>
                      <span className="font-medium">
                        {result.mdc} - {result.mdc_name}
                      </span>
                    </div>
                    <div className="flex justify-between py-2 border-b">
                      <span className="text-gray-500">DRG 유형</span>
                      <span
                        className={`font-medium ${
                          result.drg_type !== '행위별' ? 'text-green-600' : 'text-gray-600'
                        }`}
                      >
                        {result.drg_type}
                      </span>
                    </div>
                    <div className="flex justify-between py-2 border-b">
                      <span className="text-gray-500">중증도</span>
                      <span
                        className={`px-2 py-0.5 rounded text-xs ${SEVERITY_LABELS[result.severity]?.color}`}
                      >
                        {result.severity} ({SEVERITY_LABELS[result.severity]?.label})
                      </span>
                    </div>
                    <div className="flex justify-between py-2 border-b">
                      <span className="text-gray-500">상대가치점수</span>
                      <span className="font-medium">{result.relative_weight}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b">
                      <span className="text-gray-500">재원일수</span>
                      <span className="font-medium">
                        {result.los}일
                        <span className={`ml-2 ${LOS_OUTLIER_LABELS[result.los_outlier]?.color}`}>
                          ({LOS_OUTLIER_LABELS[result.los_outlier]?.label}, 기준: {result.los_lower}
                          -{result.los_upper}일)
                        </span>
                      </span>
                    </div>
                    <div className="flex justify-between py-2">
                      <span className="text-gray-500">예상 청구액</span>
                      <span className="text-lg font-bold text-blue-600">
                        {formatAmount(result.estimated_amount)}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 분류 경로 */}
                <div className="bg-white rounded-lg shadow p-4">
                  <h3 className="font-semibold mb-3">분류 경로</h3>
                  <div className="space-y-1">
                    {result.grouper_path.map((step, idx) => (
                      <div key={idx} className="flex items-center gap-2 text-sm">
                        <ChevronRight className="w-4 h-4 text-gray-400" />
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 경고 메시지 */}
                {result.warnings.length > 0 && (
                  <div className="bg-yellow-50 rounded-lg border border-yellow-200 p-4">
                    <h3 className="font-semibold text-yellow-800 mb-2 flex items-center gap-2">
                      <AlertTriangle className="w-5 h-5" />
                      주의사항
                    </h3>
                    <ul className="list-disc list-inside space-y-1 text-sm text-yellow-700">
                      {result.warnings.map((warning, idx) => (
                        <li key={idx}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 최적화 제안 */}
                {optimization?.suggestions?.length > 0 && (
                  <div className="bg-blue-50 rounded-lg border border-blue-200 p-4">
                    <h3 className="font-semibold text-blue-800 mb-3 flex items-center gap-2">
                      <Lightbulb className="w-5 h-5" />
                      최적화 제안
                    </h3>
                    <div className="space-y-2">
                      {optimization.suggestions.map((sug: OptimizationSuggestion, idx: number) => (
                        <div key={idx} className="bg-white rounded p-3 text-sm">
                          <div className="flex justify-between items-start">
                            <span className="font-medium">{sug.action}</span>
                            {sug.impact !== 0 && (
                              <span
                                className={`text-xs px-2 py-0.5 rounded ${
                                  sug.impact > 0
                                    ? 'bg-green-100 text-green-700'
                                    : 'bg-red-100 text-red-700'
                                }`}
                              >
                                {sug.impact > 0 ? '+' : ''}
                                {formatAmount(sug.impact)}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {!result && !loading && (
              <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
                <Calculator className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p>환자 정보를 입력하고 그루핑을 실행하세요</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 일괄 그루핑 탭 */}
      {activeTab === 'batch' && (
        <div className="space-y-6">
          {/* 파일 업로드 */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="font-semibold text-lg mb-4">파일 업로드</h2>

            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
              <Upload className="w-12 h-12 mx-auto mb-4 text-gray-400" />
              <p className="text-gray-600 mb-2">CSV 또는 Excel 파일을 업로드하세요</p>
              <label className="inline-block">
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleFileUpload}
                  className="hidden"
                />
                <span className="px-4 py-2 bg-blue-600 text-white rounded-lg cursor-pointer hover:bg-blue-700">
                  파일 선택
                </span>
              </label>
            </div>

            <div className="mt-4 p-4 bg-gray-50 rounded-lg">
              <p className="text-sm font-medium text-gray-700 mb-2">필수 컬럼:</p>
              <code className="text-xs bg-gray-200 px-2 py-1 rounded">
                patient_id, age, sex, admission_date, discharge_date, los, main_diagnosis
              </code>
              <p className="text-sm font-medium text-gray-700 mt-3 mb-2">선택 컬럼:</p>
              <code className="text-xs bg-gray-200 px-2 py-1 rounded">
                sub_diagnoses, procedures (쉼표로 구분)
              </code>
            </div>
          </div>

          {/* 배치 결과 */}
          {batchStats && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* 통계 요약 */}
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="font-semibold mb-4">처리 결과</h3>
                <div className="space-y-4">
                  <div className="flex justify-between items-center py-2 border-b">
                    <span className="text-gray-500">총 건수</span>
                    <span className="text-2xl font-bold">{batchStats.total}건</span>
                  </div>
                  <div className="flex justify-between items-center py-2 border-b">
                    <span className="text-gray-500">총 예상 금액</span>
                    <span className="text-lg font-bold text-blue-600">
                      {formatAmount(batchStats.totalAmount)}
                    </span>
                  </div>
                </div>
              </div>

              {/* DRG 유형별 분포 */}
              <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
                <h3 className="font-semibold mb-4">DRG 유형별 분포</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={batchStats.chartData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={70}
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    >
                      {batchStats.chartData.map((_, idx) => (
                        <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* 결과 테이블 */}
          {batchResults.length > 0 && (
            <div className="bg-white rounded-lg shadow">
              <div className="p-4 border-b flex justify-between items-center">
                <h3 className="font-semibold">그루핑 결과 ({batchResults.length}건)</h3>
                <button className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 flex items-center gap-1">
                  <Download className="w-4 h-4" />
                  Excel 다운로드
                </button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left">환자ID</th>
                      <th className="px-3 py-2 text-left">주진단</th>
                      <th className="px-3 py-2 text-center">MDC</th>
                      <th className="px-3 py-2 text-center">KDRG</th>
                      <th className="px-3 py-2 text-center">중증도</th>
                      <th className="px-3 py-2 text-left">DRG유형</th>
                      <th className="px-3 py-2 text-center">재원</th>
                      <th className="px-3 py-2 text-right">예상금액</th>
                      <th className="px-3 py-2 text-center">신뢰도</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {batchResults.slice(0, 50).map((r, idx) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-3 py-2">{r.patient_id}</td>
                        <td className="px-3 py-2 font-mono">{r.mdc}</td>
                        <td className="px-3 py-2 text-center">{r.mdc}</td>
                        <td className="px-3 py-2 text-center font-mono font-bold text-blue-600">
                          {r.kdrg}
                        </td>
                        <td className="px-3 py-2 text-center">
                          <span
                            className={`px-2 py-0.5 rounded text-xs ${SEVERITY_LABELS[r.severity]?.color}`}
                          >
                            {r.severity}
                          </span>
                        </td>
                        <td className="px-3 py-2">{r.drg_type}</td>
                        <td
                          className={`px-3 py-2 text-center ${LOS_OUTLIER_LABELS[r.los_outlier]?.color}`}
                        >
                          {r.los}일
                        </td>
                        <td className="px-3 py-2 text-right">{formatAmount(r.estimated_amount)}</td>
                        <td className="px-3 py-2 text-center">
                          <span
                            className={`text-xs ${
                              r.confidence >= 80
                                ? 'text-green-600'
                                : r.confidence >= 60
                                  ? 'text-yellow-600'
                                  : 'text-red-600'
                            }`}
                          >
                            {r.confidence}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {batchResults.length > 50 && (
                <div className="p-4 text-center text-gray-500 border-t">
                  총 {batchResults.length}건 중 50건만 표시됩니다.
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 그루핑 이력 탭 */}
      {activeTab === 'history' && (
        <div className="space-y-6">
          {/* 통계 카드 */}
          {statistics && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-lg shadow p-4">
                <div className="flex items-center gap-2 text-gray-500 mb-1">
                  <Activity className="w-4 h-4" />
                  <span className="text-sm">총 그루핑</span>
                </div>
                <p className="text-2xl font-bold">{statistics.total_groupings || 0}건</p>
              </div>
              <div className="bg-white rounded-lg shadow p-4">
                <div className="flex items-center gap-2 text-gray-500 mb-1">
                  <Calculator className="w-4 h-4" />
                  <span className="text-sm">단건</span>
                </div>
                <p className="text-2xl font-bold">{statistics.by_type?.single || 0}건</p>
              </div>
              <div className="bg-white rounded-lg shadow p-4">
                <div className="flex items-center gap-2 text-gray-500 mb-1">
                  <FileSpreadsheet className="w-4 h-4" />
                  <span className="text-sm">배치/업로드</span>
                </div>
                <p className="text-2xl font-bold">
                  {(statistics.by_type?.batch || 0) + (statistics.by_type?.upload || 0)}건
                </p>
              </div>
              <div className="bg-white rounded-lg shadow p-4">
                <div className="flex items-center gap-2 text-gray-500 mb-1">
                  <TrendingUp className="w-4 h-4" />
                  <span className="text-sm">총 예상 금액</span>
                </div>
                <p className="text-lg font-bold text-blue-600">
                  {formatAmount(statistics.total_estimated_amount || 0)}
                </p>
              </div>
            </div>
          )}

          {/* 이력 목록 */}
          <div className="bg-white rounded-lg shadow">
            <div className="p-4 border-b flex justify-between items-center">
              <h3 className="font-semibold">그루핑 이력</h3>
              <button onClick={fetchData} className="p-2 text-gray-500 hover:text-gray-700">
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>

            {history.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <History className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p>그루핑 이력이 없습니다</p>
              </div>
            ) : (
              <div className="divide-y">
                {history.map(item => (
                  <div key={item.history_id} className="p-4 hover:bg-gray-50">
                    <div className="flex justify-between items-start">
                      <div>
                        <span
                          className={`text-xs px-2 py-0.5 rounded ${
                            item.type === 'single'
                              ? 'bg-blue-100 text-blue-700'
                              : item.type === 'batch'
                                ? 'bg-green-100 text-green-700'
                                : 'bg-purple-100 text-purple-700'
                          }`}
                        >
                          {item.type === 'single'
                            ? '단건'
                            : item.type === 'batch'
                              ? '배치'
                              : '업로드'}
                        </span>
                        <span className="ml-2 font-mono text-sm">{item.history_id}</span>
                      </div>
                      <span className="text-xs text-gray-500">
                        {new Date(item.created_at).toLocaleString('ko-KR')}
                      </span>
                    </div>
                    <div className="mt-2 text-sm text-gray-600">
                      {item.patient_id && <span>환자ID: {item.patient_id}</span>}
                      {item.total && (
                        <span>
                          총 {item.total}건 ({item.success_count}건 성공)
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* DRG 정보 탭 */}
      {activeTab === 'info' && (
        <div className="space-y-6">
          {/* 7개 DRG군 정보 */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="font-semibold text-lg mb-4">7개 포괄 DRG군</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {drg7Info.map(drg => (
                <div key={drg.code} className="border rounded-lg p-4">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <span className="text-lg font-bold font-mono text-blue-600">{drg.code}</span>
                      <p className="text-sm font-medium mt-1">{drg.name}</p>
                    </div>
                    <span className="text-xs bg-gray-100 px-2 py-1 rounded">
                      가중치 {drg.base_weight}
                    </span>
                  </div>
                  <div className="mt-3 text-xs text-gray-600 space-y-1">
                    <p>
                      <span className="text-gray-500">진단:</span>{' '}
                      <code className="bg-gray-100 px-1 rounded">{drg.diagnoses.join(', ')}</code>
                    </p>
                    {drg.procedures.length > 0 && (
                      <p>
                        <span className="text-gray-500">수술:</span>{' '}
                        <code className="bg-gray-100 px-1 rounded">
                          {drg.procedures.slice(0, 3).join(', ')}...
                        </code>
                      </p>
                    )}
                    <p>
                      <span className="text-gray-500">재원일수:</span> {drg.los_lower} ~{' '}
                      {drg.los_upper}일
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 사용 안내 */}
          <div className="bg-blue-50 rounded-lg p-6">
            <h3 className="font-semibold text-blue-800 mb-4 flex items-center gap-2">
              <Info className="w-5 h-5" />
              Pre-Grouper 사용 안내
            </h3>
            <div className="text-sm text-blue-700 space-y-2">
              <p>• Pre-Grouper는 청구 전 KDRG 코드를 사전에 예측하는 도구입니다.</p>
              <p>• 실제 심평원 심사 결과와 차이가 있을 수 있으며, 참고용으로만 사용하세요.</p>
              <p>
                • 7개 포괄 DRG군 (편도, 축농증, 탈장, 담낭, 항문, 결석, 제왕절개, 질식분만)은
                정확도가 높습니다.
              </p>
              <p>• 행위별 청구 대상은 예측 정확도가 낮을 수 있습니다.</p>
              <p>• 최적화 제안은 코딩 검토 시 참고자료로 활용하세요.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
