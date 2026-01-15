import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
};

// Patients API
export const patientsAPI = {
  list: (params?: { page?: number; per_page?: number; department?: string; drg_group?: string }) =>
    api.get('/patients/', { params }),
  get: (id: number) => api.get(`/patients/${id}`),
  create: (data: unknown) => api.post('/patients/', data),
  import: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/patients/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  stats: () => api.get('/patients/stats/summary'),
};

// KDRG API
export const kdrgAPI = {
  codebook: (params?: { page?: number; per_page?: number; search?: string }) =>
    api.get('/kdrg/codebook', { params }),
  uploadCodebook: (file: File, version: string) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/kdrg/codebook/upload?version=${version}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  validate: (kdrg_code: string) => api.post('/kdrg/validate', { kdrg_code }),
  get7DRG: () => api.get('/kdrg/7drg'),
  search: (q: string) => api.get('/kdrg/search', { params: { q } }),
};

// Analysis API
export const analysisAPI = {
  dashboard: () => api.get('/analysis/dashboard'),
  optimizePatient: (id: number) => api.get(`/analysis/optimize/${id}`),
  detectLosses: (id: number) => api.get(`/analysis/losses/${id}`),
  batchOptimize: (params?: { department?: string; drg_group?: string }) =>
    api.get('/analysis/batch/optimize', { params }),
  batchLosses: (params?: { department?: string; alert_level?: string }) =>
    api.get('/analysis/batch/losses', { params }),
  revenue: (period?: string) => api.get('/analysis/revenue', { params: { period } }),
};

// HIRA API
export const hiraAPI = {
  status: () => api.get('/hira/status'),
  setApiKey: (api_key: string) => api.post('/hira/config/apikey', { api_key }),
  queryKDRG: (params?: { kdrg_code?: string; aadrg_code?: string }) =>
    api.get('/hira/kdrg', { params }),
  get7DRG: () => api.get('/hira/7drg'),
  validate: (kdrg_code: string) => api.get(`/hira/validate/${kdrg_code}`),
  compare: (current: string, alternative: string) =>
    api.get('/hira/compare', { params: { current, alternative } }),
};

// AI API
export const aiAPI = {
  status: () => api.get('/ai/status'),
  setApiKey: (provider: string, api_key: string) =>
    api.post('/ai/config/apikey', { provider, api_key }),
  recommendDRG: (data: unknown) => api.post('/ai/recommend/drg', data),
  recommendForPatient: (id: number) => api.post(`/ai/recommend/patient/${id}`),
  optimizeClaim: (data: unknown) => api.post('/ai/optimize/claim', data),
  mapDiagnosis: (diagnosis_code: string, diagnosis_name?: string) =>
    api.post('/ai/mapping/diagnosis', { diagnosis_code, diagnosis_name }),
  generateReport: (include_optimizations: boolean = true) =>
    api.post('/ai/report/audit', { include_optimizations }),
};

// Optimization API
export const optimizationAPI = {
  summary: () => api.get('/optimization/summary'),
  mdcList: () => api.get('/optimization/mdc-list'),
  statistics: () => api.get('/optimization/statistics'),
  getKDRG: (kdrg_code: string) => api.get(`/optimization/kdrg/${kdrg_code}`),
  getKDRGByMDC: (mdc: string) => api.get(`/optimization/kdrg-by-mdc/${mdc}`),
  getSeverityOptions: (aadrg: string) => api.get(`/optimization/severity-options/${aadrg}`),
  getDRG7List: () => api.get('/optimization/drg7-list'),
  analyzePatient: (data: {
    patient_id: string;
    claim_id?: string;
    kdrg: string;
    main_diagnosis: string;
    sub_diagnoses?: string[];
    procedures?: string[];
    los?: number;
    age?: number;
    sex?: string;
  }) => api.post('/optimization/analyze/patient', data),
  analyzeBatch: (data: {
    patients: unknown[];
    mdc_filter?: string;
    min_potential?: number;
  }) => api.post('/optimization/analyze/batch', data),
  simulate: (patient_data: unknown, target_kdrg: string) =>
    api.post('/optimization/simulate', { patient_data, target_kdrg }),
  compare: (kdrg1: string, kdrg2: string) =>
    api.get(`/optimization/compare/${kdrg1}/${kdrg2}`),
};

// HIRA Portal API (자동 다운로드)
export const portalAPI = {
  login: (data: { hospital_code: string; user_id: string; password: string; login_method?: string }) =>
    api.post('/feedback/portal/login', data),
  logout: () => api.post('/feedback/portal/logout'),
  getFiles: (params?: { start_date?: string; end_date?: string; file_type?: string }) =>
    api.get('/feedback/portal/files', { params }),
  download: (file_ids: string[]) =>
    api.post('/feedback/portal/download', { file_ids }),
  autoDownload: () => api.post('/feedback/portal/auto-download'),
  getStatus: () => api.get('/feedback/portal/status'),
  getConfig: () => api.get('/feedback/portal/config'),
  setConfig: (data: {
    enabled: boolean;
    schedule_time: string;
    download_path: string;
    file_types?: string[];
    days_to_keep: number;
    auto_parse: boolean;
  }) => api.post('/feedback/portal/config', data),
  getHistory: (limit?: number) => api.get('/feedback/portal/history', { params: { limit } }),
};

export default api;
