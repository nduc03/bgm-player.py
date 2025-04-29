import wave
import subprocess
import queue
import time
import threading

intro = 'm_act31side_sys_intro.wav'
loop = 'm_act31side_sys_loop.wav'

command = ['ffplay', '-f', 's16le', '-ac', '2', '-ar', '44100', '-nodisp', '-']

chunk_size = 2048

is_loop = False

data_queue = queue.Queue()

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
    with wave.open(intro, 'rb') as wf:
        data = wf.readframes(wf.getnframes())
        data_queue.put(data)
        read_loop()


def monitor_queue():
    while True:
        print(f'\n\nQueue size: {data_queue.qsize()}\n\n')
        time.sleep(1)

threading.Thread(target=read, daemon=True).start()
threading.Thread(target=monitor_queue, daemon=True).start()

with subprocess.Popen(command, stdin=subprocess.PIPE) as proc:
    while True:
        if data_queue.empty():
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
