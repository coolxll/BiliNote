import { useEffect, useState } from 'react'
import { ArrowLeft, ExternalLink, Loader2, Radio } from 'lucide-react'
import { Link, Navigate, useLocation, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import {
  getPodcastEpisodes,
  getPodcastShow,
  type PodcastCatalogItem,
  type PodcastMarket,
  type PodcastSource,
} from '@/services/podcasts'
import { EpisodeCard, LoginRequired, SourceBadge } from './components'

function isSource(value: string | undefined): value is PodcastSource {
  return value === 'apple_podcasts' || value === 'xiaoyuzhou'
}

function errorDetails(error: unknown) {
  const value = error as { msg?: string; data?: { reason?: string } }
  return {
    loginRequired: value?.data?.reason === 'xiaoyuzhou_login_required',
    message: value?.msg || '节目暂时无法读取',
  }
}

export default function PodcastShowPage() {
  const { source, podcastId } = useParams()
  const location = useLocation()
  const market: PodcastMarket =
    localStorage.getItem('bilinote-podcast-market') === 'us' ? 'us' : 'cn'
  const [show, setShow] = useState<PodcastCatalogItem | null>(null)
  const [episodes, setEpisodes] = useState<PodcastCatalogItem[]>([])
  const [cursor, setCursor] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [loginRequired, setLoginRequired] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!isSource(source) || !podcastId) return
    let active = true
    setLoading(true)
    setError('')
    setLoginRequired(false)
    Promise.all([
      getPodcastShow(source, podcastId, market),
      getPodcastEpisodes(source, podcastId, { market, limit: 20 }),
    ])
      .then(([showResult, episodePage]) => {
        if (!active) return
        setShow(showResult)
        setEpisodes(episodePage.items)
        setCursor(episodePage.cursor)
      })
      .catch(requestError => {
        if (!active) return
        const details = errorDetails(requestError)
        setLoginRequired(details.loginRequired)
        setError(details.loginRequired ? '' : details.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [market, podcastId, source])

  if (!isSource(source) || !podcastId) return <Navigate to="/podcasts" replace />

  const loadMore = async () => {
    if (cursor == null || loadingMore) return
    setLoadingMore(true)
    try {
      const page = await getPodcastEpisodes(source, podcastId, { market, cursor, limit: 20 })
      setEpisodes(current => {
        const known = new Set(current.map(item => `${item.source}-${item.id}`))
        return [...current, ...page.items.filter(item => !known.has(`${item.source}-${item.id}`))]
      })
      setCursor(page.cursor)
    } catch (requestError) {
      const details = errorDetails(requestError)
      setLoginRequired(details.loginRequired)
      setError(details.loginRequired ? '' : details.message)
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <div className="h-[100dvh] overflow-y-auto bg-neutral-50 text-neutral-900">
      <header className="sticky top-0 z-20 border-b border-neutral-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-5xl items-center gap-3 px-4 sm:px-6">
          <Button asChild variant="ghost" size="icon" className="h-10 w-10 shrink-0">
            <Link
              to={location.search ? `/podcasts${location.search}` : '/podcasts'}
              aria-label="返回 Podcast 发现页"
            >
              <ArrowLeft className="h-5 w-5" />
            </Link>
          </Button>
          <span className="truncate text-base font-semibold">{show?.title || '节目详情'}</span>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-10">
        {loading ? (
          <div className="flex min-h-64 items-center justify-center text-neutral-500">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" /> 正在读取节目
          </div>
        ) : loginRequired ? (
          <LoginRequired />
        ) : error ? (
          <div className="border-l-2 border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </div>
        ) : show ? (
          <>
            <section className="flex flex-col gap-5 border-b border-neutral-200 pb-8 sm:flex-row">
              {show.cover_url ? (
                <img
                  src={show.cover_url}
                  alt=""
                  className="h-36 w-36 shrink-0 rounded-md bg-neutral-100 object-cover sm:h-44 sm:w-44"
                />
              ) : (
                <div className="flex h-36 w-36 shrink-0 items-center justify-center rounded-md bg-neutral-100 sm:h-44 sm:w-44">
                  <Radio className="h-9 w-9 text-neutral-400" />
                </div>
              )}
              <div className="min-w-0 flex-1">
                <SourceBadge source={show.source} />
                <h1 className="mt-3 text-2xl leading-tight font-bold sm:text-3xl">{show.title}</h1>
                {show.author && <p className="mt-2 text-sm text-neutral-600">{show.author}</p>}
                {show.description && (
                  <p className="mt-4 line-clamp-4 text-sm leading-6 text-neutral-600">
                    {show.description}
                  </p>
                )}
                <Button asChild variant="outline" size="sm" className="mt-4">
                  <a href={show.canonical_url} target="_blank" rel="noreferrer">
                    <ExternalLink className="h-4 w-4" /> 打开官方页面
                  </a>
                </Button>
              </div>
            </section>

            <section className="pt-7">
              <div className="flex items-center justify-between gap-4">
                <h2 className="text-xl font-semibold">最新单集</h2>
                <span className="text-xs text-neutral-500">已载入 {episodes.length} 集</span>
              </div>
              <div className="mt-3">
                {episodes.length > 0 ? (
                  episodes.map(item => (
                    <EpisodeCard key={`${item.source}-${item.id}`} item={item} />
                  ))
                ) : (
                  <p className="py-12 text-sm text-neutral-500">暂无公开单集</p>
                )}
              </div>
              {cursor != null && (
                <div className="flex justify-center pt-6">
                  <Button type="button" variant="outline" disabled={loadingMore} onClick={loadMore}>
                    {loadingMore && <Loader2 className="h-4 w-4 animate-spin" />}
                    加载更多
                  </Button>
                </div>
              )}
            </section>
          </>
        ) : null}
      </main>
    </div>
  )
}
