import streamlit as st
import requests
import json
import re

st.set_page_config(page_title="なろう名作発掘スコッパー", layout="centered")
st.title("🔍 隠れた名作発掘システム")
st.write("「書籍化」や「巨大テンプレ」に埋もれない、熱量の高い未発掘作品を提案します。")

# --- サイドバーで条件を動的に調整できるようにする ---
st.sidebar.header("🎛 フィルタリング条件")

max_point = st.sidebar.slider(
    "総合ポイントの上限 (これより下を検索)",
    min_value=1000,
    max_value=200000,
    value=1000,
    step=500,
    help="ポイントが低めだが熱量の高い「隠れた名作」を発掘するための上限値です。"
)

# 総合ポイントの上限を無視するスイッチ
ignore_max_point = st.sidebar.checkbox(
    "総合ポイント上限による除外を無効にする", 
    value=False,
    help="【重要】累計ブックマーク順や累計ポイント順で検索する場合、このチェックをONにしないと検索結果が0件になります。"
)

min_fav = st.sidebar.slider(
    "最低ブックマーク数",
    min_value=10,
    max_value=1000,
    value=20,
    step=10
)

min_length = st.sidebar.slider(
    "最低文字数",
    min_value=5000,
    max_value=100000,
    value=10000,
    step=5000
)

genre_options = {
    "ハイファンタジー": "101",
    "ローファンタジー": "102",
    "ファンタジー (ハイ/ロー)": "101-102",
    "異世界恋愛": "201",
    "現実世界恋愛": "202",
    "恋愛 (両方)": "201-202",
    "文芸 (推理/歴史/コメディ等)": "301-302-303-304-305-306-307",
    "SF (宇宙/空想科学等)": "401-402-403-404",
    "全ジャンル対象 (指定なし)": ""
}
selected_genre_label = st.sidebar.selectbox("対象ジャンル", list(genre_options.keys()))
selected_genre_code = genre_options[selected_genre_label]

exclude_commercial = st.sidebar.checkbox("書籍化・コミカライズ済みの作品を除外する", value=True)

order_options = {
    "週間ユニークユーザー順 (weekly)": "weekly",
    "日間ポイント順 (dailypoint)": "dailypoint",
    "週間ポイント順 (weeklypoint)": "weeklypoint",
    "月間ポイント順 (monthlypoint)": "monthlypoint",
    "四半期ポイント順 (quarterpoint)": "quarterpoint",
    "年間ポイント順 (yearlypoint)": "yearlypoint",
    "【累計】ブックマーク数の多い順 (favnovelcnt)": "favnovelcnt",
    "【累計】総合評価の高い順 (hyoka)": "hyoka"
}
selected_order = st.sidebar.selectbox("なろう側の並び順基準", list(order_options.keys()))
order_code = order_options[selected_order]


@st.cache_data(ttl=300)
def fetch_narou_data(genre_code, order_code):
    url = "https://api.syosetu.com/novelapi/api/"
    
    payload = {
        "out": "json",
        "lim": 400,                 
        "order": order_code,
        "of": "t-w-n-s-k-g-gp-l-f" 
    }
    
    if genre_code:
        payload["genre"] = genre_code
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, params=payload, headers=headers, timeout=15)
        st.session_state["http_status"] = response.status_code
        st.session_state["raw_response"] = response.text[:1000]
        
        if response.status_code != 200:
            return {"error": f"サーバーエラー (コード: {response.status_code})"}
            
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
result = fetch_narou_data(selected_genre_code, order_code)

# サイドバーにログ出力
with st.sidebar:
    st.subheader("🛠 詳細な接続ログ")
    if "http_status" in st.session_state:
        st.write(f"HTTPステータス: {st.session_state['http_status']}")
        st.text_area("なろうからの実際の返答", st.session_state["raw_response"], height=150)

if isinstance(result, dict) and "error" in result:
    st.error(result["error"])
    novels = []
else:
    novels = result

# フィルタリング
filtered_novels = []

# 【機能強化】除外キーワードリストを拡充（電子、コミックなども追加）
banned_keywords = [
    "書籍化", "コミカライズ", "アニメ化", "出版", "発売", "文庫", 
    "電子書籍", "コミック", "単行本", "メディアミックス","外伝",
    "続編"
]

for n in novels:
    keywords = n.get("keyword", "")
    global_point = n.get("global_point", 0)
    length = n.get("length", 0)
    fav_count = n.get("fav_novel_cnt", 0) 
    
    # 【重要変更】タイトル、あらすじ、タグ（キーワード）を結合して、チェック用の文章を作る
    title = n.get("title", "")
    story = n.get("story", "")
    combined_text = f"{title}\n{story}\n{keywords}"
    
    # 1. 商業化済み除外フィルター（タイトル、あらすじ、タグのすべてを対象に検索）
    if exclude_commercial:
        if any(bk in combined_text for bk in banned_keywords):
            continue
            
    # 2. 総合ポイントの上限チェック（「上限無視」がOFFの場合のみ適用）
    if not ignore_max_point:
        if global_point > max_point:
            continue
        
    # 3. 最低ブックマーク数と最低文字数のチェック
    if fav_count < min_fav or length < min_length:
        continue
        
    # 4. 独自熱量スコア（ゼロ除算を防ぎつつ算出）
    length_unit = length / 10000
    if length_unit > 0:
        score = fav_count / length_unit
    else:
        score = 0
        
    n["fav_count_display"] = fav_count
    n["custom_score"] = score
    filtered_novels.append(n)

# 独自熱量スコアの高い順にソート
filtered_novels = sorted(filtered_novels, key=lambda x: x["custom_score"], reverse=True)

# 表示
st.subheader("🌟 本日の厳選・発掘作品")
if novels and not filtered_novels:
    if (selected_order in ["【累計】ブックマーク数の多い順 (favnovelcnt)", "【累計】総合評価の高い順 (hyoka)"]) and not ignore_max_point:
        st.warning("⚠️ 累計ランキングを表示しています。累計順の作品はポイントが非常に高いため、「総合ポイント上限による除外を無効にする」チェックをONにしてください。")
    else:
        st.info("データは正常に取得できましたが、厳格なフィルターにより全作品が除外されました。左側のサイドバーでスライダーを調整して条件を緩めてみてください。")
elif filtered_novels:
    st.success(f"{len(filtered_novels)}件の候補から、独自熱量スコアの高い上位5件を表示しています。")
    for idx, novel in enumerate(filtered_novels[:5]):
        with st.container():
            st.markdown(f"### {idx+1}. {novel['title']}")
            st.caption(f"作者: {novel['writer']} | 総文字数: {novel['length']:,}文字 | ブックマーク: {novel['fav_count_display']:,} | 総合ポイント: {novel['global_point']:,}")
            st.write(novel['story'][:200] + "...")
            url = f"https://ncode.syosetu.com/{novel['ncode'].lower()}/"
            st.markdown(f"[この作品を発掘する（なろうで読む）]({url})")
            st.markdown("---")