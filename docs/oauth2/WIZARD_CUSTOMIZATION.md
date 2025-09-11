# Wizard Customization Guide

## Overview

The wizard system in syft-client allows for environment-specific UI customization. Steps are defined once and can be rendered differently for terminal, Jupyter notebooks, or web interfaces.

## Step Definition Format

### Basic Step Structure

```python
class WizardStep:
    """Single step in a wizard flow"""
    
    def __init__(
        self,
        id: str,
        title: str,
        content: Dict[str, Any],
        action: Optional[Callable] = None,
        validation: Optional[Callable] = None
    ):
        self.id = id
        self.title = title
        self.content = content
        self.action = action
        self.validation = validation
```

### Content Format

```python
step = WizardStep(
    id="create_project",
    title="Create Google Cloud Project",
    content={
        "terminal": {
            "text": "1. Go to Google Cloud Console\n2. Click 'Create Project'\n3. Name it 'syft-oauth'",
            "prompt": "Press Enter when complete...",
            "url": "https://console.cloud.google.com/",
            "style": "default"
        },
        "jupyter": {
            "markdown": """
### Create Google Cloud Project

1. Open the [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Create Project**
3. Name your project `syft-oauth`
4. Click **Create**

<details>
<summary>📸 Visual Guide</summary>

![Step 1](data:image/png;base64,...)
![Step 2](data:image/png;base64,...)
</details>
""",
            "input_widget": "button",
            "button_text": "I've created the project ✓"
        },
        "colab": {
            "html": """
<div style='border: 1px solid #4285f4; padding: 20px; border-radius: 8px;'>
  <h3>🔧 Create Google Cloud Project</h3>
  <ol>
    <li>Click here: <a href='https://console.cloud.google.com/' target='_blank'>
        Open Cloud Console</a></li>
    <li>Click <code>Create Project</code></li>
    <li>Name it <code>syft-oauth</code></li>
  </ol>
  <button onclick='continueWizard()'>Continue →</button>
</div>
"""
        }
    }
)
```

## Environment Renderers

### Terminal Renderer

```python
class TerminalWizardRenderer:
    """Render wizard steps in terminal"""
    
    def render_step(self, step: WizardStep) -> Any:
        content = step.content.get('terminal', {})
        
        # Clear screen if requested
        if content.get('clear_screen', False):
            os.system('clear' if os.name == 'posix' else 'cls')
        
        # Show title
        print(f"\n{'=' * 60}")
        print(f" {step.title}")
        print(f"{'=' * 60}\n")
        
        # Show content
        print(content.get('text', ''))
        
        # Show URL if present
        if url := content.get('url'):
            if content.get('auto_open_url'):
                print(f"\nOpening {url} in browser...")
                webbrowser.open(url)
            else:
                print(f"\nURL: {url}")
        
        # Handle input
        if prompt := content.get('prompt'):
            return input(f"\n{prompt} ")
        
        return None
    
    def render_progress(self, current: int, total: int) -> None:
        """Show progress bar"""
        bar_length = 40
        filled = int(bar_length * current / total)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\rProgress: [{bar}] {current}/{total}", end='')
```

### Jupyter Renderer

```python
class JupyterWizardRenderer:
    """Render wizard steps in Jupyter notebooks"""
    
    def render_step(self, step: WizardStep) -> Any:
        from IPython.display import display, Markdown, HTML
        import ipywidgets as widgets
        
        content = step.content.get('jupyter', {})
        
        # Display markdown content
        if md := content.get('markdown'):
            display(Markdown(md))
        
        # Create input widget
        widget_type = content.get('input_widget', 'button')
        
        if widget_type == 'button':
            button = widgets.Button(
                description=content.get('button_text', 'Continue'),
                style={'button_color': '#4285f4'}
            )
            
            # Set up callback
            result_container = {'value': None}
            
            def on_click(b):
                b.description = "✓ Done"
                b.disabled = True
                result_container['value'] = True
            
            button.on_click(on_click)
            display(button)
            
            # Wait for click
            while result_container['value'] is None:
                time.sleep(0.1)
            
            return True
            
        elif widget_type == 'text':
            text_input = widgets.Text(
                placeholder=content.get('placeholder', ''),
                description=content.get('label', '')
            )
            
            submit = widgets.Button(description='Submit')
            display(widgets.HBox([text_input, submit]))
            
            # Wait for input...
            return text_input.value
    
    def render_progress(self, current: int, total: int) -> None:
        """Show progress widget"""
        from IPython.display import display
        import ipywidgets as widgets
        
        progress = widgets.IntProgress(
            value=current,
            min=0,
            max=total,
            description='Progress:',
            bar_style='success'
        )
        display(progress)
```

### Colab Renderer

