import { describe, expect, it } from 'vitest'
import { describeHealth } from './health.ts'

describe('describeHealth', () => {
  it('reports the API as up when status is ok', () => {
    expect(describeHealth({ status: 'ok' })).toBe('API is up')
  })

  it('flags any other body as unexpected', () => {
    expect(describeHealth({ status: 'down' })).toBe('API returned an unexpected response')
    expect(describeHealth(null)).toBe('API returned an unexpected response')
    expect(describeHealth('ok')).toBe('API returned an unexpected response')
  })
})
