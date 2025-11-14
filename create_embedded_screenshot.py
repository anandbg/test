#!/usr/bin/env python3
import base64
import os

# Read the screenshot file
screenshot_path = '/workspace/page_screenshot.png'
if os.path.exists(screenshot_path):
    with open(screenshot_path, 'rb') as f:
        image_data = f.read()
        # Convert to base64
        base64_data = base64.b64encode(image_data).decode('utf-8')
        
        # Create HTML template
        html_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Download Screenshot - Mobbin Design Patterns</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 20px;
        }
        .screenshot-container {
            text-align: center;
            margin: 30px 0;
        }
        .screenshot-container img {
            max-width: 100%;
            height: auto;
            border: 2px solid #ddd;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .download-btn {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 30px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            margin: 20px 10px;
            transition: transform 0.2s, box-shadow 0.2s;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }
        .download-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }
        .info-box {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #667eea;
        }
        .info-box strong {
            color: #333;
        }
        .file-details {
            margin-top: 10px;
            color: #666;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📸 HTML Page Screenshot</h1>
        <p class="subtitle">Mobbin Design Patterns Gallery - Full Page Screenshot</p>
        
        <div class="info-box">
            <strong>📋 File Information:</strong>
            <div class="file-details">
                <strong>Filename:</strong> mobbin_design_patterns_screenshot.png<br>
                <strong>Size:</strong> 1.6 MB<br>
                <strong>Dimensions:</strong> 1920 x 6468 pixels (Full Page)<br>
                <strong>Format:</strong> PNG
            </div>
        </div>

        <div class="screenshot-container">
            <img src="data:image/png;base64,{IMAGE_DATA}" alt="Mobbin Design Patterns Screenshot" id="screenshot">
        </div>

        <div style="text-align: center;">
            <a href="data:image/png;base64,{IMAGE_DATA}" download="mobbin_design_patterns_screenshot.png" class="download-btn">
                ⬇️ Download Screenshot (PNG)
            </a>
        </div>

        <div class="info-box">
            <strong>💡 Download Instructions:</strong>
            <ul style="margin-top: 10px; padding-left: 20px;">
                <li>Click the download button above to save the screenshot</li>
                <li>Or right-click on the image and select "Save image as..."</li>
                <li>The screenshot shows the complete gallery page with all 40 design patterns</li>
            </ul>
        </div>
    </div>

    <script>
        // Add download functionality
        document.getElementById('screenshot').addEventListener('click', function() {
            const link = document.createElement('a');
            link.href = this.src;
            link.download = 'mobbin_design_patterns_screenshot.png';
            link.click();
        });
        
        console.log('Screenshot loaded successfully!');
    </script>
</body>
</html>'''
        
        # Replace placeholder with actual base64 data
        html_content = html_template.replace('{IMAGE_DATA}', base64_data)
        
        # Save the standalone HTML file
        output_path = '/workspace/screenshot_download.html'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        file_size = os.path.getsize(output_path) / (1024 * 1024)  # Size in MB
        print(f"✅ Created standalone HTML file with embedded screenshot!")
        print(f"📄 File: screenshot_download.html")
        print(f"📦 File size: {file_size:.2f} MB")
        print(f"📦 Image is embedded in the HTML - no external files needed!")
        print(f"\n💡 Open screenshot_download.html in your browser to view and download!")
else:
    print("Error: Screenshot file not found at", screenshot_path)
