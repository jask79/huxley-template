'use client'

import { useState } from 'react'
import { Task, TaskStatus, TaskPriority } from '@/lib/task-manager'
import { TaskCard } from './task-card'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/retroui/card'
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCenter,
} from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'

interface KanbanBoardProps {
  tasks: Task[]
  onTaskClick: (task: Task) => void
  onStatusChange: (taskId: string, capsule: string, newStatus: TaskStatus) => Promise<void>
}

const columns: { id: TaskStatus; title: string; color: string }[] = [
  { id: 'pending', title: 'Pending', color: '' },
  { id: 'in_progress', title: 'In Progress', color: '' },
  { id: 'completed', title: 'Completed', color: '' },
]

export function KanbanBoard({ tasks, onTaskClick, onStatusChange }: KanbanBoardProps) {
  const [activeTask, setActiveTask] = useState<Task | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  )

  const handleDragStart = (event: DragStartEvent) => {
    const task = tasks.find((t) => t.id === event.active.id)
    setActiveTask(task || null)
  }

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    setActiveTask(null)

    if (!over) return

    const taskId = active.id as string
    const task = tasks.find((t) => t.id === taskId)
    if (!task) return

    // Check if dropped over a column
    const targetColumnId = over.id as TaskStatus
    if (columns.find((col) => col.id === targetColumnId)) {
      if (task.status !== targetColumnId && task.capsule) {
        await onStatusChange(taskId, task.capsule, targetColumnId)
      }
    }
  }

  const getTasksForColumn = (status: TaskStatus) => {
    return tasks.filter((task) => task.status === status)
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {columns.map((column) => {
          const columnTasks = getTasksForColumn(column.id)

          return (
            <Card
              key={column.id}
              className={column.color}
              data-column-id={column.id}
            >
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>{column.title}</span>
                  <span className="text-sm font-normal text-muted-foreground">
                    {columnTasks.length}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <SortableContext
                  items={columnTasks.map((t) => t.id)}
                  strategy={verticalListSortingStrategy}
                  id={column.id}
                >
                  <div className="space-y-2 min-h-[200px]">
                    {columnTasks.map((task) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        onClick={() => onTaskClick(task)}
                      />
                    ))}
                    {columnTasks.length === 0 && (
                      <div className="text-center text-muted-foreground text-sm py-8">
                        No tasks
                      </div>
                    )}
                  </div>
                </SortableContext>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <DragOverlay>
        {activeTask ? (
          <div className="opacity-80">
            <TaskCard task={activeTask} onClick={() => {}} />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
