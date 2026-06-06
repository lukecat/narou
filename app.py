import streamlit as st
import requests
import json
import re

st.set_page_config(page_title="なろう名作発掘スコッパー", layout="centered")
st.title(" 隠れた名作発掘システム")
st.write("「書籍化」や「巨大テンプレ」に埋もれない、熱量の高い未発掘作品を提案します。")

@st.cache_data(ttl=300)  # 5分間キャッシュ
def fetch_narou_data():
    # 【根本解決】URLには一切パラメータを直接書かず、ベースURLのみを指定
    url = "https://api.syosetu.com/novelapi/api/"
    
    # 【超重要】なろうAPIが最も好む、綺麗に構造化されたパラメータ設定
    # これにより、なろうのサーバー側での強制Web転送（リダイレクト）を確実に防ぎます
    payload = {
        "out": "json",        # JSON形式で出力
        "lim": 300,           # 最大300件取得
        "order": "weekly",    # 週間ユニークポイント順
        "of": "t-w-n-s-k-g-gp-l-f" # 必要な項目（タイトル、作者、Nコード、あらすじ、キーワード、ジャンル、ポイント、文字数、ブクマ数）を明示
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    
    try:
        # params=payload として安全にパラメータを分離して送信
        response = requests.get(url, params=payload, headers=headers, timeout=15)
        
        st.session_state["http_status"] = response.status_code
        st.session_state["raw_response"] = response.text[:1000]
        
        if response.status_code != 200:
            return {"error": f"サーバーエラー (コード: {response.status_code})"}
            
        # まだHTMLが返ってきている場合の防衛策
        if response.text.strip().startswith("<!DOCTYPE") or "<html" in response.text:
            title_match = re.search(r"<title>(.*?)</title>", response.text, re.IGNORECASE)
            page_title = title_match.group(1) if title_match else "不明なWebページ"
            return {"error": f"【通信エラー】なろうのWebページが返されています。ページ名:「{page_title}」"}

        try:
            data = response.json()
            if isinstance(data, list) and len(data) > 1:
                return data[1:]
            else:
                return {"error": "データの中身が空、または正しくありません。"}
        except json.JSONDecodeError:
            return {"error": "データの解析（JSON変換）に失敗しました。"}
            
    except Exception as e:
        return {"error": f"通信に失敗しました: {e}"}

# データ取得
result = fetch_narou_data()

# サイドバーにログ出力
with st.sidebar:
    st.subheader("🛠 詳細な接続ログ")
    if "http_status" in st.session_state:
        st.write(f"HTTPステータス: {st.session_state['http_status']}")
        st.text_area("なろうからの実際の返答", st.session_state["raw_response"], height=300)

if isinstance(result, dict) and "error" in result:
    st.error(result["error"])
    novels = []
else:
    novels = result

# フィルタリング
filtered_novels = []
for n in novels:
    # ハイファンタジー（101）とローファンタジー（102）のみを安全に抽出
    genre = n.get("genre", 0)
    if genre not in [101, 102]:
        continue

    keywords = n.get("keyword", "")
    global_point = n.get("global_point", 0)
    length = n.get("length", 0)
    fav_count = n.get("fav_count", 0)
    
    # 除外フィルター
    banned_keywords = ["書籍化", "コミカライズ", "アニメ化", "出版", "発売", "文庫"]
    if any(bk in keywords for bk in banned_keywords):
        continue
    if global_point > 30000:
        continue
    if fav_count < 20 or length < 10000:
        continue
        
    # 独自熱量スコア
    score = (fav_count) / (length / 10000)
    n["custom_score"] = score
    filtered_novels.append(n)

filtered_novels = sorted(filtered_novels, key=lambda x: x["custom_score"], reverse=True)

# 表示
st.subheader(" 本日の厳選・発掘作品")
if novels and not filtered_novels:
    st.info("データは正常に取得できましたが、厳格なフィルターにより全作品が除外されました。")
elif filtered_novels:
    for idx, novel in enumerate(filtered_novels[:5]):
        with st.container():
            st.markdown(f"### {idx+1}. {novel['title']}")
            st.caption(f"作者: {novel['writer']} | 総文字数: {novel['length']:,}文字 | ブックマーク: {novel['fav_count']:,}")
            st.write(novel['story'][:200] + "...")
            url = f"https://ncode.syosetu.com/{novel['ncode'].lower()}/"
            st.markdown(f"[この作品を発掘する（なろうで読む）]({url})")
            st.markdown("---")
