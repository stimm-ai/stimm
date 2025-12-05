'use client'

import React, { useEffect } from 'react'
import { X } from 'lucide-react'
import { THEME } from '@/lib/theme'

interface ModalWrapperProps {
    isOpen: boolean
    onClose: () => void
    title?: string
    children: React.ReactNode
    maxWidth?: string
}

export function ModalWrapper({
    isOpen,
    onClose,
    title,
    children,
    maxWidth = 'max-w-4xl',
}: ModalWrapperProps) {
    // Handle ESC key
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && isOpen) {
                onClose()
            }
        }

        document.addEventListener('keydown', handleEscape)
        return () => document.removeEventListener('keydown', handleEscape)
    }, [isOpen, onClose])

    // Prevent body scroll when modal is open
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = 'hidden'
        } else {
            document.body.style.overflow = 'unset'
        }
        return () => {
            document.body.style.overflow = 'unset'
        }
    }, [isOpen])

    if (!isOpen) return null

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in"
            onClick={onClose}
        >
            <div
                className={`${THEME.bg.gradient} ${THEME.panel.border} border rounded-xl shadow-2xl w-full ${maxWidth} max-h-[90vh] overflow-hidden flex flex-col animate-in slide-in-from-bottom-2`}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                {title && (
                    <div className="flex items-center justify-between p-6 border-b border-white/10">
                        <h2 className="text-xl font-bold text-white">{title}</h2>
                        <button
                            onClick={onClose}
                            className={`${THEME.button.ghost} rounded-full p-2 transition-colors`}
                            aria-label="Close modal"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                )}

                {/* Content */}
                <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
                    {children}
                </div>
            </div>
        </div>
    )
}
