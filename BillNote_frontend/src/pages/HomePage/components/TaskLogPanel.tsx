import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown, ChevronUp, Copy, Terminal } from 'lucide-react'

import { Button } from '@/components/ui/button.tsx'
import type { TaskLogEntry } from '@/store/taskStore'


interface TaskLogPanelProps {
  logs?: TaskLogEntry[]
  defaultOpen?: boolean
}

const levelColors: Record<string, string> = {
  debug: 'text-neutral-400',
  info: 'text-emerald-600',
  warning: 'text-amber-600',
  error: 'text-red-500',
  critical: 'text-red-600',
}

const formatLogTime = (timestamp: string) => {
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return '--:--:--'
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

const TaskLogPanel = ({ logs = [], defaultOpen = true }: TaskLogPanelProps) => {
  const [open, setOpen] = useState(defaultOpen)
  const [copied, setCopied] = useState(false)
  const viewportRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open || !viewportRef.current) return
    viewportRef.current.scrollTop = viewportRef.current.scrollHeight
  }, [logs, open])

  const copyLogs = async () => {
    const text = logs
      .map(log => `${formatLogTime(log.timestamp)} [${log.level.toUpperCase()}] ${log.message}`)
      .join('\n')
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    }
    catch {
      setCopied(false)
    }
  }

  return (
    <div className="w-full max-w-3xl overflow-hidden rounded-md border border-neutral-200 bg-white text-left shadow-sm">
      <div className="flex h-10 items-center justify-between border-b border-neutral-100 px-3">
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-2 text-sm font-medium text-neutral-700"
          onClick={() => setOpen(value => !value)}
          aria-expanded={open}
        >
          <Terminal className="h-4 w-4 shrink-0" />
          <span>处理日志</span>
          <span className="text-xs font-normal text-neutral-400">{logs.length} 条</span>
          {open ? (
            <ChevronUp className="h-4 w-4 text-neutral-400" />
          ) : (
            <ChevronDown className="h-4 w-4 text-neutral-400" />
          )}
        </button>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="h-7 w-7"
          onClick={copyLogs}
          disabled={logs.length === 0}
          title="复制处理日志"
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        </Button>
      </div>
      {open && (
        <div
          ref={viewportRef}
          className="max-h-56 min-h-24 overflow-y-auto bg-neutral-950 px-3 py-2 font-mono text-[11px] leading-5"
        >
          {logs.length === 0 ? (
            <div className="py-6 text-center text-neutral-500">等待后台日志...</div>
          ) : (
            logs.map((log, index) => (
              <div key={`${log.timestamp}-${index}`} className="flex min-w-0 gap-2">
                <span className="shrink-0 text-neutral-500">{formatLogTime(log.timestamp)}</span>
                <span className={`w-14 shrink-0 ${levelColors[log.level] || 'text-neutral-300'}`}>
                  {log.level.toUpperCase()}
                </span>
                <span className="min-w-0 break-words whitespace-pre-wrap text-neutral-200">
                  {log.message}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default TaskLogPanel
