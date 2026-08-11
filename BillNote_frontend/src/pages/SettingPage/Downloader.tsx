import { Outlet } from 'react-router-dom'
import Options from '@/components/Form/DownloaderForm/Options.tsx'
import ProxyConfig from '@/components/Form/DownloaderForm/ProxyConfig.tsx'
import { useLocation, useNavigate } from 'react-router-dom'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { Button } from '@/components/ui/button'
import { ArrowLeft } from 'lucide-react'
const Downloader = () => {
  const isMobile = useMediaQuery('(max-width: 767px)')
  const location = useLocation()
  const navigate = useNavigate()
  const showingDetail = location.pathname !== '/settings/download' && location.pathname !== '/settings/download/'

  if (isMobile) {
    return (
      <div className="h-full min-h-0 overflow-y-auto bg-white">
        {showingDetail ? (
          <>
            <div className="sticky top-0 z-10 flex h-12 items-center border-b bg-white px-2">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-11 w-11"
                onClick={() => navigate('/settings/download')}
                aria-label="返回下载配置列表"
              >
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <span className="text-sm font-medium">下载配置</span>
            </div>
            <Outlet />
          </>
        ) : (
          <div className="flex flex-col gap-4 p-3">
            <ProxyConfig />
            <Options />
          </div>
        )}
      </div>
    )
  }

  return (
    <div className={'flex h-full bg-white'}>
      <div className={'flex flex-1/5 flex-col gap-3 overflow-y-auto border-r border-neutral-200 p-2'}>
        <ProxyConfig />
        <Options></Options>
      </div>
      <div className={'flex-4/5'}>
        <Outlet />
      </div>
    </div>
  )
}
export default Downloader
