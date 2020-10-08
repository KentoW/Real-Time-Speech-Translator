# Real-Time Speech Translater
- マイク入力からリアルタイムで文章を書き下し、リアルタイムで翻訳するWebアプリ
- Webブラウザで動作（Chrome 85.0.4~で動作確認、OSはMac及びUbuntuで動作確認、Windowsは確認してないけど多分いけるやろ）
- 音声認識はGoogle Speech-to-textを使用
- Google翻訳とDeepL翻訳の両方を表示
- とにかく動けば良いの精神で実装（汚い

## 内容物
- `sr_server.py` 音声認識サーバー用スクリプト
- `tt_server.py` 翻訳サーバー用スクリプト
- `web_server.py` フロントエンドサーバー用スクリプト
- `html` フロントHTML+CSS+javascript

## 必要なもの
- Anaconda（仮想環境でやったほうが安全）
- MongoDB v4.4.0 (brewでインストールした)
    - 適当にMongoDB用のディレクトリを作ってデータベース・サーバーを起動する（後述）
- Python3.8~ 
    - パッケージ(特に断りの無い場合condaでインストール)
    - PyAudio=0.2.11
    - pymongo==3.9.0
    - six==1.15.0
    - google-api-python-client== (pip でインスコ)
    - google-cloud-speech==1.3.2 (pip でインスコ、最新版はバージョンが2になったので注意)
    - tornado==6.0.4
    - sentok==1.3.1 (pip でインスコ)
    - google-cloud-translate==2.0.1 (pip でインスコ)
    - CherryPy==18.6.0
- Google cloudのあれこれ（後述）
    - Google cloud音声認識や翻訳APIを使うが、最初の90日は300ドル分は無料、その後は従量課金になる
    - クレジットカードが必要
    - 音声認識や翻訳はDeepLと比べて対してお金かかんないと思う
- DeepL APIの有料契約（なくても良いが、もちろんDeepLは使えなくなる）

