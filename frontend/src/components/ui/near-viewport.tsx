import { type ReactNode, useEffect, useRef, useState } from "react";

/** Renders `children` only once the placeholder scrolls near the viewport, keeping heavy widgets off the boot path. */
export function NearViewport({ children, placeholder, margin = "300px" }: { children: ReactNode; placeholder: string; margin?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(typeof IntersectionObserver === "undefined");
  useEffect(() => {
    if (shown || !ref.current) return;
    const io = new IntersectionObserver((entries) => entries.some((e) => e.isIntersecting) && setShown(true), { rootMargin: margin });
    io.observe(ref.current);
    return () => io.disconnect();
  }, [shown, margin]);
  if (shown) return <>{children}</>;
  return (
    <div ref={ref} className="min-h-[220px] rounded-xl border border-dashed border-line p-4 text-xs text-ink-3 md:col-span-2 xl:col-span-3">
      {placeholder}
    </div>
  );
}
