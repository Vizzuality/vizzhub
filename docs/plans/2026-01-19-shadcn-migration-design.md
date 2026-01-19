# Shadcn UI Migration Design

**Date**: 2026-01-19
**Status**: Approved
**Approach**: Progressive migration with dark mode support

## Overview

Migrate the Project Scorecard frontend from custom Tailwind components to shadcn/ui component library. Use a progressive approach to maintain functionality while modernizing the UI. Implement dark mode with user toggle, defaulting to dark theme.

## Goals

1. Modernize UI with consistent, accessible components
2. Implement dark/light mode theming with toggle
3. Maintain all existing functionality during migration
4. Improve developer experience with reusable components
5. Keep custom score colors and branding

## Migration Strategy

**Progressive approach:**
- Phase 1: Setup and core components (Card, Button, Input, Form)
- Phase 2: Main pages (Projects, ProjectDetail)
- Phase 3: Remaining components (ScoreCard, DimensionChart, ProjectCard)
- Phase 4: Settings and authentication pages

This allows validation at each step while keeping the app functional.

## Setup and Configuration

### Shadcn Components to Install

Install via MCP server:
1. `card` - Project cards, score cards, layouts
2. `button` - All interactive buttons
3. `input` - Form fields
4. `form` - Form wrapper with react-hook-form integration
5. `badge` - Score badges, status indicators
6. `separator` - Visual dividers
7. `dropdown-menu` - Navbar navigation on mobile
8. `alert-dialog` - Delete confirmations

### Theme Configuration

**Dependencies:**
```json
{
  "next-themes": "^0.2.1"
}
```

**Tailwind config changes:**
```js
// tailwind.config.js
export default {
  darkMode: 'class', // Enable class-based dark mode
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Shadcn CSS variables (auto-generated)
        border: 'hsl(var(--border))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        // ... shadcn variables

        // Keep custom score colors
        score: {
          excellent: '#22c55e',
          good: '#84cc16',
          average: '#eab308',
          poor: '#f97316',
          critical: '#ef4444',
        },
      },
    },
  },
  plugins: [],
};
```

**CSS variables** (`src/index.css`):
- Define shadcn's CSS variables for light and dark modes
- Default theme: dark
- Variables for background, foreground, primary, secondary, etc.

**Theme Provider** (`src/components/theme-provider.tsx`):
```tsx
import { ThemeProvider as NextThemesProvider } from 'next-themes';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
    >
      {children}
    </NextThemesProvider>
  );
}
```

### File Structure

```
frontend/src/
├── components/
│   ├── ui/                    # Shadcn components (auto-generated)
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── input.tsx
│   │   ├── form.tsx
│   │   ├── badge.tsx
│   │   ├── separator.tsx
│   │   ├── dropdown-menu.tsx
│   │   └── alert-dialog.tsx
│   ├── layout/                # New: Layout components
│   │   ├── AppLayout.tsx      # Navbar + outlet
│   │   └── ThemeToggle.tsx    # Theme switcher
│   ├── Dashboard/             # Existing: Migrate internally
│   │   └── ProjectCard.tsx
│   ├── Forms/                 # Existing: Migrate internally
│   │   └── ProjectForm.tsx
│   ├── ScoreCard/             # Existing: Migrate internally
│   │   └── ScoreCard.tsx
│   └── DimensionChart/        # Existing: Migrate internally
│       └── DimensionChart.tsx
└── pages/                     # Migrate to use new components
    ├── Projects.tsx
    ├── ProjectDetail.tsx
    ├── Settings.tsx
    └── Login.tsx
```

## Layout and Navigation

### AppLayout Component

**Location**: `src/components/layout/AppLayout.tsx`

**Structure:**
```tsx
<div className="min-h-screen">
  {/* Navbar */}
  <nav className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur">
    <div className="container flex h-16 items-center justify-between">
      {/* Logo/Title */}
      <div className="flex items-center gap-6">
        <h1 className="text-xl font-bold">Project Scorecard</h1>

        {/* Desktop Navigation */}
        <div className="hidden md:flex gap-4">
          <Link to="/projects">Projects</Link>
          <Link to="/settings">Settings</Link>
        </div>
      </div>

      {/* Right side: Theme Toggle + Mobile Menu */}
      <div className="flex items-center gap-2">
        <ThemeToggle />
        <MobileNav /> {/* Dropdown menu for mobile */}
      </div>
    </div>
  </nav>

  {/* Page Content */}
  <main className="container py-6">
    <Outlet />
  </main>
</div>
```

