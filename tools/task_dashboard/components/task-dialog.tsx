'use client'

import { useState, useEffect } from 'react'
import { Task, TaskPriority, TaskStatus } from '@/lib/task-manager'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/retroui/dialog'
import { Button } from '@/components/retroui/button'
import { Input } from '@/components/retroui/input'
import { Textarea } from '@/components/retroui/textarea'
import { Label } from '@/components/retroui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/retroui/select'
import { Badge } from '@/components/retroui/badge'
import { PriorityIndicator } from '@/components/priority-indicator'
import { X } from 'lucide-react'

interface TaskDialogProps {
  task: Task | null
  capsules: string[]
  open: boolean
  onClose: () => void
  onSave: (task: Partial<Task> & { capsule: string }) => Promise<void>
  onDelete?: (taskId: string) => Promise<void>
  mode: 'view' | 'edit' | 'create'
}

export function TaskDialog({
  task,
  capsules,
  open,
  onClose,
  onSave,
  onDelete,
  mode: initialMode,
}: TaskDialogProps) {
  const [mode, setMode] = useState<'view' | 'edit' | 'create'>(initialMode)
  const [formData, setFormData] = useState<Partial<Task> & { capsule: string }>({
    description: '',
    priority: 'medium',
    status: 'pending',
    assigned_agent: '',
    tags: [],
    notes: '',
    capsule: capsules[0] || '',
  })
  const [tagInput, setTagInput] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setMode(initialMode)
    if (task) {
      setFormData({
        ...task,
        capsule: task.capsule || capsules[0] || '',
      })
    } else {
      setFormData({
        description: '',
        priority: 'medium',
        status: 'pending',
        assigned_agent: '',
        tags: [],
        notes: '',
        capsule: capsules[0] || '',
      })
    }
  }, [task, initialMode, capsules, open])

  const handleSave = async () => {
    setLoading(true)
    try {
      await onSave(formData)
      onClose()
    } catch (error) {
      console.error('Error saving task:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!task || !onDelete) return
    if (!confirm('Are you sure you want to delete this task?')) return

    setLoading(true)
    try {
      await onDelete(task.id)
      onClose()
    } catch (error) {
      console.error('Error deleting task:', error)
    } finally {
      setLoading(false)
    }
  }

  const addTag = () => {
    if (tagInput.trim() && !formData.tags?.includes(tagInput.trim())) {
      setFormData({
        ...formData,
        tags: [...(formData.tags || []), tagInput.trim()],
      })
      setTagInput('')
    }
  }

  const removeTag = (tag: string) => {
    setFormData({
      ...formData,
      tags: formData.tags?.filter((t) => t !== tag) || [],
    })
  }

  const isEditing = mode === 'edit' || mode === 'create'

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {mode === 'create' ? 'New Task' : mode === 'edit' ? 'Edit Task' : 'Task Details'}
          </DialogTitle>
          <DialogDescription>
            {mode === 'create'
              ? 'Create a new task for a capsule'
              : mode === 'edit'
              ? 'Update task details'
              : 'View task information'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Capsule Selection */}
          <div className="space-y-2">
            <Label>Capsule</Label>
            {isEditing ? (
              <Select
                value={formData.capsule}
                onValueChange={(value) => setFormData({ ...formData, capsule: value })}
                disabled={mode === 'edit'}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {capsules.map((capsule) => (
                    <SelectItem key={capsule} value={capsule}>
                      {capsule}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <p className="text-sm font-medium">{formData.capsule}</p>
            )}
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label>Description</Label>
            {isEditing ? (
              <Textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Enter task description"
                rows={3}
              />
            ) : (
              <p className="text-sm">{formData.description}</p>
            )}
          </div>

          {/* Priority and Status */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Priority</Label>
              {isEditing ? (
                <Select
                  value={formData.priority}
                  onValueChange={(value: TaskPriority) =>
                    setFormData({ ...formData, priority: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">
                      <div className="flex items-center gap-2">
                        <PriorityIndicator priority="low" size="sm" />
                        <span>Low</span>
                      </div>
                    </SelectItem>
                    <SelectItem value="medium">
                      <div className="flex items-center gap-2">
                        <PriorityIndicator priority="medium" size="sm" />
                        <span>Medium</span>
                      </div>
                    </SelectItem>
                    <SelectItem value="high">
                      <div className="flex items-center gap-2">
                        <PriorityIndicator priority="high" size="sm" />
                        <span>High</span>
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
              ) : (
                <div className="flex items-center gap-2">
                  <PriorityIndicator priority={formData.priority || 'medium'} size="sm" />
                  <span className="text-sm font-medium capitalize">{formData.priority}</span>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label>Status</Label>
              {isEditing ? (
                <Select
                  value={formData.status}
                  onValueChange={(value: TaskStatus) =>
                    setFormData({ ...formData, status: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="in_progress">In Progress</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                  </SelectContent>
                </Select>
              ) : (
                <p className="text-sm font-medium capitalize">{formData.status?.replace('_', ' ')}</p>
              )}
            </div>
          </div>

          {/* Assigned Agent */}
          <div className="space-y-2">
            <Label>Assigned Agent</Label>
            {isEditing ? (
              <Input
                value={formData.assigned_agent}
                onChange={(e) => setFormData({ ...formData, assigned_agent: e.target.value })}
                placeholder="e.g., Frontend Specialist"
              />
            ) : (
              <p className="text-sm">{formData.assigned_agent || 'Unassigned'}</p>
            )}
          </div>

          {/* Tags */}
          <div className="space-y-2">
            <Label>Tags</Label>
            {isEditing && (
              <div className="flex gap-2">
                <Input
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addTag())}
                  placeholder="Add tag and press Enter"
                />
                <Button type="button" onClick={addTag} size="sm">
                  Add
                </Button>
              </div>
            )}
            <div className="flex flex-wrap gap-1">
              {formData.tags?.map((tag) => (
                <Badge key={tag} variant="secondary" className="flex items-center gap-1">
                  {tag}
                  {isEditing && (
                    <X
                      className="h-3 w-3 cursor-pointer"
                      onClick={() => removeTag(tag)}
                    />
                  )}
                </Badge>
              ))}
            </div>
          </div>

          {/* Notes */}
          <div className="space-y-2">
            <Label>Notes</Label>
            {isEditing ? (
              <Textarea
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                placeholder="Additional notes"
                rows={3}
              />
            ) : (
              <p className="text-sm">{formData.notes || 'No notes'}</p>
            )}
          </div>

          {/* Metadata (View Only) */}
          {!isEditing && task && (
            <div className="space-y-1 text-xs text-muted-foreground pt-2 border-t">
              <p>Created: {new Date(task.created).toLocaleString()}</p>
              <p>Updated: {new Date(task.updated).toLocaleString()}</p>
              {task.completed_at && (
                <p>Completed: {new Date(task.completed_at).toLocaleString()}</p>
              )}
              <p>ID: {task.id}</p>
            </div>
          )}
        </div>

        <DialogFooter>
          {mode === 'view' && (
            <>
              <Button variant="outline" onClick={onClose}>
                Close
              </Button>
              <Button onClick={() => setMode('edit')}>Edit</Button>
              {onDelete && task && (
                <Button variant="destructive" onClick={handleDelete} disabled={loading}>
                  Delete
                </Button>
              )}
            </>
          )}
          {isEditing && (
            <>
              <Button variant="outline" onClick={onClose} disabled={loading}>
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={loading || !formData.description?.trim()}>
                {loading ? 'Saving...' : mode === 'create' ? 'Create' : 'Save'}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
