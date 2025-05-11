#!/bin/bash
set -e

echo "🔧 Setting up local development environment..."

# Step 1: Create virtual environment
if [ ! -d ".venv" ]; then
  echo "🐍 Creating Python virtual environment (.venv)..."
  python3 -m venv .venv
fi

# Step 2: Activate environment
echo "🐍 Activating virtual environment..."
source .venv/bin/activate

# Step 3: Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Step 4: Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt


# Step 6: Start FastAPI app
echo "🚀 Starting FastAPI server at http://127.0.0.1:8000 ..."
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

