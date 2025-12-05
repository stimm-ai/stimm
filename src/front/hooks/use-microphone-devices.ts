'use client'

import { useState, useEffect, useCallback } from 'react'

export interface MicrophoneDevice {
  deviceId: string
  label: string
  groupId: string
}

export interface UseMicrophoneDevicesReturn {
  devices: MicrophoneDevice[]
  selectedDeviceId: string | null
  isLoading: boolean
  error: string | null
  refreshDevices: () => Promise<void>
  setSelectedDeviceId: (deviceId: string) => void
}

export function useMicrophoneDevices(): UseMicrophoneDevicesReturn {
  const [devices, setDevices] = useState<MicrophoneDevice[]>([])
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refreshDevices = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      // Request permission to access media devices (optional but may trigger permission prompt)
      await navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
        // Immediately stop the stream to release the microphone
        stream.getTracks().forEach(track => track.stop())
      })
      const deviceInfos = await navigator.mediaDevices.enumerateDevices()
      const audioInputs = deviceInfos
        .filter(device => device.kind === 'audioinput')
        .map(device => ({
          deviceId: device.deviceId,
          label: device.label || `Microphone ${device.deviceId.slice(0, 5)}`,
          groupId: device.groupId,
        }))
      setDevices(audioInputs)
      // If no device selected yet, select the first one (or default)
      if (audioInputs.length > 0 && !selectedDeviceId) {
        const defaultDevice = audioInputs.find(d => d.deviceId === 'default') || audioInputs[0]
        setSelectedDeviceId(defaultDevice.deviceId)
      }
    } catch (err) {
      console.error('Failed to enumerate microphone devices:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }, [selectedDeviceId])

  // Load devices on mount
  useEffect(() => {
    refreshDevices()
  }, [refreshDevices])

  // Load saved device from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('stimm_selected_microphone')
    if (saved && devices.some(d => d.deviceId === saved)) {
      setSelectedDeviceId(saved)
    }
  }, [devices])

  // Persist selected device to localStorage when it changes
  useEffect(() => {
    if (selectedDeviceId) {
      localStorage.setItem('stimm_selected_microphone', selectedDeviceId)
    }
  }, [selectedDeviceId])

  return {
    devices,
    selectedDeviceId,
    isLoading,
    error,
    refreshDevices,
    setSelectedDeviceId,
  }
}