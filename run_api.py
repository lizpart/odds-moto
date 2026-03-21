"""
Startup script for the Football Analysis API
Handles environment setup and runs the FastAPI server
"""
import os
import sys
import uvicorn
from app_config import settings

def check_environment():
    """Check if required environment variables and files are set"""
    warnings = []
    errors = []
    
    # Check OpenAI API key
    if not settings.openai_api_key or settings.openai_api_key == "YOUR_OPENAI_API_KEY_HERE":
        warnings.append("⚠️  OpenAI API key not set. Predictions will not work.")
        warnings.append("   Set OPENAI_API_KEY in .env file or environment variables")
    
    # Check config file
    if not os.path.exists(settings.config_file):
        warnings.append(f"⚠️  Config file not found: {settings.config_file}")
        warnings.append("   Using default configuration")
    
    # Check output directory
    if not os.path.exists(settings.output_dir):
        print(f"📁 Creating output directory: {settings.output_dir}")
        os.makedirs(settings.output_dir, exist_ok=True)
    
    # Check cache directory
    if not os.path.exists(settings.cache_dir):
        print(f"📁 Creating cache directory: {settings.cache_dir}")
        os.makedirs(settings.cache_dir, exist_ok=True)
    
    # Print warnings
    if warnings:
        print("\n" + "="*60)
        print("⚠️  WARNINGS")
        print("="*60)
        for warning in warnings:
            print(warning)
        print("="*60 + "\n")
    
    # Print errors and exit if any
    if errors:
        print("\n" + "="*60)
        print("❌ ERRORS")
        print("="*60)
        for error in errors:
            print(error)
        print("="*60 + "\n")
        sys.exit(1)
    
    return True


def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("🏈 Football Match Analysis API")
    print("="*60)
    print(f"Version: 1.0.0")
    print(f"Host: {settings.host}")
    print(f"Port: {settings.port}")
    print(f"Debug: {settings.debug}")
    print(f"Output Dir: {settings.output_dir}")
    print(f"Cache Dir: {settings.cache_dir}")
    print("="*60 + "\n")
    
    # Check environment
    check_environment()
    
    print("🚀 Starting server...")
    # Always show localhost URLs for browser access (even if binding to 0.0.0.0)
    display_host = "localhost" if settings.host in ["0.0.0.0", "127.0.0.1"] else settings.host
    print(f"📡 API will be available at: http://{display_host}:{settings.port}")
    print(f"📚 API docs will be available at: http://{display_host}:{settings.port}/docs")
    print(f"📖 ReDoc will be available at: http://{display_host}:{settings.port}/redoc")
    print("\nPress CTRL+C to stop the server\n")
    
    # Run the server
    try:
        uvicorn.run(
            "main:app",
            host=settings.host,
            port=settings.port,
            reload=settings.debug,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n\n❌ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

