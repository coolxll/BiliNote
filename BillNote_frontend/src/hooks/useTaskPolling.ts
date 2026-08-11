import { useEffect, useRef } from 'react'
import { hasUsableMarkdown, useTaskStore } from '@/store/taskStore'
import { get_task_status } from '@/services/note.ts'
import toast from 'react-hot-toast'

export const useTaskPolling = (interval = 3000) => {
  const tasks = useTaskStore(state => state.tasks)
  const updateTaskContent = useTaskStore(state => state.updateTaskContent)

  const tasksRef = useRef(tasks)
  const verifiedFailedTasksRef = useRef(new Set<string>())

  // 每次 tasks 更新，把最新的 tasks 同步进去
  useEffect(() => {
    tasksRef.current = tasks
  }, [tasks])

  useEffect(() => {
    const timer = setInterval(async () => {
      const pendingTasks = tasksRef.current.filter(task => {
        if (task.status === 'SUCCESS') return false
        if (task.status !== 'FAILED') return true
        return !verifiedFailedTasksRef.current.has(task.id)
      })

      // 无活跃任务时跳过轮询
      if (pendingTasks.length === 0) return

      for (const task of pendingTasks) {
        try {
          const res = await get_task_status(task.id)
          const { status } = res
          const logs = Array.isArray(res.logs) ? res.logs : []
          const latestReceivedLog = logs[logs.length - 1]?.timestamp
          const latestStoredLog = task.logs?.[task.logs.length - 1]?.timestamp
          const logsChanged =
            logs.length !== (task.logs?.length || 0) || latestReceivedLog !== latestStoredLog
          const polledAt = new Date().toISOString()
          const statusData = {
            status,
            statusMessage: res.message || undefined,
            statusUpdatedAt: res.updated_at || undefined,
            lastPolledAt: polledAt,
            logs,
          }
          const hasExistingResult = hasUsableMarkdown(task.markdown)
          const recoverableResult = !hasExistingResult && res.result?.markdown

          if (status === 'FAILED') {
            verifiedFailedTasksRef.current.add(task.id)
          }

          if (
            status &&
            (status !== task.status ||
              res.message !== task.statusMessage ||
              res.updated_at !== task.statusUpdatedAt ||
              logsChanged ||
              !task.lastPolledAt ||
              recoverableResult)
          ) {
            if (status === 'SUCCESS') {
              verifiedFailedTasksRef.current.delete(task.id)
              const { markdown, transcript, audio_meta } = res.result
              toast.success('笔记生成成功')
              updateTaskContent(task.id, {
                ...statusData,
                markdown,
                transcript,
                audioMeta: audio_meta,
              })
            } else if (status === 'FAILED') {
              updateTaskContent(task.id, {
                ...statusData,
                ...(recoverableResult
                  ? {
                      markdown: res.result.markdown,
                      transcript: res.result.transcript,
                      audioMeta: res.result.audio_meta,
                    }
                  : {}),
              })
              toast.error(
                hasExistingResult || recoverableResult
                  ? '本次重新生成失败，已保留上一次成功结果'
                  : res.message || '笔记生成失败',
              )
              console.warn(`⚠️ 任务 ${task.id} 失败`)
            } else {
              updateTaskContent(task.id, statusData)
            }
          }
        } catch (error: unknown) {
          const pollingError = error as {
            data?: { message?: string; logs?: unknown[] }
            msg?: string
          }
          console.warn('任务状态查询暂时失败，将继续重试：', pollingError)
          updateTaskContent(task.id, {
            statusMessage:
              pollingError.data?.message || pollingError.msg || '状态查询暂时失败，将自动重试',
            logs: Array.isArray(pollingError.data?.logs)
              ? pollingError.data.logs
              : task.logs,
            lastPolledAt: new Date().toISOString(),
          })
        }
      }
    }, interval)

    return () => clearInterval(timer)
  }, [interval, updateTaskContent])
}
