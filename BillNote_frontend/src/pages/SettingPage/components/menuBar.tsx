import styles from './index.module.css'
import { JSX } from 'react'
import { Link, useLocation } from 'react-router-dom'

export interface IMenuProps {
  id: string
  name: string
  icon: JSX.Element
  path: string
}

const MenuBar = ({ menuItem }: { menuItem: IMenuProps }): JSX.Element => {
  const location = useLocation()
  const isActive =
    location.pathname.startsWith(menuItem.path + '/') || location.pathname === menuItem.path

  return (
    <Link to={menuItem.path} className="w-auto shrink-0 md:w-full">
      <div
        className={
          styles.menuBar +
          ' flex h-10 w-auto items-center gap-1 whitespace-nowrap rounded px-3 md:h-12 md:w-full md:px-2' +
          (isActive ? ' bg-[#F0F0F0] font-semibold text-blue-600' : '')
        }
      >
        <div className="h-5 w-5 md:h-6 md:w-6">{menuItem.icon}</div>
        <div className="text-sm md:text-[16px]">{menuItem.name}</div>
      </div>
    </Link>
  )
}

export default MenuBar
