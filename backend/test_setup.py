"""
Quick setup verification script to check if the backend is properly configured.
Run this before starting the server to verify all components.
"""

import sys
from pathlib import Path


def check_files():
    """Check if all required files exist."""
    required_files = [
        "main.py",
        "server.py",
        "graph.py",
        "agents.py",
        "prompts.py",
        "models.py",
        "config.py",
        "requirements.txt",
        ".env.example",
        "utils/__init__.py",
        "utils/llm_factory.py",
        "utils/pdf_parser.py",
        "utils/storage.py",
        "utils/gamma_client.py",
    ]

    missing = []
    for file in required_files:
        if not Path(file).exists():
            missing.append(file)

    if missing:
        print("❌ Missing files:")
        for f in missing:
            print(f"   - {f}")
        return False
    else:
        print("✅ All required files present")
        return True


def check_env():
    """Check if .env file exists and has required variables."""
    if not Path(".env").exists():
        print("⚠️  .env file not found")
        print("   Copy .env.example to .env and configure your API keys:")
        print("   cp .env.example .env")
        return False

    with open(".env", "r") as f:
        env_content = f.read()

    required_vars = ["LLM_PROVIDER"]
    missing_vars = []

    for var in required_vars:
        if var not in env_content or f"{var}=" in env_content and "your-" in env_content:
            missing_vars.append(var)

    # Check provider-specific requirements
    if "LLM_PROVIDER=anthropic" in env_content and ("ANTHROPIC_API_KEY" not in env_content or "ANTHROPIC_API_KEY=your-anthropic-key" in env_content):
        missing_vars.append("ANTHROPIC_API_KEY")

    if "LLM_PROVIDER=vertex_ai" in env_content and ("GOOGLE_CLOUD_PROJECT" not in env_content or "GOOGLE_CLOUD_PROJECT=your-" in env_content):
        missing_vars.append("GOOGLE_CLOUD_PROJECT")

    if missing_vars:
        print("⚠️  Missing or unconfigured environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    else:
        print("✅ Environment variables configured")
        return True


def check_imports():
    """Check if required packages can be imported."""
    packages = {
        "fastapi": "FastAPI",
        "uvicorn": "Uvicorn",
        "langgraph": "LangGraph",
        "langchain_core": "LangChain Core",
        "fitz": "PyMuPDF",
        "pydantic": "Pydantic",
    }

    missing = []
    for package, name in packages.items():
        try:
            __import__(package)
            print(f"✅ {name} installed")
        except ImportError:
            missing.append(name)
            print(f"❌ {name} not installed")

    if missing:
        print("\n⚠️  Install missing packages:")
        print("   pip install -r requirements.txt")
        return False

    return True


def check_llm_provider():
    """Check if LLM provider is properly configured."""
    try:
        from config import settings
        from utils.llm_factory import get_llm_info

        info = get_llm_info()
        print(f"✅ LLM Provider: {info['provider']} ({info['model']})")

        # Try to initialize LLM
        from utils.llm_factory import get_llm
        llm = get_llm()
        print(f"✅ LLM initialized successfully")

        return True

    except ValueError as e:
        print(f"❌ LLM configuration error: {e}")
        return False
    except Exception as e:
        print(f"❌ Failed to initialize LLM: {e}")
        return False


def main():
    print("=" * 50)
    print("Procurement Analysis Backend - Setup Verification")
    print("=" * 50)
    print()

    checks = [
        ("Files", check_files),
        ("Environment", check_env),
        ("Dependencies", check_imports),
        ("LLM Provider", check_llm_provider),
    ]

    results = []
    for name, check_func in checks:
        print(f"\n[{name}]")
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Error during {name} check: {e}")
            results.append(False)

    print("\n" + "=" * 50)
    if all(results):
        print("✅ All checks passed! Ready to start the server.")
        print("\nRun: python main.py")
        print("Or:  uvicorn server:app --reload")
        sys.exit(0)
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
