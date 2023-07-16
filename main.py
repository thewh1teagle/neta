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
import subprocess
import shutil

load_dotenv()  # take environment variables from .env.

LANG = 'he-IL' # English
PORCUPINE_KEY = os.getenv('PORCUPINE_KEY')
keyword_paths = ['hineta.ppn']

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
    for x in keyword_paths:
        keyword_phrase_part = os.path.basename(x).replace('.ppn', '').split('_')
        if len(keyword_phrase_part) > 6:
            keywords.append(' '.join(keyword_phrase_part[0:-6]))
        else:
            keywords.append(keyword_phrase_part[0])
    return keywords

def main():
    bard = Bard(token_from_browser=True)
    
    porcupine = pvporcupine.create(
            access_key=PORCUPINE_KEY,
            library_path=None,
            model_path=None,
            keyword_paths=keyword_paths,
            sensitivities=None
    )
    r = sr.Recognizer()
    keywords = load_keywords()
    with sr.Microphone(None, porcupine.sample_rate, porcupine.frame_length) as source:
        r.adjust_for_ambient_noise(source)  # listen for 1 second to calibrate the energy threshold for ambient noise levels
        while True:
            frame = source.stream.read(porcupine.frame_length)
            pcm = struct.unpack_from("h" * porcupine.frame_length, frame)
            result = porcupine.process(pcm)
            if result != -1:
                print('[%s] Detected %s' % (str(datetime.now()), keywords[result]))
                print("Say something!")
                audio = r.listen(source)
                prompt = r.recognize_google(audio, language=LANG)
                
                print('Asking neta...')
                answer = bard.get_answer(prompt)
                
                audio = bard.speech(answer['content'], lang=LANG)
                print('Speaking...')
                if Platform.WINDOWS:
                    import winsound
                    wav = ogg2wav(audio)
                    winsound.PlaySound(wav, winsound.SND_MEMORY)
                else:
                    if not shutil.which('ffplay'):
                        raise FileNotFoundError('ffplay must installed to play audio')
                    proc = subprocess.Popen(['ffplay', '-', '-autoexit', '-nodisp'], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    proc.stdin.write(audio)
                    proc.wait()
                print('Continue...')

if __name__ == '__main__':
    main()