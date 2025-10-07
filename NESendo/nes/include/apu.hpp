//  Program:      NESendo
//  File:         apu.hpp
//  Description:  This class houses the Audio Processing Unit (APU) for the NES
//
//  Copyright (c) 2019 Christian Kauten. All rights reserved.
//

#ifndef APU_HPP
#define APU_HPP

#include "common.hpp"
#include <vector>
#include <array>

namespace NES {

/// An NES Audio Processing Unit (APU)
class APU {
 private:
    /// Sample rate for audio output
    static const int SAMPLE_RATE = 44100;
    /// Number of samples per frame at 60 FPS
    static const int SAMPLES_PER_FRAME = SAMPLE_RATE / 60;
    /// Audio buffer for output
    std::vector<float> audio_buffer;
    /// Current sample index
    int sample_index;
    
    /// Pulse wave channel 1
    struct PulseChannel {
        bool enabled;
        bool duty_cycle;  // 0 or 1 for simple square wave
        int frequency;
        int counter;
        float volume;
        bool sweep_enabled;
        int sweep_period;
        int sweep_counter;
        int sweep_shift;
        bool sweep_negate;
        
        PulseChannel() : enabled(false), duty_cycle(false), frequency(0), counter(0), 
                        volume(0.0f), sweep_enabled(false), sweep_period(0), 
                        sweep_counter(0), sweep_shift(0), sweep_negate(false) {}
    } pulse1, pulse2;
    
    /// Triangle wave channel
    struct TriangleChannel {
        bool enabled;
        int frequency;
        int counter;
        float volume;
        bool linear_counter_enabled;
        int linear_counter;
        int linear_counter_reload;
        
        TriangleChannel() : enabled(false), frequency(0), counter(0), volume(0.0f),
                           linear_counter_enabled(false), linear_counter(0), linear_counter_reload(0) {}
    } triangle;
    
    /// Noise channel
    struct NoiseChannel {
        bool enabled;
        int period;
        int counter;
        float volume;
        int shift_register;
        bool mode;  // 0 = 15-bit, 1 = 6-bit
        
        NoiseChannel() : enabled(false), period(0), counter(0), volume(0.0f),
                        shift_register(1), mode(false) {}
    } noise;
    
    /// DMC (Delta Modulation Channel)
    struct DMCChannel {
        bool enabled;
        int sample_rate;
        int counter;
        float volume;
        bool loop;
        int address;
        int length;
        int current_address;
        int bytes_remaining;
        int shift_register;
        int bits_remaining;
        bool silence;
        
        DMCChannel() : enabled(false), sample_rate(0), counter(0), volume(0.0f),
                      loop(false), address(0), length(0), current_address(0),
                      bytes_remaining(0), shift_register(0), bits_remaining(0), silence(true) {}
    } dmc;
    
    /// Frame counter
    struct FrameCounter {
        int mode;  // 0 = 4-step, 1 = 5-step
        int step;
        int counter;
        bool irq_enabled;
        
        FrameCounter() : mode(0), step(0), counter(0), irq_enabled(false) {}
    } frame_counter;
    
    /// Master volume control
    float master_volume;
    /// Audio enabled flag
    bool audio_enabled;
    
    /// Audio filter state variables (converted from static)
    float prev_sample;
    float prev_prev_sample;
    
    /// Pulse wave phase tracking (converted from static)
    int pulse1_phase;
    int pulse2_phase;
    
    /// Triangle wave phase tracking (converted from static)
    int triangle_phase;
    
    /// Noise generation state (converted from static)
    int noise_lfsr;
    int noise_counter;
    
    /// Frame counter cycles tracking (converted from static)
    int frame_counter_cycles;

 public:
    /// Initialize a new APU
    APU();
    
    /// Reset the APU to initial state
    void reset();
    
    /// Step the APU by one CPU cycle
    void step();
    
    /// Generate audio samples for one frame
    void generate_frame_audio();
    
    /// Write to an APU register
    void write_register(NES_Address address, NES_Byte value);
    
    /// Read from an APU register
    NES_Byte read_register(NES_Address address);
    
    /// Get the current audio buffer
    const std::vector<float>& get_audio_buffer() const { return audio_buffer; }
    
    /// Clear the audio buffer
    void clear_buffer() { audio_buffer.clear(); }
    
    /// Get and clear the audio buffer (returns a copy)
    std::vector<float> get_and_clear_buffer() {
        std::vector<float> result = audio_buffer;
        audio_buffer.clear();
        return result;
    }
    
    /// Set master volume (0.0 to 1.0)
    void set_master_volume(float volume) { master_volume = std::max(0.0f, std::min(1.0f, volume)); }
    
    /// Enable/disable audio
    void set_audio_enabled(bool enabled) { audio_enabled = enabled; }
    
    /// Check if audio is enabled
    bool is_audio_enabled() const { return audio_enabled; }

 private:
    /// Generate a pulse wave sample
    float generate_pulse_sample(const PulseChannel& channel);
    
    /// Generate a triangle wave sample
    float generate_triangle_sample(const TriangleChannel& channel);
    
    /// Generate a noise sample
    float generate_noise_sample(const NoiseChannel& channel);
    
    /// Generate a DMC sample
    float generate_dmc_sample(const DMCChannel& channel);
    
    /// Update the frame counter
    void update_frame_counter();
    
    /// Clock the sweep unit for a pulse channel
    void clock_sweep(PulseChannel& channel);
    
    /// Clock the linear counter for triangle channel
    void clock_linear_counter();
    
    /// Clock the length counters
    void clock_length_counters();
    
    /// Clock the envelope generators
    void clock_envelopes();
};

}  // namespace NES

#endif  // APU_HPP
