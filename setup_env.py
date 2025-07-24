#!/usr/bin/env python3
"""
Setup script to create .env file from .env.example
"""

import os
import shutil

def setup_env_file():
    """Create .env file from .env.example if it doesn't exist"""
    
    env_example_path = '.env.example'
    env_path = '.env'
    
    if not os.path.exists(env_example_path):
        print("Error: .env.example file not found!")
        return False
    
    if os.path.exists(env_path):
        print(f".env file already exists.")
        response = input("Do you want to overwrite it? (y/n): ").lower()
        if response != 'y':
            print("Setup cancelled.")
            return False
    
    # Copy .env.example to .env
    shutil.copy2(env_example_path, env_path)
    print(f"Created {env_path} from {env_example_path}")
    
    # Ask user for OpenAI API key
    api_key = input("\nPlease enter your OpenAI API key: ").strip()
    
    if api_key:
        # Read the .env file
        with open(env_path, 'r') as f:
            content = f.read()
        
        # Replace the placeholder with actual API key
        content = content.replace('your_openai_api_key_here', api_key)
        
        # Write back to .env file
        with open(env_path, 'w') as f:
            f.write(content)
        
        print(f"\nOpenAI API key has been set in {env_path}")
        print("✅ Environment setup complete!")
        print("\nNext steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Run the application: python transcriber_app.py")
        print("3. Open your browser and go to: http://localhost:3000")
        return True
    else:
        print("\n⚠️  No API key provided. Please edit the .env file manually to add your OpenAI API key.")
        print(f"Edit {env_path} and replace 'your_openai_api_key_here' with your actual API key.")
        return False

if __name__ == "__main__":
    setup_env_file()
