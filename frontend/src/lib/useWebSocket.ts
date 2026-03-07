import { useEffect, useRef, useCallback, useState } from 'react'
import { useAuthStore } from '../store/authStore'

interface WebSocketMessage {
  channel: string
  data: Record<string, unknown>
  timestamp: string
}

interface UseWebSocketOptions {
  channels?: string[]
  onMessage?: (msg: WebSocketMessage) => void
  autoReconnect?: boolean
}

export function useWebSocket({ channels = [], onMessage, autoReconnect = true }: UseWebSocketOptions = {}) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>()
  const [connected, setConnected] = useState(false)
  const token = useAuthStore((s) => s.token)

  const connect = useCallback(() => {
    if (!token) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const channelParam = channels.length > 0 ? `&channels=${channels.join(',')}` : ''
    const url = `${protocol}//${host}/ws?token=${token}${channelParam}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WebSocketMessage
        onMessage?.(msg)
      } catch {
        // ignore non-JSON messages
      }
    }

    ws.onclose = () => {
      setConnected(false)
      if (autoReconnect) {
        reconnectTimerRef.current = setTimeout(connect, 3000)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [token, channels, onMessage, autoReconnect])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  const subscribe = useCallback((channel: string) => {
    wsRef.current?.send(JSON.stringify({ action: 'subscribe', channel }))
  }, [])

  const unsubscribe = useCallback((channel: string) => {
    wsRef.current?.send(JSON.stringify({ action: 'unsubscribe', channel }))
  }, [])

  return { connected, subscribe, unsubscribe }
}
