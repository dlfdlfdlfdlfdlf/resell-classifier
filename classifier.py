"""
classifier.py  (v3 — 브랜드 필터 적용)
"""

import sys, json, time, random, re, os, argparse, urllib.request

MASTER_FILE = 'model_master.json'

CATEGORY_KEYWORDS = {
    '가방':        ['가방', '백', 'bag', '토트', '숄더', '크로스', '클러치', '파우치', '백팩', '보스턴', '버킷', '호보', '새첼', '미니백'],
    '지갑':        ['지갑', '월렛', 'wallet', '카드지갑', '장지갑', '반지갑', '코인', '머니클립', '키홀더', '키케이스'],
    '신발':        ['신발', '슈즈', '스니커즈', '로퍼', '부츠', '샌들', '슬리퍼', '힐', '플랫', 'shoes', 'sneakers'],
    '의류':        ['자켓', '재킷', '코트', '셔츠', '티셔츠', '후드', '가디건', '스웨터', '청바지', '바지', '스커트', '원피스', '패딩', '점퍼', '블라우스'],
    '쥬얼리':      ['목걸이', '반지', '귀걸이', '팔찌', '브로치', '쥬얼리', '주얼리', 'necklace', 'ring', 'bracelet', '체인'],
    '패션악세서리': ['벨트', '스카프', '머플러', '선글라스', '모자', '장갑', '넥타이', '포켓스퀘어', '키링', '키체인'],
}


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

def fetch_gist_file(gist_owner: str, gist_id: str, filename: str, max_retry: int = 3):
    url = f'https://gist.githubusercontent.com/{gist_owner}/{gist_id}/raw/{filename}'
    for attempt in range(max_retry):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/3.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            wait = 2 ** attempt + random.uniform(0, 1)
            print(f'[Gist] 재시도 {attempt+1}/{max_retry} ({filename}): {e}')
            time.sleep(wait)
    return None


class SmartClassifier:
    def __init__(self, brand_filter: str = ''):
        self.master = load_master()
        self.brand_filter = brand_filter.strip().lower()
        print(f'[SmartClassifier] master 로드: {len(self.master)}개 브랜드 / 브랜드 필터: "{self.brand_filter}"')

        # 브랜드 필터가 있으면 해당 브랜드만 사용
        if self.brand_filter:
            filtered = {}
            for brand, info in self.master.items():
                if self.brand_filter in brand.lower():
                    filtered[brand] = info
            self.master = filtered
            print(f'[SmartClassifier] 필터 적용 후: {len(self.master)}개 브랜드')

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

        return {'model_name': '미분류', 'confidence': 0.0}


def main():
    parser = argparse.ArgumentParser(description='Resell Classifier v3')
    parser.add_argument('--gist_id',    required=True)
    parser.add_argument('--gist_owner', required=True)
    parser.add_argument('--chunk_idx',  type=int, required=True)
    args = parser.parse_args()

    print(f'=== Classifier v3 시작 === Gist:{args.gist_id[:8]}... / 청크:{args.chunk_idx}')

    # 메타 파일에서 brand_keyword 로드
    brand_keyword = ''
    meta = fetch_gist_file(args.gist_owner, args.gist_id, 'meta.json', max_retry=3)
    if meta:
        brand_keyword = meta.get('brand_keyword', '')
        print(f'[Meta] 브랜드 필터: "{brand_keyword}"')
    else:
        print('[Meta] meta.json 로드 실패 → 전체 브랜드로 분류')

    # 청크 데이터 로드
    items = fetch_gist_file(args.gist_owner, args.gist_id, f'chunk_{args.chunk_idx}.json')
    if items is None:
        print('❌ 청크 데이터 로드 실패 → 종료')
        sys.exit(1)

    classifier = SmartClassifier(brand_filter=brand_keyword)
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
