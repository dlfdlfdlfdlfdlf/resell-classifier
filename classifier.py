"""
classifier.py  (v12.0 — 역인덱스 + 색상/소재 가중치 + 동의어 강화)

변경사항 vs v11.0:
- _NOISE_WORDS에서 색상/소재 키워드 제거 → COLOR_MATERIAL_KEYWORDS로 분리
- _match_models에서 색상/소재 키워드는 모델명에 포함된 경우에만 토큰 유사도에 반영
- 역인덱스(_keyword_to_models) 구축으로 후보 모델 필터링 → 속도/정확도 향상
- 카테고리 정보가 주어지면 후보를 해당 카테고리로 한정
"""

import sys, json, time, random, re, os, argparse, urllib.request, urllib.error
from typing import Optional

MASTER_FILE = 'model_master.json'

GROQ_API_KEY  = os.environ.get('GROQ_API_KEY', '').strip()
GROQ_API_URL  = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL    = 'llama-3.1-8b-instant'

BRAND_NAMES = {
    '루이비통', '샤넬', '에르메스', '구찌', '프라다', '디올',
    '보테가베네타', '보테가', '발렌시아가', '고야드', '셀린느',
    '생로랑', '미우미우', '로에베', '펜디', '버버리',
    'louis', 'vuitton', 'lv', 'chanel', 'hermes', 'gucci', 'prada', 'dior',
    'bottega', 'veneta', 'balenciaga', 'goyard', 'celine', 'saint', 'laurent',
    'miumiu', 'loewe', 'fendi', 'burberry',
}

# 2글자지만 핵심 모델명인 단어들 — 토큰 최소 길이 예외
SHORT_IMPORTANT = {'지피', '조에', '리사', '가스파', '에바', '클레아', '팡스', '사라', '나노'}

# 진짜 잡음 단어들 (분류에 전혀 도움 안 됨)
_NOISE_WORDS = {
    '정품', '새상품', '미사용', '사용', '착용', '새제품', '중고',
    '급처', '급처분', '판매', '팝니다', '드립니다', '합니다',
    '상태', '정도', '저렴', '할인', '한정', '진품', '정가',
    # 크기 일반명 (모델명 일부가 아닌 경우)
    '미니', 'mini', '스몰', 'small', '라지', 'large',
}

# 색상/소재/패턴 키워드 — 후보 필터링과 토큰 유사도 가중치에 사용
COLOR_MATERIAL_KEYWORDS = {
    '블랙', '화이트', '베이지', '브라운', '레드', '핑크', '블루', '그린',
    'black', 'white', 'beige', 'brown', 'red', 'pink', 'blue', 'green',
    '모노그램', '다미에', '에피', '타이가', '앙프렝뜨', '섀도우', '쉐도우',
    '이클립스', '아주르', '에벤', '그래파이트', '마카사르', '누아르',
    '토뤼옹', '마히나', '캔버스', '카프스킨', '타이가라마', '아르마냑',
    '푸시아', '로즈', '발레린',
}

GIST_ID = 'd8db7c29d1fefb7ec25e1b60b32dac56'

def load_normalize_map_from_gist():
    url = f'https://gist.githubusercontent.com/dlfdlfdlfdlfdlf/{GIST_ID}/raw/normalize_map.json'
    try:
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print(f'[Gist] normalize_map.json 로드 완료 ({len(data)}개 규칙)')
            return data
    except Exception as e:
        print(f'[Gist] 맵 로드 실패, 로컬 파일 시도: {e}')
        for path in ['normalize_map.json', 'nmap_clean.json']:
            if os.path.exists(path):
                with open(path, encoding='utf-8-sig') as f:
                    d = json.load(f)
                print(f'[Gist] 로컬 {path} 사용 ({len(d)}개)')
                return d
        return {'팔레모': '팔레르모', '네버플': '네버풀'}

_NORMALIZE_MAP = load_normalize_map_from_gist()


def load_master() -> dict:
    import glob
    merged = {}
    brand_files = [
        f for f in sorted(glob.glob('model_master_*.json'))
        if 'backup' not in f and 'old' not in f
    ]
    for path in brand_files:
        try:
            with open(path, encoding='utf-8-sig') as f:
                d = json.load(f)
            merged.update(d)
            print(f'[Master] {path} 로드 ({len(d)}개 브랜드)')
        except Exception as e:
            print(f'[Master] {path} 로드 실패: {e}')

    if not merged and os.path.exists(MASTER_FILE):
        with open(MASTER_FILE, encoding='utf-8-sig') as f:
            merged = json.load(f)
        print(f'[Master] {MASTER_FILE} 로드 ({len(merged)}개 브랜드)')
    return merged


