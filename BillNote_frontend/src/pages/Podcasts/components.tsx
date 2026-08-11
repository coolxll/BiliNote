import { ExternalLink, FilePenLine, LockKeyhole, Radio } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import type { PodcastCatalogItem, PodcastSource } from '@/services/podcasts'

export const sourceLabel: Record<PodcastSource, string> = {
  apple_podcasts: 'Apple Podcasts',
  xiaoyuzhou: '小宇宙',
}

export const sourceTone: Record<PodcastSource, string> = {
  apple_podcasts: 'bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200',
  xiaoyuzhou: 'bg-orange-50 text-orange-700 border-orange-200',
}

export function formatDuration(seconds: number) {
  if (!seconds) return ''
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return hours ? `${hours} 小时 ${minutes} 分` : `${Math.max(1, minutes)} 分钟`
}

export function formatPublishedAt(value: string | null) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date)
}

function Cover({ item, size = 'large' }: { item: PodcastCatalogItem; size?: 'small' | 'large' }) {
  const dimension = size === 'large' ? 'h-28 w-28 sm:h-32 sm:w-32' : 'h-20 w-20'
  return item.cover_url ? (
    <img
      src={item.cover_url}
      alt=""
      loading="lazy"
      className={`${dimension} shrink-0 rounded-md bg-neutral-100 object-cover`}
    />
  ) : (
    <div
      className={`${dimension} flex shrink-0 items-center justify-center rounded-md bg-neutral-100`}
    >
      <Radio className="h-7 w-7 text-neutral-400" />
    </div>
  )
}

export function SourceBadge({ source }: { source: PodcastSource }) {
  return (
    <span
      className={`inline-flex items-center border px-2 py-0.5 text-xs font-medium ${sourceTone[source]}`}
    >
      {sourceLabel[source]}
    </span>
  )
}

export function ShowCard({ item }: { item: PodcastCatalogItem }) {
  const location = useLocation()
  const detailSearch = location.pathname === '/podcasts' ? location.search : ''
  return (
    <article className="flex min-w-0 gap-3 rounded-md border border-neutral-200 bg-white p-3 transition-colors hover:border-neutral-300">
      <Cover item={item} size="small" />
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="mb-2 flex items-center gap-2">
          <SourceBadge source={item.source} />
        </div>
        <Link
          to={`/podcasts/${item.source}/${item.podcast_id}${detailSearch}`}
          className="hover:text-primary line-clamp-2 text-sm font-semibold text-neutral-900"
        >
          {item.title}
        </Link>
        {item.author && <p className="mt-1 truncate text-xs text-neutral-500">{item.author}</p>}
        <a
          href={item.canonical_url}
          target="_blank"
          rel="noreferrer"
          className="hover:text-primary mt-auto inline-flex w-fit items-center gap-1 pt-2 text-xs text-neutral-500"
        >
          在{sourceLabel[item.source]}中查看
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </article>
  )
}

export function EpisodeCard({ item }: { item: PodcastCatalogItem }) {
  const navigate = useNavigate()
  const location = useLocation()
  const detailSearch = location.pathname === '/podcasts' ? location.search : ''
  const generate = () => {
    const params = new URLSearchParams({
      platform: item.source,
      video_url: item.canonical_url,
      from: 'podcasts',
    })
    navigate(`/?${params.toString()}`)
  }

  return (
    <article className="flex min-w-0 flex-col gap-3 border-b border-neutral-200 py-4 sm:flex-row sm:items-start">
      <Cover item={item} size="small" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <SourceBadge source={item.source} />
          {item.is_private && (
            <span className="inline-flex items-center gap-1 text-xs text-neutral-500">
              <LockKeyhole className="h-3 w-3" /> 私有内容
            </span>
          )}
        </div>
        <h3 className="mt-2 text-base font-semibold text-neutral-900">{item.title}</h3>
        {item.podcast_title && (
          <Link
            to={`/podcasts/${item.source}/${item.podcast_id}${detailSearch}`}
            className="hover:text-primary mt-1 block w-fit text-sm text-neutral-600"
          >
            {item.podcast_title}
          </Link>
        )}
        <div className="mt-2 flex flex-wrap gap-x-3 text-xs text-neutral-500">
          {formatPublishedAt(item.published_at) && (
            <span>{formatPublishedAt(item.published_at)}</span>
          )}
          {formatDuration(item.duration) && <span>{formatDuration(item.duration)}</span>}
        </div>
        {item.description && (
          <p className="mt-2 line-clamp-2 text-sm leading-6 text-neutral-600">{item.description}</p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2 sm:pt-7">
        <Button type="button" size="sm" disabled={item.is_private} onClick={generate}>
          <FilePenLine className="h-4 w-4" />
          生成笔记
        </Button>
        <Button asChild type="button" variant="outline" size="icon" className="h-9 w-9">
          <a href={item.canonical_url} target="_blank" rel="noreferrer" aria-label="打开来源链接">
            <ExternalLink className="h-4 w-4" />
          </a>
        </Button>
      </div>
    </article>
  )
}

export function LoadingRows() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {[0, 1, 2].map(value => (
        <div
          key={value}
          className="h-28 animate-pulse rounded-md border border-neutral-200 bg-white p-3"
        >
          <div className="h-full w-20 rounded-md bg-neutral-100" />
        </div>
      ))}
    </div>
  )
}

export function LoginRequired() {
  return (
    <div className="flex flex-col items-start gap-3 border-l-2 border-orange-300 bg-orange-50 px-4 py-3 text-sm text-orange-900 sm:flex-row sm:items-center sm:justify-between">
      <span>登录小宇宙后可读取发现流、榜单和搜索结果。</span>
      <Button asChild type="button" variant="outline" size="sm">
        <Link to="/settings/xiaoyuzhou">前往登录</Link>
      </Button>
    </div>
  )
}