```python
class ColabWizardRenderer:
    """Special renderer for Google Colab"""
    
    def render_step(self, step: WizardStep) -> Any:
        from IPython.display import display, HTML
        from google.colab import output
        
        content = step.content.get('colab', step.content.get('jupyter', {}))
        
        # Use HTML if available
        if html := content.get('html'):
            display(HTML(html))
            
            # Set up JavaScript callback
            output.register_callback('continueWizard', self._continue_callback)
            
            # Wait for callback
            self._waiting = True
            while self._waiting:
                time.sleep(0.1)
            
            return self._result
        else:
            # Fallback to Jupyter renderer
            return JupyterWizardRenderer().render_step(step)
```

## Complete Wizard Example

### OAuth2 Setup Wizard

```python
class OAuth2SetupWizard:
    """Complete OAuth2 setup wizard"""
    
    def __init__(self, platform: str, email: str):
        self.platform = platform
        self.email = email
        self.steps = self._create_steps()
    
    def _create_steps(self) -> List[WizardStep]:
        """Define all wizard steps"""
        
        return [
            # Step 1: Introduction
            WizardStep(
                id="intro",
                title="OAuth2 Setup Required",
                content={
                    "terminal": {
                        "text": f"""
This wizard will guide you through setting up OAuth2 authentication
for {self.email} on {self.platform}.

This is a one-time setup that takes about 5-10 minutes.

You'll need:
- A Google account
- Web browser access
""",
                        "prompt": "Ready to begin? (y/n)",
                        "validation": lambda x: x.lower() in ['y', 'yes']
                    },
                    "jupyter": {
                        "markdown": f"""
## 🔐 OAuth2 Setup Wizard

This wizard will guide you through setting up OAuth2 authentication for:
- **Email**: `{self.email}`
- **Platform**: `{self.platform}`

**Time required**: ~5-10 minutes

**You'll need**:
- A Google account
- Web browser access
""",
                        "input_widget": "button",
                        "button_text": "Start Setup →"
                    }
                }
            ),
            
            # Step 2: Create Project
            WizardStep(
                id="create_project",
                title="Create Google Cloud Project",
                content={
                    "terminal": {
                        "text": """
Step 1: Create a new Google Cloud Project

1. Visit: https://console.cloud.google.com/projectcreate
2. Project name: syft-oauth (or any name you prefer)
3. Leave organization as "No organization"
4. Click "Create"
5. Wait for project creation (~30 seconds)
""",
                        "url": f"https://console.cloud.google.com/projectcreate?authuser={self.email}",
                        "auto_open_url": True,
                        "prompt": "Press Enter when project is created..."
                    },
                    "jupyter": {
                        "markdown": f"""
### Step 1: Create Google Cloud Project

1. Click here: [Create New Project](https://console.cloud.google.com/projectcreate?authuser={self.email})
2. **Project name**: `syft-oauth` (or any name)
3. **Organization**: Leave as "No organization"
4. Click **Create**
5. Wait ~30 seconds for creation

> 💡 **Tip**: The link above includes `authuser={self.email}` to use the correct account
""",
                        "input_widget": "button",
                        "button_text": "✓ Project Created"
                    }
                }
            ),
            
            # Step 3: Enable APIs
            WizardStep(
                id="enable_apis",
                title="Enable Required APIs",
                content={
                    "terminal": {
                        "text": """
Step 2: Enable Google APIs

We need to enable the APIs for the services you want to use.

1. Gmail API - for sending/receiving emails
2. Google Drive API - for file storage
3. Google Sheets API - for spreadsheet access
4. Google Forms API - for form creation

Visit each link and click "Enable":
""",
                        "action": self._show_api_links,
                        "prompt": "Press Enter when all APIs are enabled..."
                    },
                    "jupyter": {
                        "markdown": """
### Step 2: Enable Required APIs

Click each link below and click the **Enable** button:

| API | Purpose | Enable Link |
|-----|---------|------------|
| Gmail | Send/receive emails | [Enable Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com) |
| Drive | File storage | [Enable Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com) |
| Sheets | Spreadsheets | [Enable Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com) |
| Forms | Create forms | [Enable Forms API](https://console.cloud.google.com/apis/library/forms.googleapis.com) |

> ⏱️ Each API takes ~10 seconds to enable
""",
                        "input_widget": "button",
                        "button_text": "✓ All APIs Enabled"
                    }
                }
            ),
            
            # Step 4: OAuth Consent
            WizardStep(
                id="oauth_consent",
                title="Configure OAuth Consent Screen",
                content={
                    "terminal": {
                        "text": """
Step 3: Configure OAuth Consent Screen

1. Visit the OAuth consent screen configuration
2. Select "External" user type
3. Click "Create"
4. Fill in:
   - App name: Syft Client (or your choice)
   - User support email: (select your email)
   - Developer email: (your email)
5. Click "Save and Continue"
6. Skip scopes (click "Save and Continue")
7. Skip test users (click "Save and Continue")
8. Click "Back to Dashboard"
""",
                        "url": f"https://console.cloud.google.com/apis/credentials/consent?authuser={self.email}",
                        "prompt": "Press Enter when consent screen is configured..."
                    },
                    "jupyter": {
                        "markdown": f"""
### Step 3: Configure OAuth Consent Screen

1. Open [OAuth Consent Configuration](https://console.cloud.google.com/apis/credentials/consent?authuser={self.email})
2. Select **External** user type → Click **Create**
3. Fill in the form:
   - **App name**: `Syft Client`
   - **User support email**: Select your email
   - **Developer email**: Your email
4. Click **Save and Continue**
5. **Scopes page**: Click **Save and Continue** (skip)
6. **Test users page**: Click **Save and Continue** (skip)
7. Click **Back to Dashboard**

<details>
<summary>❓ Why External?</summary>
"External" allows any Google account to use your app. "Internal" only works with Workspace domains.
</details>
""",
                        "input_widget": "button",
                        "button_text": "✓ Consent Screen Configured"
                    }
                }
            ),
            
            # Step 5: Create Credentials
            WizardStep(
                id="create_credentials",
                title="Create OAuth2 Credentials",
                content={
                    "terminal": {
                        "text": """
Step 4: Create OAuth2 Client Credentials

1. Visit the credentials page
2. Click "+ CREATE CREDENTIALS" → "OAuth client ID"
3. Application type: "Desktop app"
4. Name: "Syft Client" (or your choice)
5. Click "Create"
6. Click "DOWNLOAD JSON" in the popup
7. Save the file as "credentials.json"
""",
                        "url": f"https://console.cloud.google.com/apis/credentials?authuser={self.email}",
                        "prompt": "Press Enter when you've downloaded credentials.json..."
                    },
                    "jupyter": {
                        "markdown": f"""
### Step 4: Create OAuth2 Credentials

1. Open [Credentials Page](https://console.cloud.google.com/apis/credentials?authuser={self.email})
2. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
3. Settings:
   - **Application type**: `Desktop app`
   - **Name**: `Syft Client`
4. Click **Create**
5. In the popup, click **DOWNLOAD JSON**
6. Save the file as `credentials.json`

> 🔒 **Important**: Keep this file secure! It contains your app's OAuth2 secrets.
""",
                        "input_widget": "button", 
                        "button_text": "✓ Downloaded credentials.json"
                    }
                }
            ),
            
            # Step 6: Place Credentials
            WizardStep(
                id="place_credentials",
                title="Install Credentials File",
                content={
                    "terminal": {
                        "text": """
Step 5: Install the credentials file

Move the downloaded credentials.json to the Syft directory:
""",
                        "action": self._show_credential_commands,
                        "validation": self._check_credentials_placed
                    },
                    "jupyter": {
                        "markdown": """
### Step 5: Install Credentials File

Run this command to move the credentials file:

```bash
mv ~/Downloads/credentials.json ~/.syft/credentials.json
```

Or if you downloaded elsewhere:
```bash
mv /path/to/credentials.json ~/.syft/credentials.json
```

> 💡 **Colab Users**: Upload the file using the Files sidebar instead
""",
                        "action": self._show_upload_widget_jupyter
                    }
                }
            ),
            
            # Step 7: Complete
            WizardStep(
                id="complete",
                title="Setup Complete!",
                content={
                    "terminal": {
                        "text": """
✅ OAuth2 setup is complete!

Your credentials are configured and ready to use.
The browser will now open for authentication.

After you sign in and grant permissions, you'll be able to use:
- Gmail (send/receive emails)
- Google Drive (file storage)  
- Google Sheets (spreadsheets)
- Google Forms (create forms)
""",
                        "prompt": "Press Enter to continue with authentication..."
                    },
                    "jupyter": {
                        "markdown": """
## ✅ Setup Complete!

Your OAuth2 credentials are now configured. 

**What happens next:**
1. A browser window will open
2. Sign in with your Google account
3. Review and accept the permissions
4. You'll see "authentication successful"

**Available features:**
- 📧 Gmail - Send and receive emails
- 📁 Drive - Store and share files
- 📊 Sheets - Create spreadsheets
- 📝 Forms - Build forms

Click below to continue with authentication.
""",
                        "input_widget": "button",
                        "button_text": "🚀 Authenticate Now"
                    }
                }
            )
        ]
    
    def _show_api_links(self) -> None:
        """Show API enable links in terminal"""
        base_url = "https://console.cloud.google.com/apis/library/"
        apis = [
            ("Gmail API", f"{base_url}gmail.googleapis.com"),
            ("Drive API", f"{base_url}drive.googleapis.com"),
            ("Sheets API", f"{base_url}sheets.googleapis.com"),
            ("Forms API", f"{base_url}forms.googleapis.com")
        ]
        
        for name, url in apis:
            print(f"  - {name}: {url}")
    
    def _show_credential_commands(self) -> None:
        """Show commands to move credentials"""
        print("  mv ~/Downloads/credentials.json ~/.syft/credentials.json")
        print("\nOr if downloaded elsewhere:")
        print("  mv /path/to/credentials.json ~/.syft/credentials.json")
    
    def _check_credentials_placed(self, _) -> bool:
        """Validate credentials.json is in place"""
        paths = [
            Path.home() / ".syft" / "credentials.json",
            Path.home() / ".syft" / "google_oauth" / "credentials.json"
        ]
        return any(p.exists() for p in paths)
    
    def _show_upload_widget_jupyter(self) -> None:
        """Show file upload widget in Jupyter"""
        try:
            from google.colab import files
            print("Uploading credentials.json...")
            uploaded = files.upload()
            
            if 'credentials.json' in uploaded:
                # Move to correct location
                import shutil
                dest = Path.home() / ".syft" / "credentials.json"
                dest.parent.mkdir(exist_ok=True)
                
                with open(dest, 'wb') as f:
                    f.write(uploaded['credentials.json'])
                
                print(f"✓ Saved to {dest}")
        except ImportError:
            # Not in Colab, show manual instructions
            import ipywidgets as widgets
            from IPython.display import display
            
            upload = widgets.FileUpload(accept='.json', multiple=False)
            display(upload)
            
            # Handle upload...
```

