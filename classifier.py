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
    '팔레모':       '팔레르모',

    # 에튀 보야주 (구체적인 것 먼저, '에뮬' 단독은 오치환 위험으로 제거)
    '에튀보야주':   '에튀 보야주',
    '에뮬보야쥴':   '에튀 보야주',
    '에뮬보야주':   '에튀 보야주',
    '에뮬mm':       '에튀 보야주 mm',
    '에뮬gm':       '에튀 보야주 gm',
    '에뮬pm':       '에튀 보야주 pm',

    # 앙프렝뜨
    '앙프렉뜨':     '앙프렝뜨',
    '엠프렉뜨':     '앙프렝뜨',
    '앙프레뜨':     '앙프렝뜨',
    '앙프렁뜨':     '앙프렝뜨',

    # 트루빌
    '투루블':       '트루빌',
    '트루블':       '트루빌',

    # 룩스부리
    '뤽부리':       '룩스부리',
    '룩부리':       '룩스부리',
    '록스부리':     '룩스부리',
    '럭스부리':     '룩스부리',

    # 도핀
    '도피체인':     '도핀 체인',
    '도피네':       '도핀',

    # 일립스
    '엘립스':       '일립스',
    '엘리프스':     '일립스',

    # 보야주
    '보야쥴':       '보야주',
    '보야지':       '보야주',

    # 마들렌
    '마들렝':       '마들렌',
    '마들린':       '마들렌',

    # 앗치
    '아치백':       '앗치',
    '앗치백':       '앗치',

    # 포쉐트
    '포세트':       '포쉐트',
    '포쉐악':       '포쉐트 악세수아',
    '포쉐악세수아': '포쉐트 악세수아',

    # 카퓌신
    '카푸신':       '카퓌신',
    '카피쉰':       '카퓌신',
    '카퓌쉰':       '카퓌신',
    '카피신':       '카퓌신',

    # 소뮈르
    '소뮤르':       '소뮈르',

    # 수플로 + size 변형
    '수프로':       '수플로',
    '수프로bb':     '수플로 bb',
    '수프로mm':     '수플로 mm',

    # 부아뜨 샤포
    '샤포백':       '부아뜨 샤포',
    '부아뜨샤포':   '부아뜨 샤포',

    # 삭 플라
    '삭플라':       '삭 플라',

    # 쁘띠뜨 계열
    '쁘띠팔레':     '쁘띠뜨 팔레',
    '쁘띠노에':     '쁘띠뜨 노에',
    '쁘띠말':       '쁘띠뜨 말',

    # 그랑 팔레
    '그랑팔레':     '그랑 팔레',
    '그랑팔래':     '그랑 팔레',
}

