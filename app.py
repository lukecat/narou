import streamlit as st
import requests
import json

st.set_page_config(page_title="なろう名作発掘スコッパー", layout="centered")
st.title(" 隠れた名作発掘システム")
st.write("「書籍化」や「巨大テンプレ」に埋もれない、熱量の高い未発掘作品を提案します。")

@st.cache_data(ttl=900)  # キャッシュを15分に延ばして、何度もなろうAPIを叩かないように保護
def fetch_narou_data():
    # なろうAPI公式推奨の「gzip圧縮（gzip=5）」を有効化し、負荷を下げてブロックを回避
    url = "https://syosetu.com"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Encoding": "gzip, deflate"  # 圧縮データを受け入れる宣言
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10) # 10秒でタイムアウト設定
        
        if response.status_code != 200:
            return {"error": f"サーバー拒否 (ステータスコード: {response.status_code})"}
            
        # 届いたデータが本当にJSON形式か厳密にチェック
        try:
            data = response.json()
            if isinstance(data, list) and len(data) > 1:
                return data[1:]  # 正常：先頭の総件数データを除外して返す
            else:
                return {"error": "届いたデータの中身が空、または不正な形式です。"}
        except json.JSONDecodeError:
            return {"error": "なろうからデータは届きましたが、アクセス制限の警告画面（HTML）になっています。しばらく時間を置いてください。"}
            
    except Exception as e:
        return {"error": f"ネットワーク通信に失敗しました: {e}"}

# データの取得を実行
result = fetch_narou_data()

# エラーが発生している場合は、画面に分かりやすく表示して処理を止める
if isinstance(result, dict) and "error" in result:
    st.error(result["error"])
    st.info("💡 なろうAPI側のアクセス制限にかかっている可能性があります。5分〜10分ほど時間を空けて再度お試しください。")
    novels = []
else:
    novels = result

filtered_novels = []
for n in novels:
    keywords = n.get("keyword", "")
    global_point = n.get("global_point", 0)
    length = n.get("length", 0)
    fav_count = n.get("fav_count", 0)
    
    # 1. 既に出版・アニメ化されている有名作品を徹底排除
    banned_keywords = ["書籍化", "コミカライズ", "アニメ化", "出版", "発売", "文庫"]
    if any(bk in keywords for bk in banned_keywords):
        continue
        
    # 2. 累計ポイントが3万pt以上の巨大作品を足切り
    if global_point > 30000:
        continue
        
    # 3. 最低限の熱量（ブックマーク30以上、文字数1.5万文字以上）
    if fav_count < 30 or length < 15000:
        continue
        
    # 4. 独自スコア：【文字数が少ないのに、読者が外さず追っている熱量】
    score = (fav_count) / (length / 10000)
    n["custom_score"] = score
    filtered_novels.append(n)

# 独自スコア順に並び替え
filtered_novels = sorted(filtered_novels, key=lambda x: x["custom_score"], reverse=True)

# 画面への表示
st.subheader(" 本日の厳選・発掘作品")
if novels and not filtered_novels:
    st.info("データは取得できましたが、条件に合う未発掘作品がありませんでした。フィルターを緩める必要があります。")
elif filtered_novels:
    for idx, novel in enumerate(filtered_novels[:5]):
        with st.container():
            st.markdown(f"### {idx+1}. {novel['title']}")
            st.caption(f"作者: {novel['writer']} | 総文字数: {novel['length']:,}文字 | 累計ブクマ: {novel['fav_count']:,} | 総合ポイント: {novel['global_point']:,}pt")
            st.write(novel['story'][:200] + "...")
            
            url = f"https://syosetu.com{novel['ncode'].lower()}/"
            st.markdown(f"[この作品を発掘する（なろうで読む）]({url})")
            st.markdown("---")
