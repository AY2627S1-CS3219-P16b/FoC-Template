import { useEffect, useState } from "react";
import { listRequesterOrders, orderForDisplay } from "../api/orders.js";
import { requesterPollDelay } from "../utils/requesterOrders.js";

export default function useRequesterOrders({ token, userId, refreshTick }) {
  const [query, setQuery] = useState({ view: "active", page: 1 });
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const { view, page } = query;
  const key = `${userId}:${view}:${page}`;

  useEffect(() => {
    let stopped = false;
    let timer;
    let delay = view === "past" ? null : 5000;
    setLoading(true);
    setError("");
    const load = async () => {
      try {
        const result = await listRequesterOrders(token, { view, page });
        if (stopped) return;
        // A cancellation or completion can remove the last row on this page.
        const lastPage = Math.max(1, result.total_pages);
        if (page > lastPage) {
          setQuery({ view, page: lastPage });
          return;
        }
        const items = result.items.map((order) => orderForDisplay(order, userId));
        setSnapshot({ key, result: { ...result, items } });
        setError("");
        delay = requesterPollDelay(view, items);
      } catch (loadError) {
        if (!stopped) setError(loadError.message);
      } finally {
        if (!stopped) {
          setLoading(false);
          if (delay !== null) timer = setTimeout(load, delay);
        }
      }
    };
    if (token) load();
    else setLoading(false);
    return () => { stopped = true; clearTimeout(timer); };
  }, [token, userId, view, page, key, refreshTick, refresh]);

  return {
    view, page, result: snapshot?.key === key ? snapshot.result : null, loading, error,
    onViewChange: (nextView) => setQuery({ view: nextView, page: 1 }),
    onPageChange: (nextPage) => setQuery({ view, page: nextPage }),
    onRefresh: () => setRefresh((value) => value + 1),
  };
}
