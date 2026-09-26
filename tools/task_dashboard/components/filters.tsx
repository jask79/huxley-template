'use client'

import { TaskPriority } from '@/lib/task-manager'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/retroui/select'
import { Button } from '@/components/retroui/button'
import { PriorityIndicator } from '@/components/priority-indicator'

interface FiltersProps {
  capsules: string[]
  selectedCapsule: string
  selectedPriority: TaskPriority | 'all'
  onCapsuleChange: (capsule: string) => void
  onPriorityChange: (priority: TaskPriority | 'all') => void
  onReset: () => void
}

export function Filters({
  capsules,
  selectedCapsule,
  selectedPriority,
  onCapsuleChange,
  onPriorityChange,
  onReset,
}: FiltersProps) {
  return (
    <div className="flex flex-wrap gap-4 items-center">
      <div className="flex-1 min-w-[200px]">
        <Select value={selectedCapsule} onValueChange={onCapsuleChange}>
          <SelectTrigger>
            <SelectValue placeholder="Select capsule" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Capsules</SelectItem>
            {capsules.map((capsule) => (
              <SelectItem key={capsule} value={capsule}>
                {capsule}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex-1 min-w-[200px]">
        <Select value={selectedPriority} onValueChange={onPriorityChange}>
          <SelectTrigger>
            <SelectValue placeholder="Select priority" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Priorities</SelectItem>
            <SelectItem value="high">
              <div className="flex items-center gap-2">
                <PriorityIndicator priority="high" size="sm" />
                <span>High</span>
              </div>
            </SelectItem>
            <SelectItem value="medium">
              <div className="flex items-center gap-2">
                <PriorityIndicator priority="medium" size="sm" />
                <span>Medium</span>
              </div>
            </SelectItem>
            <SelectItem value="low">
              <div className="flex items-center gap-2">
                <PriorityIndicator priority="low" size="sm" />
                <span>Low</span>
              </div>
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Button variant="outline" onClick={onReset}>
        Reset Filters
      </Button>
    </div>
  )
}
