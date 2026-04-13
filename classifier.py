"""
classifier.py  (v6 — Gist category 우선 + include/exclude 구조)
"""

import sys, json, time, random, re, os, argparse, urllib.request

MASTER_FILE = 'model_master.json'

BRAND_NAMES = {
    '루이비통', '샤넬', '에르메스', '구찌', '프라다', '디올',
    '보테가베네타', '보테가', '발렌시아가', '고야드', '셀린느',
    '생로랑', '미우미우', '로에베', '펜디', '버버리',
    'louis', 'vuitton', 'lv', 'chanel', 'hermes', 'gucci', 'prada', 'dior',
    'bottega', 'veneta', 'balenciaga', 'goyard', 'celine', 'saint', 'laurent',
    'miumiu', 'loewe', 'fendi', 'burberry',
}

# app.py와 동일한 include/exclude 구조
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
            '범백', 'fanny pack', '패니팩',
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
        ],
        'exclude': [
            '쇼핑백', '백참', '포장백', '선물백', '박스백',
            '지갑', '카드지갑', '동전지갑', '장지갑', '반지갑',
            '테니스', '베니스',
            '목걸이', '반지', '귀걸이', '팔찌',
            '벨트', '스카프', '모자', '선글라스',
            '키링', '키체인',
            '박스', '상자',
        ],
    },
    '지갑': {
        'include': [
            '지갑', '월렛', 'wallet', '카드지갑', '장지갑', '반지갑',
            '머니클립', '동전지갑', '코인퍼스',
            '오거나이저', 'organizer', '포켓오거나이저', 'pocket organizer',
            '브라짜', 'brazza', '빅토린', 'victorine', '클레망스', 'clemence',
            '지피', 'zippy', '슬렌더', 'slender', '멀티플', 'multiple',
            '로잘리', 'rosalie', '조에', 'zoe', '카드홀더', 'card holder',
            '엔벨로프', 'envelope', '포르트폴리오', 'portfolio',
            '키파우치', 'key pouch', '키홀더', '키케이스',
            '에삐', '에피', 'epi',
            '쉐도우', '쉬도우', 'shadow',
            '앙프렉뜨', '엠프렉뜨', 'empreinte',
            '마르코', 'marco',
            '멀티플월릿', '다마뉴',
        ],
        'exclude': [
            '백팩', '토트', '숄더백', '크로스백', '핸드백',
            '목걸이', '귀걸이', '팔찌',   # ← '반지' 제거
        ]
    },
    '신발': {
        'include': [
            '신발', '슈즈', '스니커즈', '로퍼', '부츠', '샌들', '슬리퍼',
            '힐', '플랫', 'shoes', 'sneakers', '뮬', '펌프스', '슬링백',
            '트레이너', 'trainer', '런어웨이', 'run away', '비버리힐스',
            '구두', '운동화', '나이키', 'nike', '아디다스', 'adidas',
            '단화', '런닝화', '러닝화', '조깅화',
            '에어포스', 'air force',
        ],
        'exclude': [
            '가방', '지갑',
        ]
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
            '아웃터', 'outer', '폴로', '팬츠', '슬랙스',
            '수영복', '비키니',
        ],
        'exclude': [
            '가방', '지갑', '신발', '슈즈',
        ]
    },
    '쥬얼리': {
        'include': [
            '목걸이', '반지', '귀걸이', '팔찌', '브로치', '쥬얼리', '주얼리',
            'necklace', 'ring', 'bracelet',
            '네크리스', '브레이슬릿', '나노그램', 'nanogram',
            '에센셜v', 'essential v', '아이코닉', '이어링', '이어커프',
        ],
        'exclude': [
            '체인백', '체인가방', '체인스트랩', '반지갑',
            '가방', '지갑', '신발',
        ]
    },
    '패션악세서리': {
        'include': [
            '벨트', '스카프', '머플러', '선글라스', '모자', '장갑', '넥타이',
            '포켓스퀘어', '키링', '키체인',
            '방도', 'bandeau', '비니', 'beanie', '실크스카프',
            '이니셜벨트', 'initiales', '리버시블벨트',
            '퐁뇌프', '캡', 'cap', '햇', 'hat',
            '헤어핀', '헤어밴드', '선글래스', '안경',
            '페도라', 'fedora', '타이클립', '타이',
            '우산', '골프우산',
        ],
        'exclude': [
            '파우치백', '키홀더지갑', '키케이스지갑',
            '가방', '지갑', '신발',
        ]
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
        ],
        'exclude': []
    },
}


# ──────────────────────────────────────────────────────────────
#  유틸
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


def normalize_compact(text: str) -> str:
    return re.sub(r'[^\w]', '', text.lower())


_NOISE_WORDS = {
    # 상태/조건
    '정품', '새상품', '미사용', '사용', '착용', '새제품', '중고',
    '급처', '급처분', '판매', '팝니다', '드립니다', '합니다',
    '상태', '정도', '저렴', '할인', '한정', '진품',
    # 색상 (모델명 구분에 불필요)
    '블랙', '화이트', '베이지', '브라운', '레드', '핑크', '블루', '그린',
    'black', 'white', 'beige', 'brown', 'red', 'pink', 'blue',
    # 사이즈 표현
    '미니', 'mini', '스몰', 'small', '라지', 'large',
}

