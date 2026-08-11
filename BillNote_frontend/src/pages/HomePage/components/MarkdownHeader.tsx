'use client'

import { useEffect, useState } from 'react'
import { BrainCircuit, Copy, Download, FileText, MessageSquare, MoreHorizontal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger } from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useMediaQuery } from '@/hooks/useMediaQuery'

interface VersionNote {
  ver_id: string
  model_name?: string
  style?: string
  created_at?: string
}

interface NoteHeaderProps {
  currentTask?: {
    markdown: VersionNote[] | string
  }
  isMultiVersion: boolean
  currentVerId: string
  setCurrentVerId: (id: string) => void
  modelName: string
  style: string
  noteStyles: { value: string; label: string }[]
  onCopy: () => void
  onDownload: () => void
  createAt?: string | Date
  setShowTranscribe: (show: boolean) => void
  showChat?: false | 'half' | 'full'
  setShowChat?: (mode: false | 'half' | 'full') => void
  viewMode: 'map' | 'preview'
  setViewMode: (mode: 'map' | 'preview') => void
}

export function MarkdownHeader({
  currentTask,
  isMultiVersion,
  currentVerId,
  setCurrentVerId,
  modelName,
  style,
  noteStyles,
  onCopy,
  onDownload,
  createAt,
  showTranscribe,
  setShowTranscribe,
  showChat,
  setShowChat,
  viewMode,
  setViewMode,
}: NoteHeaderProps) {
  const [copied, setCopied] = useState(false)
  const [mobileActionsOpen, setMobileActionsOpen] = useState(false)
  const isMobile = useMediaQuery('(max-width: 767px)')

  useEffect(() => {
    let timer: NodeJS.Timeout
    if (copied) {
      timer = setTimeout(() => setCopied(false), 2000)
    }
    return () => clearTimeout(timer)
  }, [copied])

  const handleCopy = () => {
    onCopy()
    setCopied(true)
  }

  const styleName = noteStyles.find(v => v.value === style)?.label || style

  const formatDate = (date: string | Date | undefined) => {
    if (!date) return ''
    const d = typeof date === 'string' ? new Date(date) : date
    if (isNaN(d.getTime())) return ''
    return d
      .toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
      .replace(/\//g, '-')
  }

  if (isMobile) {
    return (
      <div className="sticky top-0 z-10 shrink-0 border-b bg-white/95 px-3 py-2 backdrop-blur-sm">
        <div className="flex min-w-0 items-center justify-between gap-2">
          <div className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
            {isMultiVersion && (
              <Select value={currentVerId} onValueChange={setCurrentVerId}>
                <SelectTrigger className="h-10 min-w-0 max-w-[132px] text-xs">
                  <span className="truncate">版本 {currentVerId.slice(-6)}</span>
                </SelectTrigger>
                <SelectContent>
                  {(Array.isArray(currentTask?.markdown) ? currentTask.markdown : []).map(v => (
                    <SelectItem key={v.ver_id} value={v.ver_id}>
                      版本 {v.ver_id.slice(-6)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <div className="flex min-w-0 items-center gap-1 overflow-hidden">
              <Badge variant="secondary" className="max-w-28 truncate bg-pink-100 text-pink-700">
                {modelName}
              </Badge>
              <Badge variant="secondary" className="shrink-0 bg-cyan-100 text-cyan-700">
                {styleName}
              </Badge>
            </div>
          </div>

          <div className="flex shrink-0 items-center">
            <Button
              onClick={() => setViewMode(viewMode === 'preview' ? 'map' : 'preview')}
              variant={viewMode === 'map' ? 'default' : 'ghost'}
              size="icon"
              className="h-11 w-11"
              aria-label={viewMode === 'preview' ? '查看思维导图' : '查看 Markdown'}
            >
              <BrainCircuit className="h-5 w-5" />
            </Button>
            <Button
              onClick={handleCopy}
              variant="ghost"
              size="icon"
              className="h-11 w-11"
              aria-label={copied ? '已复制' : '复制笔记'}
            >
              <Copy className="h-5 w-5" />
            </Button>
            <Button
              onClick={() => setMobileActionsOpen(true)}
              variant="ghost"
              size="icon"
              className="h-11 w-11"
              aria-label="更多笔记操作"
            >
              <MoreHorizontal className="h-5 w-5" />
            </Button>
          </div>
        </div>

        {createAt && (
          <div className="mt-1 truncate px-1 text-[11px] text-neutral-400">
            {formatDate(createAt)}
          </div>
        )}

        <Dialog open={mobileActionsOpen} onOpenChange={setMobileActionsOpen}>
          <DialogContent className="!top-auto !bottom-0 !left-0 w-full max-w-none !translate-x-0 !translate-y-0 gap-2 rounded-t-lg rounded-b-none p-4">
            <DialogHeader className="text-left">
              <DialogTitle>笔记操作</DialogTitle>
            </DialogHeader>
            <Button
              variant="ghost"
              className="h-12 w-full justify-start"
              onClick={() => {
                onDownload()
                setMobileActionsOpen(false)
              }}
            >
              <Download className="h-5 w-5" />
              导出 Markdown
            </Button>
            <Button
              variant={showTranscribe ? 'secondary' : 'ghost'}
              className="h-12 w-full justify-start"
              onClick={() => {
                setShowTranscribe(!showTranscribe)
                if (setShowChat && showChat) setShowChat(false)
                setMobileActionsOpen(false)
              }}
            >
              <FileText className="h-5 w-5" />
              {showTranscribe ? '返回笔记' : '原文参照'}
            </Button>
            {setShowChat && (
              <Button
                variant={showChat ? 'secondary' : 'ghost'}
                className="h-12 w-full justify-start"
                onClick={() => {
                  setShowChat(showChat ? false : 'full')
                  if (!showChat && showTranscribe) setShowTranscribe(false)
                  setMobileActionsOpen(false)
                }}
              >
                <MessageSquare className="h-5 w-5" />
                {showChat ? '返回笔记' : 'AI 问答'}
              </Button>
            )}
          </DialogContent>
        </Dialog>
      </div>
    )
  }

  return (
    <div className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b bg-white/95 px-4 py-2 backdrop-blur-sm">
      {/* 左侧区域：版本 + 标签 + 创建时间 */}
      <div className="flex flex-wrap items-center gap-3">
        {isMultiVersion && (
          <Select value={currentVerId} onValueChange={setCurrentVerId}>
            <SelectTrigger className="h-8 w-[160px] text-sm">
              <div className="flex items-center">
                {(() => {
                  const idx = currentTask?.markdown.findIndex(v => v.ver_id === currentVerId)
                  return idx !== -1 ? `版本（${currentVerId.slice(-6)}）` : ''
                })()}
              </div>
            </SelectTrigger>

            <SelectContent>
              {(currentTask?.markdown || []).map(v => {
                const shortId = v.ver_id.slice(-6)
                return (
                  <SelectItem key={v.ver_id} value={v.ver_id}>
                    {`版本（${shortId}）`}
                  </SelectItem>
                )
              })}
            </SelectContent>
          </Select>
        )}

        <Badge variant="secondary" className="bg-pink-100 text-pink-700 hover:bg-pink-200">
          {modelName}
        </Badge>
        <Badge variant="secondary" className="bg-cyan-100 text-cyan-700 hover:bg-cyan-200">
          {styleName}
        </Badge>

        {createAt && (
          <div className="text-muted-foreground text-sm">创建时间: {formatDate(createAt)}</div>
        )}
      </div>

      {/* 右侧操作按钮 */}
      <div className="flex items-center gap-1">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                onClick={() => {
                  setViewMode(viewMode == 'preview' ? 'map' : 'preview')
                }}
                variant="ghost"
                size="sm"
                className="h-8 px-2"
              >
                <BrainCircuit className="mr-1.5 h-4 w-4" />
                <span className="text-sm">{viewMode == 'preview' ? '思维导图' : 'markdown'}</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>思维导图</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button onClick={handleCopy} variant="ghost" size="sm" className="h-8 px-2">
                <Copy className="mr-1.5 h-4 w-4" />
                <span className="text-sm">{copied ? '已复制' : '复制'}</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>复制内容</TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button onClick={onDownload} variant="ghost" size="sm" className="h-8 px-2">
                <Download className="mr-1.5 h-4 w-4" />
                <span className="text-sm">导出 Markdown</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>下载为 Markdown 文件</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                onClick={() => {
                  setShowTranscribe(!showTranscribe)
                }}
                variant="ghost"
                size="sm"
                className="h-8 px-2"
              >
                {/*<Download className="mr-1.5 h-4 w-4" />*/}
                <span className="text-sm">原文参照</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>原文参照</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        {setShowChat && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  onClick={() => setShowChat(showChat ? false : 'half')}
                  variant={showChat ? 'default' : 'ghost'}
                  size="sm"
                  className="h-8 px-2"
                >
                  <MessageSquare className="mr-1.5 h-4 w-4" />
                  <span className="text-sm">AI 问答</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>基于笔记内容的 AI 问答</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>
    </div>
  )
}
