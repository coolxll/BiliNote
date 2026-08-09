import { FormEvent, useEffect, useState } from 'react'
import { CalendarDays, Clock3, Loader2, Search } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  getXiaoyuzhouAuthStatus,
  searchXiaoyuzhouEpisodes,
  type XiaoyuzhouEpisodeSearchItem,
} from '@/services/xiaoyuzhou'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSelect: (episode: XiaoyuzhouEpisodeSearchItem) => void
}

const formatDuration = (seconds: number) => {
  if (!seconds) return '--:--'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = seconds % 60
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
    : `${minutes}:${String(rest).padStart(2, '0')}`
}

const formatDate = (value: string) => {
  if (!value) return '日期未知'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '日期未知' : date.toLocaleDateString('zh-CN')
}

export default function XiaoyuzhouSearchDialog({ open, onOpenChange, onSelect }: Props) {
  const navigate = useNavigate()
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)
  const [query, setQuery] = useState('')
  const [items, setItems] = useState<XiaoyuzhouEpisodeSearchItem[]>([])
  const [loadMoreKey, setLoadMoreKey] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [searched, setSearched] = useState(false)

  useEffect(() => {
    if (!open) return
    setAuthenticated(null)
    getXiaoyuzhouAuthStatus()
      .then(status => setAuthenticated(status.authenticated))
      .catch(() => setAuthenticated(false))
  }, [open])

  const runSearch = async (append = false) => {
    const keyword = query.trim()
    if (!keyword) return
    if (append) {
      setLoadingMore(true)
    } else {
      setLoading(true)
    }
    try {
      const result = await searchXiaoyuzhouEpisodes({
        keyword,
        load_more_key: append ? loadMoreKey : null,
      })
      setItems(current => append ? [...current, ...result.items] : result.items)
      setLoadMoreKey(result.load_more_key)
      setSearched(true)
    } catch (error: unknown) {
      const apiError = error as { msg?: string; data?: { reason?: string } }
      if (apiError.data?.reason === 'xiaoyuzhou_login_required') {
        setAuthenticated(false)
      }
      toast.error(apiError.msg || '搜索失败，请稍后重试')
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    void runSearch(false)
  }

  const goToSettings = () => {
    onOpenChange(false)
    navigate('/settings/xiaoyuzhou')
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[min(720px,85vh)] max-w-3xl grid-rows-none flex-col gap-0 overflow-hidden p-0">
        <DialogHeader className="border-b px-6 py-5">
          <DialogTitle>搜索小宇宙单集</DialogTitle>
          <DialogDescription>选择单集后将自动填入链接</DialogDescription>
        </DialogHeader>

        {authenticated === null ? (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="text-muted-foreground h-5 w-5 animate-spin" />
          </div>
        ) : !authenticated ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
            <div className="text-sm font-medium">需要登录小宇宙账号</div>
            <Button onClick={goToSettings}>前往登录</Button>
          </div>
        ) : (
          <>
            <form onSubmit={handleSubmit} className="flex gap-2 border-b px-6 py-4">
              <Input
                autoFocus
                value={query}
                onChange={event => setQuery(event.target.value)}
                placeholder="搜索单集标题或内容"
              />
              <Button type="submit" disabled={loading || !query.trim()}>
                {loading ? <Loader2 className="animate-spin" /> : <Search />}
                搜索
              </Button>
            </form>

            <ScrollArea className="min-h-0 flex-1">
              <div className="px-6 py-3">
                {!searched && !loading && (
                  <div className="text-muted-foreground py-16 text-center text-sm">输入关键词开始搜索</div>
                )}
                {searched && items.length === 0 && !loading && (
                  <div className="text-muted-foreground py-16 text-center text-sm">没有找到相关单集</div>
                )}
                <div className="divide-y divide-neutral-200">
                  {items.map(item => (
                    <button
                      key={item.eid}
                      type="button"
                      disabled={item.is_private}
                      onClick={() => {
                        onSelect(item)
                        onOpenChange(false)
                      }}
                      className="flex w-full gap-4 py-4 text-left transition-colors hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <img
                        src={item.cover_url || '/placeholder.png'}
                        alt=""
                        className="h-20 w-20 shrink-0 rounded-md border object-cover"
                        onError={event => {
                          event.currentTarget.src = '/placeholder.png'
                        }}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="line-clamp-2 text-sm font-medium leading-5">{item.title}</div>
                        <div className="text-muted-foreground mt-1 truncate text-xs">
                          {item.podcast_title || '未知节目'}
                        </div>
                        <div className="text-muted-foreground mt-3 flex flex-wrap items-center gap-3 text-xs">
                          <span className="inline-flex items-center gap-1">
                            <Clock3 className="h-3.5 w-3.5" />{formatDuration(item.duration)}
                          </span>
                          <span className="inline-flex items-center gap-1">
                            <CalendarDays className="h-3.5 w-3.5" />{formatDate(item.pub_date)}
                          </span>
                          {item.is_private && <span className="text-amber-700">付费或私有</span>}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
                {loadMoreKey && items.length > 0 && (
                  <div className="flex justify-center py-5">
                    <Button variant="outline" onClick={() => void runSearch(true)} disabled={loadingMore}>
                      {loadingMore && <Loader2 className="animate-spin" />}
                      加载更多
                    </Button>
                  </div>
                )}
              </div>
            </ScrollArea>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