def normalize(text: str) -> str:
    text = text.lower()
    for wrong, right in _NORMALIZE_MAP.items():
        text = text.replace(wrong, right)
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def normalize_compact(text: str) -> str:
    return re.sub(r'[^\w]', '', text.lower(), flags=re.UNICODE)


def remove_brands(tokens: set) -> set:
    """브랜드명과 잡음 단어만 제거. 색상/소재 키워드는 보존."""
    return {
        t for t in tokens
        if t not in BRAND_NAMES
        and t not in _NOISE_WORDS
        and (len(t) > 1 or t in SHORT_IMPORTANT)
        and (len(t) >= 3 or t in SHORT_IMPORTANT)
        and not t.isdigit()
    }


def fetch_meta_from_gist(gist_owner: str, gist_id: str) -> dict:
    url = f'https://gist.githubusercontent.com/{gist_owner}/{gist_id}/raw/meta.json'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/12.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f'[Meta] 로드 실패: {e}')
    return {}


def fetch_chunk_from_gist(gist_owner: str, gist_id: str, chunk_idx: int, max_retry: int = 4):
    filename = f'chunk_{chunk_idx}.json'
    url = f'https://gist.githubusercontent.com/{gist_owner}/{gist_id}/raw/{filename}?t={int(time.time())}'
    print(f'[Gist] 다운로드: {url}')
    for attempt in range(max_retry):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/12.0'})
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


