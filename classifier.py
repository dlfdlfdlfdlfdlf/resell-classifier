"""
classifier.py  (v3 — 강화된 매칭 로직)
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


def load_master() -> dict:
    if os.path.exists(MASTER_FILE):
        with open(MASTER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def normalize(text: str) -> str:
    """소문자 + 특수문자 제거 + 공백 정리"""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def normalize_compact(text: str) -> str:
    """소문자 + 특수문자 제거 + 공백 완전 제거 (붙여쓰기 비교용)"""
    text = text.lower()
    text = re.sub(r'[^\w]', '', text)
    return text


def fetch_meta_from_gist(gist_owner: str, gist_id: str) -> dict:
    """meta.json에서 brand_keyword 등 메타 정보 로드"""
    url = f'https://gist.githubusercontent.com/{gist_owner}/{gist_id}/raw/meta.json'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/3.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f'[Meta] 로드 실패 (무시): {e}')
    return {}


class SmartClassifier:
    def __init__(self, brand_filter: str = ''):
        raw_master = load_master()
        self.brand_filter = brand_filter.strip().lower()

        # 브랜드 필터 적용
        if self.brand_filter:
            self.master = {
                k: v for k, v in raw_master.items()
                if self.brand_filter in k.lower()
            }
            print(f'[SmartClassifier] 브랜드 필터 "{self.brand_filter}" 적용: {len(self.master)}개 브랜드')
        else:
            self.master = raw_master
            print(f'[SmartClassifier] 전체 브랜드: {len(self.master)}개')

        # 사전 캐시 빌드 (속도 향상)
        self._model_cache = []       # (model_name, norm_model, compact_model, syns)
        self._pattern_cache = []     # (brand, pattern)
        self._build_cache()

    def _build_cache(self):
        for brand, info in self.master.items():
            for pat in info.get('patterns', []):
                self._pattern_cache.append((brand, pat))
            for model, m_info in info.get('models', {}).items():
                norm_model    = normalize(model)
                compact_model = normalize_compact(model)
                syns = m_info.get('synonyms', [])
                norm_syns = [(s, normalize(s), normalize_compact(s)) for s in syns]
                self._model_cache.append((model, norm_model, compact_model, norm_syns))

    def classify(self, title: str, content: str = '') -> dict:
        full         = normalize(title + ' ' + content)
        full_compact = normalize_compact(title + ' ' + content)

        # 1단계: 품번 정규식
        for brand, pat in self._pattern_cache:
            if re.search(pat, full):
                return {'model_name': f'{brand} 품번매칭', 'confidence': 0.95}

        # 2단계: 모델명 정확 일치 (공백 포함 / 공백 제거 둘 다)
        for model, norm_model, compact_model, _ in self._model_cache:
            if norm_model in full or compact_model in full_compact:
                return {'model_name': model, 'confidence': 1.0}

        # 3단계: 동의어 일치 (normalize 적용 + 공백 제거 버전)
        for model, _, _, norm_syns in self._model_cache:
            for syn_orig, syn_norm, syn_compact in norm_syns:
                if syn_norm in full or syn_compact in full_compact:
                    return {'model_name': model, 'confidence': 0.9}

        # 4단계: 토큰 유사도 (브랜드명 제외 핵심 토큰 기준)
        full_tokens = set(full.split())
        best_score, best_model = 0.0, None

        for model, norm_model, _, _ in self._model_cache:
            model_tokens = set(norm_model.split())
            # 1~2글자 단어(조사, 관사 등) 제외
            model_tokens = {t for t in model_tokens if len(t) > 2}
            if not model_tokens:
                continue
            intersection = full_tokens & model_tokens
            if not intersection:
                continue
            score = len(intersection) / len(model_tokens)
            if score > best_score:
                best_score = score
                best_model = model

        if best_score >= 0.5:
            return {'model_name': best_model, 'confidence': best_score}

        # 5단계: 핵심 토큰 부분 매칭 (모델 토큰이 2개 이상 전부 제목에 있으면)
        for model, norm_model, _, _ in self._model_cache:
            model_tokens = {t for t in set(norm_model.split()) if len(t) > 2}
            if len(model_tokens) >= 2 and model_tokens.issubset(full_tokens):
                return {'model_name': model, 'confidence': 0.75}
            # 3글자 이상 단일 핵심 토큰이 제목에 있으면
            if len(model_tokens) == 1:
                tok = next(iter(model_tokens))
                if len(tok) >= 3 and tok in full:
                    return {'model_name': model, 'confidence': 0.65}

        return {'model_name': '미분류', 'confidence': 0.0}


def fetch_chunk_from_gist(gist_owner: str, gist_id: str, chunk_idx: int, max_retry: int = 4):
    filename = f'chunk_{chunk_idx}.json'
    url = f'https://gist.githubusercontent.com/{gist_owner}/{gist_id}/raw/{filename}'
    print(f'[Gist] 다운로드: {url}')
    for attempt in range(max_retry):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/3.0'})
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


def main():
    parser = argparse.ArgumentParser(description='Resell Classifier v3')
    parser.add_argument('--gist_id',    required=True)
    parser.add_argument('--gist_owner', required=True)
    parser.add_argument('--chunk_idx',  type=int, required=True)
    args = parser.parse_args()

    print(f'=== Classifier v3 시작 === Gist:{args.gist_id[:8]}... / 청크:{args.chunk_idx}')

    # meta.json에서 brand_keyword 로드
    meta = fetch_meta_from_gist(args.gist_owner, args.gist_id)
    brand_keyword = meta.get('brand_keyword', '')
    print(f'[Meta] 브랜드 필터: "{brand_keyword}"')

    items = fetch_chunk_from_gist(args.gist_owner, args.gist_id, args.chunk_idx)
    if items is None:
        print('❌ 청크 로드 실패 → 종료')
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
