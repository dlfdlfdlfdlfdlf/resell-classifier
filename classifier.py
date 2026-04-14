"""
classifier.py  (v8.1 — 버그픽스 + 개선)
"""

import sys, json, time, random, re, os, argparse, urllib.request, urllib.error
from typing import Optional

MASTER_FILE = 'model_master.json'

# ──────────────────────────────────────────────────────────────────────────────
#  Groq API (GitHub Actions 환경변수에서 읽음)
# ──────────────────────────────────────────────────────────────────────────────
GROQ_API_KEY  = os.environ.get('GROQ_API_KEY', '').strip()
GROQ_API_URL  = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL    = 'llama-3.1-8b-instant'

# ──────────────────────────────────────────────────────────────────────────────
#  브랜드명 / 노이즈 단어
# ──────────────────────────────────────────────────────────────────────────────
BRAND_NAMES = {
    '루이비통', '샤넬', '에르메스', '구찌', '프라다', '디올',
    '보테가베네타', '보테가', '발렌시아가', '고야드', '셀린느',
    '생로랑', '미우미우', '로에베', '펜디', '버버리',
    'louis', 'vuitton', 'lv', 'chanel', 'hermes', 'gucci', 'prada', 'dior',
    'bottega', 'veneta', 'balenciaga', 'goyard', 'celine', 'saint', 'laurent',
    'miumiu', 'loewe', 'fendi', 'burberry',
}

_NOISE_WORDS = {
    '정품', '새상품', '미사용', '사용', '착용', '새제품', '중고',
    '급처', '급처분', '판매', '팝니다', '드립니다', '합니다',
    '상태', '정도', '저렴', '할인', '한정', '진품', '정가',
    '블랙', '화이트', '베이지', '브라운', '레드', '핑크', '블루', '그린',
    'black', 'white', 'beige', 'brown', 'red', 'pink', 'blue', 'green',
    '미니', 'mini', '스몰', 'small', '라지', 'large',
}

