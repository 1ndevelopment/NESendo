//  Program:      NESendo
//  File:         apu.cpp
//  Description:  This class houses the Audio Processing Unit (APU) for the NES
//
//  Copyright (c) 2019 Christian Kauten. All rights reserved.
//

#include "apu.hpp"
#include "log.hpp"
#include <cmath>
#include <algorithm>

namespace NES {

APU::APU() : sample_index(0), master_volume(0.5f), audio_enabled(true),
             prev_sample(0.0f), prev_prev_sample(0.0f),
             pulse1_phase(0), pulse2_phase(0), triangle_phase(0),
             noise_lfsr(1), noise_counter(0), frame_counter_cycles(0) {
    audio_buffer.reserve(SAMPLES_PER_FRAME);
    reset();
}

void APU::reset() {
    audio_buffer.clear();
    sample_index = 0;
    
    // Reset all channels to silent state
    pulse1 = PulseChannel();
    pulse1.enabled = false;
    pulse1.volume = 0.0f;
    pulse1.frequency = 0;
    
    pulse2 = PulseChannel();
    pulse2.enabled = false;
    pulse2.volume = 0.0f;
    pulse2.frequency = 0;
    
    triangle = TriangleChannel();
    triangle.enabled = false;
    triangle.volume = 0.0f;
    triangle.frequency = 0;
    
    noise = NoiseChannel();
    noise.enabled = false;
    noise.volume = 0.0f;
    noise.period = 0;
    
    dmc = DMCChannel();
    dmc.enabled = false;
    dmc.volume = 0.0f;
    
    frame_counter = FrameCounter();
    
    // Reset instance variables that were previously static
    prev_sample = 0.0f;
    prev_prev_sample = 0.0f;
    pulse1_phase = 0;
    pulse2_phase = 0;
    triangle_phase = 0;
    noise_lfsr = 1;
    noise_counter = 0;
    frame_counter_cycles = 0;
}

void APU::step() {
    if (!audio_enabled) return;
    
    // Update frame counter every 14915 CPU cycles (quarter frame)
    frame_counter_cycles++;
    if (frame_counter_cycles >= 14915) {
        update_frame_counter();
        frame_counter_cycles = 0;
    }
    
    // Clock sweep units
    clock_sweep(pulse1);
    clock_sweep(pulse2);
    
    // Clock linear counter
    clock_linear_counter();
    
    // Clock length counters
    clock_length_counters();
    
    // Clock envelopes
    clock_envelopes();
}

void APU::generate_frame_audio() {
    if (!audio_enabled) return;
    
    // Generate audio samples for one frame (60 FPS)
    // We need 44100 / 60 = 735 samples per frame
    int samples_per_frame = SAMPLE_RATE / 60;
    
    for (int i = 0; i < samples_per_frame; i++) {
        // Generate one audio sample
        float sample = 0.0f;
        
        // Only generate audio if channels are actually enabled and have valid frequencies
        // AND if the game has actually written to the audio registers
        if (pulse1.enabled && pulse1.frequency > 0 && pulse1.frequency < 20000 && pulse1.volume > 0.0f) {
            sample += generate_pulse_sample(pulse1) * 0.2f;  // Restore some volume
        }
        if (pulse2.enabled && pulse2.frequency > 0 && pulse2.frequency < 20000 && pulse2.volume > 0.0f) {
            sample += generate_pulse_sample(pulse2) * 0.2f;  // Restore some volume
        }
        if (triangle.enabled && triangle.frequency > 0 && triangle.frequency < 20000 && triangle.volume > 0.0f) {
            sample += generate_triangle_sample(triangle) * 0.2f;  // Restore some volume
        }
        if (noise.enabled && noise.period > 0 && noise.volume > 0.0f) {
            sample += generate_noise_sample(noise) * 0.1f;  // Restore some noise volume
        }
        if (dmc.enabled && dmc.volume > 0.0f) {
            sample += generate_dmc_sample(dmc) * 0.2f;  // Restore some volume
        }
        
        // Apply master volume
        sample *= master_volume;
        
        // Apply moderate low-pass filter to remove high-frequency artifacts
        
        // Two-stage low-pass filter to remove high-frequency noise
        float filtered_sample = 0.8f * sample + 0.2f * prev_sample;
        filtered_sample = 0.9f * filtered_sample + 0.1f * prev_prev_sample;
        
        prev_prev_sample = prev_sample;
        prev_sample = filtered_sample;
        sample = filtered_sample;
        
        // Clamp to valid range
        sample = std::max(-1.0f, std::min(1.0f, sample));
        
        // Add to buffer
        audio_buffer.push_back(sample);
    }
    
    // Limit buffer size to prevent memory issues (about 1 second of audio)
    if (audio_buffer.size() > SAMPLE_RATE) {
        audio_buffer.erase(audio_buffer.begin(), audio_buffer.begin() + (audio_buffer.size() - SAMPLE_RATE));
    }
}

void APU::write_register(NES_Address address, NES_Byte value) {
    // Debug: Print when audio registers are written
    // LOG(InfoVerbose) << "APU write: " << std::hex << +address << " = " << +value << std::endl;
    
    switch (address) {
        case 0x4000:  // Pulse 1 Control
            pulse1.duty_cycle = (value & 0x80) != 0;
            pulse1.volume = (value & 0x0F) / 15.0f;
            break;
            
        case 0x4001:  // Pulse 1 Sweep
            pulse1.sweep_enabled = (value & 0x80) != 0;
            pulse1.sweep_period = (value & 0x70) >> 4;
            pulse1.sweep_negate = (value & 0x08) != 0;
            pulse1.sweep_shift = value & 0x07;
            break;
            
        case 0x4002:  // Pulse 1 Timer Low
            pulse1.frequency = (pulse1.frequency & 0xFF00) | value;
            break;
            
        case 0x4003:  // Pulse 1 Timer High
            pulse1.frequency = (pulse1.frequency & 0x00FF) | (value << 8);
            pulse1.enabled = true;
            pulse1.counter = 0;
            // Ensure we have a valid frequency
            if (pulse1.frequency == 0) pulse1.frequency = 440;  // Default to A4 note
            break;
            
        case 0x4004:  // Pulse 2 Control
            pulse2.duty_cycle = (value & 0x80) != 0;
            pulse2.volume = (value & 0x0F) / 15.0f;
            break;
            
        case 0x4005:  // Pulse 2 Sweep
            pulse2.sweep_enabled = (value & 0x80) != 0;
            pulse2.sweep_period = (value & 0x70) >> 4;
            pulse2.sweep_negate = (value & 0x08) != 0;
            pulse2.sweep_shift = value & 0x07;
            break;
            
        case 0x4006:  // Pulse 2 Timer Low
            pulse2.frequency = (pulse2.frequency & 0xFF00) | value;
            break;
            
        case 0x4007:  // Pulse 2 Timer High
            pulse2.frequency = (pulse2.frequency & 0x00FF) | (value << 8);
            pulse2.enabled = true;
            pulse2.counter = 0;
            // Ensure we have a valid frequency
            if (pulse2.frequency == 0) pulse2.frequency = 440;  // Default to A4 note
            break;
            
        case 0x4008:  // Triangle Control
            triangle.linear_counter_enabled = (value & 0x80) != 0;
            triangle.linear_counter_reload = value & 0x7F;
            break;
            
        case 0x400A:  // Triangle Timer Low
            triangle.frequency = (triangle.frequency & 0xFF00) | value;
            break;
            
        case 0x400B:  // Triangle Timer High
            triangle.frequency = (triangle.frequency & 0x00FF) | (value << 8);
            triangle.enabled = true;
            triangle.counter = 0;
            // Ensure we have a valid frequency
            if (triangle.frequency == 0) triangle.frequency = 440;  // Default to A4 note
            break;
            
        case 0x400C:  // Noise Control
            noise.volume = (value & 0x0F) / 15.0f;
            break;
            
        case 0x400E:  // Noise Period
            noise.period = value & 0x0F;
            noise.mode = (value & 0x80) != 0;
            break;
            
        case 0x400F:  // Noise Length
            noise.enabled = true;
            noise.counter = 0;
            break;
            
        case 0x4010:  // DMC Control
            dmc.sample_rate = value & 0x0F;
            dmc.loop = (value & 0x40) != 0;
            // Note: irq_enabled is not part of DMCChannel structure
            break;
            
        case 0x4011:  // DMC Direct Load
            dmc.volume = (value & 0x7F) / 127.0f;
            break;
            
        case 0x4012:  // DMC Address
            dmc.address = 0xC000 + (value << 6);
            break;
            
        case 0x4013:  // DMC Length
            dmc.length = (value << 4) + 1;
            break;
            
        case 0x4015:  // Channel Enable
            pulse1.enabled = (value & 0x01) != 0;
            pulse2.enabled = (value & 0x02) != 0;
            triangle.enabled = (value & 0x04) != 0;
            noise.enabled = (value & 0x08) != 0;
            dmc.enabled = (value & 0x10) != 0;
            break;
            
        case 0x4017:  // Frame Counter
            frame_counter.mode = (value & 0x80) != 0 ? 1 : 0;
            frame_counter.irq_enabled = (value & 0x40) == 0;
            frame_counter.step = 0;
            frame_counter.counter = 0;
            break;
            
        default:
            LOG(InfoVerbose) << "APU write to unknown register: " << std::hex << +address << std::endl;
            break;
    }
}

NES_Byte APU::read_register(NES_Address address) {
    switch (address) {
        case 0x4015:  // Channel Status
            return (pulse1.enabled ? 0x01 : 0) |
                   (pulse2.enabled ? 0x02 : 0) |
                   (triangle.enabled ? 0x04 : 0) |
                   (noise.enabled ? 0x08 : 0) |
                   (dmc.enabled ? 0x10 : 0);
        default:
            return 0;
    }
}

float APU::generate_pulse_sample(const PulseChannel& channel) {
    if (!channel.enabled || channel.frequency == 0 || channel.frequency > 20000) return 0.0f;
    
    // Calculate period in samples with bounds checking
    int period = SAMPLE_RATE / channel.frequency;
    if (period <= 0 || period > SAMPLE_RATE) return 0.0f;
    
    // Use a more stable phase calculation
    int& phase = (&channel == &pulse1) ? pulse1_phase : pulse2_phase;
    
    phase = (phase + 1) % period;
    
    // Generate square wave based on duty cycle
    float sample = 0.0f;
    if (channel.duty_cycle) {
        // 50% duty cycle
        sample = (phase < period / 2) ? 1.0f : -1.0f;
    } else {
        // 25% duty cycle
        sample = (phase < period / 4) ? 1.0f : -1.0f;
    }
    
    // Apply volume and ensure we don't generate extreme values
    return sample * channel.volume * 0.4f;  // Restore some amplitude
}

float APU::generate_triangle_sample(const TriangleChannel& channel) {
    if (!channel.enabled || channel.frequency == 0 || channel.frequency > 20000) return 0.0f;
    
    // Calculate period in samples with bounds checking
    int period = SAMPLE_RATE / channel.frequency;
    if (period <= 0 || period > SAMPLE_RATE) return 0.0f;
    
    // Use a more stable phase calculation
    triangle_phase = (triangle_phase + 1) % period;
    
    // Generate triangle wave
    float sample = 0.0f;
    if (triangle_phase < period / 2) {
        sample = (2.0f * triangle_phase / (period / 2)) - 1.0f;
    } else {
        sample = 3.0f - (2.0f * triangle_phase / (period / 2));
    }
    
    // Apply volume and reduce amplitude
    return sample * channel.volume * 0.5f;  // Restore some amplitude
}

float APU::generate_noise_sample(const NoiseChannel& channel) {
    if (!channel.enabled || channel.period <= 0) return 0.0f;
    
    // Simple noise generation using linear feedback shift register
    noise_counter++;
    if (noise_counter >= channel.period) {
        noise_counter = 0;
        // 15-bit LFSR for noise generation
        int feedback = (noise_lfsr ^ (noise_lfsr >> 1)) & 1;
        noise_lfsr = (noise_lfsr >> 1) | (feedback << 14);
    }
    
    float sample = (noise_lfsr & 1) ? 1.0f : -1.0f;
    return sample * channel.volume * 0.3f;  // Reduce noise amplitude significantly
}

float APU::generate_dmc_sample(const DMCChannel& channel) {
    if (!channel.enabled) return 0.0f;
    
    // Simple DMC implementation - just return silence for now
    return 0.0f;
}

void APU::update_frame_counter() {
    frame_counter.step++;
    
    if (frame_counter.mode == 0) {  // 4-step mode
        if (frame_counter.step >= 4) {
            frame_counter.step = 0;
        }
    } else {  // 5-step mode
        if (frame_counter.step >= 5) {
            frame_counter.step = 0;
        }
    }
}

void APU::clock_sweep(PulseChannel& channel) {
    if (!channel.sweep_enabled) return;
    
    channel.sweep_counter++;
    if (channel.sweep_counter >= channel.sweep_period) {
        channel.sweep_counter = 0;
        
        int change = channel.frequency >> channel.sweep_shift;
        if (channel.sweep_negate) {
            channel.frequency -= change;
        } else {
            channel.frequency += change;
        }
        
        // Clamp frequency to valid range
        if (channel.frequency < 0) channel.frequency = 0;
        if (channel.frequency > 0x7FF) channel.frequency = 0x7FF;
    }
}

void APU::clock_linear_counter() {
    if (triangle.linear_counter_enabled) {
        if (triangle.linear_counter > 0) {
            triangle.linear_counter--;
        }
    } else {
        triangle.linear_counter = triangle.linear_counter_reload;
    }
}

void APU::clock_length_counters() {
    // Simple length counter implementation
    if (pulse1.counter > 0) pulse1.counter--;
    if (pulse2.counter > 0) pulse2.counter--;
    if (triangle.counter > 0) triangle.counter--;
    if (noise.counter > 0) noise.counter--;
}

void APU::clock_envelopes() {
    // Simple envelope implementation - just use volume directly
    // In a full implementation, this would handle ADSR envelopes
}

}  // namespace NES
