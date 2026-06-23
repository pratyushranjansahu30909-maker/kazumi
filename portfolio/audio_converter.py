import os
import av
import wave

def convert_to_wav(src_path, dest_path, sample_rate=32000):
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        container = av.open(src_path)
        stream = container.streams.audio[0]
        
        resampler = av.AudioResampler(
            format='s16',
            layout='mono',
            rate=sample_rate,
        )
        
        audio_data = []
        for frame in container.decode(stream):
            resampled_frames = resampler.resample(frame)
            for rf in resampled_frames:
                audio_data.append(rf.to_ndarray().tobytes())
                
        with wave.open(dest_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2) # 16-bit s16
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"".join(audio_data))
            
        print(f"Successfully converted {src_path} to {dest_path}")
        return True
    except Exception as e:
        print(f"Conversion failed: {e}")
        return False

def setup_reference_wav():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dest_wav = os.path.join(root_dir, "voices", "reference_voice.wav")
    
    # Try different media sources
    src_paths = [
        os.path.join(root_dir, "portfolio", "public", "audio", "reference_voice.webm"),
        # Fallback to the known absolute upload media path
        r"C:\Users\Lenovo\.gemini\antigravity-ide\brain\b14c4154-d3f0-48c0-8b45-09e3014f8fe4\uploaded_media_1782213740630.img",
        r"C:\Users\Lenovo\.gemini\antigravity-ide\brain\b14c4154-d3f0-48c0-8b45-09e3014f8fe4\uploaded_media_1782210820200.img"
    ]
    
    for src in src_paths:
        if os.path.exists(src):
            if convert_to_wav(src, dest_wav):
                return True
    return False

if __name__ == "__main__":
    setup_reference_wav()