## Custom Step Actions

### Validation Functions

```python
def validate_email(value: str) -> bool:
    """Validate email format"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, value))

def validate_project_id(value: str) -> bool:
    """Validate GCP project ID"""
    # Must be 6-30 chars, lowercase letters, numbers, hyphens
    import re
    pattern = r'^[a-z][a-z0-9-]{4,28}[a-z0-9]$'
    return bool(re.match(pattern, value))
```

### Action Functions

```python
def open_url_with_retry(url: str, max_retries: int = 3) -> bool:
    """Open URL with retry logic"""
    import webbrowser
    import time
    
    for i in range(max_retries):
        try:
            if webbrowser.open(url):
                return True
        except:
            pass
        
        if i < max_retries - 1:
            print(f"Failed to open browser, retrying in {i+1} seconds...")
            time.sleep(i + 1)
    
    return False
```

## Environment Detection

```python
def detect_environment() -> str:
    """Detect current environment"""
    
    # Check Colab
    try:
        import google.colab
        return 'colab'
    except ImportError:
        pass
    
    # Check Jupyter
    try:
        get_ipython()
        return 'jupyter'
    except NameError:
        pass
    
    # Default to terminal
    return 'terminal'

def get_renderer(environment: Optional[str] = None) -> WizardRenderer:
    """Get appropriate renderer for environment"""
    
    if environment is None:
        environment = detect_environment()
    
    renderers = {
        'terminal': TerminalWizardRenderer,
        'jupyter': JupyterWizardRenderer,
        'colab': ColabWizardRenderer
    }
    
    renderer_class = renderers.get(environment, TerminalWizardRenderer)
    return renderer_class()
```

