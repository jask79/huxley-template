import { NextRequest, NextResponse } from 'next/server'
import { getAllTasks, getCapsules, createTask } from '@/lib/task-manager'

export async function GET() {
  try {
    const tasks = await getAllTasks()
    const capsules = await getCapsules()
    return NextResponse.json({ tasks, capsules })
  } catch (error) {
    console.error('Error fetching tasks:', error)
    return NextResponse.json(
      { error: 'Failed to fetch tasks' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { capsule, ...taskData } = body

    if (!capsule) {
      return NextResponse.json(
        { error: 'Capsule is required' },
        { status: 400 }
      )
    }

    const task = await createTask(capsule, {
      description: taskData.description || '',
      status: taskData.status || 'pending',
      priority: taskData.priority || 'medium',
      assigned_agent: taskData.assigned_agent || '',
      dependencies: taskData.dependencies || [],
      tags: taskData.tags || [],
      source: taskData.source || 'manual',
      notes: taskData.notes || '',
    })

    if (!task) {
      return NextResponse.json(
        { error: 'Failed to create task' },
        { status: 500 }
      )
    }

    return NextResponse.json(task)
  } catch (error) {
    console.error('Error creating task:', error)
    return NextResponse.json(
      { error: 'Failed to create task' },
      { status: 500 }
    )
  }
}
