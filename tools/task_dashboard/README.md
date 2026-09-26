# Huxley Task Dashboard

A Next.js task management dashboard for Huxley capsules with real-time updates and Kanban board interface.

## Features

- **Kanban Board Layout**: Drag-and-drop tasks between Pending, In Progress, and Completed columns
- **Real-time Updates**: Auto-refreshes every 5 seconds to sync with task.json files
- **Filtering**: Filter tasks by capsule and priority
- **Task Management**: Create, edit, view, and delete tasks
- **Visual Indicators**: Priority emojis (🔴 high, 🟡 medium, 🔵 low)
- **Responsive Design**: Works on desktop and mobile devices

## Tech Stack

- **Next.js 14** with App Router
- **TypeScript** for type safety
- **RetroUI** - NeoBrutalism-styled component library (based on Radix UI + Tailwind CSS)
- **Tailwind CSS** for styling
- **@dnd-kit** for drag-and-drop functionality
- **date-fns** for date formatting

### UI Library

This dashboard uses **RetroUI**, a retro/neobrutalist component library featuring:
- Bold 4px black borders
- Prominent drop shadows (8px-12px offsets)
- Interactive button transforms (hover/active states)
- High-contrast color schemes
- Custom Card, Dialog, and Select components with neobrutalist styling

Components sourced from: https://www.retroui.dev

## Setup

1. **Install dependencies:**
   ```bash
   cd {{CATALYST_ROOT}}/tools/task_dashboard
   npm install
   ```

2. **Run development server:**
   ```bash
   npm run dev
   ```

3. **Open in browser:**
   ```
   http://localhost:3000
   ```

## Usage

### Viewing Tasks

The dashboard automatically loads all tasks from `{{CATALYST_ROOT}}/capsules/*/tasks.json` files.

### Creating a Task

1. Click the "New Task" button
2. Fill in the task details (description, priority, status, tags, etc.)
3. Select the target capsule
4. Click "Create"

### Editing a Task

1. Click on any task card to view details
2. Click "Edit" button
3. Modify fields
4. Click "Save"

### Changing Task Status

- **Drag-and-drop**: Drag a task card to a different column
- **Edit dialog**: Open the task and change the status dropdown

### Filtering Tasks

Use the filter dropdowns to:
- View tasks from specific capsules
- Filter by priority level
- Click "Reset Filters" to clear all filters

### Deleting a Task

1. Click on the task to view details
2. Click "Delete" button
3. Confirm deletion

## Data Format

Tasks are stored in `tasks.json` files in each capsule directory:

```json
[
  {
    "id": "358560fe",
    "description": "Task description",
    "status": "pending|in_progress|completed",
    "priority": "low|medium|high",
    "created": "2025-10-20T22:30:00Z",
    "updated": "2025-10-20T22:30:00Z",
    "assigned_agent": "Frontend Specialist",
    "dependencies": [],
    "tags": ["feature", "ui"],
    "source": "manual",
    "notes": "Additional notes",
    "completed_at": null
  }
]
```

## File Structure

```
task_dashboard/
├── app/
│   ├── api/
│   │   └── tasks/              # API routes
│   ├── layout.tsx              # Root layout
│   ├── page.tsx                # Main dashboard page
│   └── globals.css             # Global styles
├── components/
│   ├── retroui/                # RetroUI components (button, badge, card, dialog, etc.)
│   ├── kanban-board.tsx        # Kanban board component
│   ├── task-card.tsx           # Task card component
│   ├── task-dialog.tsx         # Task edit/create dialog
│   └── filters.tsx             # Filter controls
├── lib/
│   ├── task-manager.ts         # Task CRUD operations
│   └── utils.ts                # Utility functions
└── package.json
```

## Real-time Updates

The dashboard polls the API every 5 seconds to check for changes to task.json files. This ensures the UI stays in sync with external modifications (e.g., from task_manager.py CLI tool).

You can also manually refresh by clicking the "Refresh" button.

## Integration with task_manager.py

This dashboard works alongside the existing Python task manager:

```bash
# CLI tool
python3 tools/task_manager.py list example-social-capsule
python3 tools/task_manager.py add example-social-capsule "New task description"

# Changes will be reflected in the dashboard within 5 seconds
```

## Building for Production

```bash
npm run build
npm start
```

## Notes

- The dashboard reads from the actual capsule directories in Huxley
- All changes are persisted to the capsule's tasks.json file
- Drag-and-drop operations update task status immediately
- The dashboard respects the existing task schema used by task_manager.py