# ──────────────────────────────────────────────────────────────────────────────
#  카테고리 키워드 (0단계 분류 전용)
# ──────────────────────────────────────────────────────────────────────────────
CATEGORY_KEYWORDS = {
    '가방': {
        'include': [
            '가방', 'bag', '토트', '숄더', '크로스', '핸드백', '백팩',
            '보스턴', '버킷', '호보', '새첼', '미니백', '클러치', '파우치',
            '네버풀', 'neverfull', '스피디', 'speedy', '알마', 'alma',
            '노에', 'noe', '포쉐트', 'pochette', '펠리시', 'felicie',
            '메티스', 'metis', '키폴', 'keepall', '몽테뉴', 'montaigne',
            '온더고', 'onthego', '팔레르모', 'palermo', '팔레모',
            '갈리에라', 'galliera', '티볼리', 'tivoli',
            '에바', 'eva', '토탈리', 'totally', '딜라이트풀', 'delightful',
            '튀렌느', 'turenne', '루프', 'loop',
            '도핀', 'dauphine', '클루니', 'cluny', '락미', 'lockme',
            '락미에버', 'lockme ever',
            '니스', 'nice', '삭플라', 'sac plat', '에스트렐라', 'estrela',
            '다이앤', 'diane', '팜스프링스', 'palm springs',
            '파시', 'passy', '크로아제트', 'croisette', '부시', 'buci',
            '에튀', 'etui', '토일렛', 'toiletry', '키리가미', 'kirigami',
            '파빌론', 'pavillon', '마렐', 'marelle', '뉴웨이브', 'new wave',
            'woc', '월릿온체인', 'wallet on chain',
            '토트백', '토드백', '숄더백', '크로스백', '핸들백', '사첼백',
            '버킷백', '보이백', '드로우스트링백', '카메라백', '나노백',
            '범백', 'fanny pack', '패니팩', '힙색',
            '서류가방', '브리프케이스', 'briefcase',
            '메신저백', 'messenger',
            '올인', 'all in',
            '쿠상', 'coussin',
            '캐리올', 'carryall',
            '마하나', 'mahana',
            '시라쿠사', 'siracusa',
            '스폰티니', 'spontini',
            '아포제', 'apogee',
            '시스티나', 'sistina',
            '에코백',
            '도빌백', '도빌',
            '룩스부리', '룩부리',
            '까르쥬엘', '카루셀',
            '멀티백', '대형백', '여성백', '남성백',
            '앗치', '독키트', '깐느', '바방', '카퓌신',
            '팔라스', '락킷', '소뮈르',
            '보야주', '리드', '마레', '그랑팔레', '쁘띠팔레', '볼타',
            '벨뷰', '네오', '루핑', '체리우드',
            '퐁네프', '미라보', '수할리', 'go-14',
            '베이비백', '베니티',
        ],
        'exclude': [
            '쇼핑백', '백참', '포장백', '선물백', '박스백',
            '지갑', '카드지갑', '동전지갑', '장지갑', '반지갑',
            '테니스', '베니스',
            '목걸이', '반지', '귀걸이', '팔찌',
            '벨트', '스카프', '모자', '선글라스',
            '키링', '키체인',
            '박스', '상자',
            '종이가방',
            '이어폰', '무선이어폰', '블루투스이어폰',
            '스피커',
            '향수',
            '시계',
            '케이스',
        ],
    },
    '지갑': {
        'include': [
            '지갑', '월릿', 'wallet', '카드지갑', '장지갑', '반지갑',
            '머니클립', '동전지갑', '코인퍼스',
            '오거나이저', 'organizer', '포켓오거나이저', 'pocket organizer',
            '브라짜', 'brazza', '빅토린', 'victorine', '클레망스', 'clemence',
            '지피', 'zippy', '슬렌더', 'slender', '멀티플', 'multiple',
            '로잘리', 'rosalie', '조에', 'zoe', '카드홀더', 'card holder',
            '엔벨로프', 'envelope', '포르트폴리오', 'portfolio',
            '키파우치', 'key pouch', '키홀더', '키케이스',
            '에피', '쉐도우', '섀도우', 'shadow',
            '앙프렉뜨', '엠프렉뜨', 'empreinte',
            '마르코', 'marco',
            '멀티플월릿', '다마뉴',
            '컴팩트월릿', '트래블월릿', '포켓월릿',
        ],
        'exclude': [
            '백팩', '토트', '숄더백', '크로스백', '핸드백',
            '목걸이', '귀걸이', '팔찌',
        ],
    },
    '신발': {
        'include': [
            '신발', '슈즈', '스니커즈', '로퍼', '부츠', '샌들', '슬리퍼',
            '힐', '플랫', 'shoes', 'sneakers', '뮬', '펌프스', '슬링백',
            '트레이너', 'trainer', '런어웨이', 'run away', '비버리힐즈',
            '구두', '운동화', '나이키', 'nike', '아디다스', 'adidas',
            '단화', '런닝화', '러닝화', '조깅화',
            '에어포스', 'air force',
            '샌달', '쪼리', '워커', '하이탑', '웨지힐', '앵클부츠',
            '부티', '모카신', '에스파드류',
        ],
        'exclude': [
            '가방', '지갑',
        ],
    },
    '의류': {
        'include': [
            '자켓', '재킷', '코트', '셔츠', '티셔츠', '후드', '가디건',
            '스웨터', '청바지', '바지', '스커트', '원피스', '패딩', '점퍼',
            '블라우스', '크루넥', 'crewneck', '후드티', '맨투맨',
            '스웨트셔츠', 'sweatshirt', '블루종', 'blouson', '바시티', 'varsity',
            '윈드브레이커', '플리스', 'fleece', '니트', 'knit',
            '반팔', '긴팔', '풀오버', '인따르시아', '자카드',
            '트레이닝', '조거', '레깅스', '드레스', '점프수트', '저지',
            '아우터', 'outer', '폴로', '팬츠', '슬랙스',
            '수영복', '비키니',
            '집업', '세트업', '셋업', '수트', '데님', '바람막이',
            '후디', '조끼', '무스탕',
        ],
        'exclude': [
            '가방', '지갑', '신발', '슈즈',
        ],
    },
    '쥬얼리': {
        'include': [
            '목걸이', '반지', '귀걸이', '팔찌', '브로치', '쥬얼리', '주얼리',
            'necklace', 'ring', 'bracelet',
            '네크리스', '브레이슬릿', '나노그램', 'nanogram',
            '에센셜v', 'essential v', '아이코닉', '이어링', '이어커프',
            '뱅글', '발찌', '펜던트', '초커', '귀찌', '피어싱', '체인목걸이',
        ],
        'exclude': [
            '체인백', '체인가방', '체인스트랩', '반지갑',
            '가방', '지갑', '신발',
        ],
    },
    '패션악세서리': {
        'include': [
            '벨트', '스카프', '머플러', '선글라스', '모자', '장갑', '넥타이',
            '포켓스퀘어', '키링', '키체인',
            '방도', 'bandeau', '비니', 'beanie', '실크스카프',
            '이니셜벨트', 'initiales', '리버시블벨트',
            '퍼플롭', '캡', 'cap', '햇', 'hat',
            '헤어핀', '헤어밴드', '선글래스', '안경',
            '페도라', 'fedora', '타이클립', '타이',
            '우산', '골프우산',
            '머리핀', '머리띠', '헤어슈슈', '양말', '스타킹',
            '목도리', '숄', '트윌리',
            '여권케이스', '밸트',
        ],
        'exclude': [
            '파우치백', '키홀더지갑', '키케이스지갑',
            '가방', '지갑', '신발',
        ],
    },
    '기타': {
        'include': [
            '쇼핑백', '쇼핑박스', '상자', '박스', '포장재', '포장박스',
            '보증서', '영수증', '케어카드',
            '자물쇠', '열쇠', '방향제', '베어브릭', '가먼트', '비즈',
            '피규어', '인형', '석고', '디퓨저',
            '향수', '텀블러', '백참', '시계', '스마트워치',
            '담요', '쿠션', '침구',
            '다이어리', '노트', '엽서', '책', '포스터',
            '젓가락', '컵', '머그컵', '접시',
            '옷걸이', '의류커버', '옷커버',
            '종이봉투', '봉투',
            '골프공', '골프티',
            '네임택', '열쇠고리', '아트북', '보존병', '캔들',
            '트럼프카드', '립밤', '핸드크림', '바디로션',
            '순금', '골드', '금장',
        ],
        'exclude': [],
    },
}

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


# exclude / include 미리 컴파일
_CATEGORY_EXCLUDES: dict = {}
_CATEGORY_INCLUDES: list = []

def _build_category_cache():
    global _CATEGORY_EXCLUDES, _CATEGORY_INCLUDES
    _CATEGORY_EXCLUDES = {
        cat: set(data.get('exclude', []))
        for cat, data in CATEGORY_KEYWORDS.items()
    }
    _CATEGORY_INCLUDES = [
        (cat, data.get('include', []))
        for cat, data in CATEGORY_KEYWORDS.items()
        if cat != '기타'
    ]

_build_category_cache()


def infer_category(full: str) -> str:
    """exclude는 단어 단위로만 체크해서 부분문자열 오매칭 방지."""
    full_tokens = set(full.split())

    for cat, includes in _CATEGORY_INCLUDES:
        excludes = _CATEGORY_EXCLUDES.get(cat, set())
        if any(ex in full_tokens for ex in excludes):
            continue
        if any(kw in full for kw in includes):
            return cat

    for kw in CATEGORY_KEYWORDS.get('기타', {}).get('include', []):
        if kw in full:
            return '기타'

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
