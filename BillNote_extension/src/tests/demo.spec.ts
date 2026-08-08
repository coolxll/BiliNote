import { describe, expect, it } from 'vitest'
import { detectPlatform, getSupportedFormats, supportsVideoFeatures } from '../logic/platform'

const EPISODE_ID = '69b4d2f9f8b8079bfa3ae7f2'

describe('platform detection', () => {
  it('recognizes Xiaoyuzhou episode URLs', () => {
    expect(detectPlatform(`https://www.xiaoyuzhoufm.com/episode/${EPISODE_ID}`)).toBe('xiaoyuzhou')
    expect(detectPlatform(`https://xiaoyuzhoufm.com/episode/${EPISODE_ID}/?utm_source=test#player`)).toBe('xiaoyuzhou')
  })

  it('rejects non-episode and spoofed Xiaoyuzhou URLs', () => {
    expect(detectPlatform('https://www.xiaoyuzhoufm.com/podcast/62382c1103bea1ebfffa1c00')).toBeNull()
    expect(detectPlatform(`https://example.com/?next=xiaoyuzhoufm.com/episode/${EPISODE_ID}`)).toBeNull()
    expect(detectPlatform('https://www.xiaoyuzhoufm.com/episode/not-an-episode-id')).toBeNull()
  })

  it('keeps existing platforms supported', () => {
    expect(detectPlatform('https://www.bilibili.com/video/BV1xx411c7mD')).toBe('bilibili')
    expect(detectPlatform('https://www.youtube.com/watch?v=dQw4w9WgXcQ')).toBe('youtube')
    expect(detectPlatform('https://www.douyin.com/video/123')).toBe('douyin')
    expect(detectPlatform('https://www.kuaishou.com/short-video/abc')).toBe('kuaishou')
  })
})

describe('xiaoyuzhou capabilities', () => {
  it('disables video-only formats without mutating saved preferences', () => {
    const formats = ['toc', 'summary', 'screenshot', 'link'] as const
    expect(getSupportedFormats('xiaoyuzhou', [...formats])).toEqual(['toc', 'summary'])
    expect(formats).toEqual(['toc', 'summary', 'screenshot', 'link'])
    expect(supportsVideoFeatures('xiaoyuzhou')).toBe(false)
    expect(supportsVideoFeatures('bilibili')).toBe(true)
  })
})
