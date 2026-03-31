interface ShimmerSkeletonProps {
  width?: string;
  height?: string;
  borderRadius?: string;
  className?: string;
  lines?: number;
}

export function ShimmerSkeleton({ width = "100%", height = "16px", borderRadius = "6px", className = "", lines = 1 }: ShimmerSkeletonProps) {
  if (lines > 1) {
    return (
      <div style={{ display: "grid", gap: "8px" }} className={className}>
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className="cf-shimmer"
            style={{
              width: i === lines - 1 ? "70%" : width,
              height,
              borderRadius,
            }}
          />
        ))}
      </div>
    );
  }
  return (
    <div
      className={`cf-shimmer ${className}`}
      style={{ width, height, borderRadius }}
    />
  );
}