# ──────────────────────────────────────────────────────────────────────────────
#  유사 표기 통일 딕셔너리
#  ※ normalize()에서 lower() + NORMALIZE_MAP 먼저 적용 후 특수문자 제거
# ──────────────────────────────────────────────────────────────────────────────
_NORMALIZE_MAP = {
    # 팔레르모
    '팔레모':               '팔레르모',

    # 에튀 보야주
    '에튀보야주':           '에튀 보야주',
    '에뮬보야쥴':           '에튀 보야주',
    '에뮬보야주':           '에튀 보야주',
    '에뮬mm':               '에튀 보야주 mm',
    '에뮬gm':               '에튀 보야주 gm',
    '에뮬pm':               '에튀 보야주 pm',

    # 앙프렝뜨
    '앙프렉뜨':             '앙프렝뜨',
    '엠프렉뜨':             '앙프렝뜨',
    '앙프레뜨':             '앙프렝뜨',
    '앙프렁뜨':             '앙프렝뜨',
    '앙프랭뜨':             '앙프렝뜨',
    '엠프렝뜨':             '앙프렝뜨',

    # 트루빌
    '투루블':               '트루빌',
    '트루블':               '트루빌',

    # 룩스부리
    '뤽부리':               '룩스부리',
    '룩부리':               '룩스부리',
    '록스부리':             '룩스부리',
    '럭스부리':             '룩스부리',

    # 도핀
    '도피체인':             '도핀 체인',
    '도피네':               '도핀',

    # 일립스
    '엘립스':               '일립스',
    '엘리프스':             '일립스',

    # 보야주
    '보야쥴':               '보야주',
    '보야지':               '보야주',

    # 마들렌
    '마들렝':               '마들렌',
    '마들린':               '마들렌',

    # 앗치
    '아치백':               '앗치',
    '앗치백':               '앗치',

    # 포쉐트
    '포세트':               '포쉐트',
    '포쉐악':               '포쉐트 악세수아',
    '포쉐악세수아':         '포쉐트 악세수아',

    # 카퓌신
    '카푸신':               '카퓌신',
    '카피쉰':               '카퓌신',
    '카퓌쉰':               '카퓌신',
    '카피신':               '카퓌신',

    # 소뮈르
    '소뮤르':               '소뮈르',

    # 수플로
    '수프로':               '수플로',
    '수프로bb':             '수플로 bb',
    '수프로mm':             '수플로 mm',

    # 부아뜨 샤포
    '샤포백':               '부아뜨 샤포',
    '부아뜨샤포':           '부아뜨 샤포',

    # 삭 플라
    '삭플라':               '삭 플라',

    # 쁘띠뜨 계열
    '쁘띠팔레':             '쁘띠뜨 팔레',
    '쁘띠노에':             '쁘띠뜨 노에',
    '쁘띠말':               '쁘띠뜨 말',

    # 그랑 팔레
    '그랑팔레':             '그랑 팔레',
    '그랑팔래':             '그랑 팔레',

    # ── 지갑 ──────────────────────────────────────

    # 에피 유사 표기
    '에삐':                 '에피',
    '에삐가죽':             '에피',

    # 섀도우 유사 표기
    '새도우':               '섀도우',

    # 앙프렝뜨 추가
    '앙프랭뜨':             '앙프렝뜨',

    # 오거나이저
    '오거나이져':           '오거나이저',

    # 미디엄 컴팩트
    '미디엄컴팩트월릿':     '컴팩트 월릿',
    '미디엄컴팩트':         '컴팩트 월릿',

    # 지피 월릿
    '지피월릿':             '지피 월릿',
    '지피월렛':             '지피 월릿',

    # 슬렌더 월릿
    '슬렌더월릿':           '슬렌더 월릿',
    '슬렌더월렛':           '슬렌더 월릿',

    # 포켓 오거나이저
    '포켓오거나이저':       '포켓 오거나이저',

    # 멀티플 월릿
    '멀티장지갑':           '멀티플',
    '멀티월렛':             '멀티플 월렛',
    '멀티월릿':             '멀티플 월릿',
    '멀티플윌릿':           '멀티플 월릿',     # ← 신규
    '멀티플윌렛':           '멀티플 월릿',     # ← 신규

    # 브라짜
    '브라자':               '브라짜',

    # 빅토린
    '빅토렌':               '빅토린',
    '빅토리니':             '빅토린',

    # 클레망스
    '클레망':               '클레망스',
    '클레멍스':             '클레망스',

    # 에밀리
    '에밀리월릿':           '에밀리 월릿',
    '에밀리월렛':           '에밀리 월릿',

    # 사라
    '사라월렛':             '사라 월렛',
    '사라월릿':             '사라 월릿',

    # 리사 (신규)
    '리사월릿':             '리사 월릿',
    '리사월렛':             '리사 월릿',

    # 트위스트
    '트위스트월릿':         '트위스트 에피 월릿',
    '트위스트월렛':         '트위스트 에피 월릿',

    # 도핀 컴팩트
    '도핀컴팩트':           '도핀 컴팩트 월릿',

    # 가스파
    '가스파월릿':           '가스파 월릿',
    '가스파월렛':           '가스파 월릿',

    # 에피 프렌치 퍼스 (신규)
    '프렌치퍼스':           '에피 프렌치 퍼스',
    '프렌치 퍼스':          '에피 프렌치 퍼스',
}