**Features:**
- Sticky navbar with backdrop blur
- Logo/title on left
- Navigation links (desktop: inline, mobile: dropdown menu)
- Theme toggle button on right
- Container max-width for readability
- Uses react-router-dom `<Outlet />`

### ThemeToggle Component

**Location**: `src/components/layout/ThemeToggle.tsx`

**Behavior:**
- Shows `Sun` icon in dark mode (click to go light)
- Shows `Moon` icon in light mode (click to go dark)
- Uses `useTheme()` from next-themes
- Smooth fade animation between icons
- Button with `variant="ghost"` and `size="icon"`

### Routing Integration

**Update `App.tsx`:**
```tsx
<Routes>
  {/* Routes with navbar */}
  <Route element={<AppLayout />}>
    <Route path="/projects" element={<Projects />} />
    <Route path="/projects/:id" element={<ProjectDetail />} />
    <Route path="/settings" element={<Settings />} />
  </Route>

  {/* Routes without navbar */}
  <Route path="/login" element={<Login />} />
  <Route path="/" element={<Navigate to="/projects" />} />
</Routes>
```

## Page Migrations

### Projects Page

**Current state:**
- Custom `className="card"` divs
- Custom button classes `btn-primary`
- Manual grid layout
- Custom loading spinner

**Migrated:**
```tsx
// Loading state
<div className="flex items-center justify-center h-64">
  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
</div>

// Header with create button
<div className="flex items-center justify-between mb-6">
  <h1 className="text-3xl font-bold">Projects</h1>
  <Button onClick={() => setShowForm(true)}>
    <Plus className="w-4 h-4 mr-2" />
    Create Project
  </Button>
</div>

// Create form (shown when showForm is true)
{showForm && (
  <Card className="mb-6">
    <CardHeader>
      <CardTitle>Create New Project</CardTitle>
    </CardHeader>
    <CardContent>
      <ProjectForm onSubmit={handleCreate} onCancel={() => setShowForm(false)} />
    </CardContent>
  </Card>
)}

// Projects grid
<div className="grid gap-4">
  {projects.map(project => (
    <ProjectCard key={project.id} project={project} />
  ))}
</div>

// Empty state
{projects.length === 0 && (
  <Card className="text-center py-12">
    <CardContent>
      <p className="text-muted-foreground mb-4">No projects yet</p>
      <Button onClick={() => setShowForm(true)}>
        Create your first project
      </Button>
    </CardContent>
  </Card>
)}
```

**Changes:**
- Replace custom card classes with `<Card>`, `<CardHeader>`, `<CardContent>`
- Replace custom buttons with `<Button>` component
- Use semantic color tokens (`text-muted-foreground` instead of `text-gray-500`)
- Maintain all existing functionality and state management

### ProjectDetail Page

**Current state:**
- Multiple custom cards for different sections
- Custom button styling for Edit, Delete, Collect Metrics
- Manual layout with flex/grid
- Inline delete confirmation (needs improvement)

**Migrated:**

**Header section:**
```tsx
<div className="space-y-6">
  {/* Back link */}
  <Link to="/projects" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
    <ArrowLeft className="w-4 h-4" />
    Back to Projects
  </Link>

  {/* Project info card */}
  <Card>
    <CardHeader>
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <CardTitle className="text-3xl">{project.name}</CardTitle>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            {project.jira_project_key && (
              <span className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4" />
                Jira: {project.jira_project_key}
              </span>
            )}
            {project.github_repo && (
              <span className="flex items-center gap-2">
                <Github className="w-4 h-4" />
                GitHub: {project.github_repo}
              </span>
            )}
            {hasDateRange && (
              <span className="flex items-center gap-2">
                <Calendar className="w-4 h-4" />
                {formatDate(project.start_date)} - {formatDate(project.end_date)}
              </span>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setIsEditing(true)}>
            <Pencil className="w-4 h-4 mr-2" />
            Edit
          </Button>
          <Button variant="destructive" size="sm" onClick={() => setShowDeleteConfirm(true)}>
            <Trash2 className="w-4 h-4 mr-2" />
            Delete
          </Button>
        </div>
      </div>
    </CardHeader>

    {project.jira_project_key && (
      <CardContent>
        <Button onClick={handleCollectMetrics} disabled={collectJiraMetrics.isPending}>
          <RefreshCw className={cn("w-4 h-4 mr-2", collectJiraMetrics.isPending && "animate-spin")} />
          Collect Metrics
        </Button>
      </CardContent>
    )}
  </Card>
</div>
```

