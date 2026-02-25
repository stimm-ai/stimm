import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'stimm',
  tagline: 'Dual-agent voice orchestration on LiveKit',
  favicon: 'img/logo_stimm_h.png',
  url: 'https://stimm-ai.github.io',
  baseUrl: '/stimm/',
  organizationName: 'stimm-ai',
  projectName: 'stimm',
  onBrokenLinks: 'throw',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },
  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: '/',
          sidebarPath: './sidebars.ts',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],
  themeConfig: {
    image: 'img/logo_stimm_h.png',
    navbar: {
      title: 'stimm',
      logo: {
        alt: 'stimm logo',
        src: 'img/logo_stimm_h.png',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          href: 'https://github.com/stimm-ai/stimm',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {
              label: 'Getting Started',
              to: '/getting-started/getting-started-installation',
            },
            {
              label: 'Wizard Integration',
              to: '/integrations/integrations-wizard',
            },
          ],
        },
        {
          title: 'Community',
          items: [
            { label: 'GitHub', href: 'https://github.com/stimm-ai/stimm' },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} stimm`,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
