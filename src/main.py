import os
import io
import struct
from datetime import datetime
import speech_recognition as sr
import pvporcupine
from bardapi import Bard
import soundfile as sf
from dotenv import load_dotenv
from platform_detector import Platform
from wav_player import WavPlayer
from pathlib import Path
import signal

load_dotenv()  # take environment variables from .env.

LANG = 'he-IL' # English
PORCUPINE_KEY = os.getenv('PORCUPINE_KEY')
ASSETS_PATH = Path(__file__).parent / '../assets'
keyword_paths = [ASSETS_PATH / 'hineta_win.ppn' if Platform.WINDOWS else ASSETS_PATH / 'hineta_linux.ppn']

class GracefulExiter():

    def __init__(self):
        self.state = False
        signal.signal(signal.SIGINT, self.change_state)

    def change_state(self, signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        self.state = True

    def exit(self):
        return self.state

def choose_microphone_device():
    mic_list = sr.Microphone.list_microphone_names()
    if len(mic_list) == 0:
        print("No microphone devices found.")
        return None
    
    for i, mic_name in enumerate(mic_list):
        print(f"Device {i + 1}: {mic_name}")
    
    device_number = input("Enter the device number for your microphone (or Enter for default device): ")
    
    if device_number.lower() == 'q':
        return None
    
    try:
        device_number = int(device_number)
        if device_number < 1 or device_number > len(mic_list):
            print("Invalid device number. Please try again.")
            return None
        
        return device_number
    except ValueError:
        if device_number != '':
            print("Invalid input. Please enter a valid device number.")
        return None

def ogg2wav(ogg: bytes):
    ogg_buf = io.BytesIO(ogg)
    ogg_buf.name = 'file.ogg'
    data, samplerate = sf.read(ogg_buf)
    wav_buf = io.BytesIO()
    wav_buf.name = 'file.wav'
    sf.write(wav_buf, data, samplerate)
    wav_buf.seek(0)
    return wav_buf.read()

def load_keywords():
    keywords = list()
    for k in keyword_paths:
        keyword_phrase_part = k.name.replace('.ppn', '').split('_')
        if len(keyword_phrase_part) > 6:
            keywords.append(' '.join(keyword_phrase_part[0:-6]))
        else:
            keywords.append(keyword_phrase_part[0])
    return keywords

def main():
    exiter = GracefulExiter()
    bard = Bard(token_from_browser=True)
    player = WavPlayer()
    
    porcupine = pvporcupine.create(
            access_key=PORCUPINE_KEY,
            library_path=None,
            model_path=None,
            keyword_paths=keyword_paths,
            sensitivities=None
    )
    r = sr.Recognizer()
    keywords = load_keywords()
    device_index = choose_microphone_device()
    with sr.Microphone(device_index, porcupine.sample_rate, porcupine.frame_length) as source:
        r.adjust_for_ambient_noise(source)  # listen for 1 second to calibrate the energy threshold for ambient noise levels
        while True:
            if exiter.exit():
                player.stop()
                break
            frame = source.stream.read(porcupine.frame_length)
            pcm = struct.unpack_from("h" * porcupine.frame_length, frame)
            result = porcupine.process(pcm)
            if result != -1:
                player.stop()
                print('[%s] Detected %s' % (str(datetime.now()), keywords[result]))
                print("Say something!")
                audio = r.listen(source)
                try:
                    prompt = r.recognize_google(audio, language=LANG)
                except:
                    continue
                if prompt == 'תפסיקי':
                    continue
                
                print('Asking neta...')
                answer = bard.get_answer(prompt)
                
                audio = bard.speech(answer['content'], lang=LANG)
                print('Speaking...')
                wav = ogg2wav(audio)
                player.play(wav)

if __name__ == '__main__':
    main()