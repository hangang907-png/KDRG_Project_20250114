import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { analysisAPI } from '../services/api';
import { TrendingUp, AlertTriangle, DollarSign, Filter, Download } from 'lucide-react';
import clsx from 'clsx';

interface OptimizationItem {
  patient_id: number;
  masked_name: string;
  current_kdrg: string;
  recommended_kdrg: string;
  payment_difference: number;
  reason: string;
}

interface LossAlert {
  patient_id: number;
  masked_name: string;
  alert_type: string;
  estimated_loss: number;
  description: string;
  alert_level: string;
}

export default function AnalysisPage() {
  const [activeTab, setActiveTab] = useState<'optimize' | 'losses' | 'revenue'>('optimize');
  const [department, setDepartment] = useState('');

  const { data: optimizeData, isLoading: optimizeLoading } = useQuery({
    queryKey: ['batchOptimize', department],
    queryFn: () =>
      analysisAPI.batchOptimize({ department: department || undefined }).then(res => res.data),
    enabled: activeTab === 'optimize',
  });

  const { data: lossesData, isLoading: lossesLoading } = useQuery({
    queryKey: ['batchLosses', department],
    queryFn: () =>
      analysisAPI.batchLosses({ department: department || undefined }).then(res => res.data),
    enabled: activeTab === 'losses',
  });

  const { data: revenueData, isLoading: revenueLoading } = useQuery({
    queryKey: ['revenue'],
    queryFn: () => analysisAPI.revenue().then(res => res.data),
    enabled: activeTab === 'revenue',
  });

  const getAlertLevelBadge = (level: string) => {
    switch (level) {
      case 'critical':
        return 'badge-danger';
      case 'warning':
        return 'badge-warning';
      default:
        return 'badge-primary';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">분석</h1>
          <p className="mt-1 text-gray-600">DRG 최적화 및 손실 분석</p>
        </div>
        <div className="flex gap-3">
          <select
            value={department}
            onChange={e => setDepartment(e.target.value)}
            className="input w-48"
          >
            <option value="">전체 진료과</option>
            <option value="이비인후과">이비인후과</option>
            <option value="안과">안과</option>
            <option value="비뇨기과">비뇨기과</option>
            <option value="외과">외과</option>
          </select>
          <button className="btn-secondary flex items-center gap-2">
            <Download className="h-4 w-4" />
            내보내기
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-8">
          {[
            { id: 'optimize', label: '최적화 분석', icon: TrendingUp },
            { id: 'losses', label: '손실 감지', icon: AlertTriangle },
            { id: 'revenue', label: '수익 분석', icon: DollarSign },
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
      {activeTab === 'optimize' && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="card bg-primary-50 border-primary-200">
              <p className="text-sm text-primary-600">분석 대상</p>
              <p className="text-2xl font-bold text-primary-700">
                {optimizeData?.total_analyzed || 0}명
              </p>
            </div>
            <div className="card bg-success-50 border-success-200">
              <p className="text-sm text-success-600">최적화 기회</p>
              <p className="text-2xl font-bold text-success-700">
                {optimizeData?.optimization_count || 0}건
              </p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-600">현재 총액</p>
              <p className="text-2xl font-bold text-gray-900">
                ₩{((optimizeData?.total_current_payment || 0) / 10000).toFixed(0)}만
              </p>
            </div>
            <div className="card bg-primary-50 border-primary-200">
              <p className="text-sm text-primary-600">잠재 수익</p>
              <p className="text-2xl font-bold text-primary-700">
                +₩{((optimizeData?.total_potential_gain || 0) / 10000).toFixed(0)}만
              </p>
            </div>
          </div>

          {/* List */}
          <div className="card p-0">
            <div className="p-4 border-b border-gray-200">
              <h3 className="font-semibold text-gray-900">최적화 추천</h3>
            </div>
            {optimizeLoading ? (
              <div className="p-8 text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
              </div>
            ) : optimizeData?.optimizations?.length > 0 ? (
              <div className="divide-y divide-gray-100">
                {optimizeData.optimizations.map((item: OptimizationItem) => (
                  <div key={item.patient_id} className="p-4 hover:bg-gray-50">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-gray-900">{item.masked_name}</p>
                        <p className="text-sm text-gray-600">
                          {item.current_kdrg} → {item.recommended_kdrg}
                        </p>
                        <p className="text-sm text-gray-500 mt-1">{item.reason}</p>
                      </div>
                      <div className="text-right">
                        <p className="font-bold text-success-600">
                          +₩{item.payment_difference.toLocaleString()}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-gray-500">최적화 대상이 없습니다</div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'losses' && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="card">
              <p className="text-sm text-gray-600">분석 대상</p>
              <p className="text-2xl font-bold text-gray-900">
                {lossesData?.total_patients || 0}명
              </p>
            </div>
            <div className="card bg-warning-50 border-warning-200">
              <p className="text-sm text-warning-600">경고 건수</p>
              <p className="text-2xl font-bold text-warning-700">
                {lossesData?.total_alerts || 0}건
              </p>
            </div>
            <div className="card bg-danger-50 border-danger-200">
              <p className="text-sm text-danger-600">예상 손실</p>
              <p className="text-2xl font-bold text-danger-700">
                ₩{((lossesData?.total_estimated_loss || 0) / 10000).toFixed(0)}만
              </p>
            </div>
          </div>

          {/* List */}
          <div className="card p-0">
            <div className="p-4 border-b border-gray-200">
              <h3 className="font-semibold text-gray-900">손실 경고</h3>
            </div>
            {lossesLoading ? (
              <div className="p-8 text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
              </div>
            ) : lossesData?.alerts?.length > 0 ? (
              <div className="divide-y divide-gray-100">
                {lossesData.alerts.map((alert: LossAlert, idx: number) => (
                  <div key={idx} className="p-4 hover:bg-gray-50">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <AlertTriangle
                          className={clsx(
                            'h-5 w-5',
                            alert.alert_level === 'critical'
                              ? 'text-danger-500'
                              : alert.alert_level === 'warning'
                                ? 'text-warning-500'
                                : 'text-primary-500'
                          )}
                        />
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-gray-900">{alert.masked_name}</p>
                            <span className={clsx('badge', getAlertLevelBadge(alert.alert_level))}>
                              {alert.alert_level}
                            </span>
                          </div>
                          <p className="text-sm text-gray-600">{alert.alert_type}</p>
                          <p className="text-sm text-gray-500">{alert.description}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-bold text-danger-600">
                          -₩{alert.estimated_loss.toLocaleString()}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-gray-500">손실 경고가 없습니다</div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'revenue' && (
        <div className="space-y-4">
          {revenueLoading ? (
            <div className="p-8 text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
            </div>
          ) : (
            <>
              {/* Summary */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="card">
                  <p className="text-sm text-gray-600">총 수익</p>
                  <p className="text-2xl font-bold text-gray-900">
                    ₩{((revenueData?.revenue?.total || 0) / 10000).toFixed(0)}만
                  </p>
                </div>
                <div className="card">
                  <p className="text-sm text-gray-600">환자당 평균</p>
                  <p className="text-2xl font-bold text-gray-900">
                    ₩{(revenueData?.revenue?.avg_per_patient || 0).toLocaleString()}
                  </p>
                </div>
                <div className="card">
                  <p className="text-sm text-gray-600">총 환자</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {revenueData?.revenue?.patient_count || 0}명
                  </p>
                </div>
              </div>

              {/* By DRG Group */}
              <div className="card">
                <h3 className="font-semibold text-gray-900 mb-4">DRG군별 수익</h3>
                <div className="space-y-3">
                  {Object.entries(revenueData?.revenue?.by_drg_group || {}).map(([drg, amount]) => (
                    <div key={drg} className="flex items-center justify-between">
                      <span className="text-gray-600">{drg}</span>
                      <span className="font-medium text-gray-900">
                        ₩{((amount as number) / 10000).toFixed(0)}만
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* By Department */}
              <div className="card">
                <h3 className="font-semibold text-gray-900 mb-4">진료과별 수익</h3>
                <div className="space-y-3">
                  {Object.entries(revenueData?.revenue?.by_department || {}).map(
                    ([dept, amount]) => (
                      <div key={dept} className="flex items-center justify-between">
                        <span className="text-gray-600">{dept}</span>
                        <span className="font-medium text-gray-900">
                          ₩{((amount as number) / 10000).toFixed(0)}만
                        </span>
                      </div>
                    )
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
