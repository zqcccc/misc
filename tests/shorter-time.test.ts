import assert from 'node:assert/strict'
import { formatRemainingTime } from '../app/s/time'

assert.equal(formatRemainingTime(null), 'never expires')
assert.equal(formatRemainingTime(-1), 'never expires')
assert.equal(formatRemainingTime(-2), 'expired or not found')
assert.equal(formatRemainingTime(59), '59s')
assert.equal(formatRemainingTime(3661), '1h 1m 1s')
assert.equal(formatRemainingTime(90061), '1d 1h 1m 1s')
