import { AlertCircle, RefreshCw, X } from 'lucide-react';

interface ErrorMessageProps {
  message: string;
  title?: string;
  onRetry?: () => void;
  onDismiss?: () => void;
  variant?: 'inline' | 'card';
}

export default function ErrorMessage({
  message,
  title = '오류가 발생했습니다',
  onRetry,
  onDismiss,
  variant = 'inline',
}: ErrorMessageProps) {
  if (variant === 'card') {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-red-100 p-6">
        <div className="flex flex-col items-center text-center">
          <div className="p-3 bg-red-50 rounded-full mb-4">
            <AlertCircle className="h-8 w-8 text-red-500" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">{title}</h3>
          <p className="text-sm text-gray-500 mb-4">{message}</p>
          <div className="flex gap-3">
            {onRetry && (
              <button onClick={onRetry} className="btn-primary flex items-center gap-2">
                <RefreshCw className="h-4 w-4" />
                다시 시도
              </button>
            )}
            {onDismiss && (
              <button onClick={onDismiss} className="btn-secondary">
                닫기
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
      <div className="flex items-start gap-3">
        <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="font-medium text-red-800">{title}</p>
          <p className="text-sm text-red-600 mt-1">{message}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 text-sm font-medium text-red-700 hover:text-red-800 flex items-center gap-1"
            >
              <RefreshCw className="h-4 w-4" />
              다시 시도
            </button>
          )}
        </div>
        {onDismiss && (
          <button onClick={onDismiss} className="p-1 text-red-400 hover:text-red-600 rounded">
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
