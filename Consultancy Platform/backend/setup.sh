#!/bin/bash

echo "🚀 Setting up Consultancy Platform..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed. Please install Python 3.11+"
    exit 1
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check if Django is installed
echo "✅ Django installed: $(python -c 'import django; print(django.get_version())')"

# Run migrations
echo "🗄️  Running migrations..."
python manage.py migrate

# Create superuser
echo "👤 Creating superuser..."
python manage.py createsuperuser

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

echo "🎉 Setup complete! Run: python manage.py runserver"