## Running the Wizard

```python
class WizardRunner:
    """Execute wizard with appropriate renderer"""
    
    def __init__(self, wizard: OAuth2SetupWizard):
        self.wizard = wizard
        self.renderer = get_renderer()
    
    def run(self) -> Dict[str, Any]:
        """Run through all wizard steps"""
        
        results = {}
        total_steps = len(self.wizard.steps)
        
        for i, step in enumerate(self.wizard.steps):
            # Show progress
            self.renderer.render_progress(i, total_steps)
            
            # Render step
            result = self.renderer.render_step(step)
            
            # Validate if needed
            if step.validation and not step.validation(result):
                print("Invalid input, please try again...")
                # Retry logic...
            
            # Store result
            results[step.id] = result
            
            # Run action if defined
            if step.action:
                step.action()
        
        # Final progress
        self.renderer.render_progress(total_steps, total_steps)
        
        return results
```

## Usage Examples

### Basic Usage

```python
# Create and run wizard
wizard = OAuth2SetupWizard('google_personal', 'user@gmail.com')
runner = WizardRunner(wizard)
results = runner.run()
```

### Custom Environment

```python
# Force terminal mode in Jupyter
wizard = OAuth2SetupWizard('google_personal', 'user@gmail.com')
runner = WizardRunner(wizard)
runner.renderer = TerminalWizardRenderer()
results = runner.run()
```

### Subset of Steps

```python
# Run only specific steps
wizard = OAuth2SetupWizard('google_personal', 'user@gmail.com')
wizard.steps = [s for s in wizard.steps if s.id in ['create_project', 'enable_apis']]
runner = WizardRunner(wizard)
results = runner.run()
```