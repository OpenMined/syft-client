def wizard():
    """
    Creates a wizard widget that displays images with navigation.
    
    Returns a simple HTML widget with JavaScript navigation.
    """
    from IPython.display import HTML
    
    # Generate the HTML with embedded JavaScript
    html_content = '''
    <div id="wizard-widget" style="display: flex; height: 600px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden;">
        
        <!-- Left Pane -->
        <div style="flex: 1; padding: 40px; background: #f7fafc; display: flex; flex-direction: column; justify-content: space-between; min-width: 400px; height: 600px; box-sizing: border-box;">
            <div>
                <h2 style="margin: 0 0 10px 0; color: #1a202c; font-size: 28px; font-weight: 600;">Create Google Drive Credentials</h2>
                <div style="width: 60px; height: 4px; background: #4285f4; margin-bottom: 30px;"></div>
                
                <div style="margin-bottom: 30px;">
                    <div style="display: inline-block; padding: 6px 12px; background: #e2e8f0; border-radius: 20px; font-size: 14px; color: #4a5568; margin-bottom: 20px;">
                        Step <span id="currentNum">1</span> of 12
                    </div>
                    
                    <p id="caption" style="font-size: 20px; line-height: 1.6; color: #2d3748; margin: 0;">
                        Step 1: Go to Google Cloud Console and click "Select a project" dropdown at the top of the page.
                    </p>
                </div>
            </div>
            
            <div style="display: flex; gap: 15px;">
                <button onclick="goPrev()" style="padding: 12px 24px; background-color: white; color: #4a5568; border: 2px solid #e2e8f0; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: 500; transition: all 0.2s;" id="prevButton" onmouseover="this.style.backgroundColor='#f7fafc'" onmouseout="this.style.backgroundColor='white'">
                    ← Previous
                </button>
                <button onclick="goNext()" style="padding: 12px 24px; background-color: #4285f4; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: 500; transition: all 0.2s;" id="nextButton" onmouseover="this.style.backgroundColor='#3367d6'" onmouseout="this.style.backgroundColor='#4285f4'">
                    Next →
                </button>
            </div>
        </div>
        
        <!-- Right Pane -->
        <div style="flex: 1; padding: 20px; display: flex; align-items: center; justify-content: center; background: white; height: 600px; box-sizing: border-box;">
            <img id="wizardImage" src="https://github.com/OpenMined/syft-client/blob/6cdb84c419906fd794c05b47e5cfc421c9bb845b/img/wizard_1.png?raw=true" style="max-width: 100%; max-height: 560px; height: auto; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
        </div>
    </div>
    
    <script>
    (function() {
        var urls = [
            "https://github.com/OpenMined/syft-client/blob/6cdb84c419906fd794c05b47e5cfc421c9bb845b/img/wizard_1.png?raw=true",
            "https://github.com/OpenMined/syft-client/blob/6cdb84c419906fd794c05b47e5cfc421c9bb845b/img/wizard_2.png?raw=true",
            "https://github.com/OpenMined/syft-client/blob/6cdb84c419906fd794c05b47e5cfc421c9bb845b/img/wizard_3.png?raw=true",
            "https://github.com/OpenMined/syft-client/blob/6cdb84c419906fd794c05b47e5cfc421c9bb845b/img/wizard_4.png?raw=true",
            "https://github.com/OpenMined/syft-client/blob/6cdb84c419906fd794c05b47e5cfc421c9bb845b/img/wizard_5.png?raw=true",
            "https://github.com/OpenMined/syft-client/blob/6cdb84c419906fd794c05b47e5cfc421c9bb845b/img/wizard_6.png?raw=true",
            "https://github.com/OpenMined/syft-client/blob/6cdb84c419906fd794c05b47e5cfc421c9bb845b/img/wizard_7.png?raw=true",
            "https://github.com/OpenMined/syft-client/blob/6cdb84c419906fd794c05b47e5cfc421c9bb845b/img/wizard_8.png?raw=true",
            "https://github.com/OpenMined/syft-client/blob/6cdb84c419906fd794c05b47e5cfc421c9bb845b/img/wizard_9.png?raw=true",
            "https://github.com/OpenMined/syft-client/blob/6cdb84c419906fd794c05b47e5cfc421c9bb845b/img/wizard_10.png?raw=true",
            "https://github.com/OpenMined/syft-client/blob/6cdb84c419906fd794c05b47e5cfc421c9bb845b/img/wizard_11.png?raw=true",
            "https://github.com/OpenMined/syft-client/blob/6cdb84c419906fd794c05b47e5cfc421c9bb845b/img/wizard_12.png?raw=true"
            
        ];
        
        var captions = [
            "You don't have valid credentials! It's time to make some. Go to <a href='https://console.cloud.google.com/projectcreate' target='_blank' rel='noopener noreferrer' style='color: #3182ce;'>Google Cloud Console — Create Project Page</a> and fill out the form.",
            "When the dropdown appears showing the creation of your new project, wait until the project is formed and click 'SELECT PROJECT'.",
            "Navigate to <a href='https://console.cloud.google.com/apis/library/drive.googleapis.com' target='_blank' rel='noopener noreferrer' style='color: #3182ce;'>Google Drive API</a> and click 'ENABLE' to enable the Google Drive API for your project.",
            "Navigate to <a href='https://console.cloud.google.com/auth/overview' target='_blank' rel='noopener noreferrer' style='color: #3182ce;'>OAuth Overview</a> and click 'Get started'.",
            "Enter app name (anything you like) and user support email (you can use your own email) and click 'Next'.",
            "Click 'External' so that only you can use the app (and anyone you) and click 'Next'.",
            "Enter contact information (can be the same email) and click 'Next'.",
            "Read API services, tick the box, and click 'Continue'.",
            "Click 'Create'.",
            "Click 'Create OAuth Client'.",
            "In the dropdown, select 'Desktop app' and then click 'Create'.",
            "Click 'Download JSON' and save the file to your computer. Then re-run syft_client.login(your_email@gmail.com, '/path/to/credentials.json')"
        ];
        
        var idx = 0;
        
        window.goNext = function() {
            if (idx < urls.length - 1) {
                idx++;
                updateWizard();
            }
        };
        
        window.goPrev = function() {
            if (idx > 0) {
                idx--;
                updateWizard();
            }
        };
        
        function updateWizard() {
            document.getElementById('wizardImage').src = urls[idx];
            document.getElementById('currentNum').textContent = idx + 1;
            document.getElementById('caption').innerHTML = captions[idx];
            document.getElementById('prevButton').disabled = idx === 0;
            document.getElementById('nextButton').disabled = idx === urls.length - 1;
            var prevBtn = document.getElementById('prevButton');
            var nextBtn = document.getElementById('nextButton');
            
            if (idx === 0) {
                prevBtn.style.opacity = '0.5';
                prevBtn.style.cursor = 'not-allowed';
            } else {
                prevBtn.style.opacity = '1';
                prevBtn.style.cursor = 'pointer';
            }
            
            if (idx === urls.length - 1) {
                nextBtn.style.opacity = '0.5';
                nextBtn.style.cursor = 'not-allowed';
            } else {
                nextBtn.style.opacity = '1';
                nextBtn.style.cursor = 'pointer';
            }
        }
        
        // Initialize
        updateWizard();
    })();
    </script>
    '''
    
    return HTML(html_content)