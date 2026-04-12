"""
classifier.py  (v4 — 강화된 매칭 + 캐시 + 브랜드 필터)
"""

import sys, json, time, random, re, os, argparse, urllib.request

MASTER_FILE = 'model_master.json'

# 브랜드명 제거 대상 (토큰 유사도 왜곡 방지)
BRAND_NAMES = ['루이비통', '샤넬', '구찌', '에르메스', '프라다', '버버리', '발렌시아가',
               'louis', 'vuitton', 'chanel', 'gucci', 'hermes', 'prada', 'burberry']


def load_master() -> dict:
    if os.path.exists(MASTER_FILE):
        with open(MASTER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def normalize(text: str) -> str:
    """소문자 + 특수문자 → 공백 + 연속공백 제거"""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def normalize_compact(text: str) -> str:
    """소문자 + 모든 비단어 문자 제거 (공백 포함) — 붙여쓰기 비교용"""
    return re.sub(r'[^\w]', '', text.lower())


def remove_brands(tokens: set) -> set:
    """토큰 집합에서 브랜드명 제거"""
    return {t for t in tokens if t not in BRAND_NAMES and len(t) > 1}


def fetch_meta_from_gist(gist_owner: str, gist_id: str) -> dict:
    url = f'https://gist.githubusercontent.com/{gist_owner}/{gist_id}/raw/meta.json'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/4.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f'[Meta] 로드 실패: {e}')
    return {}


class SmartClassifier:
    def __init__(self, brand_filter: str = ''):
        raw_master = load_master()
        self.brand_filter = brand_filter.strip().lower()

        # 브랜드 필터 적용
        if self.brand_filter:
            self.master = {k: v for k, v in raw_master.items()
                          if self.brand_filter in k.lower()}
            print(f'[SmartClassifier] 브랜드 필터 "{self.brand_filter}": {len(self.master)}개')
        else:
            self.master = raw_master
            print(f'[SmartClassifier] 전체: {len(self.master)}개 브랜드')

        self._build_cache()

    def _build_cache(self):
        """속도 향상을 위한 사전 캐시 빌드"""
        self._pattern_cache = []  # (brand, pattern)
        self._model_cache   = []  # (model_name, norm, compact, core_tokens, syns)

        for brand, info in self.master.items():
            for pat in info.get('patterns', []):
                self._pattern_cache.append((brand, pat))

            for model, m_info in info.get('models', {}).items():
                norm    = normalize(model)
                compact = normalize_compact(model)
                # 브랜드명 제거한 핵심 토큰
                core_tokens = remove_brands(set(norm.split()))

                # 동의어 전처리
                syns = []
                for s in m_info.get('synonyms', []):
                    syns.append((s, normalize(s), normalize_compact(s)))

                self._model_cache.append((model, norm, compact, core_tokens, syns))

        print(f'[Cache] 패턴 {len(self._pattern_cache)}개 / 모델 {len(self._model_cache)}개')

    def classify(self, title: str, content: str = '') -> dict:
        raw      = title + ' ' + content
        full     = normalize(raw)
        compact  = normalize_compact(raw)
        tokens   = set(full.split())
        core_tok = remove_brands(tokens)

        # ── 1단계: 품번 정규식 ──────────────────────────────
        for brand, pat in self._pattern_cache:
            if re.search(pat, full):
                return {'model_name': f'{brand} 품번매칭', 'confidence': 0.95}

        # ── 2단계: 모델명 정확 일치 (공백포함 / 공백제거) ──
        for model, norm, comp, _, _ in self._model_cache:
            if norm in full or comp in compact:
                return {'model_name': model, 'confidence': 1.0}

        # ── 3단계: 동의어 일치 (normalize 적용) ─────────────
        for model, _, _, _, syns in self._model_cache:
            for syn_orig, syn_norm, syn_comp in syns:
                if syn_norm and (syn_norm in full or syn_comp in compact):
                    return {'model_name': model, 'confidence': 0.9}

        # ── 4단계: 핵심 토큰 완전 포함 ──────────────────────
        # 모델의 핵심 토큰이 모두 제목에 있으면 매칭
        for model, _, _, core_tokens, _ in self._model_cache:
            if not core_tokens:
                continue
            # 3글자 이상 토큰만 사용
            key_tokens = {t for t in core_tokens if len(t) >= 3}
            if not key_tokens:
                continue
            if key_tokens.issubset(core_tok):
                return {'model_name': model, 'confidence': 0.85}

        # ── 5단계: 토큰 유사도 (브랜드명 제외) ──────────────
        best_score, best_model = 0.0, None
        for model, _, _, core_tokens, _ in self._model_cache:
            key_tokens = {t for t in core_tokens if len(t) >= 3}
            if not key_tokens:
                continue
            intersection = core_tok & key_tokens
            if not intersection:
                continue
            score = len(intersection) / len(key_tokens)
            if score > best_score:
                best_score = score
                best_model = model

        if best_score >= 0.5:
            return {'model_name': best_model, 'confidence': best_score}

        # ── 6단계: 단일 핵심 키워드 매칭 ────────────────────
        # 모델명에서 가장 독특한 단어 하나가 제목에 있으면 매칭
        # (단, 4글자 이상만 — 짧은 단어 오매칭 방지)
        for model, _, _, core_tokens, _ in self._model_cache:
            for tok in core_tokens:
                if len(tok) >= 4 and tok in full:
                    return {'model_name': model, 'confidence': 0.7}

        return {'model_name': '미분류', 'confidence': 0.0}


def fetch_chunk_from_gist(gist_owner: str, gist_id: str, chunk_idx: int, max_retry: int = 4):
    filename = f'chunk_{chunk_idx}.json'
    url = f'https://gist.githubusercontent.com/{gist_owner}/{gist_id}/raw/{filename}'
    print(f'[Gist] 다운로드: {url}')
    for attempt in range(max_retry):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/4.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                print(f'[Gist] ✅ {len(data)}개 아이템 로드')
                return data
        except Exception as e:
            wait = 2 ** attempt + random.uniform(0, 1)
            print(f'[Gist] 재시도 {attempt+1}/{max_retry}: {e} (대기 {wait:.1f}s)')
            time.sleep(wait)
    print(f'[Gist] ❌ 다운로드 실패: {filename}')
    return None


def main():
    parser = argparse.ArgumentParser(description='Resell Classifier v4')
    parser.add_argument('--gist_id',    required=True)
    parser.add_argument('--gist_owner', required=True)
    parser.add_argument('--chunk_idx',  type=int, required=True)
    args = parser.parse_args()

    print(f'=== Classifier v4 시작 === Gist:{args.gist_id[:8]}... / 청크:{args.chunk_idx}')

    meta          = fetch_meta_from_gist(args.gist_owner, args.gist_id)
    brand_keyword = meta.get('brand_keyword', '')
    print(f'[Meta] 브랜드 필터: "{brand_keyword}"')

    items = fetch_chunk_from_gist(args.gist_owner, args.gist_id, args.chunk_idx)
    if items is None:
        print('❌ 청크 로드 실패 → 종료')
        sys.exit(1)

    classifier = SmartClassifier(brand_filter=brand_keyword)
    results    = {}

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
