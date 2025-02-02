import streamlit as st
import duckdb
import hashlib
import pandas as pd
import os
import datetime
import mimetypes

st.set_page_config(page_title="File Exchange - Streamlit")

st.title("FILE EXCHANGE :file_folder:")

@st.cache_resource
def get_database():
    # メモリ内のDuckDBデータベースを作成し、ファイル情報を保持するテーブルを作成する
    conn = duckdb.connect(database=":memory:", read_only=False)
    conn.execute("CREATE TABLE IF NOT EXISTS files (hash TEXT, filename TEXT)")
    return conn

@st.cache_data
def get_registered_files(email, password):
    # メールアドレス、パスワードからハッシュを生成し、ファイル情報を取得する
    file_hash = generate_hash(email, password)
    conn = get_database()
    return conn.execute("SELECT filename FROM files WHERE hash = ?", (file_hash,)).fetchall()

def generate_hash(email, password):
    # メールアドレス、パスワード、ソルトからSHA256ハッシュを生成する
    salt = st.secrets["salt"]
    combined = f"{email}{password}{salt}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()

def get_temporary_directory():
    # テンポラリディレクトリとして次のものを候補とする。先頭から探索して存在するものを返す
    for tmp_dir in ["/tmp", "C:/temp", "./tmp"]:
        if os.path.exists(tmp_dir):
            return tmp_dir
    # どれも存在しない場合はNoneを返す
    return None

def get_file_dataframe(file_list):
    # ファイルパスのリストからDataFrameに変換する
    # カラムとして、ファイル名、ファイル作成日、ファイルサイズ、MIMEタイプを追加する
    result = []
    for _, file_path in enumerate(file_list):
        basename = os.path.basename(file_path)
        create_time = datetime.datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
        size = "{} KB".format(os.path.getsize(file_path) // 1024)
        mime_type, _ = mimetypes.guess_type(file_path)
        result.append([basename, create_time, size, mime_type, file_path])
    return pd.DataFrame(result, columns=["basename", "create_time", "size", "mime_type", "file_path"])

def on_file_selected():
    st.write("ファイルが選択されました。")
    st.write(st.session_state.selected_files)

# タブの作成
tabs = st.tabs(["アップロード", "ダウンロード"])

with tabs[0]:
    upload_email = st.text_input("メールアドレス", key="upload_email")
    upload_password = st.text_input("ダウンロードパスワード", type="password", key="upload_password")
    uploaded_file = st.file_uploader("ファイルを選択", key="uploaded_file")
    
    if st.button("アップロード"):
        if upload_email and upload_password and uploaded_file:
            # メールアドレス、パスワードからハッシュ生成
            file_hash = generate_hash(upload_email, upload_password)
            # テンポラリディレクトリにファイルを保存する。存在しない場合はエラーで終了する
            tmp_dir = get_temporary_directory()
            if not tmp_dir:
                st.error("テンポラリディレクトリが見つかりません。")
                st.stop()
            # ファイルを保存
            file_path = os.path.join(tmp_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            # データベースにハッシュとファイルパスを保存
            conn = get_database()
            conn.execute("INSERT INTO files VALUES (?, ?)", (file_hash, file_path))
            st.success("ファイルがアップロードされました。")
        else:
            st.error("すべての項目を入力してください。")

with tabs[1]:
    download_email = st.text_input("メールアドレス", key="download_email")
    download_password = st.text_input("ダウンロードパスワード", type="password", key="download_password")

    if st.button("ファイル一覧を表示"):
        get_registered_files.clear()
        if download_email and download_password:
            registered_files = get_registered_files(download_email, download_password)
            if registered_files:
                # "N個のファイルがダウンロード可能です。"と表示
                count = len(registered_files)
                st.success(f"{count}個のファイルがダウンロード可能です。")
                # 表示するファイル一覧を生成
                file_list = [row[0] for row in registered_files]
                st.session_state.file_df = get_file_dataframe(file_list)
            else:
                st.error("該当するアップロード履歴が見つかりません。")
        else:
            st.error("すべての項目を入力してください。")    

    # registered_filesがある場合、DataFrameとしてファイル一覧を表示する
    if "file_df" in st.session_state:
        # file_dfからカラム名を日本語にしたDataFrameを作成
        selector_df = st.session_state.file_df.copy()
        selector_df = selector_df.drop(columns=["file_path"])
        selector_df.index = range(1, len(selector_df) + 1)
        selector_df.columns = ["ファイル名", "作成日", "ファイルサイズ", "MIMEタイプ"]
        selected_file = st.dataframe(selector_df, key="selected_files", on_select="rerun", selection_mode=["single-row"])
        if len(selected_file.selection.rows) > 0:
            selected_row_index = selected_file.selection.rows[0]
        else:
            selected_row_index = None
    else:
        selected_row_index = None

    if selected_row_index is not None:
        file_path = st.session_state.file_df.loc[selected_row_index, "file_path"]
        mime_type = st.session_state.file_df.loc[selected_row_index, "mime_type"]
        with open(file_path, "rb") as f:
            filename = os.path.basename(file_path)
            st.download_button("ダウンロード", data=f, file_name=filename, mime=mime_type)
