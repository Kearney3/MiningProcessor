import { createContext, useContext, useState, useCallback, useEffect, useRef } from "react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type ToastKind = "success" | "error" | "info";

export interface ToastItem {
  id: number;
  message: string;
  kind: ToastKind;
}

interface ToastContextValue {
  /** Show a toast notification. Returns the toast ID. */
  notify: (message: string, kind?: ToastKind) => void;
}

/* ------------------------------------------------------------------ */
/*  Context                                                            */
/* ------------------------------------------------------------------ */

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

/* ------------------------------------------------------------------ */
/*  Provider                                                           */
/* ------------------------------------------------------------------ */

let _nextId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timeoutsRef = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const remove = useCallback((id: number) => {
    const timeout = timeoutsRef.current.get(id);
    if (timeout) {
      clearTimeout(timeout);
      timeoutsRef.current.delete(id);
    }
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const notify = useCallback(
    (message: string, kind: ToastKind = "success") => {
      const id = ++_nextId;
      setToasts((prev) => [...prev, { id, message, kind }]);
      const timeout = setTimeout(() => remove(id), 3500);
      timeoutsRef.current.set(id, timeout);
    },
    [remove],
  );

  // Cleanup all timeouts on unmount
  useEffect(() => {
    const timeouts = timeoutsRef.current;
    return () => {
      timeouts.forEach((t) => clearTimeout(t));
    };
  }, []);

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      {/* Toast container — top-right, stacked */}
      <div className="fixed top-14 right-4 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <ToastCard key={t.id} item={t} onClose={() => remove(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/* ------------------------------------------------------------------ */
/*  Toast card                                                         */
/* ------------------------------------------------------------------ */

const BG: Record<ToastKind, string> = {
  success: "bg-emerald-600",
  error: "bg-red-600",
  info: "bg-slate-700",
};

function IconCheck() {
  return (
    <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

function IconWarning() {
  return (
    <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function IconInfo() {
  return (
    <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

const ICONS: Record<ToastKind, React.ReactNode> = {
  success: <IconCheck />,
  error: <IconWarning />,
  info: <IconInfo />,
};

function ToastCard({ item, onClose }: { item: ToastItem; onClose: () => void }) {
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    // Start exit animation 300ms before removal
    const t = setTimeout(() => setExiting(true), 3200);
    return () => clearTimeout(t);
  }, []);

  return (
    <div
      onClick={onClose}
      className={`
        pointer-events-auto cursor-pointer
        ${BG[item.kind]} text-white text-sm
        px-4 py-2.5 rounded-lg shadow-lg
        flex items-center gap-2 max-w-sm
        transition-all duration-300 ease-out
        ${exiting ? "opacity-0 translate-x-4" : "opacity-100 translate-x-0"}
      `}
    >
      {ICONS[item.kind]}
      <span className="truncate">{item.message}</span>
    </div>
  );
}
