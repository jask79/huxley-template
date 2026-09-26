'use client'

import { useState, useEffect, useCallback } from 'react'
import { Task, TaskPriority, TaskStatus } from '@/lib/task-manager'
import { KanbanBoard } from '@/components/kanban-board'
import { TaskDialog } from '@/components/task-dialog'
import { Filters } from '@/components/filters'
import { ThemeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/retroui/button'
import { AnimatedText } from '@/components/animated-text'
import { RetroGrid } from '@/components/ui/retro-grid'
import { Plus, RefreshCw } from 'lucide-react'

export default function Home() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [capsules, setCapsules] = useState<string[]>([])
  const [filteredTasks, setFilteredTasks] = useState<Task[]>([])
  const [selectedCapsule, setSelectedCapsule] = useState<string>('all')
  const [selectedPriority, setSelectedPriority] = useState<TaskPriority | 'all'>('all')
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogMode, setDialogMode] = useState<'view' | 'edit' | 'create'>('view')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchTasks = useCallback(async () => {
    try {
      const response = await fetch('/api/tasks')
      const data = await response.json()
      setTasks(data.tasks || [])
      setCapsules(data.capsules || [])
    } catch (error) {
      console.error('Error fetching tasks:', error)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchTasks()

    // Poll for updates every 5 seconds
    const interval = setInterval(fetchTasks, 5000)
    return () => clearInterval(interval)
  }, [fetchTasks])

  useEffect(() => {
    let filtered = tasks

    if (selectedCapsule !== 'all') {
      filtered = filtered.filter((task) => task.capsule === selectedCapsule)
    }

    if (selectedPriority !== 'all') {
      filtered = filtered.filter((task) => task.priority === selectedPriority)
    }

    setFilteredTasks(filtered)
  }, [tasks, selectedCapsule, selectedPriority])

  const handleTaskClick = (task: Task) => {
    setSelectedTask(task)
    setDialogMode('view')
    setDialogOpen(true)
  }

  const handleCreateTask = () => {
    setSelectedTask(null)
    setDialogMode('create')
    setDialogOpen(true)
  }

  const handleStatusChange = async (
    taskId: string,
    capsule: string,
    newStatus: TaskStatus
  ) => {
    try {
      const response = await fetch(`/api/tasks/${capsule}/${taskId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      })

      if (response.ok) {
        const updatedTask = await response.json()
        setTasks((prev) =>
          prev.map((task) => (task.id === taskId ? updatedTask : task))
        )
      }
    } catch (error) {
      console.error('Error updating task status:', error)
    }
  }

  const handleSaveTask = async (taskData: Partial<Task> & { capsule: string }) => {
    try {
      if (selectedTask) {
        // Update existing task
        const response = await fetch(
          `/api/tasks/${selectedTask.capsule}/${selectedTask.id}`,
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData),
          }
        )

        if (response.ok) {
          const updatedTask = await response.json()
          setTasks((prev) =>
            prev.map((task) => (task.id === selectedTask.id ? updatedTask : task))
          )
        }
      } else {
        // Create new task
        const response = await fetch('/api/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(taskData),
        })

        if (response.ok) {
          const newTask = await response.json()
          setTasks((prev) => [...prev, newTask])
        }
      }
    } catch (error) {
      console.error('Error saving task:', error)
      throw error
    }
  }

  const handleDeleteTask = async (taskId: string) => {
    if (!selectedTask) return

    try {
      const response = await fetch(
        `/api/tasks/${selectedTask.capsule}/${taskId}`,
        {
          method: 'DELETE',
        }
      )

      if (response.ok) {
        setTasks((prev) => prev.filter((task) => task.id !== taskId))
      }
    } catch (error) {
      console.error('Error deleting task:', error)
      throw error
    }
  }

  const handleRefresh = () => {
    setRefreshing(true)
    fetchTasks()
  }

  const handleResetFilters = () => {
    setSelectedCapsule('all')
    setSelectedPriority('all')
  }

  const stats = {
    total: filteredTasks.length,
    pending: filteredTasks.filter((t) => t.status === 'pending').length,
    inProgress: filteredTasks.filter((t) => t.status === 'in_progress').length,
    completed: filteredTasks.filter((t) => t.status === 'completed').length,
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-2" />
          <p className="text-muted-foreground">Loading tasks...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="bg-black p-8 border-b-4 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] relative overflow-hidden">
        <RetroGrid className="absolute inset-0 z-0" />
        <div className="max-w-7xl mx-auto relative z-10">
          <div className="flex items-center justify-between">
            <div>
              <AnimatedText
                text="Huxley Task Dashboard"
                className="text-3xl font-bold"
              />
            </div>
            <div className="flex gap-2">
              <ThemeToggle />
              <Button onClick={handleRefresh} variant="outline" disabled={refreshing} className="bg-[#3b82f6] text-white border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[2px] hover:shadow-none transition-all hover:opacity-90">
                <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
              <Button onClick={handleCreateTask} className="bg-[#3b82f6] text-white border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[2px] hover:shadow-none transition-all hover:opacity-90">
                <Plus className="h-4 w-4 mr-2" />
                New Task
              </Button>
            </div>
          </div>
        </div>
      </div>
      <div className="max-w-7xl mx-auto p-8 space-y-6">

        <Filters
          capsules={capsules}
          selectedCapsule={selectedCapsule}
          selectedPriority={selectedPriority}
          onCapsuleChange={setSelectedCapsule}
          onPriorityChange={setSelectedPriority}
          onReset={handleResetFilters}
        />

        <KanbanBoard
          tasks={filteredTasks}
          onTaskClick={handleTaskClick}
          onStatusChange={handleStatusChange}
        />

        <TaskDialog
          task={selectedTask}
          capsules={capsules}
          open={dialogOpen}
          onClose={() => setDialogOpen(false)}
          onSave={handleSaveTask}
          onDelete={handleDeleteTask}
          mode={dialogMode}
        />
      </div>
    </div>
  )
}