_NORMALIZE_MAP.update({
    # ────────────────────────────────────────────────────────────
    # 1. 띄어쓰기 / 붙여쓰기 보정
    # ────────────────────────────────────────────────────────────
    '포켓오거나이저': '포켓 오거나이저',
    '포켓오거나이져': '포켓 오거나이저',
    '멀티플월렛': '멀티플 월렛',
    '멀티플월릿': '멀티플 월렛',
    '슬렌더월릿': '슬렌더 월릿',
    '슬렌더월렛': '슬렌더 월릿',
    '브라짜월릿': '브라짜 월릿',
    '브라짜월렛': '브라짜 월릿',
    '빅토린월렛': '빅토린 월렛',
    '빅토린월릿': '빅토린 월렛',
    '클레망스월릿': '클레망스 월릿',
    '클레망스월렛': '클레망스 월릿',
    '로잘리동전지갑': '로잘리 동전 지갑',
    '지피코인퍼스': '지피 코인 퍼스',
    '키파우치동전지갑': '키 파우치 동전 지갑',
    '엔벨로프카드홀더': '엔벨로프 비즈니스 카드 홀더',
    '패스포트커버': '패스포트 커버',
    '여권커버': '패스포트 커버',
    '에어로그램오거나이저': '에어로그램 포켓 오거나이저',
    '트위스트월릿': '트위스트 에피 월릿',

    # ────────────────────────────────────────────────────────────
    # 2. 소재/시리즈명 축약 및 오기
    # ────────────────────────────────────────────────────────────
    '모노그램이클립스': '모노그램 이클립스',
    '이클립스': '모노그램 이클립스',
    '다미에그래파이트': '다미에 그래파이트',
    '다미에아쥬르': '다미에 아주르',
    '타이가블랙': '타이가 블랙',
    '에피블랙': '에피 블랙',
    '앙프렝뜨블랙': '앙프렝뜨 블랙',
    '엠보스가죽': '엠보스 가죽',

    # ────────────────────────────────────────────────────────────
    # 3. 미분류 샘플에서 발견된 빈번한 오표기
    # ────────────────────────────────────────────────────────────
    '프렌치퍼스': '에피 프렌치 퍼스',
    '프렌치 퍼스': '에피 프렌치 퍼스',
    '리사월릿': '리사 월릿',
    '리사월렛': '리사 월릿',
    '에밀리월릿': '에밀리 월릿',
    '에밀리월렛': '에밀리 월릿',
    '사라월렛': '사라 월렛',
    '사라월릿': '사라 월렛',
    '조에중지갑': '조에 중지갑',
    '마르코월릿': '마르코 월릿',
    '가스파월릿': '가스파 월릿',
    '팡스월릿': '팡스 월릿',
    '도핀컴팩트': '도핀 컴팩트 월릿',
    '카퓌신컴팩트': '카퓌신 토뤼옹 컴팩트 월릿',

    # ────────────────────────────────────────────────────────────
    # 4. 영문/한글 혼용 표준화
    # ────────────────────────────────────────────────────────────
    'wallet': '월렛',
    'pocket organizer': '포켓 오거나이저',
    'card holder': '카드 홀더',
    'coin purse': '코인 퍼스',
    'key pouch': '키 파우치',
    'passport cover': '패스포트 커버',

    # ────────────────────────────────────────────────────────────
    # 5. 기존에 추가했던 항목 유지
    # ────────────────────────────────────────────────────────────
    '오거나이져': '오거나이저',
    '에삐': '에피',
    '새도우': '섀도우',
    '앙프랭뜨': '앙프렝뜨',
})
# ──────────────────────────────────────────────────────────────────────────────
# 
# ──────────────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────────────
#  유틸
# ──────────────────────────────────────────────────────────────────────────────
def load_master() -> dict:
    if os.path.exists(MASTER_FILE):
        with open(MASTER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def normalize(text: str) -> str:
    # ★ 순서: lower() → NORMALIZE_MAP → 특수문자 제거 (특수문자 제거 전에 매핑해야 안전)
    text = text.lower()
    for wrong, right in _NORMALIZE_MAP.items():
        text = text.replace(wrong, right)
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def normalize_compact(text: str) -> str:
    return re.sub(r'[^\w]', '', text.lower())


def remove_brands(tokens: set) -> set:
    return {
        t for t in tokens
        if t not in BRAND_NAMES
        and t not in _NOISE_WORDS
        and len(t) > 1
        and not t.isdigit()
    }



def infer_category(full: str) -> str:
    """app.py에서 category를 못 받았을 때만 사용하는 최소 fallback."""
    if any(kw in full for kw in ['가방', 'bag', '토트', '숄더백', '크로스백', '핸드백', '백팩']):
        return '가방'
    if any(kw in full for kw in ['지갑', '월릿', 'wallet', '카드지갑', '장지갑', '반지갑']):
        return '지갑'
    if any(kw in full for kw in ['신발', '슈즈', 'shoes', '스니커즈']):
        return '신발'
    if any(kw in full for kw in ['자켓', '코트', '셔츠', '티셔츠', '바지', '스커트']):
        return '의류'
    if any(kw in full for kw in ['목걸이', '반지', '귀걸이', '팔찌', '쥬얼리']):
        return '쥬얼리'
    if any(kw in full for kw in ['벨트', '스카프', '모자', '선글라스']):
        return '패션악세서리'
    return ''


# ──────────────────────────────────────────────────────────────────────────────
#  Gist 통신
# ──────────────────────────────────────────────────────────────────────────────
def fetch_meta_from_gist(gist_owner: str, gist_id: str) -> dict:
    url = f'https://gist.githubusercontent.com/{gist_owner}/{gist_id}/raw/meta.json'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/8.1'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f'[Meta] 로드 실패: {e}')
    return {}


def fetch_chunk_from_gist(gist_owner: str, gist_id: str, chunk_idx: int, max_retry: int = 4):
    filename = f'chunk_{chunk_idx}.json'
    url = f'https://gist.githubusercontent.com/{gist_owner}/{gist_id}/raw/{filename}'
    print(f'[Gist] 다운로드: {url}')
    for attempt in range(max_retry):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/8.1'})
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


# ──────────────────────────────────────────────────────────────────────────────
#  AI 분류 (Groq — 2단계 fallback)
# ──────────────────────────────────────────────────────────────────────────────
def ai_classify_title(title: str, model_names: list) -> Optional[str]:
    """
    모델명을 못 찾은 가방 제목에서 번개장터 공식 모델명 추출.
    Returns: 매칭된 모델명 or None
    """
    if not GROQ_API_KEY or not model_names:
        return None

    top_models = model_names[:200]
    models_str = '\n'.join(top_models)

    prompt = (
        f'루이비통 중고 매물 제목에서 아래 공식 모델명 중 가장 유사한 것을 찾아라.\n\n'
        f'매물 제목: "{title}"\n\n'
        f'공식 모델명 목록:\n{models_str}\n\n'
        '규칙:\n'
        '1. 목록에 있는 모델명 중 하나만 정확히 출력\n'
        '2. 확실하지 않으면 없음 출력\n'
        '3. 다른 설명 없이 모델명만 출력\n\n'
        '정답:'
    )

    payload = json.dumps({
        'model':       GROQ_MODEL,
        'messages':    [{'role': 'user', 'content': prompt}],
        'max_tokens':  60,
        'temperature': 0,
    }).encode('utf-8')

    try:
        req = urllib.request.Request(
            GROQ_API_URL,
            data=payload,
            headers={
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type':  'application/json',
            },
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


# ──────────────────────────────────────────────────────────────────────────────
#  분류기
# ──────────────────────────────────────────────────────────────────────────────
class SmartClassifier:
    def __init__(self, brand_filter: str = ''):
        raw_master        = load_master()
        self.brand_filter = brand_filter.strip().lower()

        if self.brand_filter:
            self.master = {k: v for k, v in raw_master.items()
                           if self.brand_filter in k.lower()}
            print(f'[SmartClassifier] 브랜드 필터 "{self.brand_filter}": {len(self.master)}개')
        else:
            self.master = raw_master
            print(f'[SmartClassifier] 전체: {len(self.master)}개 브랜드')

        self._build_cache()
        self._bag_model_names = self._collect_bag_model_names()

    def _collect_bag_model_names(self) -> list:
        """
        model_master에서 가방 카테고리 모델명 수집.
        거래량(trade_count) 기준 내림차순 정렬 → AI 프롬프트 상위에 인기 모델 배치.
        """
        entries = []
        for brand, info in self.master.items():
            for model, m_info in info.get('models', {}).items():
                if m_info.get('category', '') == '가방':
                    trade_count = m_info.get('trade_count', 0) or 0
                    entries.append((trade_count, model))
        entries.sort(key=lambda x: x[0], reverse=True)
        return [model for _, model in entries]

    def _build_cache(self):
        self._pattern_cache   = []
        self._cat_model_cache = {}
        self._all_model_cache = []

        self._direct_patterns = [
            (re.compile(r'\b[Mm]\d{5}\b'),      '루이비통'),
            (re.compile(r'\b[Nn]\d{5}\b'),      '루이비통'),
            (re.compile(r'\b1[A-Z]{2}\d{3}\b'), '루이비통'),
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

        print(f'[Cache] 패턴 {len(self._pattern_cache)}개 / 전체 모델 {len(self._all_model_cache)}개')
        for cat, models in self._cat_model_cache.items():
            print(f'  {cat}: {len(models)}개')

    def _match_models(self, candidates, full, compact, core_tok) -> dict:
        """후보 모델 목록에서 단계별 매칭 시도."""

        # 2단계: 모델명 정확 일치
        for model, norm, comp, _, _, cat in candidates:
            if norm and (norm in full or comp in compact):
                return {'model_name': model, 'confidence': 1.0, 'category': cat}

        # 3단계: 동의어 일치
        for model, _, _, _, syns, cat in candidates:
            for _, syn_norm, syn_comp in syns:
                if syn_norm and (syn_norm in full or syn_comp in compact):
                    return {'model_name': model, 'confidence': 0.9, 'category': cat}

        # 4단계: 핵심 토큰 완전 포함
        for model, _, _, core_tokens, _, cat in candidates:
            key_tokens = {t for t in core_tokens if len(t) >= 3}
            if key_tokens and key_tokens.issubset(core_tok):
                return {'model_name': model, 'confidence': 0.85, 'category': cat}

        # 5단계: 토큰 유사도
        best_score, best_model, best_cat = 0.0, None, ''
        for model, _, _, core_tokens, _, cat in candidates:
            key_tokens = {t for t in core_tokens if len(t) >= 3}
            if not key_tokens:
                continue
            score = len(core_tok & key_tokens) / len(key_tokens)
            if score > best_score:
                best_score, best_model, best_cat = score, model, cat

        if best_score >= 0.5:
            return {'model_name': best_model, 'confidence': best_score, 'category': best_cat}

        # 6단계: 단일 핵심 키워드 (4글자 이상)
        for model, _, _, core_tokens, _, cat in candidates:
            for tok in core_tokens:
                if len(tok) >= 4 and tok in full:
                    return {'model_name': model, 'confidence': 0.7, 'category': cat}

        return {}

    def classify(self, title: str, content: str = '', category: str = '') -> dict:
        """
        category: app.py가 Gist에 실어 보낸 카테고리. 있으면 우선 사용.
        """
        raw      = title + ' ' + content
        full     = normalize(raw)
        compact  = normalize_compact(raw)
        tokens   = set(full.split())
        core_tok = remove_brands(tokens)

        # 0단계: 품번 직접 패턴 (normalize 전 원본에서 검색)
        for pat, brand in self._direct_patterns:
            if pat.search(raw):
                return {'model_name': f'{brand} 품번매칭', 'confidence': 0.95, 'category': category}

        # 1단계: model_master 품번 정규식
        for brand, pat in self._pattern_cache:
            if pat.search(full):
                return {'model_name': f'{brand} 품번매칭', 'confidence': 0.95, 'category': category}

        # 카테고리 결정
        resolved_cat = category if category and category not in ('미분류', '기타', '') \
                       else infer_category(full)

        # 카테고리 범위로 먼저 시도
        if resolved_cat and resolved_cat in self._cat_model_cache:
            result = self._match_models(
                self._cat_model_cache[resolved_cat],
                full, compact, core_tok,
            )
            if result:
                return result

        # 전체 모델 fallback
        result = self._match_models(
            self._all_model_cache,
            full, compact, core_tok,
        )
        if result:
            return result

        return {'model_name': '미분류', 'confidence': 0.0, 'category': resolved_cat}

    def classify_with_ai(self, title: str, content: str = '', category: str = '') -> dict:
        """
        기존 분류 실패 시 가방 카테고리에 한해 Groq AI로 재시도.
        """
        result = self.classify(title, content, category)

        if result['model_name'] == '미분류' and result.get('category') == '가방':
            ai_model = ai_classify_title(title, self._bag_model_names)
            if ai_model:
                result['model_name']    = ai_model
                result['confidence']    = 0.75
                result['ai_classified'] = True
                print(f'[AI] "{title}" → {ai_model}')

        return result


# ──────────────────────────────────────────────────────────────────────────────
#  메인
# ──────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Resell Classifier v8.1')
    parser.add_argument('--gist_id',    required=True)
    parser.add_argument('--gist_owner', required=True)
    parser.add_argument('--chunk_idx',  type=int, required=True)
    parser.add_argument('--use_ai',     action='store_true',
                        help='가방 미분류 항목에 Groq AI 분류 적용')
    args = parser.parse_args()

    print(f'=== Classifier v8.1 시작 === Gist:{args.gist_id[:8]}... / 청크:{args.chunk_idx}')
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

        if res['confidence'] >= 0.5 and res['model_name'] not in ('미분류', ''):
            results[title] = res['model_name']
            if res.get('ai_classified'):
                ai_count += 1

    out_file = f'classify_result_{args.chunk_idx}.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False)

    total   = len(items)
    matched = len(results)
    rate    = matched / total * 100 if total else 0
    print(f'✅ 완료: {matched}/{total}건 ({rate:.1f}%) / 스킵 {skipped}건 / AI분류 {ai_count}건 → {out_file}')


if __name__ == '__main__':
    main()
