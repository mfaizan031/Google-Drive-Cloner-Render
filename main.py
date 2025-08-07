import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory
from flask_cors import CORS

# Import only the drive blueprint since you're not using user data
from drive_api import drive_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# Use environment variable for secret key (Railway will provide this)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'fallback-secret-key-change-in-production')

# Configure CORS to allow all origins
CORS(app, 
     supports_credentials=True,
     origins="*")

# Register only the drive blueprint
app.register_blueprint(drive_bp, url_prefix='/api')

# Set preferred URL scheme to https for OAuth callbacks (important for Railway)
app.config['PREFERRED_URL_SCHEME'] = 'https'

# Health check endpoint
@app.route('/health')
def health_check():
    return {'status': 'Backend is running!', 'version': '1.0', 'environment': 'production'}

# Serve static files and handle SPA routing
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404
    
    # Check if the requested file exists
    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        # For SPA routing, serve index.html for non-API routes
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

if __name__ == '__main__':
    # Railway provides the PORT environment variable
    port = int(os.environ.get('PORT', 5000))
    
    # Debug info (will be visible in Railway logs)
    print(f"GOOGLE_CLIENT_ID: {os.environ.get('GOOGLE_CLIENT_ID', 'Not set')}")
    print(f"GOOGLE_CLIENT_SECRET: {'Set' if os.environ.get('GOOGLE_CLIENT_SECRET') else 'Not set'}")
    print(f"FLASK_SECRET_KEY: {'Set' if os.environ.get('FLASK_SECRET_KEY') else 'Using fallback'}")
    print(f"Running on port: {port}")
    print(f"Environment: {'Production' if not os.environ.get('FLASK_ENV') == 'development' else 'Development'}")
    
    # Railway deployment settings
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
