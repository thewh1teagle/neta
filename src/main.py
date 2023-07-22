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
import argparse
import json

load_dotenv()  # take environment variables from .env.

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

def print_mics():
    mic_list = sr.Microphone.list_microphone_names()
    if len(mic_list) == 0:
        print("No microphone devices found.")
        return None
    
    for i, mic_name in enumerate(mic_list):
        print(f"Device {i + 1}: {mic_name}")

def print_langs():
    with open(ASSETS_PATH / 'languages.json', 'r') as f:
        langs = json.load(f)
    for key, value in langs.items():
        print(f'{key}: --lang {value}')


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
    parser = argparse.ArgumentParser(
        prog='Neta',
        description='Bard based assistant',
    )
    parser.add_argument('--lang', default='iw-IL', required=False, type=str, help='Language to use')
    parser.add_argument('--mic', default=1, required=False, type=int, help='Mic device index')
    parser.add_argument('--stop-word', required=False, default='תפסיקי', type=str, help='Stop word, when you say it, neta will stop talk')
    parser.add_argument('--list-mics', required=False, action='store_true', help='List available microfones')
    parser.add_argument('--list-langs', required=False, action='store_true', help='List available microfones')
    args = parser.parse_args()

    if args.list_mics:
        print_mics()
        exit(0)
    if args.list_langs:
        print_langs()
        exit(0)

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
    with sr.Microphone(args.mic, porcupine.sample_rate, porcupine.frame_length) as source:
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
                    prompt = r.recognize_google(audio, language=args.lang)
                except:
                    continue
                if prompt == args.stop_word:
                    continue
                
                print('Asking neta...')
                answer = bard.get_answer(prompt)
                
                audio = bard.speech(answer['content'], lang=args.lang)
                print('Speaking...')
                wav = ogg2wav(audio)
                player.play(wav)

if __name__ == '__main__':
    main()