**Delete confirmation:**
```tsx
<AlertDialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Delete Project?</AlertDialogTitle>
      <AlertDialogDescription>
        This action cannot be undone. This will permanently delete the project
        "{project.name}" and all associated metrics.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancel</AlertDialogCancel>
      <AlertDialogAction onClick={handleDelete} className="bg-destructive">
        Delete
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

**Scores and metrics sections:**
```tsx
<Separator className="my-6" />

{/* Scores section */}
{scores && (
  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
    <ScoreCard title="Overall Score" score={scores.final_score} />
    <ScoreCard title="Time" score={scores.p_time} />
    <ScoreCard title="Cost" score={scores.p_cost} />
    {/* ... other dimensions */}
  </div>
)}

<Separator className="my-6" />

{/* Metrics section */}
{metrics && (
  <Card>
    <CardHeader>
      <CardTitle>Metrics</CardTitle>
    </CardHeader>
    <CardContent>
      <DimensionChart data={metricsData} />
    </CardContent>
  </Card>
)}
```

**Changes:**
- Use `<AlertDialog>` for delete confirmation (better UX)
- Button variants: `outline` for Edit, `destructive` for Delete, `default` for Collect
- `<Separator />` between major sections
- Semantic spacing with `space-y-*` utilities
- Loading states with animated spinner on button

## Component Migrations

### ProjectCard

**Current:** Custom card div with manual styling

**Migrated:**
```tsx
export default function ProjectCard({ project }: { project: Project }) {
  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardHeader>
        <div className="flex items-start justify-between">
          <CardTitle>{project.name}</CardTitle>
          {project.final_score !== undefined && (
            <Badge variant={getScoreVariant(project.final_score)}>
              {project.final_score}
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent>
        <div className="space-y-2 text-sm text-muted-foreground">
          {project.jira_project_key && (
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Jira: {project.jira_project_key}
            </div>
          )}
          {project.github_repo && (
            <div className="flex items-center gap-2">
              <Github className="w-4 h-4" />
              GitHub: {project.github_repo}
            </div>
          )}
        </div>
      </CardContent>

      <CardFooter>
        <Link to={`/projects/${project.id}`} className="text-sm font-medium hover:underline">
          View Details →
        </Link>
      </CardFooter>
    </Card>
  );
}

function getScoreVariant(score: number): 'default' | 'success' | 'warning' | 'destructive' {
  if (score >= 80) return 'success';
  if (score >= 60) return 'default';
  if (score >= 40) return 'warning';
  return 'destructive';
}
```

**Custom badge variants** (add to `components/ui/badge.tsx`):
```tsx
const badgeVariants = {
  // ... existing variants
  success: 'bg-score-excellent text-white',
  warning: 'bg-score-average text-white',
}
```

### ProjectForm

**Current:** Custom form with react-hook-form

**Migrated:**
```tsx
import { useForm } from 'react-hook-form';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

export default function ProjectForm({ project, onSubmit, onCancel, isLoading }: ProjectFormProps) {
  const form = useForm<ProjectCreate>({
    defaultValues: project || {
      name: '',
      jira_project_key: '',
      github_repo: '',
      start_date: '',
      end_date: '',
    },
  });

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Project Name</FormLabel>
              <FormControl>
                <Input placeholder="My Project" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="jira_project_key"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Jira Project Key</FormLabel>
              <FormControl>
                <Input placeholder="PROJ" {...field} value={field.value || ''} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Similar for github_repo, start_date, end_date */}

        <div className="flex gap-2 justify-end">
          <Button type="button" variant="outline" onClick={onCancel} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" disabled={isLoading}>
            {isLoading ? 'Saving...' : 'Save'}
          </Button>
        </div>
      </form>
    </Form>
  );
}
```

**Changes:**
- Use shadcn Form components with react-hook-form integration
- Automatic validation display with `<FormMessage>`
- Semantic form structure with FormField pattern
- Button variants for primary/secondary actions

### ScoreCard

**Current:** Custom card with score display

**Migrated:**
```tsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export default function ScoreCard({ title, score }: { title: string; score: number }) {
  const status = getScoreStatus(score);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between">
          <div className="text-3xl font-bold">{score.toFixed(1)}</div>
          <Badge
            variant={status.variant}
            className={status.className}
          >
            {status.label}
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}

