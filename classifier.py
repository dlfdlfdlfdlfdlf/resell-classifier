#!/usr/bin/env python3
"""
Resell Classifier v13.1
- 정규화 맵(normalize_map.json)을 통한 표현 통일
- 역인덱스 기반 후보 모델 필터링
- 점수 기반 랭킹 (임계값 없음, 최고 점수 선택)
- 루이비통 지갑 등 카테고리 특화
- 동의어 점수 누적 합산 (버그 수정)
"""

import sys, json, time, random, re, os, argparse, urllib.request, urllib.error
from typing import Optional, Dict, List, Set, Tuple

# ------------------------------------------------------------------
#  설정
# ------------------------------------------------------------------
MASTER_FILE = 'model_master.json'
GIST_ID = 'd8db7c29d1fefb7ec25e1b60b32dac56'

# Groq AI (선택적)
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '').strip()
GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL   = 'llama-3.1-8b-instant'

# 브랜드명 (필터링용)
BRAND_NAMES = {
    '루이비통', '샤넬', '에르메스', '구찌', '프라다', '디올',
    '보테가베네타', '보테가', '발렌시아가', '고야드', '셀린느',
    '생로랑', '미우미우', '로에베', '펜디', '버버리',
    'louis', 'vuitton', 'lv', 'chanel', 'hermes', 'gucci', 'prada', 'dior',
    'bottega', 'veneta', 'balenciaga', 'goyard', 'celine', 'saint', 'laurent',
    'miumiu', 'loewe', 'fendi', 'burberry',
}

# 2글자지만 핵심 모델명 키워드
SHORT_IMPORTANT = {
    '지피', '조에', '리사', '가스파', '에바', '클레아', '팡스', '사라', '나노',
    '삭', '플라', '노에', '말', '도빌', '트위스트', '락미', '알마', '스피디'
}

# 잡음 단어
_NOISE_WORDS = {
    '정품', '새상품', '미사용', '사용', '착용', '새제품', '중고',
    '급처', '급처분', '판매', '팝니다', '드립니다', '합니다',
    '상태', '정도', '저렴', '할인', '한정', '진품', '정가',
    '미니', 'mini', '스몰', 'small', '라지', 'large',
}

# 색상/소재 키워드 (점수 가중치 부여)
COLOR_MATERIAL_KEYWORDS = {
    '블랙', '화이트', '베이지', '브라운', '레드', '핑크', '블루', '그린',
    'black', 'white', 'beige', 'brown', 'red', 'pink', 'blue', 'green',
    '모노그램', '다미에', '에피', '타이가', '앙프렝뜨', '섀도우', '쉐도우',
    '이클립스', '아주르', '에벤', '그래파이트', '마카사르', '누아르',
    '토뤼옹', '마히나', '캔버스', '카프스킨', '타이가라마', '아르마냑',
    '푸시아', '로즈', '발레린',
}

# ------------------------------------------------------------------
#  노멀라이즈 맵 로드
# ------------------------------------------------------------------
def load_normalize_map():
    """Gist에서 최신 노멀라이즈 맵 다운로드, 실패 시 로컬 사용"""
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
    return {}

_NORMALIZE_MAP = load_normalize_map()

def normalize(text: str) -> str:
    text = text.lower()
    # 긴 패턴부터 적용 (짧은 패턴이 긴 패턴을 망가뜨리는 것 방지)
    for wrong, right in sorted(_NORMALIZE_MAP.items(), key=lambda x: -len(x[0])):
        text = text.replace(wrong, right)
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def normalize_compact(text: str) -> str:
    """공백/특수문자 제거한 압축 형태"""
    return re.sub(r'[^\w]', '', text.lower(), flags=re.UNICODE)

def remove_brands(tokens: Set[str]) -> Set[str]:
    """브랜드명, 잡음 단어 제거"""
    return {
        t for t in tokens
        if t not in BRAND_NAMES
        and t not in _NOISE_WORDS
        and (len(t) > 1 or t in SHORT_IMPORTANT)
        and (len(t) >= 3 or t in SHORT_IMPORTANT)
        and not t.isdigit()
    }

# ------------------------------------------------------------------
#  모델 마스터 로드
# ------------------------------------------------------------------
def load_master() -> dict:
    """model_master_*.json 파일들을 모두 읽어 하나의 dict로 병합"""
    import glob
    merged = {}
    brand_files = sorted(glob.glob('model_master_*.json'))
    for path in brand_files:
        if 'backup' in path or 'old' in path:
            continue
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

