import {
  Activity,
  BotMessageSquare,
  Captions,
  HardDriveDownload,
  Info,
  Podcast,
} from 'lucide-react'

import type { IMenuProps } from '@/pages/SettingPage/components/menuBar'

export const settingMenuItems: IMenuProps[] = [
  {
    id: 'model',
    name: 'AI 模型设置',
    icon: <BotMessageSquare />,
    path: '/settings/model',
  },
  {
    id: 'transcriber',
    name: '音频转写配置',
    icon: <Captions />,
    path: '/settings/transcriber',
  },
  {
    id: 'download',
    name: '下载配置',
    icon: <HardDriveDownload />,
    path: '/settings/download',
  },
  {
    id: 'xiaoyuzhou',
    name: '小宇宙账号',
    icon: <Podcast />,
    path: '/settings/xiaoyuzhou',
  },
  {
    id: 'monitor',
    name: '部署监控',
    icon: <Activity />,
    path: '/settings/monitor',
  },
  {
    id: 'about',
    name: '关于',
    icon: <Info />,
    path: '/settings/about',
  },
]
