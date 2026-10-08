export const Skeleton = ({ className = "", style }: { className?: string; style?: React.CSSProperties }) => (
  <div className={`skeleton ${className}`} style={style} aria-hidden="true" />
);

/** Placeholder rows while a list loads. */
export const ListSkeleton = ({ rows = 3 }: { rows?: number }) => (
  <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading">
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="tile-quiet flex items-center gap-4 p-4">
        <Skeleton className="h-12 w-12 shrink-0" />
        <div className="flex min-w-0 flex-1 flex-col gap-2"><Skeleton className="h-4 w-2/3" /><Skeleton className="h-3 w-1/3" /></div>
      </div>))}
  </div>
);

export const CardSkeleton = () => (
  <div className="tile flex flex-col gap-4 p-6" aria-busy="true" aria-label="Loading">
    <Skeleton className="h-6 w-1/3" /><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-4/5" /><Skeleton className="h-12 w-40" />
  </div>
);
