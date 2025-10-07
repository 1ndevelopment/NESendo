<p align="center">
<img
    src="https://raw.githubusercontent.com/1ndevelopment/NESendo/refs/heads/master/NESendo/imgs/logo.png"
    width="75%"
/>
</p>

NESendo is a [forked](https://github.com/Kautenja/nes-py) Nintendo Entertainment System (NES) emulator designed for educational and development purposes.
Based on the [SimpleNES](https://github.com/amhndu/SimpleNES) emulator.

<table align="center">
    <tr>
        <td>
            <img
                width="256"
                alt="Bomberman II"
                src="https://user-images.githubusercontent.com/2184469/84821320-8c52e780-afe0-11ea-820a-662d0e54fc90.png"
            />
        </td>
        <td>
             <img
                width="256"
                alt="Castelvania II"
                src="https://user-images.githubusercontent.com/2184469/84821323-8ceb7e00-afe0-11ea-89f1-56d379ae4286.png"
            />
        </td>
        <td>
            <img
                width="256"
                alt="Excitebike"
                src="https://user-images.githubusercontent.com/2184469/84821325-8d841480-afe0-11ea-9ae2-599b83af6f65.png"
            />
        </td>
    </tr>
    <tr>
        <td>
            <img
                width="256"
                alt="Super Mario Bros."
                src="https://user-images.githubusercontent.com/2184469/84821327-8d841480-afe0-11ea-8172-d564aca35b5e.png"
            />
        </td>
        <td>
            <img
                width="256"
                alt="The Legend of Zelda"
                src="https://user-images.githubusercontent.com/2184469/84821329-8d841480-afe0-11ea-9a57-c9daca04ed3b.png"
            />
        </td>
        <td>
            <img
                 width="256"
                 alt="Tetris"
                 src="https://user-images.githubusercontent.com/2184469/84822244-fc15a200-afe1-11ea-81de-2323845d7537.png"
            />
        </td>
    </tr>
    <tr>
        <td>
            <img
                 width="256"
                 alt="Contra"
                 src="https://user-images.githubusercontent.com/2184469/84822247-fcae3880-afe1-11ea-901d-1ef5e8378989.png"
            />
        </td>
        <td>
            <img
                 width="256"
                 alt="Mega Man II"
                 src="https://user-images.githubusercontent.com/2184469/84822249-fcae3880-afe1-11ea-8271-9e898933e571.png"
            />
        </td>
        <td>
            <img
                width="256"
                alt="Bubble Bobble"
                src="https://user-images.githubusercontent.com/2184469/84822551-79411700-afe2-11ea-9ed6-947d78f29e8f.png"
            />
        </td>
    </tr>
</table>

# What is this exactly?

NESendo combines a high-performance NES emulation core written in C++ with a Python interface and a modern PyQt5 graphical user interface (GUI) featuring a dark theme.

It supports multiple popular cartridge mappers, enabling the use of a variety of classic NES games. Allowing users to run NES games, develop custom NES environments, and experiment with emulator features in a flexible Python-based ecosystem.

# Linux Installation

Make sure you have the `clang++` compiler installed:

```shell
## On debian distros
sudo apt-get install clang scons
## On arch distros
sudo pacman -S clang scons
```

### 1.  Clone/setup project

```shell
git clone https://git.1ndev.com/1ndevelopment/NESendo
cd NESendo
```

### 2.  Install dependencies

```shell
pip install -r requirements.txt
```

### 3.  Build C++ library

```shell
make lib_nes_env
```

### 3.  Install the package

```shell
pip install -e .
```

### 4.  Play a game

```shell
## Launch via GUI:s

python -m NESendo.app.gui

## OR launch with CLI:

NESendo -r /path/to/rom.nes
```

# Building a Standalone Binary

NESendo can be compiled into a standalone binary that includes all dependencies, making it easy to distribute and run without requiring Python or additional packages to be installed.

## Prerequisites

Before building the binary, ensure you have the following installed:

- Python 3.5+ with pip
- C++ compiler (g++ or clang++)
- PyInstaller
- All project dependencies

## Build Steps

### 1. Install Dependencies

First, install the required Python packages:

```shell
pip install -r requirements.txt
pip install pyinstaller
```

### 2. Build the Binary using the provided script

A build script is provided to automate the process of compiling the C++ core and creating a standalone binary. Simply run:
```shell
./scripts/build-binary.sh
```

## Binary Features

The compiled binary includes:

- **Complete NES emulator** with C++ core
- **PyQt5 GUI** with modern dark theme
- **All dependencies** bundled (numpy, gymnasium, etc.)
- **Test ROMs** included for immediate testing
- **No installation required** - just run the executable

## Binary Size and Distribution

- **Size:** Approximately 66 MB
- **Platform:** Linux x86_64 (can be built for other platforms)
- **Dependencies:** None required on target system
- **Portable:** Can be copied and run on any compatible Linux system

## Customizing the Build

The build process is controlled by the generated `.spec` file. You can modify this file to:

- Change the binary name
- Add additional data files
- Include custom icons
- Modify build options

## Troubleshooting

If you encounter issues during the build process:

1. **Missing dependencies:** Ensure all packages in `requirements.txt` are installed
2. **C++ compilation errors:** Check that you have a compatible C++ compiler installed
3. **PyInstaller errors:** Try updating PyInstaller to the latest version
4. **Runtime errors:** Test the binary with the included test ROMs first

# PIP Package Installation

The preferred installation of `NESendo` is from `pip`:

```shell
cd /path/to/NESendo
pip install -e .
```

# Usage

To access the NES emulator from the command line use the following command.

```shell
NESendo -r <path_to_rom>
```

To print out documentation for the command line interface execute:

```shell
NESendo -h
```

## Controls

| Keyboard Key | NES Joypad    |
|:-------------|:--------------|
| W            | Up            |
| A            | Left          |
| S            | Down          |
| D            | Right         |
| O            | A             |
| P            | B             |
| Enter        | Start         |
| Space        | Select        |

## Parallelism Caveats

both the `threading` and `multiprocessing` packages are supported by
`NESendo` with some caveats related to rendering:

1.  rendering **is not** supported from instances of `threading.Thread`
2.  rendering **is** supported from instances of `multiprocessing.Process`,
    but `NESendo` must be imported within the process that executes the render
    call

# Development

To design a custom environment using `NESendo`, introduce new features, or fix
a bug, please refer to the [Wiki](https://github.com/Kautenja/NESendo/wiki).
There you will find instructions for:

-   setting up the development environment
-   designing environments based on the `NESEnv` class
-   reference material for the `NESEnv` API

# Cartridge Mapper Compatibility

0.  NROM
1.  MMC1 / SxROM
2.  UxROM
3.  CNROM

Compatible mappers: NROM (0), MMC1/SxROM (1), UxROM (2), CNROM (3)

# Disclaimer

**This project is provided for educational purposes only. It is not
affiliated with and has not been approved by Nintendo.**
