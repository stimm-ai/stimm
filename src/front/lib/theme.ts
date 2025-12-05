// Centralized theme configuration for the stimm application
// This file contains all theme constants and utilities used across the app

export const THEME = {
    // Background gradients
    bg: {
        gradient: 'bg-gradient-to-br from-blue-500 to-purple-600',
        gradientDark: 'bg-gradient-to-br from-blue-600 to-purple-700',
    },

    // Glass morphism panels
    panel: {
        base: 'bg-white/10 backdrop-blur-md',
        border: 'border-white/20',
        borderGlow: 'border-white/30',
        hover: 'hover:bg-white/15',
    },

    // Text colors
    text: {
        primary: 'text-white',
        secondary: 'text-white/80',
        muted: 'text-white/60',
        accent: 'text-cyan-300',
        accentBright: 'text-cyan-400',
        success: 'text-green-300',
        error: 'text-red-300',
        warning: 'text-yellow-300',
    },

    // Button styles
    button: {
        primary: 'bg-white/20 hover:bg-white/30 border border-white/20 text-white',
        secondary: 'bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/30 text-cyan-300',
        success: 'bg-green-500/20 hover:bg-green-500/30 border border-green-500/30 text-green-300',
        danger: 'bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 text-red-300',
        ghost: 'bg-transparent hover:bg-white/10 text-white',
    },

    // Accent colors
    accent: {
        cyan: 'text-cyan-300',
        cyanBg: 'bg-cyan-500/20',
        cyanBorder: 'border-cyan-500/30',
        purple: 'text-purple-300',
        purpleBg: 'bg-purple-500/20',
        purpleBorder: 'border-purple-500/30',
        orange: 'text-orange-300',
        orangeBg: 'bg-orange-500/20',
        orangeBorder: 'border-orange-500/30',
        green: 'text-green-300',
        greenBg: 'bg-green-500/20',
        greenBorder: 'border-green-500/30',
    },

    // Glow effects
    glow: {
        cyan: 'shadow-[0_0_20px_rgba(103,232,249,0.3)]',
        cyanBright: 'shadow-[0_0_20px_rgba(103,232,249,0.6)]',
        purple: 'shadow-[0_0_20px_rgba(192,132,252,0.3)]',
        white: 'shadow-[0_0_20px_rgba(255,255,255,0.3)]',
    },

    // Cards
    card: {
        base: 'bg-white/10 backdrop-blur-md border border-white/20 rounded-xl',
        hover: 'hover:bg-white/15 transition-all',
        selected: 'border-cyan-400 bg-cyan-900/50 shadow-[0_0_20px_rgba(103,232,249,0.3)]',
    },

    // Inputs
    input: {
        base: 'bg-white/10 border border-white/20 text-white placeholder:text-white/40 focus:border-cyan-400 focus:ring-cyan-400/20',
        select: 'bg-white/10 border border-white/20 text-white',
    },

    // Badges
    badge: {
        default: 'bg-white/20 text-white border border-white/30',
        cyan: 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30',
        purple: 'bg-purple-500/20 text-purple-300 border border-purple-500/30',
        orange: 'bg-orange-500/20 text-orange-300 border border-orange-500/30',
        green: 'bg-green-500/20 text-green-300 border border-green-500/30',
    },
} as const

// Utility function to combine theme classes
export function cn(...classes: (string | boolean | undefined | null)[]) {
    return classes.filter(Boolean).join(' ')
}

// Get provider badge color based on provider type
export function getProviderBadgeClasses(providerType: 'llm' | 'tts' | 'stt' | 'rag') {
    const colors = {
        llm: THEME.badge.cyan,
        tts: THEME.badge.purple,
        stt: THEME.badge.orange,
        rag: THEME.badge.green,
    }
    return colors[providerType] || THEME.badge.default
}

// Get provider accent color
export function getProviderAccent(providerType: 'llm' | 'tts' | 'stt' | 'rag') {
    const colors = {
        llm: { text: THEME.accent.cyan, bg: THEME.accent.cyanBg, border: THEME.accent.cyanBorder },
        tts: { text: THEME.accent.purple, bg: THEME.accent.purpleBg, border: THEME.accent.purpleBorder },
        stt: { text: THEME.accent.orange, bg: THEME.accent.orangeBg, border: THEME.accent.orangeBorder },
        rag: { text: THEME.accent.green, bg: THEME.accent.greenBg, border: THEME.accent.greenBorder },
    }
    return colors[providerType] || { text: THEME.text.primary, bg: 'bg-white/20', border: 'border-white/20' }
}
