import { FormEvent, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Headphones, Search, SlidersHorizontal } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import logo from '@/assets/icon.svg'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  discoverPodcasts,
  searchPodcasts,
  type PodcastCatalogItem,
  type PodcastEntity,
  type PodcastMarket,
  type PodcastSource,
  type XiaoyuzhouDiscoverMode,
} from '@/services/podcasts'
import { EpisodeCard, LoadingRows, LoginRequired, ShowCard } from './components'

type SectionState = {
  items: PodcastCatalogItem[]
  loading: boolean
  loginRequired: boolean
  error: string
}

const emptySection = (): SectionState => ({
  items: [],
  loading: true,
  loginRequired: false,
  error: '',
})

const sourceOptions: Array<{ value: 'all' | PodcastSource; label: string }> = [
  { value: 'all', label: '综合' },
  { value: 'apple_podcasts', label: 'Apple' },
  { value: 'xiaoyuzhou', label: '小宇宙' },
]

const xiaoyuzhouModes: Array<{ value: XiaoyuzhouDiscoverMode; label: string }> = [
  { value: 'personalized', label: '为你推荐' },
  { value: 'hot', label: '24 小时热门' },
  { value: 'rising', label: '飙升' },
  { value: 'new', label: '新星' },
]

function errorDetails(error: unknown) {
  const value = error as { msg?: string; data?: { reason?: string } }
  return {
    loginRequired: value?.data?.reason === 'xiaoyuzhou_login_required',
    message: value?.msg || '该来源暂时不可用',
  }
}

function Section({ title, state }: { title: string; state: SectionState }) {
  return (
    <section className="space-y-3">
      <div className="flex items-end justify-between gap-4">
        <h2 className="text-lg font-semibold text-neutral-900">{title}</h2>
        {!state.loading && !state.error && (
          <span className="text-xs text-neutral-500">{state.items.length} 项</span>
        )}
      </div>
      {state.loading ? (
        <LoadingRows />
      ) : state.loginRequired ? (
        <LoginRequired />
      ) : state.error ? (
        <div className="border-l-2 border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
          {state.error}
        </div>
      ) : state.items.length === 0 ? (
        <p className="py-8 text-sm text-neutral-500">暂无内容</p>
      ) : state.items[0]?.kind === 'show' ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {state.items.map(item => (
            <ShowCard key={`${item.source}-${item.id}`} item={item} />
          ))}
        </div>
      ) : (
        <div>
          {state.items.map(item => (
            <EpisodeCard key={`${item.source}-${item.id}`} item={item} />
          ))}
        </div>
      )}
    </section>
  )
}

