# -*- coding: utf-8 -*-
# Text Translator Server
# ここではGoogle翻訳APIしか使わない。
# DeepL APIはクライアントサイト側でアクセスする
# 0.2秒ごとにMongoDBを見る
# 翻訳頻度はどうする？
# tornadoサーバーでsessionがopenになったら始める

import sys
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver
import json
import time
import pymongo
import syntok.segmenter as segmenter
import warnings
warnings.simplefilter('ignore')



from google.cloud import translate_v2 as translate
translate_client = translate.Client()


conn = pymongo.MongoClient()
db = conn['sr']
table = db["result"]


low_head = lambda s: s[:1].lower() + s[1:] if s else ''


def text2sentences(text):
    sentences = ["".join([(token.spacing + token.value) for token in sentence]).strip() for paragraph in segmenter.analyze(text) for sentence in paragraph]
    return sentences



""" Define WebSocket server """
class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        self.last_sentence = "";
        self.sentences = []
        self.translations = []
        self.target_sentences = []
        self.latest_id = -1
#        sr_result = list(table.find().sort("_id", pymongo.DESCENDING).limit(1))
#        if len(sr_result) >= 1:
#            self.latest_id = sr_result[0]["_id"]
        self.cursor = -1
        self.num_complete_sr = 0        # 音声認識を完璧にした文の数
        self.num_complete_tt = 0        # 翻訳を完璧にした文の数
        print('Session opened by {}'.format(self.request.remote_ip))

    def on_message(self, message):
        self.cursor += 1
        data = json.loads(message)
        sr_result = list(table.find().sort("_id", pymongo.DESCENDING).limit(2))
        period = "."
        target_lang_code = "ja"
        """
        音声認識結果が2つ以上にならないと実行されない
        (sr_serverを起動して、しばらくすればここに入る)
        """
        if len(sr_result) >= 2:
            _id = sr_result[0]["_id"]

            """
            STEP1: 音声認識結果の整形(翻訳元文のリストsource_sentencesを作成)
            """
            mode = ""
            flug = 0                # 末尾がperiodで終了しない時flugが立つ
            source_sentences = []
            if _id != self.latest_id:
                mode = "dump"
                """
                sentences更新処理
                IDが増える時、前のIDは音声認識で確定されたので、sentencesに追加する
                - sentencesの末尾がperiodで終了する/sentencesが空の場合、新しいsentenceを作りsentenceに追加する
                - sentencesの末尾がperiodで終了しない場合、末端sentenceの末尾に追加する
                """
                confirmed_result = sr_result[1]
                sentences = text2sentences(confirmed_result["text"])
#                sentences = self.last_sentence
                if len(self.sentences) == 0:
                    #print("1")
                    self.sentences.extend(sentences)
                elif self.sentences[-1].strip().endswith(period):
                    #print("2")
                    self.sentences.extend(sentences)
                else:
                    #print("3", len(sentences), sentences)
                    flug = 1
                    if len(sentences) > 0:
                        #print("4")
                        if len(self.sentences) > 0:
                            #print("5")
                            self.sentences[-1] += (" " + low_head(sentences[0].strip()))
                        self.sentences.extend(sentences[1::])
                self.num_complete_sr = len(self.sentences)
                self.latest_id = _id
                #print(self.latest_id, self.sentences)
                source_sentences = self.sentences[::]
            else:
                mode = "process"
                """
                認識途中(未確定)音声認識結果処理
                現在進行系で音声認識をしている結果に関してはsentencesとは別の処理を行う
                - sentencesの末尾がperiodで終了する/sentencesが空の場合、進行形音声認識結果は新しい文として翻訳する
                - sentencesの末尾がperiodで終了しない場合、末端sentenceの末尾に繋げて、一緒に翻訳する
                """
                progress_result = sr_result[0]
                sentences = text2sentences(progress_result["text"])
                #print("gtaa", sentences)
                if len(sentences) > 0:
                    source_sentences = self.sentences[::]
                    self.last_sentence = sentences
                    if len(source_sentences) == 0:
                        source_sentences.extend(sentences)
                    elif source_sentences[-1].strip().endswith(period):
                        source_sentences.extend(sentences)
                    else:
                        source_sentences[-1] += (" " + low_head(sentences[0].strip()))
                        if len(sentences) > 1:
                            source_sentences.extend(sentences[1::])

            """
            STEP2: 翻訳
            すでに翻訳した文は、翻訳したくない。
            何行目まで、完璧に翻訳したかを記録し続ける必要がある。
            何行目まで、完璧に音声認識したかはSTEP1で記録済み
            翻訳は10回に1回しか行わない(約2秒に1回)
            dumpのときは必ず翻訳する
            """
            if self.cursor % 15 == 0 or mode == "dump":
                if flug == 0:
                    imcomplete_sentences = source_sentences[self.num_complete_tt::]
                else:
                    imcomplete_sentences = source_sentences[self.num_complete_tt-1::]
                if len(imcomplete_sentences) > 0:
                    translated_result = translate_client.translate("\n\n<SEP>\n\n".join(imcomplete_sentences), 
                                                                  model="nmt", 
                                                                  target_language=target_lang_code)

                    translated_sentences = translated_result["translatedText"].split("<SEP>")
                    self.num_complete_tt = self.num_complete_sr

                    """
                    翻訳結果の保存:音声認識結果が確定した時点で翻訳結果保存する
                    保存するのはsource textが必ずピリオドで終了しているもののみ
                    self.sentenceと同じ数になるまでself.translationに翻訳結果を追加
                    """
                    if mode == "dump":
                        if flug == 0:
                            self.translations.extend(translated_sentences[:len(self.sentences)-len(self.translations):])
                        else:
                            self.translations[-1] = translated_sentences[0]
                            if len(translated_sentences) > 1:
                                self.translations.extend(translated_sentences[1:1+len(self.sentences)-len(self.translations):])
                        self.target_sentences = self.translations[::]
#                        print(flug)
#                        print("\n\n".join(["\n".join([e, j]) for e, j in zip(imcomplete_sentences, translated_sentences)]))
#                        print("====")
                    else:
                        self.target_sentences = self.translations[::] + translated_sentences[::]

            output_target_sentences = []
            if len(source_sentences) > len(self.target_sentences):
                output_target_sentences = self.target_sentences[::] + ([""]*(len(source_sentences)-len(self.target_sentences)))
            else:
                output_target_sentences = self.target_sentences[::]

#            print("\n\n".join(["\n".join([e, j]) for e, j in zip(source_sentences, self.target_sentences)]))
#            print("========")

            N = 5
            start_idx = len(source_sentences) - N
            if start_idx < 0:
                start_idx = 0
            self.write_message(json.dumps({"status":mode, 
                                           "start_idx":start_idx, 
                                           "source":source_sentences[start_idx::], 
                                           "target":output_target_sentences[start_idx::]}))


        
        if self.cursor > 100:
            self.cursor = 0

    def on_close(self):
        print('Session closed by {}'.format(self.request.remote_ip))


application = tornado.web.Application([
    (r"/websocket", WebSocketHandler),
])

if __name__ == "__main__":
    application.listen(3939)
    tornado.ioloop.IOLoop.current().start()
