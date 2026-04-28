const SECONDS_PER_DAY = 24 * 60 * 60
const SECONDS_PER_HOUR = 60 * 60
const SECONDS_PER_MINUTE = 60

export function formatRemainingTime(ttl: number | null) {
  if (ttl === null || ttl === -1) return 'never expires'
  if (ttl < 0) return 'expired or not found'

  const days = Math.floor(ttl / SECONDS_PER_DAY)
  const hours = Math.floor((ttl % SECONDS_PER_DAY) / SECONDS_PER_HOUR)
  const minutes = Math.floor((ttl % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE)
  const seconds = ttl % SECONDS_PER_MINUTE
  const parts = [
    days ? `${days}d` : '',
    hours ? `${hours}h` : '',
    minutes ? `${minutes}m` : '',
    seconds || (!days && !hours && !minutes) ? `${seconds}s` : '',
  ].filter(Boolean)

  return parts.join(' ')
}
