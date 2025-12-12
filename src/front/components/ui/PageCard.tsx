import React from 'react';
import { THEME } from '@/lib/theme';

interface PageCardProps {
  title?: string;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

export function PageCard({
  title,
  icon,
  actions,
  className = '',
  children,
}: PageCardProps) {
  return (
    <div className={`${THEME.card.base} p-6 shadow-2xl ${className}`}>
      {(title || actions) && (
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            {icon && <div className={THEME.text.accent}>{icon}</div>}
            {title && <h2 className="text-xl font-bold">{title}</h2>}
          </div>
          {actions && <div className="flex gap-2">{actions}</div>}
        </div>
      )}

      <div>{children}</div>
    </div>
  );
}
