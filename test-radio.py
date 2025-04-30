# experimenting radio format

import wave
import subprocess
import queue
import time
import threading
import json
import os
import sys

DEBUG = os.environ.get('DEBUG', '0') == '1'
CHUNK_SIZE = 2048
MAX_QUEUE_SIZE = 15
QUEUE_PAUSE_THRESHOLD = 10
QUEUE_CHECK_INTERVAL = 0.001

def convert_to_pcm_s16le(path):
    pass

def parse_args():
    # syntax: play.py [intro] loop
    if len(sys.argv) < 2:
        print('Usage: playbgm [path/to/intro] path/to/loop')
        sys.exit(1)

    #    when full intro + loop             when only loop is provided
    #         vvvvv                                 vvvv
    intro = sys.argv[1] if len(sys.argv) >= 3 else None
    loop = sys.argv[2] if len(sys.argv) >= 3 else sys.argv[1]

    return intro, loop

def get_play_command(path):
    def get_info(path):
        cmd = ['ffprobe', '-show_streams', '-of', 'json', path]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f'ffprobe failed: {result.stderr}')
        info = json.loads(result.stdout)
        return info['streams'][0]

    def get_ch_layout(channels):
        if channels == 1:
            return 'mono'
        elif channels == 2:
            return 'stereo'
        else:
            raise ValueError(f'Unsupported number of channels: {channels}')

    info = get_info(path)

    sample_rate = str(info['sample_rate'])
    channel_layout = get_ch_layout(info['channels'])
    format = 's16le' if info['codec_name'] == 'pcm_s16le' else None

    if format is None:
        # TODO use ffmpeg to convert
        raise RuntimeError(f'Unsupported format: {info["codec_name"]}')

    command = ['ffmpeg',
               '-re', '-f', 's16le', '-ac', '2', '-ar', sample_rate, '-i', 'pipe:0',
               '-c:a', 'libopus', '-b:a', '320k', '-f', 'mpegts', 'udp://127.0.0.1:9000']

    return command


class BgmPlayer:
    def __init__(self):
        self.intro, self.loop = parse_args()

        self.command = get_play_command(self.loop)

        self.data_queue = queue.Queue(MAX_QUEUE_SIZE)

    def read_loop(self):
        with wave.open(self.loop, 'rb') as wf:
            while True:
                data = wf.readframes(CHUNK_SIZE)
                if not data:
                    wf.rewind()
                    continue
                self.data_queue.put(data)

                while self.data_queue.qsize() > QUEUE_PAUSE_THRESHOLD:
                    time.sleep(QUEUE_CHECK_INTERVAL)

    def read(self):
        if self.intro is not None:
            with wave.open(self.intro, 'rb') as wf:
                while True:
                    data = wf.readframes(CHUNK_SIZE)
                    if not data:
                        break
                    self.data_queue.put(data)

                    while self.data_queue.qsize() > QUEUE_PAUSE_THRESHOLD:
                        time.sleep(QUEUE_CHECK_INTERVAL)
        self.read_loop()


    def monitor_queue(self):
        if not DEBUG:
            return
        while True:
            print(f'\n\nQueue size: {self.data_queue.qsize()}\n\n')
            time.sleep(1)

    def play(self, hide_ffplay_output=True):
        ffplay_output_to = subprocess.DEVNULL if hide_ffplay_output else None
        threading.Thread(target=self.read, daemon=True).start()
        threading.Thread(target=self.monitor_queue, daemon=True).start()

        with subprocess.Popen(self.command, stdin=subprocess.PIPE, stderr=ffplay_output_to) as proc:
            while True:
                if self.data_queue.qsize() == 0:
                    time.sleep(QUEUE_CHECK_INTERVAL)
                    continue
                data = self.data_queue.get()
                if not data:
                    print('something wrong')
                    break
                proc.stdin.write(data)
                proc.stdin.flush()

            proc.stdin.close()
            proc.wait()

if __name__ == '__main__':
    try:
        player = BgmPlayer()
        player.play(not DEBUG)
    except KeyboardInterrupt:
        print('Stopped.')
        sys.exit(0)