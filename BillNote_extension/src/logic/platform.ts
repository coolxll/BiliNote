import type { NoteFormat, Platform } from './types'

const XIAOYUZHOU_EPISODE_PATH_RE = /^\/episode\/[0-9a-f]{24}\/?$/i

// 与 backend/app/validators/video_url_validator.py 保持一致
export function detectPlatform(url: string | undefined | null): Platform | null {
  if (!url)
    return null
  try {
    const parsed = new URL(url)
    if (
      ['xiaoyuzhoufm.com', 'www.xiaoyuzhoufm.com'].includes(parsed.hostname.toLowerCase())
      && XIAOYUZHOU_EPISODE_PATH_RE.test(parsed.pathname)
    ) {
      return 'xiaoyuzhou'
    }
  }
  catch {
    return null
  }
  if (/bilibili\.com\/video\//.test(url))
    return 'bilibili'
  if (url.includes('youtube.com/watch') || url.includes('youtu.be/'))
    return 'youtube'
  if (url.includes('douyin'))
    return 'douyin'
  if (url.includes('kuaishou'))
    return 'kuaishou'
  return null
}

export const PLATFORM_LABELS: Record<Platform, string> = {
  bilibili: '哔哩哔哩',
  youtube: 'YouTube',
  douyin: '抖音',
  kuaishou: '快手',
  xiaoyuzhou: '小宇宙',
  local: '本地',
}

export const PLATFORM_CONTENT_LABELS: Record<Platform, string> = {
  bilibili: '视频',
  youtube: '视频',
  douyin: '视频',
  kuaishou: '视频',
  xiaoyuzhou: '单集',
  local: '内容',
}

export function supportsVideoFeatures(platform: Platform | null): boolean {
  return platform !== 'xiaoyuzhou'
}

export function getSupportedFormats(platform: Platform, formats: NoteFormat[]): NoteFormat[] {
  if (supportsVideoFeatures(platform))
    return [...formats]
  return formats.filter(format => format !== 'screenshot' && format !== 'link')
}
