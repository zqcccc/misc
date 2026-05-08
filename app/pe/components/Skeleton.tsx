export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded-md bg-gray-200 dark:bg-[#1e2435] ${className}`} />
  )
}
