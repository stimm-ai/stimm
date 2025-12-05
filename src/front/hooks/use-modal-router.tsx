'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { useCallback, useMemo } from 'react'

export function useModalRouter() {
    const router = useRouter()
    const searchParams = useSearchParams()

    const isModalMode = useMemo(() => {
        return searchParams?.get('modal') === 'true'
    }, [searchParams])

    const openAsModal = useCallback((url: string) => {
        const separator = url.includes('?') ? '&' : '?'
        router.push(`${url}${separator}modal=true`)
    }, [router])

    const closeModal = useCallback(() => {
        router.back()
    }, [router])

    return {
        isModalMode,
        openAsModal,
        closeModal,
    }
}
