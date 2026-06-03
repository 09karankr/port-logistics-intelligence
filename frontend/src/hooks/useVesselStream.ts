import { useEffect, useRef } from "react";
import { WS_URL } from "../api/client";
import { useVesselStore } from "../store/vesselStore";
import type { LivePositionUpdate } from "../types";

export function useVesselStream() {
  const updatePosition = useVesselStore((s) => s.updatePosition);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let unmounted = false;

    function connect() {
      if (unmounted) return;
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onmessage = (e) => {
        try {
          const update: LivePositionUpdate = JSON.parse(e.data);
          updatePosition(update);
        } catch {
          // ignore malformed frames
        }
      };

      ws.onclose = () => {
        if (!unmounted) {
          reconnectTimer.current = setTimeout(connect, 3000);
        }
      };
    }

    connect();

    return () => {
      unmounted = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [updatePosition]);
}
