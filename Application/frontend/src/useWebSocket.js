/** WebSocket hook — connects to /ws/ed/live/ and dispatches events to store */
import { useEffect, useRef } from 'react'
import { useStore } from './store'
import { WS_URL } from './api'

export function useWebSocket(onEvent) {
  const wsRef = useRef(null)
  const setWsConnected = useStore(s => s.setWsConnected)

  useEffect(() => {
    let reconnectTimeout = null

    function connect() {
      try {
        const ws = new WebSocket(WS_URL)
        wsRef.current = ws

        ws.onopen = () => {
          setWsConnected(true)
          // heartbeat
          const ping = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'ping' }))
            }
          }, 25000)
          ws._pingInterval = ping
        }

        ws.onmessage = (e) => {
          try {
            const msg = JSON.parse(e.data)
            if (msg.type !== 'pong' && msg.type !== 'connected') {
              onEvent && onEvent(msg)
            }
          } catch {}
        }

        ws.onclose = () => {
          setWsConnected(false)
          clearInterval(ws._pingInterval)
          // Auto-reconnect after 3s
          reconnectTimeout = setTimeout(connect, 3000)
        }

        ws.onerror = () => {
          ws.close()
        }
      } catch {
        setWsConnected(false)
        reconnectTimeout = setTimeout(connect, 5000)
      }
    }

    connect()

    return () => {
      clearTimeout(reconnectTimeout)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
    }
  }, [])
}
