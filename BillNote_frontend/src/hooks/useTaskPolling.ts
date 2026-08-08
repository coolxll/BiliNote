import { useEffect, useRef } from 'react'
import { useTaskStore } from '@/store/taskStore'
import { get_task_status } from '@/services/note.ts'
import toast from 'react-hot-toast'

export const useTaskPolling = (interval = 3000) => {
  const tasks = useTaskStore(state => state.tasks)
  const updateTaskContent = useTaskStore(state => state.updateTaskContent)
  const updateTaskStatus = useTaskStore(state => state.updateTaskStatus)
  const removeTask = useTaskStore(state => state.removeTask)

  const tasksRef = useRef(tasks)

  // 每次 tasks 更新，把最新的 tasks 同步进去
  useEffect(() => {
    tasksRef.current = tasks
  }, [tasks])

  useEffect(() => {
    const timer = setInterval(async () => {
      const pendingTasks = tasksRef.current.filter(
        task => task.status != 'SUCCESS' && task.status != 'FAILED'
      )

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

          if (
            status &&
            (status !== task.status ||
              res.message !== task.statusMessage ||
              res.updated_at !== task.statusUpdatedAt ||
              logsChanged ||
              !task.lastPolledAt)
          ) {
            if (status === 'SUCCESS') {
              const { markdown, transcript, audio_meta } = res.result
              toast.success('笔记生成成功')
              updateTaskContent(task.id, {
                ...statusData,
                markdown,
                transcript,
                audioMeta: audio_meta,
              })
            } else if (status === 'FAILED') {
              updateTaskContent(task.id, statusData)
              console.warn(`⚠️ 任务 ${task.id} 失败`)
            } else {
              updateTaskContent(task.id, statusData)
            }
          }
        } catch (e) {
          console.error('❌ 任务轮询失败：', e)
          updateTaskContent(task.id, {
            status: 'FAILED',
            statusMessage: e?.data?.message || e?.msg || '无法获取任务状态',
            logs: Array.isArray(e?.data?.logs) ? e.data.logs : task.logs,
            lastPolledAt: new Date().toISOString(),
          })
        }
      }
    }, interval)

    return () => clearInterval(timer)
  }, [interval])
}
