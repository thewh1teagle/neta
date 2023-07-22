import wave
import pyaudio
from io import BytesIO
import threading

class WavPlayer:
    def __init__(self, output_device_index: int):
        self.chunk_size = 1024
        self.is_playing = False
        self.thread = None
        self.output_device_index = output_device_index
        self.stream = None
        self.wav_data = None
        self.p = pyaudio.PyAudio()
        

    def play(self, data: bytes):
        self.stop()
        self.wav_data = data
        self.is_playing = True
        self.thread = threading.Thread(target=self._playback)
        self.thread.start()

    def stop(self):
        self.is_playing = False
        if self.thread is not None:
            self.thread.join()
        self.thread = None

    def _playback(self):
        wave_file = wave.open(BytesIO(self.wav_data), 'rb')
        self.stream = self.p.open(
            format=self.p.get_format_from_width(wave_file.getsampwidth()),
            channels=wave_file.getnchannels(),
            rate=wave_file.getframerate(),
            output=True,
            output_device_index=self.output_device_index
        )

        while self.is_playing:
            data = wave_file.readframes(self.chunk_size)
            if not data:
                break
            self.stream.write(data)

        wave_file.close()
        self.stream.close()
