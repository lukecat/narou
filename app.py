import streamlit as st
import requests
import json
import re
from datetime import datetime

st.set_page_config(page_title="なろう名作発掘スコッパー", layout="centered")
st.title("🔍 隠れた名作発掘システム")
st.write("「書籍化」や「巨大テンプレ」に埋もれない、熱量の高い未発掘作品を提案します。")

# --- サイドバーで条件を動的に調整できるようにする ---
st.sidebar.header("🎛 フィルタリング条件")

# 総合ポイントの上限（1,000 〜 20,000）
max_point = st.sidebar.slider(
    "総合ポイントの上限 (これより下を検索)",
    min_value=1000,
    max_value=20000,
    value=1000,
    step=500,
    help="ポイントが低めだが熱量の高い「隠れた名作」を発掘するための上限値です。"
)

# 総合ポイントの上限を無視するスイッチ
ignore_max_point = st.sidebar.checkbox(
    "総合ポイント上限による除外を無効にする", 
    value=False,
    help="【重要】累計ブックマーク順や累計ポイント順で検索する場合や、転生・転移ありに絞り込む場合は、このチェックをONにしないと検索結果が0件になります。"
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

# ジャンル選択
genre_options = {
    "ハイファンタジー": "201",
    "ローファンタジー": "202",
    "ファンタジー (ハイ/ロー)": "201-202",
    "異世界恋愛": "101",
    "現実世界恋愛": "102",
    "恋愛 (両方)": "101-102",
    "文芸 (推理/歴史/コメディ等)": "301-302-303-304-305-306-307",
    "SF (宇宙/空想科学等)": "401-402-403-404",
    "全ジャンル対象 (指定なし)": ""
}
selected_genre_label = st.sidebar.selectbox("対象ジャンル", list(genre_options.keys()))
selected_genre_code = genre_options[selected_genre_label]

# 異世界転生・転移の絞り込み
tensei_options = {
    "指定なし (転生・転移どちらも含める)": "none",
    "「異世界転生」のみに絞り込む": "tensei",
    "「異世界転移」のみに絞り込む": "teni",
    "「転生」または「転移」に絞り込む": "both",
    "「転生」「転移」をすべて除外する": "exclude"
}
selected_tensei_label = st.sidebar.selectbox("異世界転生・転移の設定", list(tensei_options.keys()))
selected_tensei_code = tensei_options[selected_tensei_label]

exclude_commercial = st.sidebar.checkbox("書籍化・コミカライズ済みの作品を除外する", value=True)

# 評価ポイント（評価点）を受け取らない設定の作品を除外する設定
exclude_no_point = st.sidebar.checkbox(
    "評価ポイントを受け付けない設定の作品を除外する", 
    value=True,
    help="有名な作家のSS置き場など、ブックマークはされているが「評価（ポイント投票）」の受付をOFFにしている作品を除外します。"
)

# --- 【新機能】AI対策・ブラックリスト詳細設定 ---
st.sidebar.markdown("---")
st.sidebar.subheader("🤖 AI対策・ブラックリスト設定")

# 1. 除外する作者名
exclude_writers_input = st.sidebar.text_input(
    "除外する作者名（部分一致・カンマ区切り）",
    value="",
    placeholder="例: 怪しい作者A, 怪しい作者B"
)

# 2. 除外するユーザーID（作者名が変わってもIDで狙い撃ち可能）
exclude_userids_input = st.sidebar.text_input(
    "除外するユーザーID（完全一致・カンマ区切り）",
    value="",
    placeholder="例: 123456, 789012"
)

# 3. 特定の話数の作品を除外（70話きっちりで終わるパターンを撃退）
exclude_episodes_input = st.sidebar.text_input(
    "除外する特定の話数（カンマ区切り）",
    value="70",  # デフォルトで70話完結作品を除外
    help="AIが生成する、きっちり特定の話数（例: 70話）だけで終わっている作品を一括で除外します。"
)

# 4. 人間離れした投稿速度の作品を自動除外
exclude_fast_writing = st.sidebar.checkbox(
    "人間離れした超ハイスピード連載を除外 (AI疑い)",
    value=True,
    help="1日平均 25,000文字を超えるような異常な執筆ペースで投稿された連載作品を、AIによる大量投下とみなして自動的に除外します。"
)


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
def fetch_narou_data(genre_code, order_code, tensei_code):
    url = "https://api.syosetu.com/novelapi/api/"
    
    payload = {
        "out": "json",
        "lim": 400,                 
        "order": order_code,
        # 【機能拡張】u:ユーザーID, ga:全掲載話数, gf:初回掲載日, gl:最終掲載日, nt:小説タイプ(短編/連載)を追加
        "of": "t-w-n-s-k-g-gp-l-f-a-its-iti-u-ga-gf-gl-nt" 
    }
    
    # 1. ジャンル指定
    if genre_code:
        payload["genre"] = genre_code
        
    # 2. 異世界転生・転移パラメータ指定
    if tensei_code == "tensei":
        payload["istensei"] = 1       
    elif tensei_code == "teni":
        payload["istenni"] = 1        
    elif tensei_code == "both":
        payload["istt"] = 1           
    elif tensei_code == "exclude":
        payload["nottt"] = 1          
        
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
result = fetch_narou_data(selected_genre_code, order_code, selected_tensei_code)

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

# ブラックリストとAI除外リストのパース
exclude_writers = [w.strip() for w in exclude_writers_input.split(",") if w.strip()]
exclude_userids = [u.strip() for u in exclude_userids_input.split(",") if u.strip()]
exclude_episodes = [int(ep.strip()) for ep in exclude_episodes_input.split(",") if ep.strip().isdigit()]

# フィルタリング
filtered_novels = []
banned_keywords = [
    "書籍化", "コミカライズ", "アニメ化", "出版", "発売", "文庫", 
    "電子書籍", "コミック", "単行本", "メディアミックス"
]

for n in novels:
    keywords = n.get("keyword", "")
    global_point = n.get("global_point", 0)
    length = n.get("length", 0)
    fav_count = n.get("fav_novel_cnt", 0) 
    all_point = n.get("all_point", 0)  
    
    # 作者・ユーザーID、連載情報
    writer = n.get("writer", "")
    userid = str(n.get("userid", ""))
    episode_count = n.get("general_all_no", 0)
    novel_type = n.get("novel_type", 1)  # 1:連載, 2:短編
    
    # 異世界転生・転移のフラグ値
    novel_istensei = n.get("istensei", 0)
    novel_istenni = n.get("istenni", 0)
    
    # --- AI対策・ブラックリストフィルター ---
    
    # A. 作者名による除外（ブラックリスト・部分一致）
    if any(ew in writer for ew in exclude_writers):
        continue
        
    # B. ユーザーIDによる除外（ブラックリスト・完全一致）
    if userid in exclude_userids:
        continue
        
    # C. 特定の掲載話数による除外（70話完結対策）
    if episode_count in exclude_episodes:
        continue
        
    # D. 異常な投稿速度の作品を除外（AIによる連載一挙投下対策）
    if exclude_fast_writing and novel_type == 1:
        first_up_str = n.get("general_firstup", "")
        last_up_str = n.get("general_lastup", "")
        if first_up_str and last_up_str:
            try:
                # 掲載開始日と終了日の日付差を算出
                first_up = datetime.strptime(first_up_str, "%Y-%m-%d %H:%M:%S")
                last_up = datetime.strptime(last_up_str, "%Y-%m-%d %H:%M:%S")
                diff_days = (last_up - first_up).days
                if diff_days <= 0:
                    diff_days = 1  # 1日未満で完結・投下された場合
                
                # 1日あたりの平均連載文字数
                daily_speed = length / diff_days
                
                # 1日あたり2.5万文字以上のペースで連載（一挙投稿含む）されていたら除外
                if daily_speed > 25000:
                    continue
            except Exception:
                pass
                
    # ジャンルの徹底的なダブルチェック
    if selected_genre_code:
        allowed_genres = [int(g) for g in selected_genre_code.split("-") if g.isdigit()]
        novel_genre = n.get("genre", 0)
        if novel_genre not in allowed_genres:
            continue  
            
    # 異世界転生・転移の徹底的なダブルチェック
    if selected_tensei_code == "tensei":
        if novel_istensei != 1:
            continue  
    elif selected_tensei_code == "teni":
        if novel_istenni != 1:
            continue  
    elif selected_tensei_code == "both":
        if novel_istensei != 1 and novel_istenni != 1:
            continue  
    elif selected_tensei_code == "exclude":
        if novel_istensei == 1 or novel_istenni == 1:
            continue  
            
    title = n.get("title", "")
    story = n.get("story", "")
    combined_text = f"{title}\n{story}\n{keywords}"
    
    # 1. 商業化済み除外フィルター
    if exclude_commercial:
        if any(bk in combined_text for bk in banned_keywords):
            continue
            
    # 2. 評価ポイントを受け取らない設定の作品を除外
    if exclude_no_point:
        if all_point <= 0:
            continue
            
    # 3. 総合ポイントの上限チェック
    if not ignore_max_point:
        if global_point > max_point:
            continue
        
    # 4. 最低ブックマーク数と最低文字数のチェック
    if fav_count < min_fav or length < min_length:
        continue
        
    # 5. 独自熱量スコア（ゼロ除算を防ぎつつ算出）
    length_unit = length / 10000
    if length_unit > 0:
        score = fav_count / length_unit
    else:
        score = 0
        
    n["fav_count_display"] = fav_count
    n["all_point_display"] = all_point
    n["custom_score"] = score
    n["user_id_display"] = userid
    n["episode_count"] = episode_count
    filtered_novels.append(n)

# 独自熱量スコアの高い順にソート
filtered_novels = sorted(filtered_novels, key=lambda x: x["custom_score"], reverse=True)

# ジャンル表示用のマッピング辞書
genre_mapping = {
    101: "異世界恋愛",
    102: "現実世界恋愛",
    201: "ハイファンタジー",
    202: "ローファンタジー",
    301: "純文学",
    302: "ヒューマンドラマ",
    303: "歴史",
    304: "推理",
    305: "ホラー",
    306: "アクション",
    307: "コメディー",
    399: "文芸その他",
    401: "VRゲーム",
    402: "宇宙",
    403: "空想科学",
    404: "パニック",
    9901: "ノンジャンル",
    9902: "童話",
    9903: "詩",
    9904: "エッセイ",
    9999: "その他"
}

# 表示
st.subheader("🌟 本日の厳選・発掘作品")
if novels and not filtered_novels:
    if not ignore_max_point:
        st.warning("⚠️ 候補作品が見つかりません。ポイントが非常に高い作品が多い、またはAI対策などのフィルターですべて除外された可能性があります。フィルター条件を少し緩めてみてください。")
    else:
        st.info("データは正常に取得できましたが、厳格なフィルターにより全作品が除外されました。最低ブックマーク数などの条件を少し緩めてみてください。")
elif filtered_novels:
    st.success(f"{len(filtered_novels)}件の候補から、独自熱量スコアの高い上位5件を表示しています。")
    for idx, novel in enumerate(filtered_novels[:5]):
        with st.container():
            novel_genre_id = novel.get("genre", 0)
            genre_name = genre_mapping.get(novel_genre_id, f"その他({novel_genre_id})")
            
            # 転生・転移タグ
            tag_list = []
            if novel.get("istensei", 0) == 1:
                tag_list.append("異世界転生")
            if novel.get("istenni", 0) == 1:
                tag_list.append("異世界転移")
            tag_text = f" | 要素: {', '.join(tag_list)}" if tag_list else ""
            
            st.markdown(f"### {idx+1}. {novel['title']}")
            # キャプションに「ユーザーID」と「話数（掲載エピソード数）」を表示
            st.caption(
                f"作者: {novel['writer']} (ID: {novel['user_id_display']}) | "
                f"ジャンル: {genre_name}{tag_text} | "
                f"総話数: {novel['episode_count']}話 | "
                f"総文字数: {novel['length']:,}文字 | "
                f"ブックマーク: {novel['fav_count_display']:,} | "
                f"評価点: {novel['all_point_display']:,}pt | "
                f"総合ポイント: {novel['global_point']:,}"
            )
            st.write(novel['story'][:200] + "...")
            url = f"https://ncode.syosetu.com/{novel['ncode'].lower()}/"
            st.markdown(f"[この作品を発掘する（なろうで読む）]({url})")
            st.markdown("---")