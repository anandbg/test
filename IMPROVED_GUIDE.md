# 🚀 Complete Guide: Build & Launch a Mobile App with AI (Production-Ready)

> **From ideation to App Store & Play Store — without writing code manually**

---

## 📋 Table of Contents

1. [Prerequisites](#-prerequisites)
2. [Step 1: Find a Viral App Idea](#-step-1--find-a-viral-app-idea)
3. [Step 2: Design Inspiration (Mobbin + Figma)](#-step-2--design-inspiration-mobbin--figma)
4. [Step 3: Build the App's "Brain" (Documentation)](#-step-3--build-the-apps-brain-documentation)
5. [Step 4: Create Base Project (Expo)](#-step-4--create-base-project-expo)
6. [Step 5: Build Features with Cursor Composer](#-step-5--build-features-with-cursor-composer)
7. [Step 6: Set Up Backend (Supabase)](#-step-6--set-up-backend-supabase)
8. [Step 7: Build Core Features](#-step-7--build-core-features)
9. [Step 8: Improve UI with Mobbin](#-step-8--improve-ui-with-mobbin)
10. [Step 9: Integrate DeepSeek API](#-step-9--integrate-deepseek-api)
11. [Step 10: Testing & QA](#-step-10--testing--qa)
12. [Step 11: Publish to App Stores](#-step-11--publish-to-app-stores)
13. [Step 12: Post-Launch](#-step-12--post-launch)

---

## ✅ Prerequisites

Before starting, ensure you have:

### Required Accounts
- [ ] **Expo Account** - [expo.dev](https://expo.dev) (free)
- [ ] **Supabase Account** - [supabase.com](https://supabase.com) (free tier available)
- [ ] **DeepSeek API Key** - [deepseek.com](https://deepseek.com)
- [ ] **Apple Developer Account** - $99/year (for iOS publishing)
- [ ] **Google Play Developer Account** - $25 one-time (for Android publishing)

### Required Software
- [ ] **Node.js 18+** - [nodejs.org](https://nodejs.org)
- [ ] **Git** - [git-scm.com](https://git-scm.com)
- [ ] **Expo Go App** - Install on your phone ([iOS](https://apps.apple.com/app/expo-go/id982107779) | [Android](https://play.google.com/store/apps/details?id=host.exp.exponent))

### Recommended Tools
- **Cursor IDE** - [cursor.sh](https://cursor.sh) (AI-powered code editor)
- **Figma** - [figma.com](https://figma.com) (for design)
- **Mobbin** - [mobbin.com](https://mobbin.com) (design inspiration)

### Knowledge Base
- Basic understanding of React/React Native (helpful but not required)
- Familiarity with terminal/command line
- Understanding of REST APIs (conceptual)

---

## 💰 Cost Breakdown

| Service | Cost | Frequency |
|---------|------|-----------|
| Apple Developer | $99 | Per year |
| Google Play Developer | $25 | One-time |
| Supabase | $0-25 | Per month (free tier usually sufficient) |
| DeepSeek API | Pay-per-use | Varies by usage |
| Expo EAS | $0-29 | Per month (1 free build/month) |
| **Total Minimum** | **~$150** | First year |
| **Ongoing** | **~$50-100** | Per year |

---

## 🧠 Step 1 — Find a Viral App Idea

**Goal:** Build something people will actually use and share.

### Method:

1. **Identify a common pain point** — emotional or frustrating
   - Examples: distractions, productivity, organization, social connection
   - Ask: "What problem do I face daily?"

2. **Keep it simple** — core purpose explainable in 3 words
   - ❌ Bad: "A comprehensive productivity suite with AI integration"
   - ✅ Good: "Focus on tasks"

3. **Make it shareable** — users should naturally want to share it
   - Social features (optional)
   - Achievement system
   - Beautiful UI that users want to show off

### 💡 Example App: "DeepWork AI"

A productivity tool that helps users:
- Sort and prioritize tasks
- Focus on one task at a time (deep work)
- Chat with AI to add new tasks easily

**Why it works:**
- Solves real problem (task overwhelm)
- Simple core concept
- AI feature is shareable/demoable

---

## 🎨 Step 2 — Design Inspiration (Mobbin + Figma)

**Goal:** Use proven UI/UX from top apps.

### Process:

1. **Browse Mobbin**
   - Go to [Mobbin.com](http://mobbin.com)
   - Browse 100k+ design screenshots
   - Filter by category (e.g., Productivity, Health, Social)

2. **Select Design Flow**
   - Choose an app with similar functionality
   - Study their screen flow
   - Note: Navigation patterns, color schemes, typography

3. **Copy to Figma**
   - Click **Copy** on Mobbin screenshots
   - Open **Figma** → Create new file
   - Paste (Ctrl + V / Cmd + V)
   - Clean up: Keep only screens you'll use
   - Organize: Name layers clearly

4. **Extract Design Tokens**
   - Colors (primary, secondary, background)
   - Typography (font families, sizes)
   - Spacing (margins, padding)
   - Component patterns (buttons, cards, inputs)

### 💡 Why This Works:
- Don't reinvent the wheel
- Use tested designs
- Let AI generate code from proven patterns

---

## 🧩 Step 3 — Build the App's "Brain" (Documentation)

**Goal:** Give Cursor AI clear context so it builds your app correctly.

### Create Project Structure:

```bash
mkdir DeepworkAI
cd DeepworkAI
mkdir docs
```

### Create `docs/Context.md`:

Use this template and customize for your app:

```markdown
# App Context Documentation

## 1. App Overview
- **Name:** DeepWork AI
- **Purpose:** Help users focus on one task at a time with AI assistance
- **Target Users:** Professionals, students, anyone struggling with task management
- **Core Value:** Reduce overwhelm, increase focus, AI-powered task creation

## 2. User Stories
- As a user, I want to create tasks quickly so I can capture ideas instantly
- As a user, I want to prioritize tasks so I know what to focus on
- As a user, I want to track focus time so I can measure productivity
- As a user, I want to chat with AI so I can add multiple tasks naturally
- As a user, I want to see my progress so I stay motivated

## 3. Technical Stack
- **Frontend:** React Native + Expo + TypeScript
- **Backend:** Supabase (PostgreSQL + Auth + Storage + Realtime)
- **AI:** DeepSeek API
- **State Management:** Zustand (lightweight, simple)
- **Navigation:** Expo Router (file-based routing)
- **Styling:** React Native StyleSheet + custom theme

## 4. Database Schema

```sql
-- Tasks table
CREATE TABLE tasks (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  priority TEXT CHECK (priority IN ('low', 'medium', 'high')) DEFAULT 'medium',
  deadline TIMESTAMP,
  completed BOOLEAN DEFAULT false,
  focus_time_minutes INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index for faster queries
CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_completed ON tasks(completed);

-- Row Level Security (RLS) Policies
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;

-- Users can only see their own tasks
CREATE POLICY "Users can view own tasks"
  ON tasks FOR SELECT
  USING (auth.uid() = user_id);

-- Users can insert their own tasks
CREATE POLICY "Users can insert own tasks"
  ON tasks FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Users can update their own tasks
CREATE POLICY "Users can update own tasks"
  ON tasks FOR UPDATE
  USING (auth.uid() = user_id);

-- Users can delete their own tasks
CREATE POLICY "Users can delete own tasks"
  ON tasks FOR DELETE
  USING (auth.uid() = user_id);
```

## 5. API Endpoints

### Supabase (Auto-generated)
- `POST /rest/v1/tasks` - Create task
- `GET /rest/v1/tasks` - List user tasks (filtered by RLS)
- `PATCH /rest/v1/tasks?id=eq.{id}` - Update task
- `DELETE /rest/v1/tasks?id=eq.{id}` - Delete task

### DeepSeek API
- `POST https://api.deepseek.com/v1/chat/completions` - AI chat

## 6. Screen Flow

```
1. Splash Screen
   ↓
2. Onboarding (first time only)
   ↓
3. Authentication
   ├─ Sign Up
   └─ Sign In
   ↓
4. Dashboard (Task List)
   ├─ Task Card (tap) → Task Detail
   ├─ Add Task Button → Create Task Modal
   ├─ AI Chat Button → AI Chat Screen
   └─ Focus Timer Button → Timer Screen
   ↓
5. Task Detail Screen
   ├─ Edit Task
   ├─ Mark Complete
   ├─ Delete Task
   └─ Start Focus Timer
   ↓
6. Focus Timer Screen
   ├─ Start/Stop Timer
   ├─ Task Display
   └─ Complete Task
```

## 7. Key Features

### Authentication
- Email/password signup
- Email verification (handled by Supabase)
- Password reset
- Persistent session

### Task Management
- Create task (title, description, priority, deadline)
- List tasks (filtered by user, sorted by priority/date)
- Update task
- Delete task
- Mark complete/incomplete
- Task search

### Focus Timer
- Pomodoro technique (25 min work, 5 min break)
- Customizable timer duration
- Track focus time per task
- Background timer support

### AI Chat
- Natural language task creation
- Multi-task extraction from single message
- Context-aware suggestions
- Chat history (optional)

### Progress Tracking
- Daily/weekly focus time stats
- Completed tasks count
- Streak counter
- Visual progress charts

## 8. Design System

### Colors
- Primary: #6366F1 (Indigo)
- Secondary: #8B5CF6 (Purple)
- Success: #10B981 (Green)
- Warning: #F59E0B (Amber)
- Error: #EF4444 (Red)
- Background: #F9FAFB (Light Gray)
- Text: #111827 (Dark Gray)

### Typography
- Headings: System Bold (SF Pro / Roboto)
- Body: System Regular
- Sizes: 12, 14, 16, 20, 24, 32

### Spacing
- Base unit: 4px
- Common: 8, 12, 16, 24, 32, 48

## 9. Folder Structure

```
DeepworkAI/
├── app/                    # Expo Router pages
│   ├── (auth)/
│   │   ├── login.tsx
│   │   └── signup.tsx
│   ├── (tabs)/
│   │   ├── index.tsx       # Dashboard
│   │   ├── timer.tsx
│   │   └── profile.tsx
│   └── _layout.tsx
├── components/
│   ├── TaskCard.tsx
│   ├── TaskForm.tsx
│   ├── Timer.tsx
│   └── AIChat.tsx
├── lib/
│   ├── supabase.ts         # Supabase client
│   ├── deepseek.ts         # DeepSeek API client
│   └── utils.ts
├── store/
│   └── useTaskStore.ts     # Zustand store
├── types/
│   └── index.ts            # TypeScript types
├── docs/
│   └── Context.md          # This file
├── .env                    # Environment variables (gitignored)
├── .gitignore
├── app.json
├── package.json
└── tsconfig.json
```

## 10. Environment Variables

```bash
# .env (DO NOT COMMIT)
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_anon_key
DEEPSEEK_API_KEY=your_deepseek_api_key
```

## 11. Development Priorities

### MVP (Must Have)
1. Authentication
2. Basic task CRUD
3. Simple timer
4. AI chat for task creation

### Phase 2 (Nice to Have)
1. Task prioritization UI
2. Focus time tracking
3. Progress charts
4. Task search

### Phase 3 (Future)
1. Social features
2. Team collaboration
3. Advanced analytics
4. Widgets
```

### Generate Context with ChatGPT:

1. Go to **ChatGPT**
2. Describe your app idea
3. Use this prompt:

```
I'm building a productivity app using React Native, Expo, Supabase, and DeepSeek API.
I need a detailed Context.md file that includes:
- App overview and user stories
- Complete database schema with SQL
- Screen flow diagram
- API endpoints
- Folder structure
- Design system
- Development priorities

Please generate this in Markdown format, following the structure I'll provide.
```

4. Copy ChatGPT's response into `docs/Context.md`
5. Customize for your specific app

### Tag in Cursor:

- In Cursor, use `@Context.md` to reference this file
- AI will always use it as context for code generation

---

## ⚙️ Step 4 — Create Base Project (Expo)

**Goal:** Generate a working app skeleton.

### Commands:

```bash
# Create Expo app with router
npx create-expo-app@latest DeepworkAI --template expo-router

# Navigate to project
cd DeepworkAI

# Move docs folder into project (if created separately)
# mv ../docs ./docs

# Install essential dependencies
npm install @supabase/supabase-js zustand @react-native-async-storage/async-storage

# Install TypeScript types
npm install --save-dev @types/react @types/react-native

# Create .env file (DO NOT COMMIT)
touch .env
echo "# Add your keys here" > .env

# Create .env.example (safe to commit)
cat > .env.example << EOF
SUPABASE_URL=
SUPABASE_ANON_KEY=
DEEPSEEK_API_KEY=
EOF

# Update .gitignore
echo ".env" >> .gitignore
echo ".env.local" >> .gitignore
echo "node_modules/" >> .gitignore

# Start development server
npx expo start
```

### Verify Setup:

1. Scan QR code with **Expo Go** app on your phone
2. You should see a blank app running
3. ✅ Base project is ready

### Project Structure Check:

```
DeepworkAI/
├── app/
├── components/
├── lib/
├── store/
├── types/
├── docs/          # Your Context.md goes here
├── .env           # Your secrets (gitignored)
└── package.json
```

---

## 🤖 Step 5 — Build Features with Cursor Composer

**Goal:** Use natural language to generate working app components.

### Process:

1. **Open Cursor Composer**
   - Press `Ctrl + i` (Windows/Linux) or `Cmd + i` (Mac)
   - Or click Composer icon

2. **Reference Context**
   ```
   Use @Context.md to build the app step by step.
   Start with authentication flow.
   ```

3. **Review Development Plan**
   - Cursor will generate a plan
   - Review and accept/modify as needed
   - Break into smaller tasks if needed

4. **Execute Tasks Sequentially**
   - "Build authentication screens (login and signup)"
   - "Set up Supabase client configuration"
   - "Create task list dashboard"
   - "Build task creation form"
   - "Implement focus timer component"
   - "Add AI chat interface"

5. **Handle Errors**
   - Copy error message
   - Paste into Composer: "Fix this error: [paste error]"
   - Cursor will analyze and fix automatically

### Tips:

- **Be Specific:** "Create a task card component with title, priority badge, and complete button"
- **Iterate:** Build one feature at a time, test, then move on
- **Use References:** Always tag `@Context.md` for consistency

---

## 🗄️ Step 6 — Set Up Backend (Supabase)

**Goal:** Add authentication + database.

### 1. Create Supabase Project

1. Go to [Supabase.com](https://supabase.com)
2. Click **New Project**
3. Fill in:
   - Name: `deepwork-ai` (or your app name)
   - Database Password: (save this securely)
   - Region: Choose closest to your users
4. Wait 2-3 minutes for setup

### 2. Get API Credentials

1. Go to **Settings** → **API**
2. Copy:
   - **Project URL** → `SUPABASE_URL`
   - **anon public key** → `SUPABASE_ANON_KEY`
3. Add to `.env`:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here
```

### 3. Set Up Database Schema

1. Go to **SQL Editor** in Supabase dashboard
2. Run the SQL from your `Context.md` (Step 4 - Database Schema)
3. Verify tables created: Go to **Table Editor**

### 4. Configure Authentication

1. Go to **Authentication** → **Providers**
2. Enable **Email** provider
3. Configure email templates (optional):
   - Go to **Authentication** → **Email Templates**
   - Customize welcome email, password reset, etc.

### 5. Test Connection

In Cursor Composer, ask:

```
Create a Supabase client configuration file at lib/supabase.ts
Use environment variables from .env
Test the connection by logging the client.
```

### 6. Verify Setup

```typescript
// lib/supabase.ts should look like:
import { createClient } from '@supabase/supabase-js';
import Constants from 'expo-constants';

const supabaseUrl = Constants.expoConfig?.extra?.supabaseUrl || process.env.SUPABASE_URL;
const supabaseAnonKey = Constants.expoConfig?.extra?.supabaseAnonKey || process.env.SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing Supabase environment variables');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
```

✅ Authentication and database are now ready!

---

## 🧱 Step 7 — Build Core Features

**Goal:** Task management & focus timer.

### Feature 1: Authentication

In Cursor Composer:

```
Build authentication screens:
1. Login screen with email/password
2. Signup screen with email/password
3. Use Supabase auth
4. Handle loading and error states
5. Navigate to dashboard on success
```

### Feature 2: Task Management

```
Build task management:
1. Task list screen showing user's tasks
2. Create task form (title, description, priority, deadline)
3. Update task functionality
4. Delete task with confirmation
5. Mark task as complete/incomplete
6. Use Zustand for state management
```

### Feature 3: Focus Timer

```
Build focus timer:
1. Timer component with start/stop/pause
2. Pomodoro technique (25 min work, 5 min break)
3. Visual countdown display
4. Background timer support
5. Track focus time and save to task
```

### Testing Each Feature:

After each feature:
1. Test on Expo Go app
2. Verify database updates in Supabase dashboard
3. Check for errors in terminal
4. Fix issues before moving on

✅ Core features are now functional (basic UI)

---

## 🎨 Step 8 — Improve UI with Mobbin

**Goal:** Make the app look professional.

### Process:

1. **Collect Design Screenshots**
   - Browse Mobbin for similar apps
   - Screenshot 5-10 screens you like
   - Focus on: Colors, spacing, typography, components

2. **Paste into Cursor**
   - Copy screenshots (Ctrl+C)
   - Paste into Cursor Composer (Ctrl+V)
   - Or save images and reference them

3. **Apply Design**

   ```
   Use these design screenshots as inspiration for my app.
   Apply the color scheme, typography, and component styles.
   Make the UI modern and polished.
   Keep functionality intact.
   ```

4. **Iterate**

   ```
   Improve the task card design to match the inspiration.
   Add subtle shadows, better spacing, and modern colors.
   ```

### Design Improvements to Request:

- Consistent color scheme
- Better typography hierarchy
- Improved spacing and padding
- Modern button styles
- Card designs with shadows
- Loading states
- Empty states
- Error states

✅ App now looks professional and polished!

---

## 🧠 Step 9 — Integrate DeepSeek API

**Goal:** Add AI-assisted task creation.

### 1. Get DeepSeek API Key

1. Go to [DeepSeek.com](https://deepseek.com)
2. Sign up / Log in
3. Navigate to API section
4. Generate API key
5. Copy key

### 2. Add to Environment

```bash
# Add to .env
DEEPSEEK_API_KEY=your-deepseek-api-key-here
```

### 3. Create API Client

In Cursor Composer:

```
Create a DeepSeek API client at lib/deepseek.ts:
1. Function to send chat messages
2. Extract tasks from natural language
3. Return structured task data (title, description, priority)
4. Handle errors gracefully
5. Use environment variable for API key
```

### 4. Build AI Chat Interface

```
Build AI chat feature:
1. Chat screen with message history
2. Input field for user messages
3. Send button
4. Display AI responses
5. Parse AI response to extract tasks
6. Auto-create tasks from AI response
7. Show loading state during API call
```

### 5. Test AI Feature

1. Type: "Buy groceries: milk, eggs, bread"
2. AI should extract 3 tasks
3. Verify tasks appear in dashboard

### Example Implementation:

```typescript
// lib/deepseek.ts
export async function chatWithAI(message: string) {
  const response = await fetch('https://api.deepseek.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${process.env.DEEPSEEK_API_KEY}`,
    },
    body: JSON.stringify({
      model: 'deepseek-chat',
      messages: [
        {
          role: 'system',
          content: 'You are a task extraction assistant. Extract tasks from user messages and return as JSON array with title, description, and priority fields.'
        },
        {
          role: 'user',
          content: message
        }
      ],
    }),
  });

  if (!response.ok) {
    throw new Error('AI API call failed');
  }

  const data = await response.json();
  return data.choices[0].message.content;
}
```

✅ AI chat feature is now working!

---

## 🧪 Step 10 — Testing & QA

**Goal:** Ensure app works perfectly before publishing.

### Testing Checklist:

#### Authentication
- [ ] Sign up with new email
- [ ] Verify email received
- [ ] Login with correct credentials
- [ ] Login with wrong password (error handling)
- [ ] Password reset flow
- [ ] Logout functionality
- [ ] Session persistence (app restart)

#### Task Management
- [ ] Create task (all fields)
- [ ] View task list
- [ ] Update task
- [ ] Delete task
- [ ] Mark complete/incomplete
- [ ] Filter by priority
- [ ] Search tasks
- [ ] Handle empty state

#### Focus Timer
- [ ] Start timer
- [ ] Pause timer
- [ ] Stop timer
- [ ] Timer completes (notification)
- [ ] Focus time saved to task
- [ ] Background timer (app minimized)

#### AI Chat
- [ ] Send message
- [ ] Receive AI response
- [ ] Extract tasks from response
- [ ] Handle API errors
- [ ] Handle network errors
- [ ] Loading states

#### Performance
- [ ] App loads quickly (< 3 seconds)
- [ ] Smooth scrolling (60 FPS)
- [ ] No memory leaks
- [ ] Works on low-end devices
- [ ] Battery usage reasonable

#### Edge Cases
- [ ] Offline mode (graceful degradation)
- [ ] Slow network (loading states)
- [ ] Invalid input handling
- [ ] Large task lists (pagination)
- [ ] Special characters in tasks

### Testing Tools:

1. **Expo DevTools**
   - Open: `http://localhost:19002`
   - Check logs, network requests

2. **React Native Debugger**
   - Install: `npm install -g react-native-debugger`
   - Debug JavaScript code

3. **Device Testing**
   - Test on iOS device
   - Test on Android device
   - Test on different screen sizes

### Fix Issues:

For each bug found:
1. Document the issue
2. Reproduce it
3. Ask Cursor to fix: "Fix this bug: [description]"
4. Re-test
5. Mark as resolved

✅ App is tested and ready for publishing!

---

## 🚀 Step 11 — Publish to App Stores

**Goal:** Deploy to App Store & Play Store using Expo EAS.

### Pre-Publishing Checklist:

- [ ] All features tested and working
- [ ] No console errors or warnings
- [ ] Privacy Policy created and hosted (required)
- [ ] App icons generated (all sizes)
- [ ] Screenshots prepared (multiple device sizes)
- [ ] App Store description written
- [ ] Keywords researched (ASO)
- [ ] Terms of Service (recommended)

### 1. Install EAS CLI

```bash
npm install -g eas-cli
```

### 2. Login to Expo

```bash
eas login
```

Use your [expo.dev](https://expo.dev) credentials.

### 3. Configure App Metadata

Update `app.json`:

```json
{
  "expo": {
    "name": "DeepWork AI",
    "slug": "deepwork-ai",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
    "userInterfaceStyle": "light",
    "splash": {
      "image": "./assets/splash.png",
      "resizeMode": "contain",
      "backgroundColor": "#6366F1"
    },
    "ios": {
      "bundleIdentifier": "com.yourcompany.deepworkai",
      "buildNumber": "1",
      "supportsTablet": true,
      "infoPlist": {
        "NSUserTrackingUsageDescription": "We use this to improve your experience."
      }
    },
    "android": {
      "package": "com.yourcompany.deepworkai",
      "versionCode": 1,
      "adaptiveIcon": {
        "foregroundImage": "./assets/adaptive-icon.png",
        "backgroundColor": "#6366F1"
      },
      "permissions": []
    },
    "web": {
      "favicon": "./assets/favicon.png"
    },
    "extra": {
      "supabaseUrl": process.env.SUPABASE_URL,
      "supabaseAnonKey": process.env.SUPABASE_ANON_KEY
    }
  }
}
```

### 4. Configure EAS Build

```bash
eas build:configure
```

Choose:
- **Platform:** All (iOS + Android)
- **Build profile:** Production

### 5. Generate App Icons & Splash

```bash
# Install icon generator
npm install -g @expo/cli

# Generate icons (requires icon.png 1024x1024)
npx expo install @expo/image-utils
```

Or use online tools:
- [AppIcon.co](https://www.appicon.co)
- [IconKitchen](https://icon.kitchen)

### 6. Build for iOS

**Prerequisites:**
- Apple Developer account ($99/year)
- Mac computer (for local builds) OR use EAS cloud builds

```bash
# Build iOS app
eas build --platform ios

# Follow prompts:
# - Choose: "Build for App Store"
# - Wait for build to complete (10-20 minutes)
```

**After build completes:**

```bash
# Submit to App Store
eas submit --platform ios

# Follow prompts:
# - App Store Connect credentials
# - App metadata
```

**App Store Connect Setup:**
1. Go to [App Store Connect](https://appstoreconnect.apple.com)
2. Create new app
3. Fill in:
   - Name, description, keywords
   - Screenshots (required: 6.5" and 5.5" displays)
   - Privacy Policy URL (required)
   - Support URL
   - Marketing URL (optional)
4. Submit for review
5. Wait 1-7 days for approval

### 7. Build for Android

**Prerequisites:**
- Google Play Developer account ($25 one-time)

```bash
# Build Android app
eas build --platform android

# Follow prompts:
# - Choose: "Build for Play Store"
# - Wait for build to complete (10-20 minutes)
```

**After build completes:**

1. Download the AAB file from EAS dashboard
2. Go to [Google Play Console](https://play.google.com/console)
3. Create new app
4. Fill in:
   - App name, description, graphics
   - Screenshots (required: phone, 7" tablet, 10" tablet)
   - Privacy Policy URL (required)
   - Content rating questionnaire
5. Upload AAB file
6. Submit for review
7. Wait 1-3 days for approval

### 8. Store Listing Requirements

#### App Store (iOS)
- **Screenshots:** 6.5" display (required), 5.5" display (optional)
- **App Preview Video:** Optional but recommended
- **Description:** Up to 4000 characters
- **Keywords:** 100 characters max
- **Privacy Policy:** Required URL
- **Support URL:** Required
- **Age Rating:** Complete questionnaire

#### Play Store (Android)
- **Screenshots:** Phone (2-8), 7" tablet (1-8), 10" tablet (1-8)
- **Feature Graphic:** 1024x500px
- **Description:** Up to 4000 characters
- **Short Description:** 80 characters
- **Privacy Policy:** Required URL
- **Content Rating:** Complete questionnaire
- **Data Safety:** Complete form

### 9. Privacy Policy Template

Create a privacy policy (required by both stores). Host it on:
- Your website
- GitHub Pages (free)
- Notion (public page)

**Minimum Required Sections:**
- What data you collect
- How you use data
- Third-party services (Supabase, DeepSeek)
- User rights
- Contact information

✅ App is published and pending review!

---

## 📊 Step 12 — Post-Launch

**Goal:** Monitor, improve, and grow your app.

### 1. Monitoring Setup

#### Error Tracking
```bash
# Install Sentry
npm install @sentry/react-native
```

Configure Sentry for crash reporting.

#### Analytics
- **Expo Analytics:** Built-in, automatic
- **Mixpanel:** User behavior tracking
- **Firebase Analytics:** Free alternative

### 2. User Feedback

- **In-App Feedback:** Add feedback button
- **App Store Reviews:** Respond to reviews
- **Email Support:** Provide support email
- **Social Media:** Create Twitter/Instagram for app

### 3. Iteration Strategy

- **Week 1:** Monitor crashes, fix critical bugs
- **Week 2-4:** Collect user feedback, prioritize features
- **Month 2+:** Release updates with improvements

### 4. Marketing

- **ASO (App Store Optimization):**
  - Optimize keywords
  - A/B test screenshots
  - Encourage reviews
- **Content Marketing:**
  - Blog posts
  - Social media
  - Product Hunt launch
- **Paid Ads:** (Optional)
  - Google Ads
  - Facebook Ads
  - Apple Search Ads

### 5. Metrics to Track

- **Downloads:** Total and daily
- **Active Users:** DAU, MAU
- **Retention:** Day 1, Day 7, Day 30
- **Crashes:** Crash-free rate
- **Reviews:** Average rating, review count
- **Revenue:** (if monetized)

### 6. Update Releases

```bash
# Update version in app.json
# Build new version
eas build --platform all

# Submit updates
eas submit --platform ios
eas submit --platform android
```

✅ App is live and growing!

---

## 🎯 Summary Table

| Stage | Tool | Purpose | Time Estimate |
|-------|------|---------|---------------|
| 1. Idea | ChatGPT | Find viral idea | 1-2 hours |
| 2. Design | Mobbin + Figma | Copy proven UI | 2-3 hours |
| 3. Context | Markdown | Define blueprint | 2-4 hours |
| 4. Setup | Expo | Scaffold project | 30 min |
| 5. Build | Cursor AI | Generate code | 10-20 hours |
| 6. Backend | Supabase | Auth + DB | 1-2 hours |
| 7. Core Features | Cursor | Task mgmt, timer | 5-10 hours |
| 8. UI Polish | Mobbin + Cursor | Apply designs | 3-5 hours |
| 9. AI Integration | DeepSeek | Smart task input | 2-3 hours |
| 10. Testing | Manual + Tools | QA & fixes | 4-8 hours |
| 11. Publish | Expo EAS | App Store + Play Store | 2-4 hours |
| 12. Post-Launch | Monitoring | Growth & iteration | Ongoing |

**Total Time:** ~30-60 hours (depending on complexity)

---

## 🆘 Troubleshooting

### Common Issues

#### "Module not found"
```bash
# Clear cache and reinstall
rm -rf node_modules
npm install
npx expo start --clear
```

#### "Supabase connection failed"
- Check `.env` file exists
- Verify environment variables are correct
- Restart Expo server

#### "Build failed on EAS"
- Check `app.json` for errors
- Verify all required fields filled
- Check EAS build logs for specific error

#### "App rejected by App Store"
- Read rejection reason carefully
- Common issues: Missing privacy policy, incomplete metadata
- Fix and resubmit

---

## 📚 Additional Resources

- **Expo Docs:** https://docs.expo.dev
- **Supabase Docs:** https://supabase.com/docs
- **React Native Docs:** https://reactnative.dev/docs/getting-started
- **App Store Guidelines:** https://developer.apple.com/app-store/review/guidelines/
- **Play Store Policies:** https://play.google.com/about/developer-content-policy/
- **ASO Guide:** https://www.apptweak.com/en/blog/app-store-optimization-guide

---

## ✅ Final Checklist

Before considering your app "complete":

- [ ] All features working
- [ ] Tested on iOS and Android
- [ ] No critical bugs
- [ ] Privacy policy published
- [ ] App icons and screenshots ready
- [ ] Store listings complete
- [ ] Error tracking configured
- [ ] Analytics set up
- [ ] User feedback mechanism in place
- [ ] Marketing plan ready

---

**Congratulations!** 🎉 You've built and launched a mobile app using AI tools. Now iterate, improve, and grow your user base!
