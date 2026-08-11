import { FC, useEffect, useRef, useState } from 'react'
import HomeLayout, { type MobileHomeView } from '@/layouts/HomeLayout.tsx'
import NoteForm from '@/pages/HomePage/components/NoteForm.tsx'
import MarkdownViewer from '@/pages/HomePage/components/MarkdownViewer.tsx'
import { hasUsableMarkdown, useTaskStore } from '@/store/taskStore'
import History from '@/pages/HomePage/components/History.tsx'
type ViewStatus = 'idle' | 'loading' | 'success' | 'failed'
export const HomePage: FC = () => {
  const tasks = useTaskStore(state => state.tasks)
  const currentTaskId = useTaskStore(state => state.currentTaskId)

  const currentTask = tasks.find(t => t.id === currentTaskId)

  const [status, setStatus] = useState<ViewStatus>('idle')
  const [mobileView, setMobileView] = useState<MobileHomeView>(currentTaskId ? 'note' : 'create')
  const previousTaskId = useRef(currentTaskId)
  const setCurrentTask = useTaskStore(state => state.setCurrentTask)

  useEffect(() => {
    if (!currentTask) {
      setStatus('idle')
    } else if (
      currentTask.status === 'SUCCESS' ||
      (currentTask.status === 'FAILED' && hasUsableMarkdown(currentTask.markdown))
    ) {
      setStatus('success')
    } else if (currentTask.status === 'FAILED') {
      setStatus('failed')
    } else {
      // PENDING、PARSING、DOWNLOADING、TRANSCRIBING、SUMMARIZING 等所有进行中状态
      setStatus('loading')
    }
  }, [currentTask, currentTask?.status])

  useEffect(() => {
    if (currentTaskId && currentTaskId !== previousTaskId.current) {
      setMobileView('note')
    }
    else if (!currentTaskId && previousTaskId.current) {
      setMobileView(tasks.length > 0 ? 'history' : 'create')
    }
    previousTaskId.current = currentTaskId
  }, [currentTaskId, tasks.length])

  const handleHistorySelect = (taskId: string) => {
    setCurrentTask(taskId)
    setMobileView('note')
  }

  // useEffect( () => {
  //     get_task_status('d4e87938-c066-48a0-bbd5-9bec40d53354').then(res=>{
  //         console.log('res1',res)
  //         setContent(res.data.result.markdown)
  //     })
  // }, [tasks]);
  return (
    <HomeLayout
      NoteForm={<NoteForm />}
      Preview={<MarkdownViewer status={status} />}
      History={<History onSelect={handleHistorySelect} />}
      mobileView={mobileView}
      onMobileViewChange={setMobileView}
    />
  )
}
