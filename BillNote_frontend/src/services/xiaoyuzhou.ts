import request from '@/utils/request'

export interface XiaoyuzhouAuthStatus {
  authenticated: boolean
  uid: string
  nickname: string
  updated_at: number | null
}

export interface XiaoyuzhouEpisodeSearchItem {
  eid: string
  pid: string
  title: string
  podcast_title: string
  duration: number
  pub_date: string
  cover_url: string
  description: string
  is_private: boolean
  episode_url: string
}

export interface XiaoyuzhouSearchResult {
  items: XiaoyuzhouEpisodeSearchItem[]
  load_more_key: Record<string, unknown> | null
}

export interface XiaoyuzhouSendCodeResult {
  message: string
  request_id: string
}

export interface XiaoyuzhouQrSession {
  id: string
  url: string
  status: string
  expires_in: number
}

export interface XiaoyuzhouQrPollResult {
  status: string
  authenticated: boolean
}

export const getXiaoyuzhouAuthStatus = async (): Promise<XiaoyuzhouAuthStatus> => {
  return await request.get('/xiaoyuzhou/auth/status', { suppressToast: true })
}

export const sendXiaoyuzhouCode = async (data: {
  mobile_phone_number: string
  area_code?: string
}): Promise<XiaoyuzhouSendCodeResult> => {
  return await request.post('/xiaoyuzhou/auth/send-code', data)
}

export const createXiaoyuzhouQrSession = async (): Promise<XiaoyuzhouQrSession> => {
  return await request.post('/xiaoyuzhou/auth/qrcode/create')
}

export const pollXiaoyuzhouQrSession = async (
  id: string,
): Promise<XiaoyuzhouQrPollResult> => {
  return await request.post('/xiaoyuzhou/auth/qrcode/poll', { id }, { suppressToast: true })
}

export const loginXiaoyuzhou = async (data: {
  mobile_phone_number: string
  verify_code: string
  area_code?: string
}): Promise<XiaoyuzhouAuthStatus> => {
  return await request.post('/xiaoyuzhou/auth/login', data)
}

export const logoutXiaoyuzhou = async (): Promise<XiaoyuzhouAuthStatus> => {
  return await request.post('/xiaoyuzhou/auth/logout')
}

export const searchXiaoyuzhouEpisodes = async (data: {
  keyword: string
  load_more_key?: Record<string, unknown> | null
  pid?: string
}): Promise<XiaoyuzhouSearchResult> => {
  return await request.post('/xiaoyuzhou/search', data, { suppressToast: true })
}
