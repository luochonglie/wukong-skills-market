---
name: tapd-timesheet-manager
description: Use this skill when the user asks to "manage TAPD timesheets", "fill in timesheets", "check TAPD tasks", "analyze missing timesheets", or "create TAPD records", mentions "TAPD timesheets" or "timesheet management", or discusses TAPD project time tracking and task management. It covers all mcp-server-tapd MCP operations, including querying iterations, analyzing missing timesheets, and distributing hours across tasks.
version: 1.0.0
---

# TAPD Timesheet Manager

This skill provides comprehensive TAPD timesheet tracking and task management — efficient querying, analysis, and management of working hours and tasks.

## When to use this skill

Activate this skill when a user request involves:

- TAPD timesheet management and working-hour tracking
- Querying iteration tasks and user assignments
- Analyzing missing timesheet records
- Creating or updating timesheet entries
- Managing task status within an iteration
- Timesheet allocation and scheduling
- Any TAPD project time-tracking operation

## Runtime dependency

This skill is a pure orchestration skill: it contains no executable code and works entirely through the **`mcp-server-tapd`** MCP server. The following tools are the primary surface area:

- `get_stories_or_tasks` — query stories/tasks
- `get_timesheets` — query timesheet records
- `add_timesheets` — create timesheet records
- `update_timesheets` — update timesheet records
- `update_story_or_task` — update story/task status
- `get_iterations` — query iteration information
- `get_workspace_info` — get project information
- `get_workspace_users` — get project members

Required configuration: a `workspace_id` (TAPD project ID) and valid TAPD API credentials, supplied by the MCP server environment.

## Core features

### 1. Iteration task query

Query the tasks assigned to a specific user within an iteration.

**Key parameters:**

- `workspace_id`: TAPD project ID (e.g. `40888836`)
- `iteration_id`: iteration ID (e.g. `1140888836001000828`)
- `owner`: username (e.g. `张三`)
- `entity_type`: `"tasks"` for tasks, `"stories"` for stories

**Tool call pattern:**

```javascript
mcp__mcp-server-tapd__get_stories_or_tasks({
  workspace_id: "40888836",
  options: {
    entity_type: "tasks",
    iteration_id: "1140888836001000828",
    owner: "张三",
    fields: "id,name,status",
    limit: 100
  }
})
```

### 2. Missing-timesheet analysis

Analyze which timesheet records are missing within a given date range.

**Analysis steps:**

1. Fetch the user's existing timesheet records.
2. Identify the working days (Monday–Friday, excluding weekends).
3. Compare existing records against the expected working days.
4. Compute the completion rate and list the missing dates.

**Tool call pattern:**

```javascript
mcp__mcp-server-tapd__get_timesheets({
  workspace_id: "40888836",
  options: {
    owner: "张三",
    limit: 200,
    order: "spentdate desc"
  }
})
```

### 3. Smart hour distribution

Distribute working hours evenly across multiple tasks.

**Distribution strategy:**

- **Daily total:** 8 hours (a standard working day).
- **Algorithm:**
  - Base hours per task: `Math.floor(8 / task_count)`
  - Remainder distribution: the first `8 % task_count` tasks each get +1 hour.
  - The total always sums to exactly 8 hours per day.

**Tool call pattern:**

```javascript
// For each missing date and each task
mcp__mcp-server-tapd__add_timesheets({
  workspace_id: "40888836",
  options: {
    entity_type: "task",
    entity_id: "full task ID",
    timespent: "allocated hours",
    spentdate: "YYYY-MM-DD",
    owner: "张三"
  }
})
```

### 4. Task status management

Update task status in bulk.

**Common status values:**

- `open` — not started
- `progressing` — in progress
- `done` — completed

**Tool call pattern:**

```javascript
mcp__mcp-server-tapd__update_story_or_task({
  workspace_id: "40888836",
  options: {
    entity_type: "tasks",
    id: "task ID",
    status: "progressing"
  }
})
```

## Typical workflows

### Workflow 1: Monthly timesheet backfill

**User request:** "Help me process June's timesheets" or "Fill in my June timesheets."

**Steps:**

1. **Query iteration tasks**
   - Fetch all tasks assigned to the user in the specified iteration.
   - Extract task IDs and names.

2. **Analyze missing timesheets**
   - Determine the working days in the target month.
   - Identify dates with no timesheet record.
   - Compute the total number of missing days.

3. **Distribute hours**
   - Create a timesheet record for each missing date.
   - Apply smart distribution (8 hours ÷ task count).
   - Use the full entity ID (with the workspace_id prefix).

4. **Confirm completion**
   - Report the total number of records created.
   - Verify each day's total equals 8 hours.
   - Provide a completion summary.

### Workflow 2: Timesheet status check