## 初期設定
1. まずは[Google Cloud Platform](https://console.cloud.google.com/apis/dashboard?folder=&hl=ja) にて、自身のGoogleアカウントを登録する
2. Google Cloud Platformの[無料トライアル](https://cloud.google.com/free?hl=ja)に登録する
    - クレジットカード登録が必要
3. text to speech APIの登録、認証設定
    - [認証の設定](https://cloud.google.com/speech-to-text/docs/libraries?hl=ja#cloud-console)の手順に従い、サービスアカウントキーの作成をする。
    - `新しいサービスアカウント` を選択し、ロールを `project` -> `オーナー` にする
    - キーのタイプは `JSON` にして作成
    - jsonファイル `hogehoge-hugahuga.json` がダウンロードされるので、このリポジトリに移動しておく。
4. google translate APIの登録、認証設定
    - [サービスアカウントとキーの設定](https://cloud.google.com/translate/docs/setup?hl=ja#creating_service_accounts_and_keys)の手順に従い、サービスアカウントキーの作成をする。
    - `新しいサービスアカウント` を選択し、ロールを `project` -> `オーナー` にする
    - キーのタイプは `JSON` にして作成
    - jsonファイル `piyopiyo-barbar.json` がダウンロードされるので、このリポジトリに移動しておく。
5. (optional) DeepL APIの登録
    - [DeepL API](https://www.deepl.com/ja/pro/#developer) を契約
    - 月額630円で、プラスして従量課金
    - [アカウントページ](https://www.deepl.com/pro-account.html)にて認証キーをコピー
    - `web_server.py` の50行目の変数 api_keyに認証キーをペースト

## 起動
0. 起動の順番が重要
1. MongoDBの起動
    - 適当なディレクトリを作成 `mkdir -p data/db`
    - DBの起動 `mongod -d data/db`
2. 音声認識サーバーの起動
    - 認証キーの読み込み、シェル上に入力（もしくはシェル設定ファイルに入力） `export GOOGLE_APPLICATION_CREDENTIALS=hogehoge-hugahuga.json` 
    - サーバーの起動 `python sr_server.py`
3. 翻訳サーバーの起動
    - 認証キーの読み込み、シェル上に入力（もしくはシェル設定ファイルに入力） `export GOOGLE_APPLICATION_CREDENTIALS=piyopiyo-barbar.json` 
    - サーバーの起動 `python tt_server.py`
4. Webサーバーの起動
    - `python web_server.py` を実行
5. あとは `http://localhost:8000/web` にアクセスするだけ
    - このURLにアクセスした時点から翻訳が開始される。

## 注意点
- `sr_server.py` を起動するとmongoDB内の音声認識結果は全部消える。(mongoDBはあくまでキャッシュ扱い)
- webページをリロードすると今までの翻訳結果は見れなくなる。
- リロードする前にそのwebページの保存をお勧めする（コマンドSとかで、その時のHTMLの状態をオフラインに保存できる）

## 実装のあれこれTips、参考
- [マイクからのリアルタイム入力](https://cloud.google.com/speech-to-text/docs/streaming-recognize?hl=ja#performing_streaming_speech_recognition_on_an_audio_stream) `sr_server.py` はこれがベース。
- [句読点入力の自動化](https://cloud.google.com/speech-to-text/docs/automatic-punctuation) 句読点も判定してくれる。便利。既に実装済み、他にも色々あるので楽しい。

## 何故、こんなに手順が面倒くさい構成になったのか？
- Pythonで実装前提でリアルタイム性+実装の簡単さを追求したらこうなった。
    - 基本的に同期処理なので、音声認識->翻訳->描画というのを一つのスクリプトでやろうとすると、リアルタイム性が損なわれる。（特にDeepL APIは重い）
    - リアルタイム性を追求した結果、「音声認識結果をDBにプールし、翻訳機はDBにプールされた認識結果を定期的に監視する」というのが最もリアルタイム性を損なわず、かつ実装が楽だった。
    - 翻訳頻度は多分2秒に一回、これは `html/js/app.js` の38行目の `100` (ms) をいじれば変えられる。
    - 音声認識結果の描画は100ms(0.1秒)ごとに行われる。
    - Google翻訳は100ms(0.1秒)ごとに行われる。
    - DeepL翻訳は音声認識結果の描画が20回行われるごとに翻訳される（DeepLは重いので…）。この20回のパラメータは `html/js/app.js` の82行目で変えられる。
    - GET/POSTで0.1秒ごとにアクセスし続けるのはアレなのでWebsocketで通信。
    - 常に翻訳しているわけではなく、`app.js` が実行時、つまり `http://localhost:8000/web` にアクセスしている時に限り翻訳している。
    - つまり、このwebページを複数開いていると、それだけ翻訳しているので、料金がかかるので注意
    - ちなみに音声認識は `sr_server.py` が起動している間ずっと実行されており、DBに保存され続ける。
    - MongoDB内の音声認識結果は `sr_server.py` を起動し続けるたびに全消去されるので注意。
    - 翻訳は `tt_server.py` がしているが実はGoogle翻訳だけしている。DeepL翻訳は `web_server.py` のREST APIが実行している。
    - 一つのサーバーで２つの翻訳を実行すると、処理時間がボトルネックになるので、処理を分散した。
- 翻訳の範囲について
    - 実装で一番面倒くさかったのは、「どの範囲のテキストを翻訳するか？」
    - 認識した文を全部翻訳し直していたら、料金が膨れ上がるし、レスポンスも遅くなるので、ある程度、量を絞って翻訳する必要がある。
    - 音声認識はタイムアウトの関係上、文の途中で認識を区切ることがあった。
    - また音声認識結果は句点を消したり追加したりするので、文の分割やマージなどが面倒でもある。
    - できるだけ、句点で終わる文をマージして、翻訳したい。
    - 適当に句点をトリガーにして文をマージ、ある程度文をキューに数文ためて、そのキューだけを翻訳することで、翻訳の分量を節約する。
    - 確信度が高い文が一定数貯まり、翻訳が終わったらキューを空にする。
    - 以上のアルゴリズムを実装（したつもり）