export default function PodcastsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const sourceParam = searchParams.get('source')
  const activeSource: 'all' | PodcastSource =
    sourceParam === 'apple_podcasts' || sourceParam === 'xiaoyuzhou' ? sourceParam : 'all'
  const entityParam = searchParams.get('entity')
  const defaultEntity: PodcastEntity = activeSource === 'xiaoyuzhou' ? 'episode' : 'show'
  const entity: PodcastEntity =
    entityParam === 'show' || entityParam === 'episode' ? entityParam : defaultEntity
  const queryParam = searchParams.get('query') || ''
  const modeParam = searchParams.get('mode')
  const xiaoyuzhouMode: XiaoyuzhouDiscoverMode = xiaoyuzhouModes.some(
    item => item.value === modeParam
  )
    ? (modeParam as XiaoyuzhouDiscoverMode)
    : 'personalized'
  const storedMarket = localStorage.getItem('bilinote-podcast-market')
  const marketParam = searchParams.get('market')
  const market: PodcastMarket =
    marketParam === 'cn' || marketParam === 'us' ? marketParam : storedMarket === 'us' ? 'us' : 'cn'
  const [searchInput, setSearchInput] = useState(queryParam)
  const [combined, setCombined] = useState<Record<string, SectionState>>({
    apple: emptySection(),
    personalized: emptySection(),
    hot: emptySection(),
  })
  const [sourceState, setSourceState] = useState<SectionState>(emptySection())

  const setParams = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams)
    Object.entries(updates).forEach(([key, value]) => {
      if (value) next.set(key, value)
      else next.delete(key)
    })
    setSearchParams(next)
  }

  useEffect(() => {
    setSearchInput(queryParam)
  }, [queryParam])

  useEffect(() => {
    if (activeSource !== 'all') return
    let active = true
    setCombined({ apple: emptySection(), personalized: emptySection(), hot: emptySection() })
    const requests = {
      apple: discoverPodcasts({
        source: 'apple_podcasts',
        mode: 'top',
        entity: 'show',
        market,
        limit: 9,
      }),
      personalized: discoverPodcasts({
        source: 'xiaoyuzhou',
        mode: 'personalized',
        entity: 'episode',
        limit: 6,
      }),
      hot: discoverPodcasts({
        source: 'xiaoyuzhou',
        mode: 'hot',
        entity: 'episode',
        limit: 6,
      }),
    }
    Object.entries(requests).forEach(([key, request]) => {
      request
        .then(page => {
          if (!active) return
          setCombined(current => ({
            ...current,
            [key]: { items: page.items, loading: false, loginRequired: false, error: '' },
          }))
        })
        .catch(error => {
          if (!active) return
          const details = errorDetails(error)
          setCombined(current => ({
            ...current,
            [key]: {
              items: [],
              loading: false,
              loginRequired: details.loginRequired,
              error: details.loginRequired ? '' : details.message,
            },
          }))
        })
    })
    return () => {
      active = false
    }
  }, [activeSource, market])

  const sourceRequest = useMemo(() => {
    if (activeSource === 'all') return null
    if (queryParam) {
      return () =>
        searchPodcasts({ source: activeSource, entity, query: queryParam, market, limit: 30 })
    }
    if (activeSource === 'apple_podcasts') {
      return () =>
        discoverPodcasts({
          source: activeSource,
          mode: 'top',
          entity,
          market,
          limit: 30,
        })
    }
    return () =>
      discoverPodcasts({
        source: activeSource,
        mode: xiaoyuzhouMode,
        entity,
        limit: 30,
      })
  }, [activeSource, entity, market, queryParam, xiaoyuzhouMode])

  useEffect(() => {
    if (!sourceRequest) return
    let active = true
    setSourceState(emptySection())
    sourceRequest()
      .then(page => {
        if (!active) return
        setSourceState({ items: page.items, loading: false, loginRequired: false, error: '' })
      })
      .catch(error => {
        if (!active) return
        const details = errorDetails(error)
        setSourceState({
          items: [],
          loading: false,
          loginRequired: details.loginRequired,
          error: details.loginRequired ? '' : details.message,
        })
      })
    return () => {
      active = false
    }
  }, [sourceRequest])

  const handleSearch = (event: FormEvent) => {
    event.preventDefault()
    setParams({ query: searchInput.trim() || null, entity })
  }

  const updateMarket = (value: PodcastMarket) => {
    localStorage.setItem('bilinote-podcast-market', value)
    setParams({ market: value })
  }

  const selectSource = (value: 'all' | PodcastSource) => {
    setSearchInput('')
    setParams({
      source: value === 'all' ? null : value,
      entity: value === 'all' ? null : value === 'xiaoyuzhou' ? 'episode' : 'show',
      query: null,
      mode: null,
    })
  }

  const selectEntity = (value: PodcastEntity) => {
    setSearchInput('')
    setParams({ entity: value, query: null })
  }

  const selectXiaoyuzhouMode = (value: XiaoyuzhouDiscoverMode) => {
    setSearchInput('')
    setParams({ mode: value, query: null })
  }

  const title = queryParam
    ? `搜索${entity === 'show' ? '节目' : '单集'}“${queryParam}”`
    : activeSource === 'apple_podcasts'
      ? entity === 'show'
        ? '热门节目'
        : '热门单集'
      : `${xiaoyuzhouModes.find(item => item.value === xiaoyuzhouMode)?.label || '为你推荐'}${entity === 'show' ? '节目' : ''}`

  return (
    <div className="h-[100dvh] overflow-y-auto bg-neutral-50 text-neutral-900">
      <header className="sticky top-0 z-20 border-b border-neutral-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6">
          <Button asChild variant="ghost" size="icon" className="h-10 w-10 shrink-0">
            <Link to="/" aria-label="返回首页">
              <ArrowLeft className="h-5 w-5" />
            </Link>
          </Button>
          <img src={logo} alt="" className="h-8 w-8" />
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg font-semibold">Podcast 发现</h1>
          </div>
          <Button asChild variant="ghost" size="icon" className="h-10 w-10">
            <Link to="/settings" aria-label="打开设置">
              <SlidersHorizontal className="h-5 w-5" />
            </Link>
          </Button>
        </div>
        <div className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4 pb-3 sm:px-6">
          {sourceOptions.map(option => (
            <button
              key={option.value}
              type="button"
              onClick={() => selectSource(option.value)}
              className={`h-9 shrink-0 px-4 text-sm font-medium transition-colors ${
                activeSource === option.value
                  ? 'bg-neutral-900 text-white'
                  : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-10 px-4 py-6 sm:px-6 sm:py-8">
        {activeSource === 'all' ? (
          <>
            <Section title="Apple 热门节目" state={combined.apple} />
            <Section title="小宇宙 · 为你推荐" state={combined.personalized} />
            <Section title="小宇宙 · 24 小时热门" state={combined.hot} />
          </>
        ) : (
          <>
            <div className="space-y-4 border-b border-neutral-200 pb-5">
              <div className="space-y-3">
                {activeSource === 'apple_podcasts' ? (
                  <div className="flex items-center gap-1 bg-neutral-100 p-1">
                    {(['cn', 'us'] as PodcastMarket[]).map(value => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => updateMarket(value)}
                        className={`h-8 px-3 text-sm ${market === value ? 'bg-white font-medium shadow-sm' : 'text-neutral-600'}`}
                      >
                        {value === 'cn' ? '中国区' : '美国区'}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="flex max-w-full gap-1 overflow-x-auto">
                    {xiaoyuzhouModes.map(item => (
                      <button
                        key={item.value}
                        type="button"
                        onClick={() => selectXiaoyuzhouMode(item.value)}
                        className={`h-9 shrink-0 px-3 text-sm ${
                          xiaoyuzhouMode === item.value && !queryParam
                            ? 'bg-neutral-900 text-white'
                            : 'bg-neutral-100 text-neutral-600'
                        }`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex w-fit shrink-0 bg-neutral-100 p-1" aria-label="内容类型">
                  {(['show', 'episode'] as PodcastEntity[]).map(value => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => selectEntity(value)}
                      className={`h-8 px-4 text-sm ${entity === value ? 'bg-white font-medium shadow-sm' : 'text-neutral-600'}`}
                    >
                      {value === 'show' ? '节目' : '单集'}
                    </button>
                  ))}
                </div>
                <form onSubmit={handleSearch} className="flex w-full gap-2 sm:w-auto">
                  <Input
                    value={searchInput}
                    onChange={event => setSearchInput(event.target.value)}
                    placeholder={`搜索${entity === 'show' ? '节目' : '单集'}`}
                    className="h-10 min-w-0 lg:w-64"
                  />
                  <Button
                    type="submit"
                    size="icon"
                    className="h-10 w-10 shrink-0"
                    aria-label="搜索"
                  >
                    <Search className="h-4 w-4" />
                  </Button>
                </form>
              </div>
            </div>
            <Section title={title} state={sourceState} />
          </>
        )}
        <div className="flex items-center justify-center gap-2 pb-5 text-xs text-neutral-400">
          <Headphones className="h-4 w-4" />
          选择公开单集后返回创建页确认模型与笔记选项
        </div>
      </main>
    </div>
  )
}
