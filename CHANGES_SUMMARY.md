# Git Changes Summary

## Overview
This appears to be a major refactoring of the NESendo project, involving package restructuring, dependency updates, and API modernization.

## Major Changes

### 1. Package Restructuring
- **Renamed package**: `nes_py` → `NESendo`
- **Updated imports**: All references to `nes_py` have been changed to `NESendo`
- **Updated entry points**: 
  - `nes_py` → `NESendo`
  - Added new GUI entry point: `NESendo-gui`

### 2. Dependency Updates
- **Gym → Gymnasium**: Updated from `gym>=0.17.2` to `gymnasium>=0.28.0`
- **Added GUI dependencies**: 
  - `PyQt5>=5.15.0`
  - `PyQt5.QtMultimedia>=5.15.0`

### 3. API Modernization (Gymnasium Migration)
- **Environment reset**: Changed from `env.reset()` to `env.reset()` returning `(state, info)` tuple
- **Environment step**: Changed from `env.step(action)` returning `(state, reward, done, info)` to `(state, reward, terminated, truncated, info)`
- **Done flag handling**: Now uses `terminated or truncated` instead of single `done` flag

### 4. File Structure Changes
- **Removed test files**: All test files under `nes_py/tests/` have been deleted
- **Removed wrapper files**: All wrapper files under `nes_py/wrappers/` have been deleted
- **Updated paths**: All file paths have been updated to reflect the new package structure

### 5. Setup Configuration Updates
- **Package name**: Changed from `nes_py` to `NESendo`
- **Library name**: Updated from `nes_py.lib_nes_env` to `NESendo.lib_nes_env`
- **Source paths**: Updated to use `NESendo/nes/` instead of `nes_py/nes/`
- **Include directories**: Updated to use `NESendo/nes/include`
- **Simplified setup**: Removed extensive metadata and classifiers, focusing on core functionality

### 6. Code Updates
- **Scripts updated**: Both `scripts/run.py` and `speedtest.py` have been updated to:
  - Use new import paths (`from NESendo import NESEnv`)
  - Handle new Gymnasium API (tuple returns from reset/step)
  - Use new ROM file paths

## Files Modified
- `requirements.txt` - Updated dependencies
- `setup.py` - Simplified and updated package configuration
- `scripts/run.py` - Updated for new API and paths
- `speedtest.py` - Updated for new API and paths

## Files Deleted
- All files under `nes_py/tests/` (test cases, ROM files, utilities)
- All files under `nes_py/wrappers/` (environment wrappers)
- `nes_py/__init__.py` and related package files

## Impact
This is a significant modernization effort that:
1. **Updates the project to use modern Gymnasium API** instead of deprecated Gym
2. **Adds GUI capabilities** with PyQt5 integration
3. **Simplifies the package structure** by removing test files and wrappers
4. **Maintains core NES emulation functionality** while modernizing the interface

The changes suggest this is either a fork of the original `nes-py` project or a major version upgrade that modernizes the codebase for current Python/Gymnasium standards.