function getScoreStatus(score: number) {
  if (score >= 80) return {
    variant: 'default',
    className: 'bg-score-excellent',
    label: 'Excellent'
  };
  if (score >= 60) return {
    variant: 'default',
    className: 'bg-score-good',
    label: 'Good'
  };
  if (score >= 40) return {
    variant: 'default',
    className: 'bg-score-average',
    label: 'Average'
  };
  if (score >= 20) return {
    variant: 'default',
    className: 'bg-score-poor',
    label: 'Poor'
  };
  return {
    variant: 'destructive',
    className: 'bg-score-critical',
    label: 'Critical'
  };
}
```

**Changes:**
- Uses custom score colors defined in Tailwind config
- Badge shows status with color coding
- Large score number for prominence
- Maintains existing score status logic

### DimensionChart

**Current:** Custom wrapper around Recharts

**Migrated:**
```tsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';

export default function DimensionChart({ data, title }: DimensionChartProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title || 'Dimension Scores'}</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data}>
            <XAxis
              dataKey="name"
              stroke="hsl(var(--muted-foreground))"
              fontSize={12}
            />
            <YAxis
              stroke="hsl(var(--muted-foreground))"
              fontSize={12}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '0.5rem',
              }}
              labelStyle={{ color: 'hsl(var(--foreground))' }}
            />
            <Bar
              dataKey="score"
              fill="hsl(var(--primary))"
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
```

**Changes:**
- Wraps Recharts in shadcn Card
- Uses CSS variables for colors (adapts to theme)
- Tooltip styled to match theme
- Maintains all Recharts functionality

## Theme Variables

Add to `src/index.css`:

```css
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 222.2 84% 4.9%;
    --primary: 221.2 83.2% 53.3%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 221.2 83.2% 53.3%;
    --radius: 0.5rem;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --card-foreground: 210 40% 98%;
    --popover: 222.2 84% 4.9%;
    --popover-foreground: 210 40% 98%;
    --primary: 217.2 91.2% 59.8%;
    --primary-foreground: 222.2 47.4% 11.2%;
    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 40% 98%;
    --destructive: 0 62.8% 30.6%;
    --destructive-foreground: 210 40% 98%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 224.3 76.3% 48%;
  }
}
```

## Implementation Order

1. **Setup** (Day 1)
   - Install next-themes
   - Install shadcn components via MCP
   - Configure Tailwind with CSS variables
   - Create ThemeProvider wrapper

2. **Layout** (Day 1)
   - Create AppLayout component
   - Create ThemeToggle component
   - Update App.tsx routing
   - Test navigation and theme switching

3. **Pages** (Day 2)
   - Migrate Projects page
   - Migrate ProjectDetail page
   - Test all functionality

4. **Components** (Day 2-3)
   - Migrate ProjectCard
   - Migrate ProjectForm
   - Migrate ScoreCard
   - Migrate DimensionChart

5. **Polish** (Day 3)
   - Test dark/light mode in all components
   - Verify all interactions work
   - Check responsive design
   - Update any remaining custom styles

## Testing Checklist

- [ ] Theme toggle switches between dark/light
- [ ] Default theme is dark on first load
- [ ] All buttons work in both themes
- [ ] Forms validate and submit correctly
- [ ] Cards display properly in both themes
- [ ] Charts render with theme-aware colors
- [ ] Mobile navigation works (dropdown menu)
- [ ] All existing functionality preserved
- [ ] No console errors or warnings
- [ ] Custom score colors visible in both themes

## Notes

- Keep custom `score.*` colors in Tailwind config - they're project-specific
- All existing hooks (useProjects, useMetrics, etc.) remain unchanged
- State management logic unchanged
- API calls unchanged
- Only UI layer is affected
- Backward compatible: can migrate one component at a time
