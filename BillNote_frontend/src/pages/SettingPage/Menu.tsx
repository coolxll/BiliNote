import MenuBar from '@/pages/SettingPage/components/menuBar.tsx'
import { settingMenuItems } from '@/pages/SettingPage/settingMenuItems'

const Menu = () => {
  return (
    <div className="flex h-full flex-col">
      <div className="hidden w-full flex-col gap-2 md:flex">
        <div className="text-2xl font-medium">设置</div>
        <div className="text-sm font-light text-gray-800">全局配置与模型设置</div>
      </div>
      <div className="flex min-w-max gap-1 md:mt-6 md:min-w-0 md:flex-1 md:flex-col">
        {settingMenuItems &&
          settingMenuItems.map(item => {
            return <MenuBar key={item.id} menuItem={item} />
          })}
      </div>
    </div>
  )
}
export default Menu
