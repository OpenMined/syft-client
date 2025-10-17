# Adaptive OAuth2 Setup Wizard Plan

## Overview

This document outlines the plan for an intelligent, adaptive wizard that guides users through Google OAuth2 setup with minimal steps. The wizard detects existing configuration and skips unnecessary steps.

## Core Principles

1. **Skip everything that's already working**
2. **Use credentials.json as the gateway** - without it, we can't detect API status
3. **Ask minimal questions** to determine the shortest path
4. **Verify each step** before proceeding

## Flow Diagram

```
START
│
├─ Check Environment
│  ├─ If Colab → "Good news! No credentials.json needed"
│  │  └─ But still need project + APIs → Skip to Project Check
│  │
│  └─ If Local → Continue to credential check
│
├─ Look for credentials.json in all possible locations
│  ├─ ~/.syft/{email}/credentials.json
│  ├─ ~/.syft/credentials.json
│  └─ ./credentials.json
│
├─ If credentials.json EXISTS:
│  │
│  ├─ Validate JSON structure
│  │  └─ If invalid → "Corrupted credentials found. Need to re-download."
│  │
│  ├─ Extract project_id from JSON
│  │
│  ├─ Try to authenticate with these credentials
│  │  ├─ Success → Go to API Status Check
│  │  └─ Failure → "Credentials expired or revoked. Need to re-download."
│  │
│  └─ API Status Check (we can now make authenticated calls):
│     ├─ Check Gmail API → ✓ or ✗
│     ├─ Check Drive API → ✓ or ✗
│     ├─ Check Sheets API → ✓ or ✗
│     └─ Check Forms API → ✓ or ✗
│
│     Results:
│     ├─ All ✓ → "Everything working! You're ready to go."
│     ├─ Some ✗ → "Found issues. Let's fix them:"
│     │  └─ Show ONLY the steps needed:
│     │     - "Enable Forms API: [URL]"
│     │     - "Enable Sheets API: [URL]"
│     └─ All ✗ → "APIs not enabled. Let's fix this:" → Step 4
│
└─ If credentials.json MISSING:
   │
   └─ "No OAuth2 credentials found. Let's set them up!"
      │
      └─ "Have you created a Google Cloud project for Syft before? (y/n)"
         │
         ├─ YES → Fast Track Path
         │  │
         │  └─ "Do you remember your Google Cloud project ID? (y/n)"
         │     │
         │     ├─ YES → "Enter your project ID:"
         │     │  └─ Jump directly to downloading credentials (Step 6)
         │     │     Show URL: console.cloud.google.com/apis/credentials?project={PROJECT_ID}
         │     │
         │     └─ NO → "Let's find your existing project:"
         │        ├─ Show URL: console.cloud.google.com/projects
         │        ├─ "Look for projects named like 'syft-client' or similar"
         │        └─ "Enter the project ID you found:"
         │           └─ Jump to Step 6 with that project
         │
         └─ NO → Full Wizard Path (Steps 1-7)
```

## Full Wizard Steps (When Starting Fresh)

### Step 1: Create Project

- URL: `console.cloud.google.com/projectcreate`
- Instructions:
  - "Name it something like 'syft-client'"
  - "Click CREATE"
  - "Wait ~30 seconds for creation"
- Wait: "Press Enter when created..."

### Step 2: Select Project

- Instructions:
  - "Click the dropdown at the top of Google Cloud Console"
  - "Select your new project"
  - "Make sure it's selected before continuing"
- Wait: "Press Enter when selected..."

### Step 3: Get Project ID

- Instructions:
  - "The project ID is shown in the dropdown"
  - "It's like 'syft-client-123456'"
  - "It's different from the project name"
- Input: "Enter project ID:" → Store for URL building

### Step 4: Enable APIs

For each API, show URL with project_id:

- Gmail: `console.cloud.google.com/marketplace/product/google/gmail.googleapis.com?project={ID}`
- Drive: `console.cloud.google.com/marketplace/product/google/drive.googleapis.com?project={ID}`
- Sheets: `console.cloud.google.com/marketplace/product/google/sheets.googleapis.com?project={ID}`
- Forms: `console.cloud.google.com/marketplace/product/google/forms.googleapis.com?project={ID}`

Note: "📍 API tends to flicker for 5-10 seconds before enabling"
Wait: "Press Enter after enabling all APIs..."

### Step 5: OAuth Consent Screen

- URL: `console.cloud.google.com/auth/overview/create?project={ID}`
- Sub-steps:
  1. "Enter app name (e.g., 'Syft Client')"
  2. "Enter support email (your email)"
  3. "Select 'External' user type"
  4. "Add contact information"
  5. "Save and continue through all sections"
- Wait: "Press Enter when consent screen is configured..."

### Step 6: Create OAuth Credentials

- URL: `console.cloud.google.com/apis/credentials?project={ID}`
- Instructions:
  1. "Click '+ CREATE CREDENTIALS'"
  2. "Choose 'OAuth client ID'"
  3. "Select 'Desktop app' as application type"
  4. "Name it 'Syft Client'"
  5. "Click 'CREATE'"

### Step 7: Download & Place Credentials

- Instructions:
  - "Click the download icon next to your new credential"
  - "Save as 'credentials.json'"
- Input: "Enter path to downloaded file:"
  - Copy to `~/.syft/{email}/credentials.json`
  - Verify it's valid JSON

## Fast Track Paths

### Path A: Existing Project, Lost Credentials

1. Ask for project ID
2. Jump to Step 6 with direct URL
3. Download new credentials

### Path B: Have Credentials, Some APIs Disabled

1. Parse credentials for project_id
2. Test each API
3. Show only URLs for disabled APIs
4. Verify they're working

### Path C: Colab User

1. Skip credential download
2. Check if project exists
3. Guide through project creation if needed
4. Enable APIs only

## Smart URL Building

Always build URLs with:

- `?project={project_id}` when known
- `&authuser={email}` for account switching
- Use marketplace URLs for better UX

Example: `https://console.cloud.google.com/marketplace/product/google/gmail.googleapis.com?authuser=user@gmail.com&project=syft-client-123456`

## Post-Setup Verification

After any path completes:

1. Load credentials.json
2. Authenticate
3. Test each API with actual calls
4. Show final status:
   ```
   ✓ Gmail API working
   ✓ Drive API working
   ✓ Sheets API working
   ✓ Forms API working
   ✅ Setup complete!
   ```

## Error Recovery States

### Common Issues to Handle:

1. **Wrong credentials type**: Service account instead of OAuth
2. **Wrong project**: Credentials from different project
3. **Expired tokens**: Need to re-authenticate
4. **API quota exceeded**: Wait and retry
5. **Browser auth failed**: Provide manual token entry

## Implementation Notes

### State Detection Functions Needed:

- `find_credentials()` - Search all possible locations
- `validate_credentials_json()` - Check structure and type
- `test_api_access()` - Try actual API calls
- `extract_project_id()` - Get from credentials.json

### Wizard State Class:

```python
class WizardState:
    has_credentials: bool
    project_id: Optional[str]
    api_status: Dict[str, bool]  # {gmail: True, drive: False, ...}
    environment: Environment
    credentials_path: Optional[Path]
```

### Step Functions:

Each step should:

1. Check if needed via state
2. Execute if needed
3. Verify success
4. Update state
5. Return next needed step

This adaptive approach ensures users do only what's necessary to get working!
