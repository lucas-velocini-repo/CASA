import { useEffect, useState } from "react";

// A request key prevents data from an old station/period being displayed during a change.
// A failed refresh clears the result so it cannot be exported as current/complete data.
export function usePolling(key, loader, interval = 60_000) {
  const [state, setState] = useState({
    key: null,
    status: "loading",
    data: null,
    error: null,
  });
  useEffect(() => {
    if (!key) return;
    const controller = new AbortController();
    let timer;
    async function load() {
      try {
        const data = await loader(controller.signal);
        if (!controller.signal.aborted)
          setState({ key, status: "success", data, error: null });
      } catch (error) {
        if (!controller.signal.aborted)
          setState({ key, status: "error", data: null, error: error.message });
      } finally {
        if (!controller.signal.aborted && interval)
          timer = setTimeout(load, interval);
      }
    }
    load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [key, loader, interval]);
  return state.key === key
    ? state
    : { status: "loading", data: null, error: null };
}
