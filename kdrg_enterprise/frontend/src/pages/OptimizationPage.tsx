import { useState, useEffect } from 'react';
import {
  TrendingUp,
  Search,
  Filter,
  Download,
  RefreshCw,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
  Info,
  BarChart3,
  DollarSign,
  Layers,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react';
import clsx from 'clsx';
import { optimizationAPI, patientsAPI } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import EmptyState from '../components/EmptyState';

interface MDCSummary {
  mdc: string;
  mdc_name: string;
  total_cases: number;
  total_current_revenue: number;
  total_potential_revenue: number;
  optimization_potential: number;
  optimization_rate: number;
}

interface OptimizationSuggestion {
  suggestion_id: string;
  optimization_type: string;
  current_kdrg: string;
  suggested_kdrg: string;
  current_amount: number;
  suggested_amount: number;
  revenue_difference: number;
  revenue_change_pct: number;
  required_actions: string[];
  risk_level: string;
  confidence: number;
  rationale: string;
}

interface PatientOptimization {
  patient_id: string;
  current_kdrg: string;
  current_amount: number;
  optimization_potential: number;
  best_suggestion: OptimizationSuggestion | null;
}

export default function OptimizationPage() {
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Data states
  const [summary, setSummary] = useState<any>(null);
  const [statistics, setStatistics] = useState<any>(null);
  const [mdcSummaries, setMdcSummaries] = useState<MDCSummary[]>([]);
  const [topOpportunities, setTopOpportunities] = useState<PatientOptimization[]>([]);
  const [selectedMDC, setSelectedMDC] = useState<string>('');
  const [mdcList, setMdcList] = useState<{ code: string; name: string }[]>([]);

  // Report state
  const [reportData, setReportData] = useState<any>(null);

  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    setLoading(true);
    setError(null);

    try {
      const [summaryRes, statsRes, mdcRes] = await Promise.all([
        optimizationAPI.summary(),
        optimizationAPI.statistics(),
        optimizationAPI.mdcList(),
      ]);

      setSummary(summaryRes.data);
      setStatistics(statsRes.data);
      setMdcList(mdcRes.data);
    } catch (err: any) {
      setError(err.message || '데이터 로딩 실패');
    } finally {
      setLoading(false);
    }
  };

  const runBatchAnalysis = async () => {
    setAnalyzing(true);
    setError(null);

    try {
      // 환자 데이터 가져오기
      const patientsRes = await patientsAPI.list({ per_page: 100 });
      const patients = patientsRes.data.items || [];

      if (patients.length === 0) {
        setError('분석할 환자 데이터가 없습니다.');
        return;
      }

      // 배치 분석 실행
      const analysisRes = await optimizationAPI.analyzeBatch({
        patients: patients.map((p: any) => ({
          patient_id: p.patient_id || p.id,
          kdrg: p.kdrg || p.kdrg_code || '',
          main_diagnosis: p.main_diagnosis || p.diagnosis || '',
          sub_diagnoses: p.sub_diagnoses || [],
          procedures: p.procedures || [],
          los: p.los || 0,
          age: p.age || 0,
          sex: p.sex || 'M',
        })),
        mdc_filter: selectedMDC || undefined,
        min_potential: 0,
      });

      setReportData(analysisRes.data);
      setMdcSummaries(analysisRes.data.mdc_summaries || []);
      setTopOpportunities(analysisRes.data.top_opportunities || []);
    } catch (err: any) {
      setError(err.message || '분석 실행 실패');
    } finally {
      setAnalyzing(false);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('ko-KR', {
      style: 'currency',
      currency: 'KRW',
      maximumFractionDigits: 0,
    }).format(value);
  };

  const getRiskBadgeColor = (risk: string) => {
    switch (risk) {
      case 'low':
        return 'bg-green-100 text-green-800';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800';
      case 'high':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      severity_upgrade: '중증도 상향',
      diagnosis_coding: '진단 코딩',
      procedure_coding: '수술 코딩',
      complication_add: '합병증 추가',
      drg7_conversion: 'DRG군 전환',
    };
    return labels[type] || type;
  };

  if (loading) {
    return <LoadingSpinner message="최적화 데이터 로딩 중..." />;
  }

  if (error && !reportData) {
    return <ErrorMessage message={error} onRetry={loadInitialData} />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">전역 KDRG 최적화</h1>
          <p className="text-sm text-gray-500 mt-1">
            전체 MDC에 대한 KDRG 수익성 분석 및 코딩 개선 제안
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={selectedMDC}
            onChange={e => setSelectedMDC(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500"
          >
            <option value="">전체 MDC</option>
            {mdcList.map(mdc => (
              <option key={mdc.code} value={mdc.code}>
                {mdc.code} - {mdc.name}
              </option>
            ))}
          </select>

          <button
            onClick={runBatchAnalysis}
            disabled={analyzing}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${analyzing ? 'animate-spin' : ''}`} />
            {analyzing ? '분석 중...' : '최적화 분석 실행'}
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Layers className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">등록 KDRG</p>
              <p className="text-xl font-bold text-gray-900">
                {statistics?.total_kdrg_codes || 0}개
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 rounded-lg">
              <BarChart3 className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">평균 상대가치</p>
              <p className="text-xl font-bold text-gray-900">
                {statistics?.average_relative_weight?.toFixed(3) || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 rounded-lg">
              <DollarSign className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">평균 기준수가</p>
              <p className="text-xl font-bold text-gray-900">
                {formatCurrency(statistics?.average_base_amount || 0)}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-orange-100 rounded-lg">
              <TrendingUp className="h-5 w-5 text-orange-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">7개 DRG군</p>
              <p className="text-xl font-bold text-gray-900">
                {statistics?.drg7_kdrg_count || 0}개
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Report Summary (after analysis) */}
      {reportData && (
        <div className="bg-gradient-to-r from-primary-600 to-primary-700 rounded-xl p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">최적화 분석 결과</h2>
              <p className="text-primary-100 text-sm mt-1">보고서 ID: {reportData.report_id}</p>
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold">
                {formatCurrency(reportData.total_optimization_potential)}
              </p>
              <p className="text-primary-100 text-sm">총 최적화 잠재력</p>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-4 mt-6">
            <div className="bg-white/10 rounded-lg p-3">
              <p className="text-primary-100 text-xs">분석 케이스</p>
              <p className="text-xl font-semibold">{reportData.total_cases_analyzed}건</p>
            </div>
            <div className="bg-white/10 rounded-lg p-3">
              <p className="text-primary-100 text-xs">현재 수익</p>
              <p className="text-xl font-semibold">
                {formatCurrency(reportData.total_current_revenue)}
              </p>
            </div>
            <div className="bg-white/10 rounded-lg p-3">
              <p className="text-primary-100 text-xs">잠재 수익</p>
              <p className="text-xl font-semibold">
                {formatCurrency(reportData.total_potential_revenue)}
              </p>
            </div>
            <div className="bg-white/10 rounded-lg p-3">
              <p className="text-primary-100 text-xs">최적화 비율</p>
              <p className="text-xl font-semibold">{reportData.optimization_rate}%</p>
            </div>
          </div>
        </div>
      )}

      {/* MDC Summaries */}
      {mdcSummaries.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900">MDC별 최적화 현황</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    MDC
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    분류
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    케이스
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    현재 수익
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    잠재 수익
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    최적화 잠재력
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    최적화율
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {mdcSummaries.map(mdc => (
                  <tr key={mdc.mdc} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center justify-center w-8 h-8 bg-primary-100 text-primary-700 font-semibold rounded-lg">
                        {mdc.mdc}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">{mdc.mdc_name}</td>
                    <td className="px-6 py-4 text-sm text-gray-600 text-right">
                      {mdc.total_cases}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600 text-right">
                      {formatCurrency(mdc.total_current_revenue)}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600 text-right">
                      {formatCurrency(mdc.total_potential_revenue)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span
                        className={clsx(
                          'text-sm font-medium',
                          mdc.optimization_potential > 0 ? 'text-green-600' : 'text-gray-500'
                        )}
                      >
                        {mdc.optimization_potential > 0 && '+'}
                        {formatCurrency(mdc.optimization_potential)}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span
                        className={clsx(
                          'inline-flex px-2 py-1 text-xs font-medium rounded-full',
                          mdc.optimization_rate >= 50
                            ? 'bg-green-100 text-green-800'
                            : mdc.optimization_rate >= 20
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-gray-100 text-gray-800'
                        )}
                      >
                        {mdc.optimization_rate}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Top Opportunities */}
      {topOpportunities.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900">최적화 기회 상위 케이스</h2>
          </div>
          <div className="divide-y divide-gray-100">
            {topOpportunities.slice(0, 10).map((opp, idx) => (
              <div key={opp.patient_id} className="px-6 py-4 hover:bg-gray-50 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <span className="flex items-center justify-center w-8 h-8 bg-gray-100 text-gray-600 font-medium rounded-full text-sm">
                      {idx + 1}
                    </span>
                    <div>
                      <p className="font-medium text-gray-900">환자 {opp.patient_id}</p>
                      <p className="text-sm text-gray-500">
                        현재 KDRG: {opp.current_kdrg} | 현재 수가:{' '}
                        {formatCurrency(opp.current_amount)}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-semibold text-green-600">
                      +{formatCurrency(opp.optimization_potential)}
                    </p>
                    {opp.best_suggestion && (
                      <div className="flex items-center gap-2 mt-1">
                        <span
                          className={clsx(
                            'px-2 py-0.5 text-xs font-medium rounded',
                            getRiskBadgeColor(opp.best_suggestion.risk_level)
                          )}
                        >
                          {opp.best_suggestion.risk_level === 'low'
                            ? '낮은 위험'
                            : opp.best_suggestion.risk_level === 'medium'
                              ? '검토 필요'
                              : '주의'}
                        </span>
                        <span className="text-xs text-gray-500">
                          {getTypeLabel(opp.best_suggestion.optimization_type)}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
                {opp.best_suggestion && (
                  <div className="mt-3 pl-12">
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <span className="font-medium">{opp.best_suggestion.current_kdrg}</span>
                      <ArrowUpRight className="h-4 w-4 text-green-500" />
                      <span className="font-medium text-green-700">
                        {opp.best_suggestion.suggested_kdrg}
                      </span>
                      <span className="text-gray-400">|</span>
                      <span className="text-green-600">
                        +{opp.best_suggestion.revenue_change_pct}%
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">{opp.best_suggestion.rationale}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!reportData && (
        <EmptyState
          title="최적화 분석 대기 중"
          description="'최적화 분석 실행' 버튼을 클릭하여 전체 환자 데이터에 대한 KDRG 최적화 분석을 시작하세요."
          icon={TrendingUp}
          actionLabel="최적화 분석 실행"
          onAction={runBatchAnalysis}
        />
      )}

      {/* Risk Distribution */}
      {reportData?.risk_distribution && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">위험도 분포</h2>
          <div className="grid grid-cols-3 gap-4">
            <div className="flex items-center gap-3 p-4 bg-green-50 rounded-lg">
              <CheckCircle className="h-8 w-8 text-green-600" />
              <div>
                <p className="text-2xl font-bold text-green-700">
                  {reportData.risk_distribution.low || 0}
                </p>
                <p className="text-sm text-green-600">낮은 위험</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-4 bg-yellow-50 rounded-lg">
              <Info className="h-8 w-8 text-yellow-600" />
              <div>
                <p className="text-2xl font-bold text-yellow-700">
                  {reportData.risk_distribution.medium || 0}
                </p>
                <p className="text-sm text-yellow-600">검토 필요</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-4 bg-red-50 rounded-lg">
              <AlertTriangle className="h-8 w-8 text-red-600" />
              <div>
                <p className="text-2xl font-bold text-red-700">
                  {reportData.risk_distribution.high || 0}
                </p>
                <p className="text-sm text-red-600">높은 위험</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
