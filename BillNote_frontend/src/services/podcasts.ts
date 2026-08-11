import request from '@/utils/request'

export type PodcastSource = 'apple_podcasts' | 'xiaoyuzhou'
export type PodcastEntity = 'show' | 'episode'
export type PodcastMarket = 'cn' | 'us'
export type XiaoyuzhouDiscoverMode = 'personalized' | 'hot' | 'rising' | 'new'

export interface PodcastCatalogItem {
  source: PodcastSource
  kind: PodcastEntity
  id: string
  podcast_id: string
  title: string
  podcast_title: string
  author: string
  description: string
  cover_url: string
  genres: string[]
  duration: number
  published_at: string | null
  canonical_url: string
  is_private: boolean
}

export interface PodcastCatalogPage {
  items: PodcastCatalogItem[]
  cursor: unknown | null
  total: number | null
}

export const discoverPodcasts = async (data: {
  source: PodcastSource
  mode: 'top' | XiaoyuzhouDiscoverMode
  entity?: PodcastEntity
  market?: PodcastMarket
  cursor?: unknown
  limit?: number
}): Promise<PodcastCatalogPage> => {
  return await request.post('/podcasts/discover', data, {
    suppressToast: true,
    timeout: 35_000,
  })
}

export const searchPodcasts = async (data: {
  source: PodcastSource
  entity: PodcastEntity
  query: string
  market?: PodcastMarket
  cursor?: unknown
  limit?: number
}): Promise<PodcastCatalogPage> => {
  return await request.post('/podcasts/search', data, {
    suppressToast: true,
    timeout: 35_000,
  })
}

export const getPodcastShow = async (
  source: PodcastSource,
  podcastId: string,
  market: PodcastMarket = 'cn'
): Promise<PodcastCatalogItem> => {
  return await request.get(`/podcasts/${source}/shows/${podcastId}`, {
    params: { market },
    suppressToast: true,
    timeout: 35_000,
  })
}

export const getPodcastEpisodes = async (
  source: PodcastSource,
  podcastId: string,
  data: { market?: PodcastMarket; cursor?: unknown; limit?: number } = {}
): Promise<PodcastCatalogPage> => {
  return await request.post(`/podcasts/${source}/shows/${podcastId}/episodes`, data, {
    suppressToast: true,
    timeout: 35_000,
  })
}
