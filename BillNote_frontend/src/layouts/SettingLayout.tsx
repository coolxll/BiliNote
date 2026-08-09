import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip.tsx'
import { Link, Outlet } from 'react-router-dom'
import { SlidersHorizontal } from 'lucide-react'
import React from 'react'
import logo from '@/assets/icon.svg'

interface ISettingLayoutProps {
  Menu: React.ReactNode
}
const SettingLayout = ({ Menu }: ISettingLayoutProps) => {
  return (
    <div
      className="h-screen min-h-0 w-full"
      style={{
        backgroundColor: 'var(--color-muted)',
      }}
    >
      <div className="flex h-full min-h-0 flex-col md:flex-row">
        {/* 左侧部分：Header + 表单 */}
        <aside className="flex shrink-0 flex-col border-b border-neutral-200 bg-white md:h-full md:w-[300px] md:border-r md:border-b-0">
          {/* Header */}
          <header className="flex h-14 shrink-0 items-center justify-between px-4 md:h-16 md:px-6">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center overflow-hidden rounded-lg md:h-10 md:w-10">
                <img src={logo} alt="logo" className="h-full w-full object-contain" />
              </div>
              <div className="text-xl font-bold text-gray-800 md:text-2xl">BiliNote</div>
            </div>
            <div>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <Link to={'/'}>
                      <SlidersHorizontal className="text-muted-foreground hover:text-primary cursor-pointer" />
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent>
                    <span>返回首页</span>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </header>

          {/* 表单内容 */}
          <div className="overflow-x-auto px-3 pb-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden md:flex-1 md:overflow-auto md:p-4">
            {/*<NoteForm />*/}
            {Menu}
          </div>
        </aside>

        {/* 右侧预览区域 */}
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
export default SettingLayout


