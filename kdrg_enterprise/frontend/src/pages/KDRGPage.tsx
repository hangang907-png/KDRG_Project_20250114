import { useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { kdrgAPI } from '../services/api';
import { Search, Upload, FileCode, CheckCircle, XCircle } from 'lucide-react';
import clsx from 'clsx';

interface KDRGCode {
  kdrg_code: string;
  kdrg_name: string;
  aadrg_code: string;
  aadrg_name?: string;
  mdc_code?: string;
  cc_level?: string;
  relative_weight?: number;
  avg_los?: number;
}

interface DRGGroup {
  aadrg_code: string;
  name: string;
  description: string;
  conditions: string[];
  kdrg_count: number;
}

export default function KDRGPage() {
  const [activeTab, setActiveTab] = useState<'codebook' | '7drg' | 'validate'>('codebook');
  const [search, setSearch] = useState('');
  const [validateCode, setValidateCode] = useState('');
  const [validationResult, setValidationResult] = useState<{
    valid: boolean;
    message: string;
    kdrg_info?: KDRGCode;
  } | null>(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadVersion, setUploadVersion] = useState('V4.6');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const { data: codebookData, isLoading: codebookLoading } = useQuery({
    queryKey: ['kdrgCodebook', search],
    queryFn: () =>
      kdrgAPI.codebook({ search: search || undefined, per_page: 50 }).then(res => res.data),
    enabled: activeTab === 'codebook',
  });

  const { data: drg7Data, isLoading: drg7Loading } = useQuery({
    queryKey: ['7drg'],
    queryFn: () => kdrgAPI.get7DRG().then(res => res.data),
    enabled: activeTab === '7drg',
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => kdrgAPI.uploadCodebook(file, uploadVersion),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['kdrgCodebook'] });
      setShowUploadModal(false);
    },
  });

  const validateMutation = useMutation({
    mutationFn: (code: string) => kdrgAPI.validate(code),
    onSuccess: response => {
      setValidationResult(response.data);
    },
  });

  const handleValidate = () => {
    if (validateCode.trim()) {
      validateMutation.mutate(validateCode.trim().toUpperCase());
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadMutation.mutate(file);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">KDRG 관리</h1>
          <p className="mt-1 text-gray-600">KDRG 코드북 및 7개 DRG군 관리</p>
        </div>
        <button
          onClick={() => setShowUploadModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Upload className="h-4 w-4" />
          코드북 업로드
        </button>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-8">
          {[
            { id: 'codebook', label: '코드북', icon: FileCode },
            { id: '7drg', label: '7개 DRG군', icon: FileCode },
            { id: 'validate', label: '코드 검증', icon: CheckCircle },
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
      {activeTab === 'codebook' && (
        <div className="space-y-4">
          {/* Search */}
          <div className="card">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                type="text"
                placeholder="KDRG 코드 또는 명칭 검색..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="input pl-10"
              />
            </div>
          </div>

          {/* Table */}
          <div className="card p-0 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="table-header px-6 py-4">KDRG</th>
                    <th className="table-header px-6 py-4">명칭</th>
                    <th className="table-header px-6 py-4">AADRG</th>
                    <th className="table-header px-6 py-4">CC</th>
                    <th className="table-header px-6 py-4">상대가치</th>
                    <th className="table-header px-6 py-4">평균재원</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {codebookLoading ? (
                    <tr>
                      <td colSpan={6} className="px-6 py-12 text-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
                      </td>
                    </tr>
                  ) : codebookData?.codes?.length > 0 ? (
                    codebookData.codes.map((code: KDRGCode) => (
                      <tr key={code.kdrg_code} className="hover:bg-gray-50">
                        <td className="px-6 py-4">
                          <code className="text-sm bg-primary-50 text-primary-700 px-2 py-1 rounded">
                            {code.kdrg_code}
                          </code>
                        </td>
                        <td className="px-6 py-4 text-gray-900">{code.kdrg_name}</td>
                        <td className="px-6 py-4 text-gray-600">{code.aadrg_code}</td>
                        <td className="px-6 py-4 text-gray-600">{code.cc_level || '-'}</td>
                        <td className="px-6 py-4 text-gray-900 font-medium">
                          {code.relative_weight?.toFixed(4) || '-'}
                        </td>
                        <td className="px-6 py-4 text-gray-600">
                          {code.avg_los ? `${code.avg_los}일` : '-'}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                        {search ? '검색 결과가 없습니다' : '코드북을 업로드해주세요'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {activeTab === '7drg' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {drg7Loading ? (
            <div className="col-span-2 p-8 text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
            </div>
          ) : drg7Data?.drg_groups?.length > 0 ? (
            drg7Data.drg_groups.map((group: DRGGroup) => (
              <div key={group.aadrg_code} className="card">
                <div className="flex items-center gap-3 mb-3">
                  <code className="text-lg bg-primary-100 text-primary-700 px-3 py-1 rounded-lg font-bold">
                    {group.aadrg_code}
                  </code>
                  <h3 className="font-semibold text-gray-900">{group.name}</h3>
                </div>
                <p className="text-gray-600 mb-3">{group.description}</p>
                <div className="flex flex-wrap gap-2 mb-3">
                  {group.conditions.map(condition => (
                    <span key={condition} className="badge-primary">
                      {condition}
                    </span>
                  ))}
                </div>
                <p className="text-sm text-gray-500">관련 KDRG 코드: {group.kdrg_count}개</p>
              </div>
            ))
          ) : (
            <div className="col-span-2 card text-center text-gray-500">
              7개 DRG군 정보가 없습니다
            </div>
          )}
        </div>
      )}

      {activeTab === 'validate' && (
        <div className="max-w-xl mx-auto">
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">KDRG 코드 유효성 검증</h3>
            <div className="flex gap-3 mb-4">
              <input
                type="text"
                placeholder="KDRG 코드 입력 (예: T0110)"
                value={validateCode}
                onChange={e => setValidateCode(e.target.value.toUpperCase())}
                className="input flex-1"
                maxLength={5}
              />
              <button
                onClick={handleValidate}
                disabled={!validateCode.trim() || validateMutation.isPending}
                className="btn-primary"
              >
                {validateMutation.isPending ? '검증 중...' : '검증'}
              </button>
            </div>

            {validationResult && (
              <div
                className={clsx(
                  'p-4 rounded-lg',
                  validationResult.valid
                    ? 'bg-success-50 border border-success-200'
                    : 'bg-danger-50 border border-danger-200'
                )}
              >
                <div className="flex items-center gap-3 mb-2">
                  {validationResult.valid ? (
                    <CheckCircle className="h-5 w-5 text-success-600" />
                  ) : (
                    <XCircle className="h-5 w-5 text-danger-600" />
                  )}
                  <p
                    className={clsx(
                      'font-medium',
                      validationResult.valid ? 'text-success-800' : 'text-danger-800'
                    )}
                  >
                    {validationResult.message}
                  </p>
                </div>

                {validationResult.kdrg_info && (
                  <div className="mt-4 space-y-2 text-sm">
                    <p>
                      <span className="text-gray-600">코드:</span>{' '}
                      <span className="font-medium">{validationResult.kdrg_info.kdrg_code}</span>
                    </p>
                    <p>
                      <span className="text-gray-600">명칭:</span>{' '}
                      <span className="font-medium">{validationResult.kdrg_info.kdrg_name}</span>
                    </p>
                    <p>
                      <span className="text-gray-600">AADRG:</span>{' '}
                      <span className="font-medium">{validationResult.kdrg_info.aadrg_code}</span>
                    </p>
                    {validationResult.kdrg_info.relative_weight && (
                      <p>
                        <span className="text-gray-600">상대가치:</span>{' '}
                        <span className="font-medium">
                          {validationResult.kdrg_info.relative_weight.toFixed(4)}
                        </span>
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">KDRG 코드북 업로드</h3>
            <div className="mb-4">
              <label className="label">버전</label>
              <select
                value={uploadVersion}
                onChange={e => setUploadVersion(e.target.value)}
                className="input"
              >
                <option value="V4.6">KDRG V4.6</option>
                <option value="V3.5">KDRG V3.5 (7개 DRG)</option>
              </select>
            </div>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".csv,.xlsx,.xls"
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadMutation.isPending}
              className="w-full btn-primary mb-3"
            >
              {uploadMutation.isPending ? '업로드 중...' : '파일 선택'}
            </button>
            <button onClick={() => setShowUploadModal(false)} className="w-full btn-secondary">
              취소
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
