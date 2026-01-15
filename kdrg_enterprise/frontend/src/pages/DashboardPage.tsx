import { useQuery } from '@tanstack/react-query';
import { analysisAPI, patientsAPI } from '../services/api';
import {
  Users,
  TrendingUp,
  AlertTriangle,
  DollarSign,
  ArrowUpRight,
  ArrowDownRight,
  BarChart2,
  RefreshCw,
} from 'lucide-react';
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
} from 'recharts';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import ErrorMessage from '../components/ErrorMessage';

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899'];

interface StatsCardProps {
  title: string;
  value: string | number;
  change?: number;
  icon: React.ElementType;
  color: string;
}

function StatsCard({ title, value, change, icon: Icon, color }: StatsCardProps) {
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="mt-2 text-3xl font-bold text-gray-900">{value}</p>
          {change !== undefined && (
            <p
              className={`mt-2 flex items-center text-sm ${
                change >= 0 ? 'text-success-600' : 'text-danger-600'
              }`}
            >
              {change >= 0 ? (
                <ArrowUpRight className="h-4 w-4 mr-1" />
              ) : (
                <ArrowDownRight className="h-4 w-4 mr-1" />
              )}
              {Math.abs(change)}%
            </p>
          )}
        </div>
        <div className={`p-3 rounded-xl ${color}`}>
          <Icon className="h-6 w-6 text-white" />
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data: dashboardData, isLoading: dashboardLoading, error: dashboardError, refetch: refetchDashboard } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => analysisAPI.dashboard().then((res) => res.data),
  });

  const { data: statsData, isLoading: statsLoading, error: statsError, refetch: refetchStats } = useQuery({
    queryKey: ['patientStats'],
    queryFn: () => patientsAPI.stats().then((res) => res.data),
  });

  const handleRefetch = () => {
    refetchDashboard();
    refetchStats();
  };

  if (dashboardLoading || statsLoading) {
    return <LoadingSpinner message="대시보드 데이터를 불러오는 중..." size="lg" />;
  }

  if (dashboardError || statsError) {
    return (
      <div className="max-w-md mx-auto mt-12">
        <ErrorMessage
          title="데이터를 불러올 수 없습니다"
          message="대시보드 데이터를 가져오는 중 오류가 발생했습니다. 네트워크 연결을 확인하고 다시 시도해주세요."
          onRetry={handleRefetch}
          variant="card"
        />
      </div>
    );
  }

  const dashboard = dashboardData?.dashboard;
  const stats = statsData?.stats;

  const drgData = dashboard?.by_drg_group?.map((item: { drg_group: string; patient_count: number }) => ({
    name: item.drg_group.replace(' - ', '\n'),
    value: item.patient_count,
  })) || [];

  const deptData = dashboard?.by_department?.map((item: { department: string; patient_count: number }) => ({
    name: item.department,
    patients: item.patient_count,
  })) || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">대시보드</h1>
        <p className="mt-1 text-gray-600">KDRG 관리 현황을 한눈에 확인하세요</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard
          title="총 환자 수"
          value={stats?.total_patients || 0}
          icon={Users}
          color="bg-primary-500"
        />
        <StatsCard
          title="최적화 기회"
          value={dashboard?.summary?.optimization_opportunities || 0}
          icon={TrendingUp}
          color="bg-success-500"
        />
        <StatsCard
          title="경고 건수"
          value={dashboard?.summary?.loss_alerts || 0}
          icon={AlertTriangle}
          color="bg-warning-500"
        />
        <StatsCard
          title="잠재 수익"
          value={`₩${((dashboard?.summary?.total_potential_gain || 0) / 10000).toFixed(0)}만`}
          icon={DollarSign}
          color="bg-primary-600"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* DRG Group Distribution */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">DRG군별 분포</h3>
          {drgData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={drgData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) =>
                    `${name} (${(percent * 100).toFixed(0)}%)`
                  }
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {drgData.map((_entry: unknown, index: number) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState
              icon={BarChart2}
              title="DRG 분포 데이터 없음"
              description="환자 데이터를 업로드하면 DRG군별 분포를 확인할 수 있습니다."
            />
          )}
        </div>

        {/* Department Distribution */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">진료과별 환자 수</h3>
          {deptData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={deptData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="patients" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState
              icon={Users}
              title="진료과 데이터 없음"
              description="환자 데이터가 등록되면 진료과별 현황을 확인할 수 있습니다."
            />
          )}
        </div>
      </div>

      {/* Critical Alerts */}
      {dashboard?.critical_alerts?.length > 0 && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            긴급 경고
          </h3>
          <div className="space-y-3">
            {dashboard.critical_alerts.map((alert: {
              patient_id: number;
              masked_name: string;
              alert_type: string;
              description: string;
              estimated_loss: number;
            }, index: number) => (
              <div
                key={index}
                className="flex items-center gap-4 p-4 bg-danger-50 rounded-lg border border-danger-200"
              >
                <AlertTriangle className="h-5 w-5 text-danger-600 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-danger-800">
                    {alert.masked_name} - {alert.alert_type}
                  </p>
                  <p className="text-sm text-danger-600">{alert.description}</p>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="font-medium text-danger-600">
                    ₩{alert.estimated_loss.toLocaleString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
