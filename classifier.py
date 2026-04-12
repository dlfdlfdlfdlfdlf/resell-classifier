"""
classifier.py  (v5 — 카테고리 우선 분류)
"""

import sys, json, time, random, re, os, argparse, urllib.request

MASTER_FILE = 'model_master.json'

BRAND_NAMES = [
    # 한글
    '루이비통', '샤넬', '에르메스', '구찌', '프라다', '디올',
    '보테가베네타', '발렌시아가', '고야드', '셀린느', '생로랑', '미우미우',
    # 영문
    'louis', 'vuitton', 'chanel', 'hermes', 'gucci', 'prada', 'dior',
    'bottega', 'veneta', 'balenciaga', 'goyard', 'celine', 'saint', 'laurent', 'miumiu',
]

CATEGORY_KEYWORDS = {
    '가방': [
        '가방', '백', 'bag', '토트', '숄더', '크로스', '클러치', '파우치', '핸드백', '백팩',
        '보스턴', '버킷', '호보', '새첼', '미니백',
        '네버풀', 'neverfull', '스피디', 'speedy', '알마', 'alma',
        '노에', 'noe', '포쉐트', 'pochette', '펠리시', 'felicie',
        '메티스', 'metis', '키폴', 'keepall', '몽테뉴', 'montaigne',
        '온더고', 'onthego', '팔레르모', 'palermo', '갈리에라', 'galliera',
        '티볼리', 'tivoli', '에바', 'eva', '토탈리', 'totally',
        '딜라이트풀', 'delightful', '튀렌느', 'turenne', '루프', 'loop',
        '도핀', 'dauphine', '클루니', 'cluny', '락미', 'lockme',
        '니스', 'nice', '삭플라', 'sac plat', '에스트렐라', 'estrela',
        '다이앤', 'diane', '팜스프링스', 'palm springs',
        '파시', 'passy', '크로아제트', 'croisette', '부시', 'buci',
        '에튀', 'etui', '토일렛', 'toiletry', '키리가미', 'kirigami',
        '파빌론', 'pavillon', '마렐', 'marelle', '뉴웨이브', 'new wave',
        '데일리파우치', 'daily pouch', '쁘띠삭', 'petit sac',
        'woc', '월릿온체인', 'wallet on chain',
        '트위스트백', '록키', 'locky', '마이락미', 'lockme',
        '버킷백', '쇼핑백', '토트백', '핸들백', '사첼백',
        '카메라백', '나노백', '미니백', '보이백', '드로우스트링백',
    ],
    '지갑': [
        '지갑', '월렛', 'wallet', '카드지갑', '장지갑', '반지갑', '코인', '머니클립',
        '키홀더', '키케이스',
        '오거나이저', 'organizer', '포켓오거나이저', 'pocket organizer',
        '브라짜', 'brazza', '빅토린', 'victorine', '클레망스', 'clemence',
        '지피', 'zippy', '슬렌더', 'slender', '멀티플', 'multiple',
        '로잘리', 'rosalie', '조에', 'zoe', '카드홀더', 'card holder',
        '엔벨로프', 'envelope', '코인퍼스', 'coin purse', '동전지갑',
        '포르트폴리오', 'portfolio', '포르트모네', '장지갑', '반지갑',
        '키파우치', 'key pouch', '더블카드홀더', '비즈니스카드홀더',
    ],
    '신발': [
        '신발', '슈즈', '스니커즈', '로퍼', '부츠', '샌들', '슬리퍼', '힐', '플랫',
        'shoes', 'sneakers',
        '트레이너', 'trainer', '런어웨이', 'run away', '비버리힐스', 'beverly hills',
        '아쿠아', '스케이트', '플랫폼', '뮬', '슬링백', '펌프스',
    ],
    '의류': [
        '자켓', '재킷', '코트', '셔츠', '티셔츠', '후드', '가디건', '스웨터',
        '청바지', '바지', '스커트', '원피스', '패딩', '점퍼', '블라우스',
        '크루넥', 'crewneck', '후드티', '맨투맨', '스웨트셔츠', 'sweatshirt',
        '블루종', 'blouson', '바시티', 'varsity', '윈드브레이커', 'windbreaker',
        '플리스', 'fleece', '니트', 'knit', '반팔', '긴팔', '풀오버', 'pullover',
        '인따르시아', 'intarsia', '자카드', 'jacquard', '데그라데', 'degrade',
        '트레이닝', '저지', '조거', '레깅스', '드레스', '점프수트',
    ],
    '쥬얼리': [
        '목걸이', '반지', '귀걸이', '팔찌', '브로치', '쥬얼리', '주얼리',
        'necklace', 'ring', 'bracelet', '체인',
        '네크리스', '브레이슬릿', '나노그램', 'nanogram', '에센셜v', 'essential v',
        '아이코닉', 'iconic', '버질아블로', '이어링', '귀걸이', '이어커프',
        '골드메탈', '실버메탈', '체인링크',
    ],
    '패션악세서리': [
        '벨트', '스카프', '머플러', '선글라스', '모자', '장갑', '넥타이',
        '포켓스퀘어', '키링', '키체인',
        '방도', 'bandeau', '비니', 'beanie', '실크스카프', 'silk scarf',
        '이니셜벨트', 'initiales', '리버시블벨트', 'reversible belt',
        '퐁뇌프', 'pont neuf', '캡', 'cap', '햇', 'hat',
        '선글래스', '안경', '헤어밴드', '헤어핀', '헤어악세서리',
        '키홀더', '키케이스', '키링', '파우치',
    ],
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


def normalize_compact(text: str) -> str:
    return re.sub(r'[^\w]', '', text.lower())


def remove_brands(tokens: set) -> set:
    return {t for t in tokens if t not in BRAND_NAMES and len(t) > 1}


def infer_category(full: str) -> str:
    """키워드 기반 카테고리 추론"""
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw in full:
                return cat
    return ''


def fetch_meta_from_gist(gist_owner: str, gist_id: str) -> dict:
    url = f'https://gist.githubusercontent.com/{gist_owner}/{gist_id}/raw/meta.json'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f'[Meta] 로드 실패: {e}')
    return {}


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

    def _build_cache(self):
        self._pattern_cache = []
        self._model_cache   = []
        # 카테고리별 모델 캐시
        self._cat_model_cache = {}

        for brand, info in self.master.items():
            for pat in info.get('patterns', []):
                self._pattern_cache.append((brand, pat))

            for model, m_info in info.get('models', {}).items():
                norm        = normalize(model)
                compact     = normalize_compact(model)
                core_tokens = remove_brands(set(norm.split()))
                category    = m_info.get('category', '')

                syns = []
                for s in m_info.get('synonyms', []):
                    syns.append((s, normalize(s), normalize_compact(s)))

                entry = (model, norm, compact, core_tokens, syns, category)
                self._model_cache.append(entry)

                # 카테고리별 분류
                if category:
                    if category not in self._cat_model_cache:
                        self._cat_model_cache[category] = []
                    self._cat_model_cache[category].append(entry)

        print(f'[Cache] 패턴 {len(self._pattern_cache)}개 / 모델 {len(self._model_cache)}개')
        for cat, models in self._cat_model_cache.items():
            print(f'  {cat}: {len(models)}개')

    def _match_models(self, candidates, full, compact, tokens, core_tok) -> dict:
        """후보 모델 목록에서 매칭 시도"""

        # 2단계: 모델명 정확 일치
        for model, norm, comp, _, _, cat in candidates:
            if norm in full or comp in compact:
                return {'model_name': model, 'confidence': 1.0, 'category': cat}

        # 3단계: 동의어 일치
        for model, _, _, _, syns, cat in candidates:
            for syn_orig, syn_norm, syn_comp in syns:
                if syn_norm and (syn_norm in full or syn_comp in compact):
                    return {'model_name': model, 'confidence': 0.9, 'category': cat}

        # 4단계: 핵심 토큰 완전 포함
        for model, _, _, core_tokens, _, cat in candidates:
            key_tokens = {t for t in core_tokens if len(t) >= 3}
            if not key_tokens:
                continue
            if key_tokens.issubset(core_tok):
                return {'model_name': model, 'confidence': 0.85, 'category': cat}

        # 5단계: 토큰 유사도
        best_score, best_model, best_cat = 0.0, None, ''
        for model, _, _, core_tokens, _, cat in candidates:
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
                best_cat   = cat

        if best_score >= 0.5:
            return {'model_name': best_model, 'confidence': best_score, 'category': best_cat}

        # 6단계: 단일 핵심 키워드 (4글자 이상)
        for model, _, _, core_tokens, _, cat in candidates:
            for tok in core_tokens:
                if len(tok) >= 4 and tok in full:
                    return {'model_name': model, 'confidence': 0.7, 'category': cat}

        return {}

    def classify(self, title: str, content: str = '') -> dict:
        raw      = title + ' ' + content
        full     = normalize(raw)
        compact  = normalize_compact(raw)
        tokens   = set(full.split())
        core_tok = remove_brands(tokens)

        # 1단계: 품번 정규식
        for brand, pat in self._pattern_cache:
            if re.search(pat, full):
                return {'model_name': f'{brand} 품번매칭', 'confidence': 0.95}

        # 0단계: 카테고리 추론
        inferred_cat = infer_category(full)

        # 카테고리 맞는 모델 먼저 시도
        if inferred_cat and inferred_cat in self._cat_model_cache:
            result = self._match_models(
                self._cat_model_cache[inferred_cat],
                full, compact, tokens, core_tok
            )
            if result:
                return result

        # 카테고리 매칭 실패 시 전체 모델에서 시도
        result = self._match_models(
            self._model_cache, full, compact, tokens, core_tok
        )
        if result:
            return result

        return {'model_name': '미분류', 'confidence': 0.0}


def fetch_chunk_from_gist(gist_owner: str, gist_id: str, chunk_idx: int, max_retry: int = 4):
    filename = f'chunk_{chunk_idx}.json'
    url = f'https://gist.githubusercontent.com/{gist_owner}/{gist_id}/raw/{filename}'
    print(f'[Gist] 다운로드: {url}')
    for attempt in range(max_retry):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'resell-classifier/5.0'})
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
    parser = argparse.ArgumentParser(description='Resell Classifier v5')
    parser.add_argument('--gist_id',    required=True)
    parser.add_argument('--gist_owner', required=True)
    parser.add_argument('--chunk_idx',  type=int, required=True)
    args = parser.parse_args()

    print(f'=== Classifier v5 시작 === Gist:{args.gist_id[:8]}... / 청크:{args.chunk_idx}')

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
