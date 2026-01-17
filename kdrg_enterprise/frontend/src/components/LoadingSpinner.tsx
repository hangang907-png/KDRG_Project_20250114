import { Loader2 } from 'lucide-react';
import clsx from 'clsx';

interface LoadingSpinnerProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
  fullScreen?: boolean;
}

export default function LoadingSpinner({
  message = '로딩 중...',
  size = 'md',
  fullScreen = false,
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'h-6 w-6',
    md: 'h-10 w-10',
    lg: 'h-14 w-14',
  };

  const content = (
    <div className="flex flex-col items-center justify-center gap-3">
      <Loader2 className={clsx('animate-spin text-primary-600', sizeClasses[size])} />
      {message && <p className="text-sm text-gray-500 animate-pulse">{message}</p>}
    </div>
  );

  if (fullScreen) {
    return <div className="min-h-screen flex items-center justify-center">{content}</div>;
  }

  return <div className="flex items-center justify-center py-12">{content}</div>;
}