**User request:** "Check my timesheets for this week" or "Show this week's timesheets."

**Steps:**

1. Get the current week's date range.
2. Query timesheet records for this period.
3. Identify which working days have records.
4. Report the completion rate and missing dates.
5. If anything is missing, suggest the next step.

### Workflow 3: Task status update

**User request:** "Set all my tasks to in progress" or "Bulk-update task status."

**Steps:**

1. Query the current task assignments.
2. Extract task IDs from the results.
3. Update each task's status in sequence.
4. Confirm successful updates.
5. Report any failures or errors.

## Implementation details

### Data-processing logic

**Working-day detection:**

```javascript
function isWorkday(date) {
  const day = date.getDay();
  // 0 = Sunday, 6 = Saturday
  return day !== 0 && day !== 6;
}
```

**Hour-distribution algorithm:**

```javascript
function distributeHours(taskCount, totalHours = 8) {
  const baseHours = Math.floor(totalHours / taskCount);
  const remainder = totalHours % taskCount;

  return Array.from({ length: taskCount }, (_, i) =>
    i < remainder ? baseHours + 1 : baseHours
  );
}
```

### Error handling

**Common issues and fixes:**

1. **Timesheet API returns 404**
   - **Cause:** incomplete entity ID.
   - **Fix:** use the full ID with the workspace_id prefix (e.g. `"1140888836001053133"`, not `"1053133"`).

2. **Missing `owner` parameter**
   - **Cause:** `add_timesheets` called without `owner`.
   - **Fix:** always include `owner` with the correct username.

3. **Duplicate timesheet records**
   - **Cause:** creating a record for a date that already has one.
   - **Fix:** check existing records before creating new ones.

4. **Invalid status value**
   - **Cause:** using a status name that does not exist in the workflow.
   - **Fix:** check the workflow configuration, or use `v_status` with a Chinese status name.

### Best practices

**Data validation:**

- Validate `workspace_id` and `iteration_id` before operating.
- Confirm the username matches the TAPD system exactly.
- Use the full entity-ID format.
- Validate the date format (`YYYY-MM-DD`).

**Bulk operations:**

- Create multiple timesheet records in parallel (up to 7 tasks × 11 days = 77 records).
- Use appropriate error handling for partial failures.
- Implement retry logic for transient API errors.

**Data consistency:**

- Ensure timesheet totals equal exactly 8 hours per day.
- Keep timesheets consistent with task status.
- Periodically verify timesheet completeness.

## Usage examples

### Example 1: Full monthly processing

**User:** "Help me process June's timesheets."

**Assistant response:**

1. Querying the tasks assigned to you in iteration 0706...
2. Analyzing missing timesheets in June up to today...
3. Creating timesheet records for the missing dates...
4. Completed creating 11 days × 7 tasks = 77 timesheet records.
5. Hour distribution: 8 hours per day, evenly split across 7 tasks.

### Example 2: Quick status check

**User:** "Check my timesheets for this week."

**Assistant response:**

- Working days this week: 5
- Timesheets filled: 3 (Mon, Wed, Fri)
- Timesheets missing: 2 (Tue, Thu)
- Coverage: 60%
- Suggestion: backfill the 2 missing days.

### Example 3: Task status update

**User:** "Set all my tasks to in progress."

**Assistant response:**

Updating task status...
✅ Successfully updated 7 tasks to "in progress":

- Task 1053133: open → progressing
- Task 1053072: open → progressing
- Task 1053066: open → progressing
- Task 1053055: open → progressing
- Task 1053049: open → progressing
- Task 1053039: open → progressing
- Task 1053033: open → progressing

## MCP tool reference

**Primary tools:**

- `mcp__mcp-server-tapd__get_stories_or_tasks`: query stories/tasks
- `mcp__mcp-server-tapd__get_timesheets`: query timesheet records
- `mcp__mcp-server-tapd__add_timesheets`: create timesheet records
- `mcp__mcp-server-tapd__update_story_or_task`: update task status
- `mcp__mcp-server-tapd__get_iterations`: query iteration information

**Common parameters:**

- `workspace_id`: required for all operations
- `options`: holds operation-specific parameters
- `limit`: controls result-set size (default: 10–100)
- `fields`: specifies which fields to return
- `order`: result sort order

## Performance

**Concurrency:**

- Bulk-create timesheet records (7 tasks per day).
- Update multiple task statuses in parallel.
- Efficient pagination for large result sets.

**Memory management:**

- Use pagination for large timesheet datasets.
- Process results in chunks to avoid memory issues.
- Use an appropriate `limit` per operation.

---

**Version:** 1.0.0
**Last updated:** 2026-06-16
**Compatibility:** TAPD MCP Server v1.x
**Maintainer:** Claude Code team