# ------------------------------------------------------------------
#  SmartClassifier
# ------------------------------------------------------------------
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
        # AI fallback 용 가방 모델 리스트
        self._bag_model_names = self._collect_model_names_by_cat('가방')
        self._style_to_model  = self._build_style_map()

    def _collect_model_names_by_cat(self, category: str) -> List[str]:
        entries = []
        for brand, info in self.master.items():
            for model, m_info in info.get('models', {}).items():
                if m_info.get('category', '') == category:
                    entries.append((m_info.get('trade_count', 0) or 0, model))
        entries.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in entries]

    def _build_style_map(self) -> Dict[str, Tuple[str, str]]:
        style_map = {}
        for brand, info in self.master.items():
            for model, m_info in info.get('models', {}).items():
                style = m_info.get('style_code', '')
                if style:
                    style_map[style.upper().strip()] = (model, m_info.get('category', ''))
        print(f'[StyleMap] 품번 {len(style_map)}개 매핑됨')
        return style_map

    def _build_cache(self):
        """모델 데이터 구조화 및 역인덱스 구축"""
        self._model_dict: Dict[str, dict] = {}
        self._cat_model_cache: Dict[str, List[dict]] = {}
        self._keyword_to_models: Dict[str, Set[str]] = {}

        # 품번 직접 매칭 패턴 (루이비통)
        self._direct_patterns = [
            (re.compile(r'\b[MNmn]\d{4,5}[A-Z0-9]?\b'),         '루이비통'),
            (re.compile(r'\b1[A-Z0-9]{5}\b'),                    '루이비통'),
            (re.compile(r'\b[Mm][A-Z]{1,2}\d{3,4}[A-Z0-9]?\b'), '루이비통'),
            (re.compile(r'\b[Qq]\d{4,5}[A-Z0-9]{0,2}\b'),        '루이비통'),
        ]

        for brand, info in self.master.items():
            for model, m_info in info.get('models', {}).items():
                norm_model = normalize(model)
                comp_model = normalize_compact(model)
                core_tokens = remove_brands(set(norm_model.split()))
                category = m_info.get('category', '')
                trade_count = m_info.get('trade_count', 0) or 0
                style_code = m_info.get('style_code', '')

                # 동의어 (보조적)
                synonyms = []
                for s in m_info.get('synonyms', []):
                    synonyms.append((s, normalize(s), normalize_compact(s)))

                entry = {
                    'model_name': model,
                    'norm': norm_model,
                    'compact': comp_model,
                    'core_tokens': core_tokens,
                    'synonyms': synonyms,
                    'category': category,
                    'trade_count': trade_count,
                    'style_code': style_code,
                }
                self._model_dict[model] = entry

                if category:
                    self._cat_model_cache.setdefault(category, []).append(entry)

                # ----- 역인덱스 구축 -----
                # 1) 모델명 자체의 핵심 토큰
                for tok in core_tokens:
                    if len(tok) >= 2:
                        self._keyword_to_models.setdefault(tok, set()).add(model)
                # 2) 모델명 전체 (compact)
                if len(comp_model) >= 3:
                    self._keyword_to_models.setdefault(comp_model, set()).add(model)
                # 3) 동의어에서 추출한 토큰
                for _, syn_norm, syn_comp in synonyms:
                    for tok in syn_norm.split():
                        if len(tok) >= 2:
                            self._keyword_to_models.setdefault(tok, set()).add(model)
                    if len(syn_comp) >= 3:
                        self._keyword_to_models.setdefault(syn_comp, set()).add(model)

        print(f'[Cache] 모델 {len(self._model_dict)}개 / 역인덱스 키워드 {len(self._keyword_to_models)}개')
        for cat, models in self._cat_model_cache.items():
            print(f'  {cat}: {len(models)}개')

    def _calculate_score(self, entry: dict, full: str, compact: str, core_tok: Set[str], raw: str) -> float:
        """후보 모델에 대한 점수 계산 (동의어 점수 누적 합산)"""
        score = 0.0
        model_name = entry['model_name']
        norm_model = entry['norm']
        core_model_tokens = entry['core_tokens']
        synonyms = entry['synonyms']
        style_code = entry.get('style_code', '')

        # 1. 정규화된 모델명이 텍스트에 정확히 포함 (최고 점수)
        if norm_model in full:
            score += 10.0

        # 2. 동의어 포함 (누적 합산)
        syn_score = 0.0
        for _, syn_norm, syn_comp in synonyms:
            matched_syn = None
            if syn_norm and len(syn_norm) >= 4 and syn_norm in full:
                matched_syn = syn_norm
            elif syn_comp and len(syn_comp) >= 4 and syn_comp in compact:
                matched_syn = syn_comp

            if matched_syn:
                # 동의어 길이에 비례한 점수 (더 구체적일수록 높은 점수)
                length_bonus = min(len(matched_syn) / 5.0, 2.0)
                syn_score += 4.0 + length_bonus   # ← 누적 합산

        score += syn_score

        # 3. 핵심 토큰 교집합 비율 (최대 5점)
        if core_model_tokens:
            overlap = core_tok.intersection(core_model_tokens)
            ratio = len(overlap) / len(core_model_tokens)
            score += ratio * 5.0

        # 4. 색상/소재 키워드 일치 (모델명에도 해당 키워드가 있는 경우만 가산)
        for tok in core_tok:
            if tok in COLOR_MATERIAL_KEYWORDS and tok in core_model_tokens:
                score += 0.5   # 미세 가중치

        # 5. 품번 직접 포함 (확실한 신호)
        if style_code and style_code.upper() in raw.upper():
            score += 15.0

        return score

    def classify(self, title: str, content: str = '', category: str = '') -> dict:
        """메인 분류 함수"""
        raw = title + ' ' + content
        full = normalize(raw)
        compact = normalize_compact(raw)
        tokens = set(full.split())
        core_tok = remove_brands(tokens)

        # 0. 품번 직접 매칭 (가장 강력)
        for pat, brand in self._direct_patterns:
            match = pat.search(raw)
            if match:
                style_code = match.group(0).upper()
                if style_code in self._style_to_model:
                    model_name, model_cat = self._style_to_model[style_code]
                    return {
                        'model_name': model_name,
                        'confidence': 1.0,
                        'category': model_cat or category,
                        'method': 'style_code'
                    }
                break   # 첫 매칭만 사용

        # 1. 역인덱스 기반 후보 모델 집합 생성
        candidates: Set[str] = set()
        for tok in core_tok:
            if tok in self._keyword_to_models:
                candidates.update(self._keyword_to_models[tok])
        if compact in self._keyword_to_models:
            candidates.update(self._keyword_to_models[compact])

        # 2. 카테고리 필터 (주어진 경우)
        if category and category in self._cat_model_cache:
            cat_model_names = {e['model_name'] for e in self._cat_model_cache[category]}
            filtered = candidates.intersection(cat_model_names)
            if filtered:  # 필터 후에도 후보가 있을 때만 적용
                candidates = filtered
            # 없으면 카테고리 무시하고 전체 후보 유지

        if not candidates:
            return {'model_name': '미분류', 'confidence': 0.0, 'category': category, 'method': 'no_candidates'}

        # 3. 후보 모델별 점수 계산
        scored = []
        for model_name in candidates:
            entry = self._model_dict.get(model_name)
            if not entry:
                continue
            score = self._calculate_score(entry, full, compact, core_tok, raw)
            scored.append((score, entry))

        if not scored:
            return {'model_name': '미분류', 'confidence': 0.0, 'category': category, 'method': 'no_scored'}

        # 4. 점수 + 인기도로 정렬
        scored.sort(key=lambda x: (x[0], x[1].get('trade_count', 0)), reverse=True)
        best_score, best_entry = scored[0]

        if best_score > 0:
            return {
                'model_name': best_entry['model_name'],
                'confidence': min(best_score / 15.0, 1.0),
                'category': best_entry.get('category', category),
                'method': f'score_{best_score:.2f}'
            }
        else:
            return {'model_name': '미분류', 'confidence': 0.0, 'category': category, 'method': 'score_zero'}

    def classify_with_ai(self, title: str, content: str = '', category: str = '') -> dict:
        """AI fallback 포함 분류"""
        result = self.classify(title, content, category)
        if result['model_name'] == '미분류' and result.get('category') == '가방':
            if GROQ_API_KEY and self._bag_model_names:
                ai_model = self._ai_classify_title(title, self._bag_model_names[:200])
                if ai_model:
                    result['model_name'] = ai_model
                    result['confidence'] = 0.75
                    result['method'] = 'ai'
                    print(f'[AI] "{title}" → {ai_model}')
        return result

    def _ai_classify_title(self, title: str, model_names: List[str]) -> Optional[str]:
        """Groq API로 제목에서 모델명 추론"""
        if not model_names:
            return None
        models_str = '\n'.join(model_names)
        prompt = (
            f'명품 중고 매물 제목에서 아래 공식 모델명 중 가장 유사한 것을 찾아라.\n\n'
            f'매물 제목: "{title}"\n\n'
            f'공식 모델명 목록:\n{models_str}\n\n'
            '규칙:\n'
            '1. 목록에 있는 모델명 중 하나만 정확히 출력\n'
            '2. 확실하지 않으면 "없음" 출력\n'
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
                if answer == '없음' or answer not in model_names:
                    return None
                return answer
        except Exception as e:
            print(f'[Groq] 오류: {e}')
            return None

# ------------------------------------------------------------------
#  Gist 관련 함수
# ------------------------------------------------------------------
def fetch_meta_from_gist(gist_owner: str, gist_id: str) -> dict:
    url = f'https://gist.githubusercontent.com/{gist_owner}/{gist_id}/raw/meta.json'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/13.1'})
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
            req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/13.1'})
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

# ------------------------------------------------------------------
#  메인
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='Resell Classifier v13.1')
    parser.add_argument('--gist_id',    required=True)
    parser.add_argument('--gist_owner', required=True)
    parser.add_argument('--chunk_idx',  type=int, required=True)
    parser.add_argument('--use_ai',     action='store_true')
    args = parser.parse_args()

    print(f'=== Classifier v13.1 시작 === Gist:{args.gist_id[:8]}... / 청크:{args.chunk_idx}')
    if GROQ_API_KEY:
        print(f'[Groq] API 키 로드됨 (use_ai={args.use_ai})')
    else:
        print('[Groq] API 키 없음 — AI 분류 비활성')

    meta = fetch_meta_from_gist(args.gist_owner, args.gist_id)
    brand_keyword = meta.get('brand_keyword', '')
    print(f'[Meta] 브랜드 필터: "{brand_keyword}"')

    items = fetch_chunk_from_gist(args.gist_owner, args.gist_id, args.chunk_idx)
    if items is None:
        print('❌ 청크 로드 실패 → 종료')
        sys.exit(1)

    classifier = SmartClassifier(brand_filter=brand_keyword)
    use_ai = args.use_ai and bool(GROQ_API_KEY)

    results = {}
    skipped = 0
    ai_count = 0

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

        all_confidences.append((title, res['confidence'], res['model_name'], res.get('method', '')))

        if res['confidence'] > 0 and res['model_name'] not in ('미분류', ''):
            results[title] = res['model_name'].strip()
            if res.get('method') == 'ai':
                ai_count += 1
        else:
            unclassified.append({
                'title': title,
                'content': item.get('content', '')[:300],
                'category': category,
                'url': item.get('url', ''),
                'confidence': round(res['confidence'], 3),
                'method': res.get('method', ''),
            })

    # 디버그 출력
    above_0 = sum(1 for _, c, _, _ in all_confidences if c > 0)
    print(f'[DEBUG] confidence>0: {above_0}개 / 전체: {len(all_confidences)}개')
    print('[DEBUG] 샘플 10개:')
    for title, conf, model, method in all_confidences[:10]:
        print(f'  [{conf:.2f}][{method}] {title[:25]} -> {model}')

    # 결과 파일 저장
    out_file = f'classify_result_{args.chunk_idx}.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False)

    unclassified_file = f'unclassified_{args.chunk_idx}.json'
    with open(unclassified_file, 'w', encoding='utf-8') as f:
        json.dump(unclassified, f, ensure_ascii=False)

    total = len(items)
    matched = len(results)
    rate = matched / total * 100 if total else 0
    print(f'✅ 완료: {matched}/{total}건 ({rate:.1f}%) / 스킵 {skipped}건 / AI분류 {ai_count}건')
    print(f'📋 미분류: {len(unclassified)}건 → {unclassified_file}')
    print(f'→ 결과: {out_file}')

if __name__ == '__main__':
    main()
