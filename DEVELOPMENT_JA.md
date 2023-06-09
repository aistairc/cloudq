# Development Notes of CloudQ Agent

Copyright 2022-2023 National Institute of Advanced Industrial Science and Technology (AIST), Japan and
Hitachi, Ltd.


# CloudQの構成
CloudQは**クライアント**と**エージェント**から構成され、クライアントは利用者端末上にて、
エージェントはジョブを実行する計算機クラスタのフロントエンドノードにて稼働する。
クライアントとエージェントは、クラウドストレージを介してジョブの入出力データのやり取りを行う。

## CloudQクライアントの役割
CloudQシステムにおけるクライアントは、ユーザーからのコマンドを受けて
クラウドストレージに対するデータのダウンロード・アップロードを行う。

それにより、ユーザーに以下の機能を提供する:
- ジョブの投入やキャンセルを実行する
- ジョブの状態や実行記録を取得し、ユーザーに通知する
- ジョブの実行結果をダウンロードする
- クラウドストレージ上のジョブのデータを削除する

## CloudQエージェントの役割
CloudQシステムにおけるエージェントは、クラウドストレージに格納されたジョブのデータを取得し、
計算機クラスタのローカルスケジューラにてジョブの実行を行う。

CloudQシステムにおけるエージェントの役割は以下の通り:
- CloudQクライアントにより投入されたジョブを受け取る
- 受け取ったジョブがメタジョブスクリプトで記述されている場合は、ローカルジョブスクリプトに変換する
- ジョブを計算機クラスタのローカルスケジューラへ投入する
- ローカルスケジューラへ投入したジョブの状態を確認し、CloudQクライアントへ通知する

# CloudQエージェントを開発するには
特定の計算機クラスタ向けのCloudQエージェントを開発するには、開発者は以下の作業を行う必要がある:

1. ジョブ管理機能IFを継承し、計算機クラスタ固有の実装クラスを作成する
2. メタジョブスクリプト変換機能IFを継承し、計算機クラスタ固有の実装クラスを作成する
3. 「計算機クラスタ固有の処理の追加方法」に従い、実装したクラスを登録する


# ジョブ管理機能IF
## 機能
本インターフェースはCloudQが仕様の異なる複数の計算機クラスタに対応することを容易にするためのものであり、本インターフェイスを継承した計算機クラスタ固有の派生クラスを用意することで、その計算機クラスタへのジョブ投入や状態管理を実現する。

## 抽象クラス名
AbstractJobManager

## プロパティ
### Target System Name

```python
    def SYSTEM_NAME(self):
```

対象となる計算機クラスタのシステム名を返す。

## メソッド
### Submit a Job

```python
    def submit_job(self, manifest):
```

引数
- manifest dict[str, obj]: マニフェストファイルの内容

戻り値
- dict[str, obj]: 実行後のマニフェストファイルの内容

ローカルスケジューラに対してジョブ投入を行うこと。
`manifest`にて示されたジョブを、エージェントを実行するアカウントでローカルスケジューラへ投入すること。
投入結果として、ローカルスケジューラにおけるジョブのID、ローカルグループ名、ジョブ投入コマンドを書き加えたマニフェストを返すこと。
エラー発生時はエラーメッセージを書き加えたマニフェストを返すこと。

本メソッドはジョブ作業ディレクトリをカレントとして呼び出されるものとし、スクリプトファイルはジョブ作業ディレクトリに格納されているものとする。

### Get the Status of Jobs

```python
    def get_jobs_status(self):
```

戻り値
- dict[str, str]: エージェントによりローカルスケジューラに登録されたすべてのジョブの状態一覧。

ローカルスケジューラが保有するジョブの状態を取得し、ジョブIDをkey、ジョブ状態をvalueとする辞書形式として返すこと。
本メソッドではエージェントを実行するアカウントでローカルスケジューラへ投入された、終了していないジョブすべての状態を返すこと。

本メソッドにて状態が返却されなくなったジョブは、CloudQエージェントによって正常終了したジョブとみなされる。

### Cancel a Job

```python
    def cancel_job(self, manifest, force=False):
```

引数
- manifest dict[str, obj]: マニフェストファイルの内容
- force bool: 強制キャンセルを行うか否か

戻り値
- dict[str, obj]: 実行後のマニフェストファイルの内容

ローカルスケジューラに対してジョブキャンセルを行うこと。
`manifest`にて示されたジョブについてローカルスケジューラへジョブキャンセルを指示すること。
`force`がTrueの場合は、強制キャンセルを行うこと。
エラー発生時はエラーメッセージを書き加えたマニフェストを返却すること。

### Get the Job Logs

```python
    def get_job_log(self, manifest, error=False):
```

引数
- manifest dict[str, obj]: マニフェストファイルの内容

戻り値
- dict[str, obj]: 実行後のマニフェストファイルの内容