def remove_brands(tokens: set) -> set:
    return {
        t for t in tokens
        if t not in BRAND_NAMES
        and t not in _NOISE_WORDS
        and len(t) > 1
        and not t.isdigit()  # 순수 숫자 제거
    }


def infer_category(full: str) -> str:
    # full을 단어 집합으로 만들어서 exclude 체크
    full_tokens = set(full.split())

    for cat, data in CATEGORY_KEYWORDS.items():
        if cat == '기타':
            continue
        includes = data.get('include', [])
        excludes = data.get('exclude', [])
        # exclude: 단어 단위로 체크 (부분문자열 오매칭 방지)
        if any(ex in full_tokens or ex in full for ex in excludes):
            continue
        if any(kw in full for kw in includes):
            return cat

    for kw in CATEGORY_KEYWORDS.get('기타', {}).get('include', []):
        if kw in full:
            return '기타'

    return ''


# ──────────────────────────────────────────────────────────────
#  Gist 통신
# ──────────────────────────────────────────────────────────────
def fetch_meta_from_gist(gist_owner: str, gist_id: str) -> dict:
    url = f'https://gist.githubusercontent.com/{gist_owner}/{gist_id}/raw/meta.json'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/6.0'})
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
            req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/6.0'})
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


# ──────────────────────────────────────────────────────────────
#  분류기
# ──────────────────────────────────────────────────────────────
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

    def _build_cache(self):
        self._pattern_cache   = []
        self._cat_model_cache = {}
        self._all_model_cache = []

        # 품번 직접 패턴
        self._direct_patterns = [
            (re.compile(r'\b[Mm]\d{5}\b'), '루이비통'),
            (re.compile(r'\b[Nn]\d{5}\b'), '루이비통'),
        ]

        # ... 기존 코드 유지

        for brand, info in self.master.items():
            for pat in info.get('patterns', []):
                try:
                    self._pattern_cache.append((brand, re.compile(pat)))
                except re.error:
                    pass  # 잘못된 패턴 skip

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

        # 0단계: 품번 직접 패턴 (M12345, N12345 형태)
        _direct_patterns = [
            (re.compile(r'\b[Mm]\d{5}\b'), '루이비통'),
            (re.compile(r'\b[Nn]\d{5}\b'), '루이비통'),
        ]
        # 0단계: 품번 직접 패턴
        for pat, brand in self._direct_patterns:
            if pat.search(raw):
                return {'model_name': f'{brand} 품번매칭', 'confidence': 0.95, 'category': category}

        # 1단계: model_master 품번 정규식
        for brand, pat in self._pattern_cache:
            if pat.search(full):
                return {'model_name': f'{brand} 품번매칭', 'confidence': 0.95, 'category': category}

        # 카테고리 결정: Gist에서 받은 것 우선, 없으면 직접 추론
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

        # 카테고리 매칭 실패 → 전체 모델 fallback
        result = self._match_models(
            self._all_model_cache,
            full, compact, core_tok,
        )
        if result:
            return result

        return {'model_name': '미분류', 'confidence': 0.0, 'category': resolved_cat}


# ──────────────────────────────────────────────────────────────
#  메인
# ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Resell Classifier v6')
    parser.add_argument('--gist_id',    required=True)
    parser.add_argument('--gist_owner', required=True)
    parser.add_argument('--chunk_idx',  type=int, required=True)
    args = parser.parse_args()

    print(f'=== Classifier v6 시작 === Gist:{args.gist_id[:8]}... / 청크:{args.chunk_idx}')

    meta          = fetch_meta_from_gist(args.gist_owner, args.gist_id)
    brand_keyword = meta.get('brand_keyword', '')
    print(f'[Meta] 브랜드 필터: "{brand_keyword}"')

    items = fetch_chunk_from_gist(args.gist_owner, args.gist_id, args.chunk_idx)
    if items is None:
        print('❌ 청크 로드 실패 → 종료')
        sys.exit(1)

    classifier = SmartClassifier(brand_filter=brand_keyword)
    results    = {}
    skipped    = 0

    for item in items:
        title = item.get('title', '').strip()
        if not title:
            skipped += 1
            continue

        # Gist에 category 필드가 있으면 그대로 사용
        category = item.get('category', '')

        res = classifier.classify(title, item.get('content', ''), category)

        if res['confidence'] >= 0.5 and res['model_name'] not in ('미분류', ''):
            results[title] = res['model_name']

    out_file = f'classify_result_{args.chunk_idx}.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False)

    total   = len(items)
    matched = len(results)
    rate    = matched / total * 100 if total else 0
    print(f'✅ 완료: {matched}/{total}건 ({rate:.1f}%) / 스킵 {skipped}건 → {out_file}')


if __name__ == '__main__':
    main()
