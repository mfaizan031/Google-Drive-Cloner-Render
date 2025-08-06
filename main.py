import os
from flask import Flask
from flask_cors import CORS
from drive_api import drive_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'fallback-secret-key-change-in-production')

# Configure CORS for your Netlify frontend
CORS(app, 
     supports_credentials=True,
     origins=[
         'http://localhost:3000',  # For local development
         'https://*.netlify.app',  # For Netlify deployments
         'https://*.netlify.com'   # Alternative Netlify domain
     ])

# Register blueprints
app.register_blueprint(drive_bp, url_prefix='/api')

@app.route('/')
def health_check():
    return {'status': 'Backend is running!', 'version': '1.0'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print(f"GOOGLE_CLIENT_ID: {os.environ.get('GOOGLE_CLIENT_ID', 'Not set')}")
    print(f"GOOGLE_CLIENT_SECRET: {'Set' if os.environ.get('GOOGLE_CLIENT_SECRET') else 'Not set'}")
    print(f"Running on port: {port}")
    
    app.run(host='0.0.0.0', port=port, debug=False)