ローカルスケジューラからジョブ実行時の標準出力、または標準エラー出力を取得し、ジョブ作業ディレクトリにファイル出力すること。
出力ファイル名は、標準出力は`stdout`、標準エラー出力は`stderr`とすること。
ジョブに対して標準出力・標準エラー出力が複数ファイルある場合は、上記ファイル名の末尾に`.(通し番号)`を付けること。
通し番号は各ファイルを区別する一意の番号とする。
エラー発生時はエラーメッセージを書き加えたマニフェストを返却すること。


# メタジョブスクリプト変換機能IF
## 機能
本インターフェースはCloudQに投入されたメタジョブスクリプトを仕様の異なる複数の計算機クラスタ向けに変換することを容易にするためのものであり、本インターフェイスを継承した計算機クラスタ固有の派生クラスを用意することで、メタジョブスクリプトをその計算機クラスタ向けのローカルジョブスクリプトへ変換する機能を提供する。

## 抽象クラス名
AbstractMetaJobScriptConverter

## プロパティ

```python
    def SYSTEM_NAME(self):
```

対象となる計算機クラスタのシステム名を返却する。

## メソッド
### Convert to Local Jobscript

```python
    def to_local_job_script(self, manifest, endpoint_url, aws_profile):
```

引数
- manifest dict[str, obj]: マニフェストファイルの内容
- endpoint_url str: クラウドストレージのエンドポイントURL
- aws_profile str: AWSのプロファイル名

戻り値
- dict[str, obj]: 変換後のマニフェストファイルの内容

メタジョブスクリプトをローカルジョブスクリプトに変換し、ジョブ作業ディレクトリに保存すること。
ジョブ管理機能IFにて変換後のスクリプトファイル名を利用する場合は、マニフェストに追記すること。
エラー発生時はエラーメッセージを書き加えたマニフェストを返すこと。

本メソッドはジョブ作業ディレクトリをカレントとして呼び出されるものとし、変換前のスクリプトファイルはジョブ作業ディレクトリに格納されているものとする。


# マニフェスト
マニフェストファイルに記述される内容を以下に列挙する。

|  パラメータ名  |  説明  |
| ---- | ---- |
|  uuid  |  CloudQにおけるジョブのID |
|  jobid  |  ローカルスケジューラにおけるジョブのID  |
|  name  |  実行するスクリプトファイル名  |
|  jobscript_type  |  実行するスクリプトの種別。<br>`local`はローカルジョブスクリプトを表し、`meta`はメタジョブスクリプトを表す。  |
|  hold_jid  |  依存ジョブ(本ジョブを実行する前に完了していなければならないジョブ)のジョブID。  |
|  array_tid  |  アレイジョブとして実行するタスクIDの定義  |
|  submit_to  |  利用者が指定した、本ジョブを実行するシステム名  |
|  submit_opt  |  利用者が指定した、本ジョブ実行時に指定するオプション  |
|  state  |  ジョブの進捗状態  |
|  workdir  |  ジョブ作業ディレクトリのパス  |
|  run_system  |  ジョブが実行されたシステム名  |
|  local_account  |  ジョブ実行時に指定されたアカウント名  |
|  local_group  |  ジョブ実行時に指定されたグループ名  |
|  submit_command  |  ローカルスケジューラへのジョブ投入コマンド  |
|  time_submit  |  クライアントがジョブを投入した日時  |
|  time_receive  |  エージェントがジョブを受理した日時  |
|  time_ready  |  ローカルスケジューラにて、ジョブが実行待ちの状態に遷移した日時 |
|  time_start  |  ローカルスケジューラにてジョブの実行が開始された日時  |
|  time_stageout_start  |  出力データのアップロード(zip圧縮含む)を開始した日時  |
|  time_stageout_finish  |  出力データのアップロードが完了した日時  |
|  time_finish  |  ジョブが完了した日時  |
|  size_input  |  ジョブスクリプトのファイルサイズ  |
|  size_output  |  出力データ(output.zip)のファイルサイズ  |
|  error_msg  |  エラー内容を通知するメッセージ  |


# 計算機クラスタ固有の処理の追加方法
開発者は`cloudq/interface.py` の下記の箇所を編集する。

```python
# Import job manager module
import job_manager_for_your_system

# Import meta jobscript converter module
import meta_jobscript_converter_for_your_system

JOB_MANAGER_IMPL_LIST = [
    # add class name of job manager for your system
    YourSystemJobManager
]

META_JOB_SCRIPT_CONVERTER_IMPL_LIST = [
    # add class name of meta jobscript converter for your system
    YourSystemMetaJobScriptConverter
]
```


# 計算機固有の処理の削除方法
開発者は`cloudq/interface.py` を編集し、「計算機クラスタ固有の処理の追加方法」にて追加したimport文ならびにクラス名を削除する。
