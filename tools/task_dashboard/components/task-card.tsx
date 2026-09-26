'use client'

import { Task } from '@/lib/task-manager'
import { Card, CardContent } from '@/components/retroui/card'
import { Badge } from '@/components/retroui/badge'
import { PriorityIndicator } from '@/components/priority-indicator'
import { formatDistanceToNow } from 'date-fns'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

interface TaskCardProps {
  task: Task
  onClick: () => void
}

const priorityColors = {
  high: 'bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950/30 dark:text-rose-300 dark:border-rose-800',
  medium: 'bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-950/30 dark:text-blue-300 dark:border-blue-800',
  low: 'bg-purple-100 text-purple-800 border-purple-300 dark:bg-purple-950/30 dark:text-purple-300 dark:border-purple-800',
}

export function TaskCard({ task, onClick }: TaskCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <Card
        className="mb-2 cursor-pointer hover:shadow-md transition-shadow"
        onClick={onClick}
      >
        <CardContent className="p-4">
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-center gap-2 flex-1">
              <PriorityIndicator priority={task.priority} />
              <p className="text-sm font-medium flex-1 line-clamp-2">
                {task.description}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-1 mb-2">
            {task.tags.map((tag) => (
              <Badge key={tag} variant="secondary" className="text-xs">
                {tag}
              </Badge>
            ))}
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="font-medium">{task.capsule}</span>
            <span>{formatDistanceToNow(new Date(task.updated), { addSuffix: true })}</span>
          </div>

          {task.assigned_agent && (
            <div className="mt-2 text-xs text-muted-foreground">
              Assigned: {task.assigned_agent}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
