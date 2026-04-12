"""
classifier.py  (v2 — Gist 기반)

변경점:
  --server 방식 제거 (GitHub Actions에서 localhost 접근 불가)
  → Gist raw URL에서 직접 청크 데이터를 다운로드하는 방식으로 교체
"""

import sys, json, time, random, re, os, argparse, urllib.request

MASTER_FILE = 'model_master.json'

CATEGORY_KEYWORDS = {
    '가방':        ['가방', '백', 'bag', '토트', '숄더', '크로스', '클러치', '파우치', '백팩', '보스턴', '버킷', '호보', '새첼', '미니백'],
    '지갑':        ['지갑', '월렛', 'wallet', '카드지갑', '장지갑', '반지갑', '코인', '머니클립', '키홀더', '키케이스'],
    '신발':        ['신발', '슈즈', '스니커즈', '로퍼', '부츠', '샌들', '슬리퍼', '힐', '플랫', 'shoes', 'sneakers'],
    '의류':        ['자켓', '재킷', '코트', '셔츠', '티셔츠', '후드', '가디건', '스웨터', '청바지', '바지', '스커트', '원피스', '패딩', '점퍼', '블라우스'],
    '쥬얼리':      ['목걸이', '반지', '귀걸이', '팔찌', '브로치', '쥬얼리', '주얼리', 'necklace', 'ring', 'bracelet', '체인'],
    '패션악세서리': ['벨트', '스카프', '머플러', '선글라스', '모자', '장갑', '넥타이', '포켓스퀘어', '브레이슬릿', '시계줄', '키링', '키체인'],
}


# ──────────────────────────────────────────────────────────────
#  SmartClassifier
# ──────────────────────────────────────────────────────────────

def load_master() -> dict:
    if os.path.exists(MASTER_FILE):
        with open(MASTER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

class SmartClassifier:
    def __init__(self):
        self.master = load_master()
        print(f'[SmartClassifier] master 로드: {len(self.master)}개 브랜드')

    def classify(self, title: str, content: str = '') -> dict:
        full = normalize(title + ' ' + content)

        # 1단계: 정규식 패턴 (품번)
        for brand, info in self.master.items():
            for pat in info.get('patterns', []):
                if re.search(pat, full):
                    return {'model_name': f'{brand} 품번매칭', 'confidence': 0.95}

        # 2단계: 정확 일치
        for brand, info in self.master.items():
            for model, m_info in info.get('models', {}).items():
                if model in full:
                    return {'model_name': model, 'confidence': 1.0}

        # 3단계: 동의어
        for brand, info in self.master.items():
            for model, m_info in info.get('models', {}).items():
                for syn in m_info.get('synonyms', []):
                    if syn in full:
                        return {'model_name': model, 'confidence': 0.9}

        # 4단계: 토큰 유사도
        tokens = set(full.split())
        best_score, best_model = 0.0, None
        for brand, info in self.master.items():
            for model, m_info in info.get('models', {}).items():
                model_tokens = set(normalize(model).split())
                if not model_tokens:
                    continue
                score = len(tokens & model_tokens) / len(model_tokens)
                if score > best_score:
                    best_score = score
                    best_model = model
        if best_score >= 0.6:
            return {'model_name': best_model, 'confidence': best_score}

        # 5단계: 카테고리 키워드
        for cat, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in full:
                    return {'model_name': '기타', 'confidence': 0.5}

        return {'model_name': '미분류', 'confidence': 0.0}


# ──────────────────────────────────────────────────────────────
#  Gist 다운로드
# ──────────────────────────────────────────────────────────────

def fetch_chunk_from_gist(gist_owner: str, gist_id: str, chunk_idx: int, max_retry: int = 4) -> list | None:
    filename = f'chunk_{chunk_idx}.json'
    url = f'https://gist.githubusercontent.com/{gist_owner}/{gist_id}/raw/{filename}'
    print(f'[Gist] 다운로드: {url}')

    for attempt in range(max_retry):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/2.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                print(f'[Gist] ✅ {len(data)}개 아이템 로드')
                return data
        except Exception as e:
            wait = 2 ** attempt + random.uniform(0, 1)
            print(f'[Gist] 재시도 {attempt + 1}/{max_retry}: {e} (대기 {wait:.1f}s)')
            time.sleep(wait)

    print(f'[Gist] ❌ 다운로드 실패: {filename}')
    return None


# ──────────────────────────────────────────────────────────────
#  메인
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Resell Classifier v2')
    parser.add_argument('--gist_id',    required=True, help='GitHub Gist ID')
    parser.add_argument('--gist_owner', required=True, help='Gist 소유자 계정명')
    parser.add_argument('--chunk_idx',  type=int, required=True, help='처리할 청크 인덱스')
    args = parser.parse_args()

    print(f'=== Classifier v2 시작 ===')
    print(f'Gist: {args.gist_id[:8]}... / Owner: {args.gist_owner} / 청크: {args.chunk_idx}')

    items = fetch_chunk_from_gist(args.gist_owner, args.gist_id, args.chunk_idx)
    if items is None:
        print('❌ 데이터 로드 실패 → 종료')
        sys.exit(1)

    classifier = SmartClassifier()
    results = {}

    for item in items:
        title = item.get('title', '').strip()
        if not title:
            continue
        res = classifier.classify(title, item.get('content', ''))
        if res['confidence'] >= 0.5 and res['model_name'] not in ('미분류', ''):
            results[title] = res['model_name']

    out_file = f'classify_result_{args.chunk_idx}.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False)

    total   = len(items)
    matched = len(results)
    rate    = matched / total * 100 if total else 0
    print(f'✅ 완료: {matched}/{total}건 ({rate:.1f}%) → {out_file}')


if __name__ == '__main__':
    main()
