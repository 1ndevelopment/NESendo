//  Program:      NESendo
//  File:         emulator.hpp
//  Description:  This class houses the logic and data for an NES emulator
//
//  Copyright (c) 2019 Christian Kauten. All rights reserved.
//

#ifndef EMULATOR_HPP
#define EMULATOR_HPP

#include <string>
#include "common.hpp"
#include "cartridge.hpp"
#include "controller.hpp"
#include "cpu.hpp"
#include "ppu.hpp"
#include "main_bus.hpp"
#include "picture_bus.hpp"
#include "apu.hpp"

namespace NES {

/// An NES Emulator and OpenAI Gym interface
class Emulator {
 private:
    /// The number of cycles in 1 frame
    static const int CYCLES_PER_FRAME = 29781;
    /// the virtual cartridge with ROM and mapper data
    Cartridge cartridge;
    /// the 2 controllers on the emulator
    Controller controllers[2];

    /// the main data bus of the emulator
    MainBus bus;
    /// the picture bus from the PPU of the emulator
    PictureBus picture_bus;
    /// The emulator's CPU
    CPU cpu;
    /// the emulators' PPU
    PPU ppu;
    /// the emulator's APU
    APU apu;

    /// the main data bus of the emulator
    MainBus backup_bus;
    /// the picture bus from the PPU of the emulator
    PictureBus backup_picture_bus;
    /// The emulator's CPU
    CPU backup_cpu;
    /// the emulators' PPU
    PPU backup_ppu;
    /// the emulator's APU
    APU backup_apu;

 public:
    /// The width of the NES screen in pixels
    static const int WIDTH = SCANLINE_VISIBLE_DOTS;
    /// The height of the NES screen in pixels
    static const int HEIGHT = VISIBLE_SCANLINES;

    /// Initialize a new emulator with a path to a ROM file.
    ///
    /// @param rom_path the path to the ROM for the emulator to run
    ///
    explicit Emulator(std::string rom_path);

    /// Return a 32-bit pointer to the screen buffer's first address.
    ///
    /// @return a 32-bit pointer to the screen buffer's first address
    ///
    inline NES_Pixel* get_screen_buffer() { return ppu.get_screen_buffer(); }

    /// Return a 8-bit pointer to the RAM buffer's first address.
    ///
    /// @return a 8-bit pointer to the RAM buffer's first address
    ///
    inline NES_Byte* get_memory_buffer() { return bus.get_memory_buffer(); }

    /// Return a pointer to a controller port
    ///
    /// @param port the port of the controller to return the pointer to
    /// @return a pointer to the byte buffer for the controller state
    ///
    inline NES_Byte* get_controller(int port) {
        return controllers[port].get_joypad_buffer();
    }

    /// Return a pointer to the audio buffer
    ///
    /// @return a pointer to the audio buffer
    ///
    inline const std::vector<float>* get_audio_buffer() { return &apu.get_audio_buffer(); }
    
    /// Get and clear the audio buffer
    ///
    /// @return a copy of the audio buffer, then clears the original
    ///
    inline std::vector<float> get_and_clear_audio_buffer() { return apu.get_and_clear_buffer(); }

    /// Set the master volume for audio output
    ///
    /// @param volume the volume level (0.0 to 1.0)
    ///
    inline void set_master_volume(float volume) { apu.set_master_volume(volume); }

    /// Enable or disable audio output
    ///
    /// @param enabled whether audio should be enabled
    ///
    inline void set_audio_enabled(bool enabled) { apu.set_audio_enabled(enabled); }

    /// Load the ROM into the NES.
    inline void reset() { cpu.reset(bus); ppu.reset(); apu.reset(); }

    /// Perform a step on the emulator, i.e., a single frame.
    void step();

    /// Create a backup state on the emulator.
    inline void backup() {
        backup_bus = bus;
        backup_picture_bus = picture_bus;
        backup_cpu = cpu;
        backup_ppu = ppu;
        backup_apu = apu;
    }

    /// Restore the backup state on the emulator.
    inline void restore() {
        bus = backup_bus;
        picture_bus = backup_picture_bus;
        cpu = backup_cpu;
        ppu = backup_ppu;
        apu = backup_apu;
    }
};

}  // namespace NES

#endif  // EMULATOR_HPP
