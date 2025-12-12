import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { THEME } from '@/lib/theme';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Logo } from '@/components/ui/Logo';
import { Bot, Database } from 'lucide-react';

interface PageLayoutProps {
  title: string;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  breadcrumbs?: Array<{ label: string; href: string }>;
  error?: string | null;
  children: React.ReactNode;
  className?: string;
  showNavigation?: boolean;
}

interface NavigationLink {
  href: string;
  label: string;
  icon: React.ReactNode;
}

const navLinks: NavigationLink[] = [
  { href: '/agent/admin', label: 'Agents', icon: <Bot className="w-4 h-4" /> },
  {
    href: '/rag/admin',
    label: 'RAG Configs',
    icon: <Database className="w-4 h-4" />,
  },
];

export function PageLayout({
  title,
  icon,
  actions,
  breadcrumbs,
  error,
  children,
  className = '',
  showNavigation = true,
}: PageLayoutProps) {
  const pathname = usePathname();

  const isActive = (href: string) => {
    return pathname?.startsWith(href);
  };

  return (
    <div
      className={`min-h-screen ${THEME.bg.gradient} ${THEME.text.primary} font-sans p-4 md:p-8`}
    >
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <Logo />
          {actions && <div className="flex gap-2">{actions}</div>}
        </div>

        {breadcrumbs && breadcrumbs.length > 0 && (
          <nav className="flex items-center gap-2 text-sm mb-4">
            {breadcrumbs.map((crumb, index) => (
              <React.Fragment key={crumb.href}>
                {index > 0 && <span className={THEME.text.muted}>/</span>}
                <a
                  href={crumb.href}
                  className={`${THEME.text.secondary} hover:${THEME.text.primary} transition-colors`}
                >
                  {crumb.label}
                </a>
              </React.Fragment>
            ))}
          </nav>
        )}

        {/* Merged Title and Navigation Bar */}
        <div
          className={`${THEME.panel.base} ${THEME.panel.border} border rounded-xl p-4 shadow-lg`}
        >
          <div className="flex items-center justify-between">
            {/* Title on the left */}
            <div className="flex items-center gap-3">
              {icon && <div className={THEME.text.accent}>{icon}</div>}
              <h1 className="text-2xl font-bold">{title}</h1>
            </div>

            {/* Navigation items on the right */}
            {showNavigation && (
              <nav className="flex items-center gap-2">
                {navLinks.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`
                                            flex items-center gap-2 px-4 py-2 rounded-lg transition-all font-medium text-sm
                                            ${
                                              isActive(link.href)
                                                ? `${THEME.accent.cyanBg} ${THEME.accent.cyan} ${THEME.accent.cyanBorder} border ${THEME.glow.cyan}`
                                                : `${THEME.button.ghost}`
                                            }
                                        `}
                  >
                    {link.icon}
                    <span>{link.label}</span>
                  </Link>
                ))}
              </nav>
            )}
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert
          variant="destructive"
          className="mb-6 bg-red-900/50 border-red-500/50"
        >
          <AlertDescription className="text-white">{error}</AlertDescription>
        </Alert>
      )}

      {/* Content */}
      <div className={className}>{children}</div>
    </div>
  );
}
