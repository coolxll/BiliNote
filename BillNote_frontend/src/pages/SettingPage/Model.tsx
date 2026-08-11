import Provider from '@/components/Form/modelForm/Provider.tsx'
import { ArrowLeft } from 'lucide-react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useMediaQuery } from '@/hooks/useMediaQuery'

const Model = () => {
  const isMobile = useMediaQuery('(max-width: 767px)')
  const location = useLocation()
  const navigate = useNavigate()
  const showingDetail = location.pathname !== '/settings/model' && location.pathname !== '/settings/model/'

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
                onClick={() => navigate('/settings/model')}
                aria-label="返回模型供应商列表"
              >
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <span className="text-sm font-medium">模型供应商</span>
            </div>
            <Outlet />
          </>
        ) : (
          <div className="p-3">
            <Provider />
          </div>
        )}
      </div>
    )
  }

  return (
    <div className={'flex h-full min-h-0 bg-white'}>
      <div className={'flex-1/5 min-h-0 overflow-y-auto border-r border-neutral-200 p-2'}>
        <Provider></Provider>
      </div>
      <div className={'flex-4/5 min-h-0 overflow-y-auto'}>
        <Outlet />
      </div>
    </div>
  )
}
export default Model
