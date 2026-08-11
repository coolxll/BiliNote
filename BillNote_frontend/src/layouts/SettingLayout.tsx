import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip.tsx'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { ArrowLeft, Menu as MenuIcon } from 'lucide-react'
import React, { useState } from 'react'
import logo from '@/assets/icon.svg'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { settingMenuItems } from '@/pages/SettingPage/settingMenuItems'

interface ISettingLayoutProps {
  Menu: React.ReactNode
}
const SettingLayout = ({ Menu }: ISettingLayoutProps) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const location = useLocation()
  const currentItem =
    settingMenuItems.find(item => location.pathname.startsWith(item.path)) || settingMenuItems[0]

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
          <header className="flex h-14 shrink-0 items-center justify-between px-2 md:h-16 md:px-6">
            <div className="hidden items-center gap-2 md:flex">
              <div className="flex h-9 w-9 items-center justify-center overflow-hidden rounded-lg md:h-10 md:w-10">
                <img src={logo} alt="logo" className="h-full w-full object-contain" />
              </div>
              <div className="text-xl font-bold text-gray-800 md:text-2xl">BiliNote</div>
            </div>
            <div className="flex min-w-0 flex-1 items-center gap-1 md:hidden">
              <Link
                to="/"
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-neutral-600 hover:bg-neutral-100"
                aria-label="返回首页"
              >
                <ArrowLeft className="h-5 w-5" />
              </Link>
              <span className="truncate text-base font-semibold">{currentItem.name}</span>
            </div>
            <div className="hidden md:block">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <Link to={'/'}>
                      <ArrowLeft className="text-muted-foreground hover:text-primary cursor-pointer" />
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent>
                    <span>返回首页</span>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-11 w-11 md:hidden"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="打开设置菜单"
            >
              <MenuIcon className="h-5 w-5" />
            </Button>
          </header>

          {/* 表单内容 */}
          <div className="hidden md:block md:flex-1 md:overflow-auto md:p-4">
            {/*<NoteForm />*/}
            {Menu}
          </div>
        </aside>

        {/* 右侧预览区域 */}
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>

      <Dialog open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
        <DialogContent className="!top-auto !bottom-0 !left-0 w-full max-w-none !translate-x-0 !translate-y-0 gap-2 rounded-t-lg rounded-b-none p-4 md:hidden">
          <DialogHeader className="text-left">
            <DialogTitle>设置</DialogTitle>
          </DialogHeader>
          <nav className="flex flex-col gap-1" aria-label="设置导航">
            {settingMenuItems.map(item => {
              const active = location.pathname.startsWith(item.path)
              return (
                <Link
                  key={item.id}
                  to={item.path}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex min-h-12 items-center gap-3 rounded-md px-3 text-sm ${
                    active ? 'bg-primary-light font-medium text-primary' : 'text-neutral-700'
                  }`}
                >
                  <span className="h-5 w-5">{item.icon}</span>
                  <span>{item.name}</span>
                </Link>
              )
            })}
          </nav>
        </DialogContent>
      </Dialog>
    </div>
  )
}
export default SettingLayout


