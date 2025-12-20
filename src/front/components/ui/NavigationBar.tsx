'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { THEME } from '@/lib/theme';
import { Bot, Database } from 'lucide-react';

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

export function NavigationBar() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === '/stimm') return pathname === href;
    return pathname?.startsWith(href);
  };

  return (
    <div className="mb-6">
      <div
        className={`${THEME.panel.base} ${THEME.panel.border} border rounded-xl p-4 shadow-lg`}
      >
        <div className="flex items-center justify-end">
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
        </div>
      </div>
    </div>
  );
}
