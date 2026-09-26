# Quick Start Guide

## Installation (One-time setup)

```bash
cd {{CATALYST_ROOT}}/tools/task_dashboard
npm install
```

## Running the Dashboard

### Option 1: Quick Start Script (Recommended)
```bash
./start.sh
```
This will:
- Start the development server
- Automatically open http://localhost:3000 in your browser

### Option 2: Manual Start
```bash
npm run dev
```
Then open: http://localhost:3000

## Common Tasks

### View All Tasks
- Default view shows all tasks from all capsules
- Tasks organized in 3 columns: Pending, In Progress, Completed

### Create a New Task
1. Click "New Task" button (top right)
2. Fill in details:
   - Select capsule (required)
   - Enter description (required)
   - Set priority (low/medium/high)
   - Add tags (optional)
   - Assign agent (optional)
   - Add notes (optional)
3. Click "Create"

### Edit a Task
1. Click on any task card
2. Click "Edit" button
3. Modify fields
4. Click "Save"

### Change Task Status
**Method 1: Drag and Drop**
- Drag task card to different column (Pending → In Progress → Completed)

**Method 2: Edit Dialog**
- Click task → Edit → Change Status dropdown → Save

### Filter Tasks
Use the filter dropdowns at the top:
- **By Capsule**: View tasks from specific capsule or all
- **By Priority**: Filter by low/medium/high priority
- **Reset**: Clear all filters

### Delete a Task
1. Click on task card
2. Click "Delete" button
3. Confirm deletion

## Real-time Updates

The dashboard automatically refreshes every 5 seconds to sync with task.json files.

You can also click the "Refresh" button to manually update.

## Integration with CLI

The dashboard works alongside the Python task manager:

```bash
# Add task via CLI
python3 {{CATALYST_ROOT}}/tools/task_manager.py add example-social-capsule "New feature"

# Changes appear in dashboard within 5 seconds
```

## Data Location

Tasks are stored in: `{{CATALYST_ROOT}}/capsules/*/tasks.json`

All changes made in the dashboard are immediately persisted to these files.

## Troubleshooting

**Dashboard not loading?**
- Check if port 3000 is already in use
- Try `pkill -f "next dev"` then restart

**Tasks not showing?**
- Verify tasks.json files exist in capsule directories
- Check browser console for errors

**Build errors?**
- Run `npm install` again
- Delete `.next` folder and rebuild

## Development

### Build for Production
```bash
npm run build
npm start
```

### Run Type Checking
```bash
npm run lint
```

## Tech Stack Summary
- Next.js 14 (App Router)
- TypeScript
- shadcn/ui components
- Tailwind CSS
- @dnd-kit (drag-and-drop)
- date-fns (date formatting)
