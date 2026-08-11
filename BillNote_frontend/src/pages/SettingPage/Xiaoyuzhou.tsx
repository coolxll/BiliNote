import { useCallback, useEffect, useState } from 'react'
import { QRCode } from 'antd'
import { CheckCircle2, Loader2, LogOut, Podcast, RefreshCw, ScanLine } from 'lucide-react'
import toast from 'react-hot-toast'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  getXiaoyuzhouAuthStatus,
  createXiaoyuzhouQrSession,
  logoutXiaoyuzhou,
  pollXiaoyuzhouQrSession,
  type XiaoyuzhouAuthStatus,
  type XiaoyuzhouQrSession,
} from '@/services/xiaoyuzhou'

const EMPTY_STATUS: XiaoyuzhouAuthStatus = {
  authenticated: false,
  uid: '',
  nickname: '',
  updated_at: null,
}

export default function XiaoyuzhouSettings() {
  const [status, setStatus] = useState<XiaoyuzhouAuthStatus>(EMPTY_STATUS)
  const [loading, setLoading] = useState(true)
  const [loggingOut, setLoggingOut] = useState(false)
  const [qrSession, setQrSession] = useState<XiaoyuzhouQrSession | null>(null)
  const [qrStatus, setQrStatus] = useState('')
  const [qrLoading, setQrLoading] = useState(false)
  const [qrError, setQrError] = useState('')

  useEffect(() => {
    getXiaoyuzhouAuthStatus()
      .then(setStatus)
      .finally(() => setLoading(false))
  }, [])

  const createQrSession = useCallback(async () => {
    setQrLoading(true)
    setQrError('')
    try {
      const nextSession = await createXiaoyuzhouQrSession()
      setQrSession(nextSession)
      setQrStatus(nextSession.status)
    } catch {
      setQrSession(null)
      setQrError('二维码创建失败，请稍后重试')
    } finally {
      setQrLoading(false)
    }
  }, [])

  useEffect(() => {
    if (loading || status.authenticated || qrSession || qrLoading) return
    void createQrSession()
  }, [createQrSession, loading, qrLoading, qrSession, status.authenticated])

  useEffect(() => {
    if (!qrSession || status.authenticated) return
    let cancelled = false
    let polling = false

    const poll = async () => {
      if (polling) return
      polling = true
      try {
        const result = await pollXiaoyuzhouQrSession(qrSession.id)
        if (cancelled) return
        setQrStatus(result.status)
        if (result.authenticated) {
          setStatus(await getXiaoyuzhouAuthStatus())
          toast.success('小宇宙登录成功')
          return
        }
        if (['EXPIRED', 'USED'].includes(result.status)) {
          setQrError('二维码已失效，请刷新后重试')
        }
      } catch {
        if (!cancelled) setQrError('登录状态查询失败，请刷新二维码')
      } finally {
        polling = false
      }
    }

    void poll()
    const timer = window.setInterval(poll, 2000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [qrSession, status.authenticated])

  const handleLogout = async () => {
    setLoggingOut(true)
    try {
      setStatus(await logoutXiaoyuzhou())
      setQrSession(null)
      setQrStatus('')
      toast.success('已退出小宇宙')
    } finally {
      setLoggingOut(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto bg-white">
      <div className="mx-auto w-full max-w-2xl px-4 py-6 sm:px-8 sm:py-8">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-[#fff0ec] text-[#f36c4f]">
            <Podcast className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-semibold">小宇宙账号</h1>
            <p className="text-muted-foreground mt-1 text-sm">用于搜索小宇宙单集</p>
          </div>
        </div>

        <div className="border-y border-neutral-200 py-5">
          <div className="flex min-h-9 items-center justify-between gap-4">
            <div className="min-w-0">
              <div className="text-sm font-medium">登录状态</div>
              <div className="text-muted-foreground mt-1 truncate text-sm">
                {loading
                  ? '正在读取...'
                  : status.authenticated
                    ? status.nickname || status.uid || '已登录'
                    : '未登录'}
              </div>
            </div>
            {status.authenticated ? (
              <Badge className="bg-emerald-600">
                <CheckCircle2 />已登录
              </Badge>
            ) : (
              <Badge variant="outline">未登录</Badge>
            )}
          </div>
        </div>

        {status.authenticated ? (
          <div className="mt-6">
            <Button variant="outline" onClick={handleLogout} disabled={loggingOut}>
              {loggingOut ? <Loader2 className="animate-spin" /> : <LogOut />}
              退出登录
            </Button>
          </div>
        ) : (
          <div className="mt-6 flex flex-col items-center gap-4 text-center">
            <div className="flex h-[min(14rem,calc(100vw-4rem))] w-[min(14rem,calc(100vw-4rem))] items-center justify-center rounded-md border border-neutral-200 bg-white p-3">
              {qrSession ? (
                <QRCode value={qrSession.url} size={200} bordered={false} />
              ) : qrLoading ? (
                <Loader2 className="text-muted-foreground h-7 w-7 animate-spin" />
              ) : (
                <ScanLine className="text-muted-foreground h-8 w-8" />
              )}
            </div>
            <div>
              <div className="text-sm font-medium">
                {qrStatus === 'SCANNED' ? '已扫码，请在小宇宙 App 中确认' : '使用小宇宙 App 扫码登录'}
              </div>
              <div className="text-muted-foreground mt-1 text-sm">
                二维码约 3 分钟内有效，确认后页面会自动完成登录。
              </div>
              {qrError && <div className="mt-2 text-sm text-red-600">{qrError}</div>}
            </div>
            <Button variant="outline" onClick={createQrSession} disabled={qrLoading}>
              {qrLoading ? <Loader2 className="animate-spin" /> : <RefreshCw />}
              刷新二维码
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
