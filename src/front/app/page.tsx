'use client'

import React from 'react'
import Link from 'next/link'
import { PageLayout } from '@/components/ui/PageLayout'
import { THEME } from '@/lib/theme'
import { Bot, Database, MessageSquare, BookOpen, Activity, Cpu, Layers } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'

export default function Home() {
  const quickLinks = [
    {
      title: 'Agent Management',
      description: 'Configure and manage your voice agents, set up their providers (LLM, TTS, STT) and personalities.',
      href: '/agent/admin',
      icon: <Bot className="w-8 h-8 text-cyan-300" />,
      color: 'cyan'
    },
    {
      title: 'RAG Configuration',
      description: 'Manage knowledge bases and RAG pipelines to give your agents context and specific knowledge.',
      href: '/rag/admin',
      icon: <Database className="w-8 h-8 text-purple-300" />,
      color: 'purple'
    },
    {
      title: 'Talk to Agent',
      description: 'Interact directly with your configured agents to test their responses and latency in real-time.',
      href: '/stimm',
      icon: <MessageSquare className="w-8 h-8 text-green-300" />,
      color: 'green'
    },
    {
      title: 'Documentation',
      description: 'Access the full documentation to understand how to integrate and extend the Stimm platform.',
      href: 'https://stimm-ai.github.io/stimm/',
      icon: <BookOpen className="w-8 h-8 text-orange-300" />,
      color: 'orange',
      external: true
    }
  ]

  return (
    <PageLayout
      title="Platform Overview"
      icon={<Activity className="w-6 h-6" />}
      showNavigation={true}
    >
      <div className="space-y-8 max-w-7xl mx-auto">
        {/* Welcome Section */}
        <div className="flex flex-col md:flex-row gap-8 items-center md:items-start">
          <div className="flex-1 space-y-4">
            <h2 className="text-3xl font-bold text-white">Welcome to Stimm</h2>
            <p className="text-lg text-white/80 leading-relaxed">
              Stimm is an open-source voice agent platform designed for orchestrating ultra-low latency AI pipelines. 
              It combines state-of-the-art LLMs, TTS, and STT providers with real-time WebRTC communication.
            </p>
            <div className="flex flex-wrap gap-3 pt-2">
              <div className={`px-3 py-1 rounded-full text-xs font-medium border flex items-center gap-2 ${THEME.badge.cyan}`}>
                <Cpu className="w-3 h-3" /> Real-time Inference
              </div>
              <div className={`px-3 py-1 rounded-full text-xs font-medium border flex items-center gap-2 ${THEME.badge.purple}`}>
                <Layers className="w-3 h-3" /> Modular Architecture
              </div>
              <div className={`px-3 py-1 rounded-full text-xs font-medium border flex items-center gap-2 ${THEME.badge.orange}`}>
                <Activity className="w-3 h-3" /> Low Latency
              </div>
            </div>
          </div>
        </div>

        {/* Quick Links Grid */}
        <div>
            <h3 className="text-xl font-bold text-white/90 mb-6 flex items-center gap-2">
                Quick Access
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {quickLinks.map((link) => (
                <Link 
                key={link.title} 
                href={link.href}
                target={link.external ? "_blank" : undefined}
                rel={link.external ? "noopener noreferrer" : undefined}
                className="group h-full"
                >
                <div className={`
                    h-full p-6 rounded-xl border transition-all duration-300 flex flex-col gap-4
                    ${THEME.panel.base} ${THEME.panel.border} ${THEME.panel.hover}
                    hover:border-white/40 hover:-translate-y-1 hover:shadow-xl
                `}>
                    <div className={`
                    p-3 rounded-lg w-fit transition-colors duration-300
                    ${link.color === 'cyan' ? 'bg-cyan-500/10 group-hover:bg-cyan-500/20' : ''}
                    ${link.color === 'purple' ? 'bg-purple-500/10 group-hover:bg-purple-500/20' : ''}
                    ${link.color === 'green' ? 'bg-green-500/10 group-hover:bg-green-500/20' : ''}
                    ${link.color === 'orange' ? 'bg-orange-500/10 group-hover:bg-orange-500/20' : ''}
                    `}>
                    {link.icon}
                    </div>
                    <div>
                    <h4 className={`text-lg font-bold mb-2 group-hover:text-white transition-colors ${THEME.text.primary}`}>
                        {link.title}
                    </h4>
                    <p className={`text-sm leading-relaxed ${THEME.text.muted} group-hover:text-white/80 transition-colors`}>
                        {link.description}
                    </p>
                    </div>
                </div>
                </Link>
            ))}
            </div>
        </div>
      </div>
    </PageLayout>
  )
}
