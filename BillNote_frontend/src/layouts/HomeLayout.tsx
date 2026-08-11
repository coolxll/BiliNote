import React, { FC, useRef, useState } from 'react'
import {
  BookOpenText,
  FilePenLine,
  History as HistoryIcon,
  PanelLeftClose,
  PanelLeftOpen,
  Podcast,
  SlidersHorizontal,
} from 'lucide-react'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip.tsx'

import { Link } from 'react-router-dom'
import { ResizablePanel, ResizablePanelGroup, ResizableHandle } from '@/components/ui/resizable'
import { ScrollArea } from "@/components/ui/scroll-area.tsx"
import type { ImperativePanelHandle } from 'react-resizable-panels'
import logo from '@/assets/icon.svg'
import { useMediaQuery } from '@/hooks/useMediaQuery'

export type MobileHomeView = 'create' | 'history' | 'note'

interface IProps {
  NoteForm: React.ReactNode
  Preview: React.ReactNode
  History: React.ReactNode
  mobileView: MobileHomeView
  onMobileViewChange: (view: MobileHomeView) => void
}

const mobileNavItems: Array<{
  id: MobileHomeView
  label: string
  icon: typeof FilePenLine
}> = [
  { id: 'create', label: '创建', icon: FilePenLine },
  { id: 'history', label: '历史', icon: HistoryIcon },
  { id: 'note', label: '笔记', icon: BookOpenText },
]

const HomeLayout: FC<IProps> = ({
  NoteForm,
  Preview,
  History,
  mobileView,
  onMobileViewChange,
}) => {
  const [, setShowSettings] = useState(false)
  const [isLeftCollapsed, setIsLeftCollapsed] = useState(false)
  const [isMiddleCollapsed, setIsMiddleCollapsed] = useState(false)
  const leftPanelRef = useRef<ImperativePanelHandle>(null)
  const middlePanelRef = useRef<ImperativePanelHandle>(null)
  const isMobile = useMediaQuery('(max-width: 767px)')

  if (isMobile) {
    const content = {
      create: NoteForm,
      history: History,
      note: Preview,
    }[mobileView]

    return (
      <div className="flex h-[100dvh] min-h-0 flex-col overflow-hidden bg-white">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-neutral-200 px-4">
          <div className="flex min-w-0 items-center gap-2">
            <img src={logo} alt="BiliNote" className="h-8 w-8 shrink-0 object-contain" />
            <span className="truncate text-lg font-bold text-neutral-800">BiliNote</span>
          </div>
          <div className="flex items-center gap-1">
            <Link
              to="/podcasts"
              className="flex h-11 w-11 items-center justify-center rounded-md text-neutral-600 hover:bg-neutral-100"
              aria-label="发现 Podcast"
            >
              <Podcast className="h-5 w-5" />
            </Link>
            <Link
              to="/settings"
              className="flex h-11 w-11 items-center justify-center rounded-md text-neutral-600 hover:bg-neutral-100"
              aria-label="打开设置"
            >
              <SlidersHorizontal className="h-5 w-5" />
            </Link>
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-hidden">{content}</main>

        <nav
          className="grid shrink-0 grid-cols-3 border-t border-neutral-200 bg-white"
          style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
          aria-label="首页导航"
        >
          {mobileNavItems.map(item => {
            const Icon = item.icon
            const active = item.id === mobileView
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onMobileViewChange(item.id)}
                className={`flex min-h-14 flex-col items-center justify-center gap-1 text-xs transition-colors ${
                  active ? 'text-primary' : 'text-neutral-500'
                }`}
                aria-current={active ? 'page' : undefined}
              >
                <Icon className="h-5 w-5" />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <ResizablePanelGroup direction="horizontal" className="h-full w-full">
        {/* 左边表单 */}
        <ResizablePanel
          ref={leftPanelRef}
          defaultSize={23}
          minSize={10}
          maxSize={35}
          collapsible
          collapsedSize={0}
          onCollapse={() => setIsLeftCollapsed(true)}
          onExpand={() => setIsLeftCollapsed(false)}
        >
          <aside className="flex h-full flex-col overflow-hidden border-r border-neutral-200 bg-white">
            <header className="flex h-16 items-center justify-between px-6">
              <div className="flex items-center gap-2">
                <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-2xl">
                  <img src={logo} alt="logo" className="h-full w-full object-contain" />
                </div>
                <div className="text-2xl font-bold text-gray-800">BiliNote</div>
              </div>
              <div className="flex items-center gap-1">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Link
                        to="/podcasts"
                        className="text-muted-foreground hover:text-primary rounded p-1 hover:bg-neutral-100"
                        aria-label="发现 Podcast"
                      >
                        <Podcast className="h-5 w-5" />
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent>
                      <span>发现 Podcast</span>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() => leftPanelRef.current?.collapse()}
                        className="text-muted-foreground hover:text-primary cursor-pointer rounded p-1 hover:bg-neutral-100"
                      >
                        <PanelLeftClose className="h-5 w-5" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <span>收起工作区</span>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger onClick={() => setShowSettings(true)}>
                      <Link to={'/settings'}>
                        <SlidersHorizontal className="text-muted-foreground hover:text-primary cursor-pointer" />
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent>
                      <span>全局配置</span>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
            </header>
            <ScrollArea className="flex-1 overflow-auto">
              <div className="p-4">{NoteForm}</div>
            </ScrollArea>
          </aside>
        </ResizablePanel>

        <ResizableHandle />

        {/* 左面板折叠时的展开按钮 */}
        {isLeftCollapsed && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => leftPanelRef.current?.expand()}
                  className="flex h-full w-8 shrink-0 items-center justify-center border-r border-neutral-200 bg-white hover:bg-neutral-50"
                >
                  <PanelLeftOpen className="h-4 w-4 text-muted-foreground" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">
                <span>展开工作区</span>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}

        {/* 中间历史 */}
        <ResizablePanel
          ref={middlePanelRef}
          defaultSize={16}
          minSize={10}
          maxSize={30}
          collapsible
          collapsedSize={0}
          onCollapse={() => setIsMiddleCollapsed(true)}
          onExpand={() => setIsMiddleCollapsed(false)}
        >
          <aside className="flex h-full flex-col overflow-hidden border-r border-neutral-200 bg-white">
            <header className="flex h-10 shrink-0 items-center justify-between border-b border-neutral-100 px-3">
              <span className="text-sm font-medium text-gray-600">生成历史</span>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      onClick={() => middlePanelRef.current?.collapse()}
                      className="text-muted-foreground hover:text-primary cursor-pointer rounded p-1 hover:bg-neutral-100"
                    >
                      <PanelLeftClose className="h-4 w-4" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <span>收起历史</span>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </header>
            <ScrollArea className="flex-1 overflow-auto">
              <div>{History}</div>
            </ScrollArea>
          </aside>
        </ResizablePanel>

        <ResizableHandle />

        {/* 中间面板折叠时的展开按钮 */}
        {isMiddleCollapsed && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => middlePanelRef.current?.expand()}
                  className="flex h-full w-8 shrink-0 items-center justify-center border-r border-neutral-200 bg-white hover:bg-neutral-50"
                >
                  <HistoryIcon className="h-4 w-4 text-muted-foreground" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">
                <span>展开历史</span>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}

        {/* 右边预览 */}
        <ResizablePanel defaultSize={61} minSize={30}>
          <main className="flex h-full flex-col overflow-hidden bg-white p-6">{Preview}</main>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}

export default HomeLayout
