import { TaskPriority } from '@/lib/task-manager'

interface PriorityIndicatorProps {
  priority: TaskPriority
  size?: 'sm' | 'md' | 'lg'
}

const colors = {
  high: '#ec4899',    // rose
  medium: '#3b82f6',  // blue
  low: '#a855f7'      // purple
}

const sizes = {
  sm: 'w-2.5 h-2.5',
  md: 'w-3 h-3',
  lg: 'w-4 h-4'
}

export function PriorityIndicator({ priority, size = 'md' }: PriorityIndicatorProps) {
  return (
    <div
      className={`${sizes[size]} rounded-full border-2 border-black flex-shrink-0`}
      style={{ backgroundColor: colors[priority] }}
      aria-label={`${priority} priority`}
    />
  )
}
