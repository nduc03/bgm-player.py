import wave
import subprocess
import queue
import time
import threading
import json
import os
import sys

DEBUG = os.environ.get('DEBUG', '0') == '1'

# syntax: play.py [intro] loop
if len(sys.argv) < 2:
    print('Usage: python3 play.py [path/to/intro] path/to/loop')
    sys.exit(1)

#    when full intro + loop             when only loop is provided
#         vvvvv                                 vvvv
intro = sys.argv[1] if len(sys.argv) >= 3 else None
loop = sys.argv[2] if len(sys.argv) >= 3 else sys.argv[1]

def get_info(path):
    cmd = ['ffprobe', '-show_streams', '-of', 'json', path]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f'ffprobe failed: {result.stderr}')
    info = json.loads(result.stdout)
    return info['streams'][0]

info = get_info(loop)

sample_rate = str(info['sample_rate'])
channels = str(info['channels'])
format = 's16le' if info['codec_name'] == 'pcm_s16le' else None

if format is None:
    # TODO use ffmpeg to convert
    raise RuntimeError(f'Unsupported format: {info["codec_name"]}')

command = ['ffplay', '-f', 's16le', '-ac', channels, '-ar', sample_rate, '-nodisp', '-']

chunk_size = 2048

data_queue = queue.Queue(15)

def read_loop():
    with wave.open(loop, 'rb') as wf:
        while True:
            data = wf.readframes(chunk_size)
            if not data:
                wf.rewind()
                continue
            data_queue.put(data)

            while data_queue.qsize() > 10:
                time.sleep(0.001)

def read():
    if intro is not None:
        with wave.open(intro, 'rb') as wf:
            while True:
                data = wf.readframes(chunk_size)
                if not data:
                    break
                data_queue.put(data)

                while data_queue.qsize() > 10:
                    time.sleep(0.001)
    read_loop()


def monitor_queue():
    if not DEBUG:
        return
    while True:
        print(f'\n\nQueue size: {data_queue.qsize()}\n\n')
        time.sleep(1)

threading.Thread(target=read, daemon=True).start()
threading.Thread(target=monitor_queue, daemon=True).start()

with subprocess.Popen(command, stdin=subprocess.PIPE) as proc:
    while True:
        if data_queue.qsize() == 0:
            time.sleep(0.001)
            continue
        data = data_queue.get()
        if not data:
            print('something wrong')
            break
        proc.stdin.write(data)
        proc.stdin.flush()

    proc.stdin.close()
    proc.wait()

data_queue.join()
