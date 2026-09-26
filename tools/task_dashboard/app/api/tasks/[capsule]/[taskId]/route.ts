import { NextRequest, NextResponse } from 'next/server'
import { updateTask, deleteTask } from '@/lib/task-manager'

export async function PUT(
  request: NextRequest,
  { params }: { params: { capsule: string; taskId: string } }
) {
  try {
    const body = await request.json()
    const { capsule, taskId } = params

    const task = await updateTask(capsule, taskId, body)

    if (!task) {
      return NextResponse.json(
        { error: 'Task not found' },
        { status: 404 }
      )
    }

    return NextResponse.json(task)
  } catch (error) {
    console.error('Error updating task:', error)
    return NextResponse.json(
      { error: 'Failed to update task' },
      { status: 500 }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { capsule: string; taskId: string } }
) {
  try {
    const { capsule, taskId } = params

    const success = await deleteTask(capsule, taskId)

    if (!success) {
      return NextResponse.json(
        { error: 'Task not found' },
        { status: 404 }
      )
    }

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Error deleting task:', error)
    return NextResponse.json(
      { error: 'Failed to delete task' },
      { status: 500 }
    )
  }
}
