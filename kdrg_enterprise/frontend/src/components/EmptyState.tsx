import { LucideIcon, FileX, Database, Users, Search } from 'lucide-react';
import clsx from 'clsx';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  variant?: 'default' | 'search' | 'error';
}

const variantStyles = {
  default: {
    iconBg: 'bg-gray-100',
    iconColor: 'text-gray-400',
  },
  search: {
    iconBg: 'bg-blue-50',
    iconColor: 'text-blue-400',
  },
  error: {
    iconBg: 'bg-red-50',
    iconColor: 'text-red-400',
  },
};

export default function EmptyState({
  icon: Icon = FileX,
  title,
  description,
  actionLabel,
  onAction,
  variant = 'default',
}: EmptyStateProps) {
  const styles = variantStyles[variant];

  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      <div className={clsx('p-4 rounded-full mb-4', styles.iconBg)}>
        <Icon className={clsx('h-12 w-12', styles.iconColor)} />
      </div>
      <h3 className="text-lg font-medium text-gray-900 mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-gray-500 text-center max-w-sm mb-4">
          {description}
        </p>
      )}
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="btn-primary"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
