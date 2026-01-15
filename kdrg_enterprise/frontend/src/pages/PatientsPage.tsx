import { useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { patientsAPI } from '../services/api';
import { Upload, Search, Plus, Users, FileUp, CheckCircle, AlertCircle } from 'lucide-react';
import clsx from 'clsx';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import ErrorMessage from '../components/ErrorMessage';
import Modal from '../components/Modal';
import Pagination from '../components/Pagination';
import Tooltip from '../components/Tooltip';

interface Patient {
  id: number;
  masked_patient_id: string;
  masked_name: string;
  gender?: string;
  age?: number;
  age_group?: string;
  department?: string;
  admission_date?: string;
  discharge_date?: string;
  length_of_stay?: number;
  kdrg_code?: string;
  aadrg_code?: string;
  drg_group?: string;
  claim_amount?: number;
}

export default function PatientsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [selectedDept, setSelectedDept] = useState('');
  const [showImportModal, setShowImportModal] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const itemsPerPage = 20;

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['patients', page, selectedDept],
    queryFn: () =>
      patientsAPI
        .list({ page, per_page: itemsPerPage, department: selectedDept || undefined })
        .then((res) => res.data),
  });

  const importMutation = useMutation({
    mutationFn: (file: File) => patientsAPI.import(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setUploadSuccess(true);
      setTimeout(() => {
        setShowImportModal(false);
        setUploadSuccess(false);
      }, 2000);
    },
  });

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      importMutation.mutate(file);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file && (file.name.endsWith('.csv') || file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
      importMutation.mutate(file);
    }
  };

  const filteredPatients = data?.patients?.filter((p: Patient) =>
    search
      ? p.masked_name.includes(search) ||
        p.kdrg_code?.includes(search) ||
        p.department?.includes(search)
      : true
  );

  const getDRGBadgeColor = (drg_group?: string) => {
    if (!drg_group || drg_group === '미분류') return 'badge-secondary';
    if (drg_group === '기타 DRG') return 'bg-gray-100 text-gray-600';
    return 'badge-primary';
  };

  const totalPages = Math.ceil((data?.total || 0) / itemsPerPage);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">환자 관리</h1>
          <p className="mt-1 text-gray-600">
            총 <span className="font-medium text-primary-600">{(data?.total || 0).toLocaleString()}</span>명의 환자 데이터
          </p>
        </div>
        <div className="flex gap-3">
          <Tooltip content="CSV 또는 Excel 파일로 데이터 가져오기">
            <button
              onClick={() => setShowImportModal(true)}
              className="btn-secondary flex items-center gap-2"
            >
              <Upload className="h-4 w-4" />
              데이터 가져오기
            </button>
          </Tooltip>
          <Tooltip content="새 환자 정보 등록">
            <button className="btn-primary flex items-center gap-2">
              <Plus className="h-4 w-4" />
              환자 등록
            </button>
          </Tooltip>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <label htmlFor="search" className="sr-only">검색</label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                id="search"
                type="text"
                placeholder="환자명, KDRG 코드, 진료과 검색..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="input pl-10"
                aria-label="환자 검색"
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  aria-label="검색어 지우기"
                >
                  ×
                </button>
              )}
            </div>
          </div>
          <div>
            <label htmlFor="department" className="sr-only">진료과 선택</label>
            <select
              id="department"
              value={selectedDept}
              onChange={(e) => {
                setSelectedDept(e.target.value);
                setPage(1);
              }}
              className="input w-full sm:w-48"
              aria-label="진료과 필터"
            >
              <option value="">전체 진료과</option>
              <option value="이비인후과">이비인후과</option>
              <option value="안과">안과</option>
              <option value="비뇨기과">비뇨기과</option>
              <option value="외과">외과</option>
              <option value="피부과">피부과</option>
            </select>
          </div>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <ErrorMessage
          title="데이터를 불러올 수 없습니다"
          message="환자 목록을 가져오는 중 오류가 발생했습니다."
          onRetry={() => refetch()}
        />
      )}

      {/* Table */}
      <div className="card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="table-header px-6 py-4">환자</th>
                <th className="table-header px-6 py-4">진료과</th>
                <th className="table-header px-6 py-4">KDRG</th>
                <th className="table-header px-6 py-4">DRG군</th>
                <th className="table-header px-6 py-4">재원일수</th>
                <th className="table-header px-6 py-4">청구금액</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12">
                    <LoadingSpinner message="환자 목록을 불러오는 중..." size="md" />
                  </td>
                </tr>
              ) : filteredPatients?.length > 0 ? (
                filteredPatients.map((patient: Patient) => (
                  <tr 
                    key={patient.id} 
                    className="table-row-interactive group"
                    tabIndex={0}
                    role="button"
                    aria-label={`${patient.masked_name} 환자 상세 보기`}
                  >
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium text-gray-900 group-hover:text-primary-600 transition-colors">
                          {patient.masked_name}
                        </p>
                        <p className="text-sm text-gray-500">
                          {patient.masked_patient_id} · {patient.age_group}
                        </p>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-gray-600">
                      {patient.department || '-'}
                    </td>
                    <td className="px-6 py-4">
                      <code className="text-sm bg-gray-100 px-2 py-1 rounded font-mono">
                        {patient.kdrg_code || '-'}
                      </code>
                    </td>
                    <td className="px-6 py-4">
                      <span className={clsx('badge', getDRGBadgeColor(patient.drg_group))}>
                        {patient.drg_group || '미분류'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-gray-600">
                      {patient.length_of_stay ? `${patient.length_of_stay}일` : '-'}
                    </td>
                    <td className="px-6 py-4 text-gray-900 font-medium">
                      {patient.claim_amount
                        ? `₩${patient.claim_amount.toLocaleString()}`
                        : '-'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6}>
                    {search ? (
                      <EmptyState
                        icon={Search}
                        title="검색 결과 없음"
                        description={`"${search}"에 해당하는 환자를 찾을 수 없습니다. 다른 검색어를 시도해보세요.`}
                        actionLabel="검색어 지우기"
                        onAction={() => setSearch('')}
                        variant="search"
                      />
                    ) : (
                      <EmptyState
                        icon={Users}
                        title="환자 데이터가 없습니다"
                        description="환자 데이터를 업로드하거나 새 환자를 등록해주세요."
                        actionLabel="데이터 가져오기"
                        onAction={() => setShowImportModal(true)}
                      />
                    )}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data?.total > 0 && totalPages > 1 && (
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            totalItems={data.total}
            itemsPerPage={itemsPerPage}
            onPageChange={setPage}
          />
        )}
      </div>

      {/* Import Modal */}
      <Modal
        isOpen={showImportModal}
        onClose={() => {
          if (!importMutation.isPending) {
            setShowImportModal(false);
            setUploadSuccess(false);
          }
        }}
        title="데이터 가져오기"
        size="md"
      >
        {uploadSuccess ? (
          <div className="text-center py-8">
            <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
              <CheckCircle className="h-8 w-8 text-green-600" />
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">업로드 완료!</h3>
            <p className="text-gray-500">환자 데이터가 성공적으로 등록되었습니다.</p>
          </div>
        ) : (
          <>
            <p className="text-gray-600 mb-6">
              환자 데이터가 포함된 <strong>CSV</strong> 또는 <strong>Excel</strong> 파일을 업로드하세요.
            </p>
            
            {/* Drag and Drop Zone */}
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              className={clsx(
                'border-2 border-dashed rounded-xl p-8 text-center transition-colors',
                dragActive
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-gray-300 hover:border-gray-400',
                importMutation.isPending && 'opacity-50 pointer-events-none'
              )}
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                accept=".csv,.xlsx,.xls"
                className="hidden"
                disabled={importMutation.isPending}
              />
              
              <div className="mx-auto w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                <FileUp className={clsx('h-6 w-6', dragActive ? 'text-primary-600' : 'text-gray-400')} />
              </div>
              
              <p className="text-gray-600 mb-2">
                파일을 여기에 끌어다 놓거나
              </p>
              
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={importMutation.isPending}
                className="btn-primary"
              >
                {importMutation.isPending ? (
                  <span className="flex items-center gap-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                    업로드 중...
                  </span>
                ) : (
                  '파일 선택'
                )}
              </button>
              
              <p className="text-sm text-gray-400 mt-4">
                지원 형식: .csv, .xlsx, .xls (최대 10MB)
              </p>
            </div>

            {importMutation.isError && (
              <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
                <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-red-800">업로드 실패</p>
                  <p className="text-sm text-red-600">
                    파일 형식을 확인하고 다시 시도해주세요.
                  </p>
                </div>
              </div>
            )}
          </>
        )}
      </Modal>
    </div>
  );
}
