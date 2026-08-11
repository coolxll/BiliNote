import NoteHistory from '@/pages/HomePage/components/NoteHistory.tsx'
import { useTaskStore } from '@/store/taskStore'
import { Clock } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'

interface HistoryProps {
  onSelect?: (taskId: string) => void
}

const History = ({ onSelect }: HistoryProps) => {
  const currentTaskId = useTaskStore(state => state.currentTaskId)
  const setCurrentTask = useTaskStore(state => state.setCurrentTask)
  return (
    <>
      <div className="flex h-full w-full flex-col gap-3 overflow-hidden px-3 py-2 md:gap-4 md:px-2.5 md:py-1.5">
        {/*生成历史    */}
        <div className="flex h-10 shrink-0 items-center gap-2 md:my-4">
          <Clock className="h-4 w-4 text-neutral-500" />
          <h2 className="text-base font-medium text-neutral-900">生成历史</h2>
        </div>
        <ScrollArea className="min-h-0 w-full flex-1">
          {/*<div className="w-full flex-1 overflow-y-auto">*/}
          <NoteHistory onSelect={onSelect || setCurrentTask} selectedId={currentTaskId} />
          {/*</div>*/}
        </ScrollArea>
      </div>
    </>
  )
}

export default History
