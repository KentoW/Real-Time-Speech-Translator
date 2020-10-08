# -*- coding: utf-8 -*-
# ひたすら音声認識した結果をmongodbに書き続けるサーバー
# 毎回mongodbはリセットする
import sys
import re
import time
import json
import pyaudio
import pymongo
import argparse
from six.moves import queue
import warnings
warnings.simplefilter('ignore')
try:
    from google.cloud import speech_v1p1beta1 as speech
except:
    from google.cloud import speech



""" initialization db """
conn = pymongo.MongoClient()
db = conn['sr']
table = db["result"]

if table.estimated_document_count() > 0:
    conn.drop_database('sr')

tabl = db["result"]
table.create_index([('_id', pymongo.ASCENDING)])


""" initialize speech recognition """
STREAMING_LIMIT = 240000  # 4 minutes
SAMPLE_RATE = 16000
CHUNK_SIZE = int(SAMPLE_RATE / 10)  # 100ms


""" Return Current Time in MS """
def get_current_time():
    return int(round(time.time() * 1000))

""" Opens a recording stream as a generator yielding the audio chunks """
class ResumableMicrophoneStream:
    def __init__(self, rate, chunk_size):
        self._rate = rate
        self.chunk_size = chunk_size
        self._num_channels = 1
        self._buff = queue.Queue()
        self.closed = True
        self.start_time = get_current_time()
        self.restart_counter = 0
        self.audio_input = []
        self.last_audio_input = []
        self.result_end_time = 0
        self.is_final_end_time = 0
        self.final_request_end_time = 0
        self.bridging_offset = 0
        self.new_stream = True
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            channels=self._num_channels,
            rate=self._rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

    def __enter__(self):
        self.closed = False
        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, *args, **kwargs):
        """ Continuously collect data from the audio stream, into the buffer """
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        """ Stream Audio from microphone to API and to local buffer """
        while not self.closed:
            data = []
            if self.new_stream and self.last_audio_input:
                chunk_time = STREAMING_LIMIT / len(self.last_audio_input)
                if chunk_time != 0:
                    if self.bridging_offset < 0:
                        self.bridging_offset = 0
                    if self.bridging_offset > self.final_request_end_time:
                        self.bridging_offset = self.final_request_end_time
                    chunks_from_ms = round((self.final_request_end_time -
                                            self.bridging_offset) / chunk_time)
                    self.bridging_offset = (round((
                        len(self.last_audio_input) - chunks_from_ms)
                                                  * chunk_time))
                    for i in range(chunks_from_ms, len(self.last_audio_input)):
                        data.append(self.last_audio_input[i])
                self.new_stream = False
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            self.audio_input.append(chunk)
            if chunk is None:
                return
            data.append(chunk)
            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                    self.audio_input.append(chunk)
                except queue.Empty:
                    break
            yield b''.join(data)


def main(args):
    if args.source == "ja":
        language_code = 'ja-JP'
        use_enhanced = False
        model = "default"
    else:
        language_code = 'en-US'  
        use_enhanced = True
        model = args.model

    """ Start bidirectional streaming from microphone input to speech API """
    client = speech.SpeechClient()
    config = speech.types.RecognitionConfig(
        encoding=speech.enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=SAMPLE_RATE,
        language_code=language_code,
        model = model,                                      # 認識モデル
        use_enhanced = use_enhanced,                        # 拡張モデルの有効化
    #    enable_speaker_diarization=True,                    # 話者分離
    #    diarization_speaker_count=6,                        # 話者の数
        enable_automatic_punctuation=True,                  # 句点推定
        speech_contexts=[speech.types.SpeechContext()],     # 音声適応
        max_alternatives=1)

    streaming_config = speech.types.StreamingRecognitionConfig(
        config=config,
        interim_results=True)

    mic_manager = ResumableMicrophoneStream(SAMPLE_RATE, CHUNK_SIZE)

    table.insert_one({"_id":0, "text":"", "lang":args.source, "status":"dump"})
    table.insert_one({"_id":1, "text":"", "lang":args.source, "status":"dump"})
    _id = 2

    with mic_manager as stream:
        while not stream.closed:
            sys.stdout.write('\n' + str(STREAMING_LIMIT * stream.restart_counter) + ': NEW REQUEST\n')
            stream.audio_input = []
            audio_generator = stream.generator()
            requests = (speech.types.StreamingRecognizeRequest(audio_content=content)for content in audio_generator)
            responses = client.streaming_recognize(streaming_config, requests)

            for response in responses:
                if get_current_time() - stream.start_time > STREAMING_LIMIT:
                    stream.start_time = get_current_time()
                    break
                if not response.results:
                    continue
                result = response.results[0]
                if not result.alternatives:
                    continue
                transcript = result.alternatives[0].transcript
                result_seconds = 0
                result_nanos = 0
                if result.result_end_time.seconds:
                    result_seconds = result.result_end_time.seconds
                if result.result_end_time.nanos:
                    result_nanos = result.result_end_time.nanos
                stream.result_end_time = int((result_seconds * 1000)
                                             + (result_nanos / 1000000))
                corrected_time = (stream.result_end_time - stream.bridging_offset
                                  + (STREAMING_LIMIT * stream.restart_counter))


                if result.is_final:
                    data = table.find_one({"_id":_id})
                    if data:
                        data["text"] = transcript
                        data["status"] = "dump"
                        table.save(data)
                        #print("hoge 2", _id, transcript)
                    else:
                        table.insert_one({"_id":_id, "text":transcript, "lang":args.source, "status":"dump"})
                        #print("piyo 2", _id, transcript)
                    stream.is_final_end_time = stream.result_end_time
                    _id += 1
                else:
                    data = table.find_one({"_id":_id})
                    if data:
                        data["text"] = transcript
                        #print("hoge 1", _id, transcript)
                        table.save(data)
                    else:
                        table.insert_one({"_id":_id, "text":transcript, "lang":args.source, "status":"process"})
                        #print("piyo 1", _id, transcript)





            if stream.result_end_time > 0:
                stream.final_request_end_time = stream.is_final_end_time
            stream.result_end_time = 0
            stream.last_audio_input = []
            stream.last_audio_input = stream.audio_input
            stream.audio_input = []
            stream.restart_counter = stream.restart_counter + 1

            stream.new_stream = True






if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--source", dest="source", default="en", type=str, help="source langage (ja/en)")
    parser.add_argument("-m", "--model", dest="model", default="video", type=str, help="speech recognition model (video/phone_call)")
    args = parser.parse_args()
    main(args)
