import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    {
      type: 'category',
      label: 'Getting Started',
      items: [
        'getting-started/getting-started-overview',
        'getting-started/getting-started-installation',
        'getting-started/getting-started-quickstart',
      ],
    },
    {
      type: 'category',
      label: 'Integrations',
      items: [
        'integrations/integrations-wizard',
        'integrations/integrations-agent-md',
        'integrations/integrations-supervisor-observability',
      ],
    },
    {
      type: 'category',
      label: 'Reference',
      items: ['reference/reference-providers-catalog', 'reference/reference-runtime-contract'],
    },
  ],
};

export default sidebars;
