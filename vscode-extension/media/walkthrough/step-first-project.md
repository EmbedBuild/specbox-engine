## Onboard Your First Project

Now that SpecBox Engine is installed, set up your project:

### 1. Create CLAUDE.md
Copy the engine template and customize it. The path depends on where you cloned the engine (check `specbox.enginePath` in settings):
```
cp <engine-path>/templates/CLAUDE.md.template CLAUDE.md
```

> **Tip:** The extension auto-detects the engine in common locations like `~/specbox-engine`, `~/Desktop/specbox-engine`, or wherever you configured `specbox.enginePath`.

### 2. Start developing
Open Claude Code and use the skills:

```
/prd "User authentication with OAuth2"
```
Creates a Product Requirements Document with testable acceptance criteria.

```
/plan PROJECT-42
```
Generates a technical implementation plan with UI designs.

```
/implement auth_plan
```
Autopilot: implements the plan end-to-end with quality gates.

### 3. Monitor quality
The status bar shows the engine version — click it anytime to see the health of your setup.

Click **Open Onboarding Wizard** for a guided walkthrough in your current project.
