import fs from 'fs/promises'
import path from 'path'

export type TaskStatus = 'pending' | 'in_progress' | 'completed'
export type TaskPriority = 'low' | 'medium' | 'high'

export interface Task {
  id: string
  description: string
  status: TaskStatus
  priority: TaskPriority
  created: string
  updated: string
  assigned_agent: string
  dependencies: string[]
  tags: string[]
  source: string
  notes: string
  completed_at: string | null
  capsule?: string // Added for UI purposes
}

const CAPSULES_DIR = '{{CATALYST_ROOT}}/capsules'

export async function getCapsules(): Promise<string[]> {
  try {
    const entries = await fs.readdir(CAPSULES_DIR, { withFileTypes: true })
    return entries
      .filter(entry => entry.isDirectory() && !entry.name.startsWith('.'))
      .map(entry => entry.name)
      .sort()
  } catch (error) {
    console.error('Error reading capsules directory:', error)
    return []
  }
}

export async function getTasksForCapsule(capsule: string): Promise<Task[]> {
  const tasksPath = path.join(CAPSULES_DIR, capsule, 'tasks.json')

  try {
    const content = await fs.readFile(tasksPath, 'utf-8')
    const tasks = JSON.parse(content) as Task[]
    // Add capsule name to each task
    return tasks.map(task => ({ ...task, capsule }))
  } catch (error) {
    // File doesn't exist or is invalid - return empty array
    return []
  }
}

export async function getAllTasks(): Promise<Task[]> {
  const capsules = await getCapsules()
  const taskPromises = capsules.map(capsule => getTasksForCapsule(capsule))
  const taskArrays = await Promise.all(taskPromises)
  return taskArrays.flat()
}

export async function updateTask(capsule: string, taskId: string, updates: Partial<Task>): Promise<Task | null> {
  const tasksPath = path.join(CAPSULES_DIR, capsule, 'tasks.json')

  try {
    const content = await fs.readFile(tasksPath, 'utf-8')
    const tasks = JSON.parse(content) as Task[]

    const taskIndex = tasks.findIndex(t => t.id === taskId)
    if (taskIndex === -1) {
      return null
    }

    // Update task
    const updatedTask = {
      ...tasks[taskIndex],
      ...updates,
      updated: new Date().toISOString(),
    }

    // If status changed to completed, set completed_at
    if (updates.status === 'completed' && tasks[taskIndex].status !== 'completed') {
      updatedTask.completed_at = new Date().toISOString()
    }

    // If status changed from completed, clear completed_at
    if (updates.status !== 'completed' && tasks[taskIndex].status === 'completed') {
      updatedTask.completed_at = null
    }

    tasks[taskIndex] = updatedTask

    // Write back to file
    await fs.writeFile(tasksPath, JSON.stringify(tasks, null, 2), 'utf-8')

    return { ...updatedTask, capsule }
  } catch (error) {
    console.error('Error updating task:', error)
    return null
  }
}

export async function deleteTask(capsule: string, taskId: string): Promise<boolean> {
  const tasksPath = path.join(CAPSULES_DIR, capsule, 'tasks.json')

  try {
    const content = await fs.readFile(tasksPath, 'utf-8')
    const tasks = JSON.parse(content) as Task[]

    const filteredTasks = tasks.filter(t => t.id !== taskId)

    if (filteredTasks.length === tasks.length) {
      return false // Task not found
    }

    await fs.writeFile(tasksPath, JSON.stringify(filteredTasks, null, 2), 'utf-8')
    return true
  } catch (error) {
    console.error('Error deleting task:', error)
    return false
  }
}

export async function createTask(capsule: string, task: Omit<Task, 'id' | 'created' | 'updated' | 'completed_at'>): Promise<Task | null> {
  const tasksPath = path.join(CAPSULES_DIR, capsule, 'tasks.json')

  try {
    let tasks: Task[] = []

    // Try to read existing tasks
    try {
      const content = await fs.readFile(tasksPath, 'utf-8')
      tasks = JSON.parse(content)
    } catch {
      // File doesn't exist, start with empty array
    }

    // Generate ID (simple 8-char hex)
    const id = Math.random().toString(16).substring(2, 10)
    const now = new Date().toISOString()

    const newTask: Task = {
      ...task,
      id,
      created: now,
      updated: now,
      completed_at: task.status === 'completed' ? now : null,
      capsule,
    }

    tasks.push(newTask)

    await fs.writeFile(tasksPath, JSON.stringify(tasks, null, 2), 'utf-8')
    return newTask
  } catch (error) {
    console.error('Error creating task:', error)
    return null
  }
}
