//  Program:      NESendo
//  File:         lib_nes_env.cpp
//  Description:  file describes the outward facing ctypes API for Python
//
//  Copyright (c) 2019 Christian Kauten. All rights reserved.
//

#include <string>
#include <cstring>
#include "common.hpp"
#include "emulator.hpp"

// Windows-base systems
#if defined(_WIN32) || defined(WIN32) || defined(__CYGWIN__) || defined(__MINGW32__) || defined(__BORLANDC__)
    // setup the module initializer. required to link visual studio C++ ctypes
    void PyInit_lib_nes_env() { }
    // setup the function modifier to export in the DLL
    #define EXP __declspec(dllexport)
// Unix-like systems
#else
    // setup the modifier as a dummy
    #define EXP
#endif

// definitions of functions for the Python interface to access
extern "C" {
    /// Return the width of the NES.
    EXP int Width() {
        return NES::Emulator::WIDTH;
    }

    /// Return the height of the NES.
    EXP int Height() {
        return NES::Emulator::HEIGHT;
    }

    /// Initialize a new emulator and return a pointer to it
    EXP NES::Emulator* Initialize(wchar_t* path) {
        // convert the c string to a c++ std string data structure
        std::wstring ws_rom_path(path);
        std::string rom_path(ws_rom_path.begin(), ws_rom_path.end());
        // create a new emulator with the given ROM path
        return new NES::Emulator(rom_path);
    }

    /// Return a pointer to a controller on the machine
    EXP NES::NES_Byte* Controller(NES::Emulator* emu, int port) {
        return emu->get_controller(port);
    }

    /// Return the pointer to the screen buffer
    EXP NES::NES_Pixel* Screen(NES::Emulator* emu) {
        return emu->get_screen_buffer();
    }

    /// Return the pointer to the memory buffer
    EXP NES::NES_Byte* Memory(NES::Emulator* emu) {
        return emu->get_memory_buffer();
    }

    /// Reset the emulator
    EXP void Reset(NES::Emulator* emu) {
        emu->reset();
    }

    /// Perform a discrete step in the emulator (i.e., 1 frame)
    EXP void Step(NES::Emulator* emu) {
        emu->step();
    }

    /// Create a deep copy (i.e., a clone) of the given emulator
    EXP void Backup(NES::Emulator* emu) {
        emu->backup();
    }

    /// Create a deep copy (i.e., a clone) of the given emulator
    EXP void Restore(NES::Emulator* emu) {
        emu->restore();
    }

    /// Set the master volume for audio output
    EXP void SetMasterVolume(NES::Emulator* emu, float volume) {
        emu->set_master_volume(volume);
    }

    /// Enable or disable audio output
    EXP void SetAudioEnabled(NES::Emulator* emu, bool enabled) {
        emu->set_audio_enabled(enabled);
    }

    /// Get the audio buffer size
    EXP int GetAudioBufferSize(NES::Emulator* emu) {
        const std::vector<float>* buffer = emu->get_audio_buffer();
        return buffer ? static_cast<int>(buffer->size()) : 0;
    }

    /// Get audio buffer data
    EXP const float* GetAudioBuffer(NES::Emulator* emu) {
        const std::vector<float>* buffer = emu->get_audio_buffer();
        return buffer && !buffer->empty() ? buffer->data() : nullptr;
    }

    /// Get and clear the audio buffer
    EXP void GetAndClearAudioBuffer(NES::Emulator* emu, float* output_buffer, int max_size) {
        std::vector<float> buffer = emu->get_and_clear_audio_buffer();
        int copy_size = std::min(static_cast<int>(buffer.size()), max_size);
        if (copy_size > 0 && output_buffer) {
            std::memcpy(output_buffer, buffer.data(), copy_size * sizeof(float));
        }
    }

    /// Clear the audio buffer
    EXP void ClearAudioBuffer(NES::Emulator* emu) {
        // Use the get_and_clear_buffer method instead of direct manipulation
        emu->get_and_clear_audio_buffer();
    }

    /// Close the emulator, i.e., purge it from memory
    EXP void Close(NES::Emulator* emu) {
        delete emu;
    }
}

// un-define the macro
#undef EXP
