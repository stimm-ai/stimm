import { Button } from '@/components/ui/button'
import { THEME } from '@/lib/theme'
import { Mic, Plus } from 'lucide-react'

interface PageHeaderActionsProps {
    type: 'agent' | 'rag'
}

export function PageHeaderActions({ type }: PageHeaderActionsProps) {
    const createConfig = {
        agent: {
            href: '/agent/create',
            label: 'Create Agent',
        },
        rag: {
            href: '/rag/create',
            label: 'Create RAG Configuration',
        },
    }

    const config = createConfig[type]

    return (
        <>
            <Button asChild className={`${THEME.button.ghost} rounded-full px-4`}>
                <a href="/stimm" className="flex items-center gap-2">
                    <Mic className="w-4 h-4" />
                    Speak with an agent
                </a>
            </Button>
            <Button asChild className={`${THEME.button.secondary} rounded-full px-4`}>
                <a href={config.href} className="flex items-center gap-2">
                    <Plus className="w-4 h-4" />
                    {config.label}
                </a>
            </Button>
        </>
    )
}
