# Authentication

**If you're using Google Colab, authentication is handled by colab via a browser pop-up when you initialize a SyftClient, you can stop reading here.** Once authenticated, Syft Client uses Google Drive as its communication protocol — all messages, events, and files are synced through the Drive API.

## Local / Jupyter Lab Setup

To use Syft Client outside of Google Colab, you need to set up a Google Cloud project with OAuth credentials.

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** in the top navigation bar
3. Click **New Project** in the dialog that appears
4. Enter a project name (e.g., "Syft Client")
5. Click **Create**
6. Wait for the project to be created, then select it

## Step 2: Enable the Google Drive API

1. In your project, go to **APIs & Services** > **Library**
2. Search for "Google Drive API"
3. Click on **Google Drive API**
4. Click **Enable**

## Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** > **OAuth consent screen**
2. Select **External** user type (unless you have a Google Workspace organization)
3. Click **Create**
4. Fill in the required fields:
   - **App name**: "Syft Client" (or your preferred name)
   - **User support email**: Your email address
   - **Developer contact information**: Your email address
5. Click **Save and Continue**
6. On the **Scopes** page:
   - Click **Add or Remove Scopes**
   - Search for and select `https://www.googleapis.com/auth/drive`
   - Click **Update**
   - Click **Save and Continue**
7. On the **Test users** page:
   - Click **Add Users**
   - Add the email addresses of users who will test the app
   - Click **Save and Continue**
8. Review the summary and click **Back to Dashboard**

## Step 4: Create OAuth Client Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. Select **Desktop app** as the application type
4. Enter a name (e.g., "Syft Client Desktop")
5. Click **Create**
6. **Download the JSON file** - this contains your client credentials
7. Save this file securely (e.g., as `credentials.json`)

## Step 5: Publish the App

For testing, your app can remain in "Testing" mode with up to 100 test users. To allow any Google user to authenticate:

1. Go to **APIs & Services** > **OAuth consent screen**
2. Click **Publish App**
3. Confirm the publishing

**Important:** If your app is not published (i.e., remains in "Testing" mode), OAuth tokens expire every 7 days and users will need to re-authenticate. Publishing the app removes this limitation.

> **Note:** Publishing may require verification for apps requesting sensitive scopes like Google Drive access.

## Generating a Token

Once you've completed the Google Cloud Console setup, generate a token:

```bash
python scripts/create_token.py --credentials path/to/credentials.json --output token.json
```

Then pass the token path when logging in:

```python
do_client = login_do(email="your@email.com", token_path="path/to/token.json")
```

If your app is not published, tokens expire every 7 days and you'll need to regenerate them.
