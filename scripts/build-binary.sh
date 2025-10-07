#!/bin/bash

# Build script for NESendo GUI binary
# This script creates a standalone binary from nesendo_gui.py using PyInstaller

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

print_status "NESendo Binary Build Script"
print_status "Project root: $PROJECT_ROOT"

# Check if we're in the right directory
if [ ! -f "$PROJECT_ROOT/nesendo_gui.py" ]; then
    print_error "nesendo_gui.py not found in project root: $PROJECT_ROOT"
    exit 1
fi

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    print_error "PyInstaller is not installed. Please install it first:"
    print_error "pip install pyinstaller"
    exit 1
fi

# Check if required dependencies are available
print_status "Checking dependencies..."

# Check for PyQt5
python3 -c "import PyQt5" 2>/dev/null || {
    print_warning "PyQt5 is not installed. Attempting to install it..."
    pip install PyQt5 || {
        print_error "Failed to install PyQt5. Please install it manually:"
        print_error "pip install PyQt5"
        exit 1
    }
}

# Check for numpy
python3 -c "import numpy" 2>/dev/null || {
    print_warning "numpy is not installed. Attempting to install it..."
    pip install numpy || {
        print_error "Failed to install numpy. Please install it manually:"
        print_error "pip install numpy"
        exit 1
    }
}

# Check for gymnasium
python3 -c "import gymnasium" 2>/dev/null || {
    print_warning "gymnasium is not installed. Attempting to install it..."
    pip install gymnasium || {
        print_error "Failed to install gymnasium. Please install it manually:"
        print_error "pip install gymnasium"
        exit 1
    }
}

print_success "All dependencies are available"

# Create build directory
BUILD_DIR="$PROJECT_ROOT/build"
DIST_DIR="$PROJECT_ROOT/dist"
SPEC_FILE="$PROJECT_ROOT/nesendo_gui.spec"

print_status "Creating build directories..."
mkdir -p "$BUILD_DIR"
mkdir -p "$DIST_DIR"

# Clean previous builds
print_status "Cleaning previous builds..."
rm -rf "$BUILD_DIR"/*
rm -rf "$DIST_DIR"/*

# Check if the C++ library exists
LIB_PATH="$PROJECT_ROOT/NESendo/lib_nes_env.so"
if [ ! -f "$LIB_PATH" ]; then
    print_warning "C++ library not found at $LIB_PATH"
    print_warning "You may need to build the C++ components first using 'make'"
fi

# Create PyInstaller spec file
print_status "Creating PyInstaller spec file..."

cat > "$SPEC_FILE" << 'EOF'
# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

# Get the project root directory
project_root = os.path.dirname(os.path.abspath(SPEC))

# Define the main script
main_script = os.path.join(project_root, 'nesendo_gui.py')

# Define data files to include
datas = []

# Include the NESendo package
nesendo_package = os.path.join(project_root, 'NESendo')
if os.path.exists(nesendo_package):
    datas.append((nesendo_package, 'NESendo'))

# Include the C++ library if it exists
lib_path = os.path.join(project_root, 'NESendo', 'lib_nes_env.so')
if os.path.exists(lib_path):
    datas.append((lib_path, '.'))

# Include the logo image
logo_path = os.path.join(project_root, 'nesendo-snakes-logo.png')
if os.path.exists(logo_path):
    datas.append((logo_path, '.'))

# Include any other necessary files
additional_files = [
    'README.md',
    'LICENSE',
    'requirements.txt'
]

for file in additional_files:
    file_path = os.path.join(project_root, file)
    if os.path.exists(file_path):
        datas.append((file_path, '.'))

# Hidden imports (modules that PyInstaller might miss)
hiddenimports = [
    'PyQt5.QtCore',
    'PyQt5.QtGui', 
    'PyQt5.QtWidgets',
    'PyQt5.QtMultimedia',
    'numpy',
    'gymnasium',
    'pyglet',
    'tqdm',
    'pickle',
    'json',
    'threading',
    'time',
    'pathlib',
    'typing'
]

# Analysis configuration
a = Analysis(
    [main_script],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Remove duplicate entries
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Create executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='nesendo-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True if you want console output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one
)
EOF

print_success "Spec file created: $SPEC_FILE"

# Run PyInstaller
print_status "Running PyInstaller..."
print_status "This may take several minutes..."

cd "$PROJECT_ROOT"

# Run PyInstaller with the spec file
pyinstaller --clean "$SPEC_FILE"

# Check if the binary was created
BINARY_PATH="$DIST_DIR/nesendo-gui"
if [ -f "$BINARY_PATH" ]; then
    print_success "Binary created successfully: $BINARY_PATH"
    
    # Make the binary executable
    chmod +x "$BINARY_PATH"
    
    # Get binary size
    BINARY_SIZE=$(du -h "$BINARY_PATH" | cut -f1)
    print_success "Binary size: $BINARY_SIZE"
    
    # Test if the binary runs (just check if it starts without errors)
    print_status "Testing binary..."
    timeout 5s "$BINARY_PATH" --help 2>/dev/null || {
        print_warning "Binary test failed, but this might be normal for GUI applications"
    }
    
    print_success "Build completed successfully!"
    print_status "Binary location: $BINARY_PATH"
    print_status "You can now run the binary with: $BINARY_PATH"
    
else
    print_error "Binary was not created. Check the build output above for errors."
    exit 1
fi

# Clean up spec file
print_status "Cleaning up..."
rm -f "$SPEC_FILE"

print_success "Build process completed!"
print_status "The standalone binary is ready at: $BINARY_PATH"
