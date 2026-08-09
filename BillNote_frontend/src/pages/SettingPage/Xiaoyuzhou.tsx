import { useEffect, useState } from 'react'
import { CheckCircle2, Loader2, LogOut, MessageSquareText, Podcast } from 'lucide-react'
import toast from 'react-hot-toast'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  getXiaoyuzhouAuthStatus,
  loginXiaoyuzhou,
  logoutXiaoyuzhou,
  sendXiaoyuzhouCode,
  type XiaoyuzhouAuthStatus,
} from '@/services/xiaoyuzhou'

const EMPTY_STATUS: XiaoyuzhouAuthStatus = {
  authenticated: false,
  uid: '',
  nickname: '',
  updated_at: null,
}

export default function XiaoyuzhouSettings() {
  const [status, setStatus] = useState<XiaoyuzhouAuthStatus>(EMPTY_STATUS)
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [loggingIn, setLoggingIn] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const [countdown, setCountdown] = useState(0)

  useEffect(() => {
    getXiaoyuzhouAuthStatus()
      .then(setStatus)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (countdown <= 0) return
    const timer = window.setTimeout(() => setCountdown(value => value - 1), 1000)
    return () => window.clearTimeout(timer)
  }, [countdown])

  const handleSendCode = async () => {
    if (!phone.trim()) {
      toast.error('请输入手机号')
      return
    }
    setSending(true)
    try {
      await sendXiaoyuzhouCode({ mobile_phone_number: phone.trim(), area_code: '+86' })
      setCountdown(60)
      toast.success('验证码已发送')
    } finally {
      setSending(false)
    }
  }

  const handleLogin = async () => {
    if (!phone.trim() || !code.trim()) {
      toast.error('请输入手机号和验证码')
      return
    }
    setLoggingIn(true)
    try {
      const nextStatus = await loginXiaoyuzhou({
        mobile_phone_number: phone.trim(),
        verify_code: code.trim(),
        area_code: '+86',
      })
      setStatus(nextStatus)
      setCode('')
      toast.success('小宇宙登录成功')
    } finally {
      setLoggingIn(false)
    }
  }

  const handleLogout = async () => {
    setLoggingOut(true)
    try {
      setStatus(await logoutXiaoyuzhou())
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
          <div className="mt-6 space-y-5">
            <div className="space-y-2">
              <label htmlFor="xiaoyuzhou-phone" className="text-sm font-medium">手机号</label>
              <div className="flex gap-2">
                <div className="flex h-9 w-16 shrink-0 items-center justify-center rounded-md border bg-neutral-50 text-sm">
                  +86
                </div>
                <Input
                  id="xiaoyuzhou-phone"
                  inputMode="tel"
                  autoComplete="tel"
                  value={phone}
                  onChange={event => setPhone(event.target.value)}
                  placeholder="请输入手机号"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="xiaoyuzhou-code" className="text-sm font-medium">验证码</label>
              <div className="flex gap-2">
                <Input
                  id="xiaoyuzhou-code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={event => setCode(event.target.value)}
                  placeholder="请输入验证码"
                  maxLength={8}
                />
                <Button
                  type="button"
                  variant="outline"
                  className="w-32 shrink-0"
                  disabled={sending || countdown > 0}
                  onClick={handleSendCode}
                >
                  {sending ? (
                    <Loader2 className="animate-spin" />
                  ) : (
                    <MessageSquareText />
                  )}
                  {countdown > 0 ? `${countdown}s` : '发送验证码'}
                </Button>
              </div>
            </div>

            <Button onClick={handleLogin} disabled={loggingIn}>
              {loggingIn && <Loader2 className="animate-spin" />}
              登录
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