def ai_classify_title(title: str, model_names: list, brand: str = '루이비통') -> Optional[str]:
    if not GROQ_API_KEY or not model_names:
        return None
    top_models = model_names[:200]
    models_str = '\n'.join(top_models)
    prompt = (
        f'{brand} 중고 매물 제목에서 아래 공식 모델명 중 가장 유사한 것을 찾아라.\n\n'
        f'매물 제목: "{title}"\n\n'
        f'공식 모델명 목록:\n{models_str}\n\n'
        '규칙:\n'
        '1. 목록에 있는 모델명 중 하나만 정확히 출력\n'
        '2. 확실하지 않으면 없음 출력\n'
        '3. 다른 설명 없이 모델명만 출력\n\n'
        '정답:'
    )
    payload = json.dumps({
        'model': GROQ_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 60,
        'temperature': 0,
    }).encode('utf-8')
    try:
        req = urllib.request.Request(
            GROQ_API_URL, data=payload,
            headers={'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            answer = result['choices'][0]['message']['content'].strip()
            if answer == '없음' or answer not in top_models:
                return None
            return answer
    except Exception as e:
        print(f'[Groq] 오류: {e}')
        return None


class SmartClassifier:
    def __init__(self, brand_filter: str = ''):
        raw_master = load_master()
        self.brand_filter = brand_filter.strip().lower()

        if self.brand_filter:
            self.master = {k: v for k, v in raw_master.items()
                           if self.brand_filter in k.lower()}
            print(f'[SmartClassifier] 브랜드 필터 "{self.brand_filter}": {len(self.master)}개')
        else:
            self.master = raw_master
            print(f'[SmartClassifier] 전체: {len(self.master)}개 브랜드')

        self._build_cache()
        self._bag_model_names = self._collect_model_names_by_cat('가방')
        self._style_to_model  = self._build_style_map()

    def _collect_model_names_by_cat(self, category: str) -> list:
        entries = []
        for brand, info in self.master.items():
            for model, m_info in info.get('models', {}).items():
                if m_info.get('category', '') == category:
                    entries.append((m_info.get('trade_count', 0) or 0, model))
        entries.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in entries]

    def _build_style_map(self) -> dict:
        style_map = {}
        for brand, info in self.master.items():
            for model, m_info in info.get('models', {}).items():
                style = m_info.get('style_code', '')
                if style:
                    style_map[style.upper().strip()] = (model, m_info.get('category', ''))
        print(f'[StyleMap] 품번 {len(style_map)}개 매핑됨')
        return style_map

    def _build_cache(self):
        self._pattern_cache   = []
        self._cat_model_cache = {}
        self._all_model_cache = []

        # 역인덱스: keyword -> set of model names
        self._keyword_to_models = {}

        self._direct_patterns = [
            (re.compile(r'\b[MNmn]\d{4,5}[A-Z0-9]?\b'),         '루이비통'),
            (re.compile(r'\b1[A-Z0-9]{5}\b'),                    '루이비통'),
            (re.compile(r'\b[Mm][A-Z]{1,2}\d{3,4}[A-Z0-9]?\b'), '루이비통'),
            (re.compile(r'\b[Qq]\d{4,5}[A-Z0-9]{0,2}\b'),        '루이비통'),
        ]

        for brand, info in self.master.items():
            for pat in info.get('patterns', []):
                try:
                    self._pattern_cache.append((brand, re.compile(pat)))
                except re.error:
                    pass

            for model, m_info in info.get('models', {}).items():
                norm        = normalize(model)
                compact     = normalize_compact(model)
                core_tokens = remove_brands(set(norm.split()))
                category    = m_info.get('category', '')

                syns = [
                    (s, normalize(s), normalize_compact(s))
                    for s in m_info.get('synonyms', [])
                ]

                entry = (model, norm, compact, core_tokens, syns, category)
                self._all_model_cache.append(entry)
                if category:
                    self._cat_model_cache.setdefault(category, []).append(entry)

                # ----- 역인덱스 구축 -----
                # 1) 모델명 자체에서 추출한 핵심 토큰
                for tok in core_tokens:
                    if len(tok) >= 2:
                        self._keyword_to_models.setdefault(tok, set()).add(model)

                # 2) 동의어들
                for syn_raw, syn_norm, syn_comp in syns:
                    for tok in syn_norm.split():
                        if len(tok) >= 2:
                            self._keyword_to_models.setdefault(tok, set()).add(model)
                    if len(syn_comp) >= 3:
                        self._keyword_to_models.setdefault(syn_comp, set()).add(model)

        print(f'[Cache] 패턴 {len(self._pattern_cache)}개 / 전체 모델 {len(self._all_model_cache)}개')
        print(f'[Cache] 역인덱스 키워드 {len(self._keyword_to_models)}개')
        for cat, models in self._cat_model_cache.items():
            print(f'  {cat}: {len(models)}개')

    def _match_models(self, candidates, full, compact, core_tok) -> dict:
        # 2단계: 모델명 정확 일치
        for model, norm, comp, _, _, cat in candidates:
            if norm and norm in full:
                return {'model_name': model, 'confidence': 1.0, 'category': cat}

        # 3단계: 동의어 일치 (정규화 + compact 양쪽 체크)
        for model, _, _, _, syns, cat in candidates:
            for s_raw, s_norm, s_comp in syns:
                if s_norm and len(s_norm) >= 2 and s_norm in full:
                    return {'model_name': model, 'confidence': 0.95, 'category': cat}
                if s_comp and len(s_comp) >= 4 and s_comp in compact:
                    return {'model_name': model, 'confidence': 0.92, 'category': cat}

        # 4단계: 핵심 토큰 완전 포함 (★ SHORT_IMPORTANT 포함)
        for model, _, _, core_tokens, _, cat in candidates:
            key_tokens = {t for t in core_tokens if len(t) >= 3 or t in SHORT_IMPORTANT}
            if key_tokens and key_tokens.issubset(core_tok):
                return {'model_name': model, 'confidence': 0.88, 'category': cat}

        # 5단계: 토큰 유사도 (색상/소재 가중치 적용)
        best_score, best_model, best_cat = 0.0, None, ''
        for model, _, _, core_tokens, _, cat in candidates:
            key_tokens = {t for t in core_tokens if len(t) >= 3 or t in SHORT_IMPORTANT}
            if not key_tokens:
                continue

            # 색상/소재 키워드는 모델명에 포함된 경우에만 유효
            valid_tokens = set()
            for tok in core_tok:
                if tok in COLOR_MATERIAL_KEYWORDS:
                    if tok in core_tokens:
                        valid_tokens.add(tok)
                else:
                    valid_tokens.add(tok)

            score = len(valid_tokens & key_tokens) / len(key_tokens)
            if score > best_score:
                best_score, best_model, best_cat = score, model, cat

        if best_score >= 0.65:
            return {'model_name': best_model, 'confidence': best_score, 'category': best_cat}

        # 6단계: 단일 핵심 키워드 (4글자 이상)
        for model, _, _, core_tokens, _, cat in candidates:
            for tok in core_tokens:
                if len(tok) >= 4 and tok in full:
                    return {'model_name': model, 'confidence': 0.75, 'category': cat}

        return {}

    def classify(self, title: str, content: str = '', category: str = '') -> dict:
        raw      = title + ' ' + content
        full     = normalize(raw)
        compact  = normalize_compact(raw)
        tokens   = set(full.split())
        core_tok = remove_brands(tokens)

        # 0단계: 품번 매핑
        for pat, brand in self._direct_patterns:
            match = pat.search(raw)
            if match:
                style_code = match.group(0).upper()
                if style_code in self._style_to_model:
                    model_name, model_cat = self._style_to_model[style_code]
                    return {
                        'model_name': model_name,
                        'confidence': 1.0,
                        'category':   model_cat or category,
                    }
                break

        resolved_cat = category if category and category not in ('미분류', '기타', '') else ''

        # ----- 역인덱스 기반 후보 필터링 -----
        candidate_models = set()
        # 1) 핵심 토큰으로 검색
        for tok in core_tok:
            if tok in self._keyword_to_models:
                candidate_models.update(self._keyword_to_models[tok])
        # 2) compact 전체로 검색
        if compact in self._keyword_to_models:
            candidate_models.update(self._keyword_to_models[compact])

        if candidate_models:
            candidates = [e for e in self._all_model_cache if e[0] in candidate_models]
            if resolved_cat and resolved_cat in self._cat_model_cache:
                cat_model_names = {e[0] for e in self._cat_model_cache[resolved_cat]}
                candidates = [e for e in candidates if e[0] in cat_model_names]
        else:
            if resolved_cat and resolved_cat in self._cat_model_cache:
                candidates = self._cat_model_cache[resolved_cat]
            else:
                candidates = self._all_model_cache

        # 매칭 실행
        result = self._match_models(candidates, full, compact, core_tok)
        if result:
            return result

        return {'model_name': '미분류', 'confidence': 0.0, 'category': resolved_cat}

    def classify_with_ai(self, title: str, content: str = '', category: str = '') -> dict:
        result = self.classify(title, content, category)
        if result['model_name'] == '미분류' and result.get('category') == '가방':
            brand = self.brand_filter if self.brand_filter else '명품'
            ai_model = ai_classify_title(title, self._bag_model_names, brand=brand)
            if ai_model:
                result['model_name']    = ai_model
                result['confidence']    = 0.75
                result['ai_classified'] = True
                print(f'[AI] "{title}" → {ai_model}')
        return result


def main():
    parser = argparse.ArgumentParser(description='Resell Classifier v12.0')
    parser.add_argument('--gist_id',    required=True)
    parser.add_argument('--gist_owner', required=True)
    parser.add_argument('--chunk_idx',  type=int, required=True)
    parser.add_argument('--use_ai',     action='store_true')
    args = parser.parse_args()

    print(f'=== Classifier v12.0 시작 === Gist:{args.gist_id[:8]}... / 청크:{args.chunk_idx}')
    if GROQ_API_KEY:
        print(f'[Groq] API 키 로드됨 (use_ai={args.use_ai})')
    else:
        print('[Groq] API 키 없음 — AI 분류 비활성')

    meta          = fetch_meta_from_gist(args.gist_owner, args.gist_id)
    brand_keyword = meta.get('brand_keyword', '')
    print(f'[Meta] 브랜드 필터: "{brand_keyword}"')

    items = fetch_chunk_from_gist(args.gist_owner, args.gist_id, args.chunk_idx)
    if items is None:
        print('❌ 청크 로드 실패 → 종료')
        sys.exit(1)

    classifier = SmartClassifier(brand_filter=brand_keyword)
    use_ai     = args.use_ai and bool(GROQ_API_KEY)
    results    = {}
    skipped    = 0
    ai_count   = 0

    unclassified = []
    all_confidences = []

    for item in items:
        title = item.get('title', '').strip()
        if not title:
            skipped += 1
            continue

        category = item.get('category', '')

        if use_ai:
            res = classifier.classify_with_ai(title, item.get('content', ''), category)
        else:
            res = classifier.classify(title, item.get('content', ''), category)

        all_confidences.append((title, res['confidence'], res['model_name']))

        if res['confidence'] >= 0.65 and res['model_name'] not in ('미분류', ''):
            results[title] = res['model_name'].strip()
            if res.get('ai_classified'):
                ai_count += 1
        else:
            unclassified.append({
                'title':    title,
                'content':  item.get('content', '')[:300],
                'category': category,
                'url':      item.get('url', ''),
                'confidence': round(res['confidence'], 3),
            })

    unclassified_file = f'unclassified_{args.chunk_idx}.json'
    with open(unclassified_file, 'w', encoding='utf-8') as f:
        json.dump(unclassified, f, ensure_ascii=False)

    above_065 = sum(1 for _, c, _ in all_confidences if c >= 0.65)
    above_05  = sum(1 for _, c, _ in all_confidences if c >= 0.5)
    above_0   = sum(1 for _, c, _ in all_confidences if c > 0)
    print(f'[DEBUG] confidence>=0.65: {above_065}개 / >=0.5: {above_05}개 / >0: {above_0}개 / 전체: {len(all_confidences)}개')
    print('[DEBUG] 샘플 10개:')
    for title, conf, model in all_confidences[:10]:
        print(f'  [{conf:.2f}] {title[:25]} -> {model}')

    out_file = f'classify_result_{args.chunk_idx}.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False)

    total   = len(items)
    matched = len(results)
    rate    = matched / total * 100 if total else 0
    print(f'✅ 완료: {matched}/{total}건 ({rate:.1f}%) / 스킵 {skipped}건 / AI분류 {ai_count}건')
    print(f'📋 미분류: {len(unclassified)}건 → {unclassified_file}')
    print(f'→ 결과: {out_file}')


if __name__ == '__main__':
    main()
