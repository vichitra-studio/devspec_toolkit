#!/bin/bash

# Complete setup script for devspec toolkit virtual environment
echo "Setting up complete devspec toolkit environment..."

# Create virtual environment if it doesn't exist
if [ ! -d "devspec_env" ]; then
    echo "Creating virtual environment..."
    python3 -m venv devspec_env
else
    echo "Virtual environment already exists"
fi

# Activate the virtual environment
source devspec_env/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip3 install --upgrade pip

# Install dependencies
echo "Installing toolkit dependencies..."
pip3 install -r ./devspec_toolkit/tools/requirements.txt

# Install the toolkit in development mode
echo "Installing devspec toolkit..."
pip3 install -e ./devspec_toolkit/tools

# Set up PYTHONPATH for toolkit modules
export PYTHONPATH="${PWD}/devspec_toolkit/tools:$PYTHONPATH"

# Verify installation
echo "Verifying specdev_tools availability..."
python3 -c "import specdev_tools; print('specdev_tools is available')"

echo "Setup complete!"
echo "To use the toolkit, activate the environment with:"
echo "  source devspec_env/bin/activate"
echo "Then run commands with:"
echo "  PYTHONPATH=\"\${PWD}/devspec_toolkit/tools\" python3 -m specdev_tools.cli --help"
echo ""
echo "Example usage:"
echo "  PYTHONPATH=\"\${PWD}/devspec_toolkit/tools\" python3 -m specdev_tools.cli validate spec/00_charter.json --repo-root ./devspec_toolkit"
