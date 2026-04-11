import sys, json, urllib.request, argparse, re, os
from typing import Dict, List, Optional

MASTER_FILE = 'model_master.json'
CATEGORY_KEYWORDS = {
    '가방': ['가방', '백', 'bag', '토트', '숄더', '크로스', '클러치', '파우치', '백팩', '보스턴', '버킷', '호보', '새첼', '미니백'],
    '지갑': ['지갑', '월렛', 'wallet', '카드지갑', '장지갑', '반지갑', '코인', '머니클립', '키홀더', '키케이스'],
    '신발': ['신발', '슈즈', '스니커즈', '로퍼', '부츠', '샌들', '슬리퍼', '힐', '플랫', 'shoes', 'sneakers'],
    '의류': ['자켓', '재킷', '코트', '셔츠', '티셔츠', '후드', '가디건', '스웨터', '청바지', '바지', '스커트', '원피스', '패딩', '점퍼', '블라우스'],
    '쥬얼리': ['목걸이', '반지', '귀걸이', '팔찌', '브로치', '쥬얼리', '주얼리', 'necklace', 'ring', 'bracelet', '체인'],
    '패션악세서리': ['벨트', '스카프', '머플러', '선글라스', '모자', '장갑', '넥타이', '포켓스퀘어', '브레이슬릿', '시계줄', '키링', '키체인']
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

class SmartClassifier:
    def __init__(self):
        self.master = load_master()

    def classify(self, title: str, content: str = '') -> dict:
        full = normalize(title + ' ' + content)
        # 1. 패턴
        for brand, info in self.master.items():
            for pat in info.get('patterns', []):
                if re.search(pat, full):
                    return {'category': '기타', 'model_name': f'{brand} 품번매칭', 'confidence': 0.95}
        # 2. 정확 일치
        for brand, info in self.master.items():
            for model, m_info in info.get('models', {}).items():
                if model in full:
                    return {'category': m_info.get('category', '기타'), 'model_name': model, 'confidence': 1.0}
        # 3. 동의어
        for brand, info in self.master.items():
            for model, m_info in info.get('models', {}).items():
                for syn in m_info.get('synonyms', []):
                    if syn in full:
                        return {'category': m_info.get('category', '기타'), 'model_name': model, 'confidence': 0.9}
        # 4. 유사도
        tokens = set(full.split())
        best_score = 0.0
        best_model = None
        best_cat = None
        for brand, info in self.master.items():
            for model, m_info in info.get('models', {}).items():
                model_tokens = set(normalize(model).split())
                if not model_tokens:
                    continue
                common = len(tokens & model_tokens)
                score = common / len(model_tokens)
                if score > best_score:
                    best_score = score
                    best_model = model
                    best_cat = m_info.get('category', '기타')
        if best_score >= 0.6:
            return {'category': best_cat, 'model_name': best_model, 'confidence': best_score}
        # 5. 카테고리 키워드
        for cat, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in full:
                    return {'category': cat, 'model_name': '기타', 'confidence': 0.5}
        return {'category': '미분류', 'model_name': '미분류', 'confidence': 0.0}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', required=True)
    parser.add_argument('--chunk_start', type=int, required=True)
    parser.add_argument('--chunk_end', type=int, required=True)
    args = parser.parse_args()

    url = f'{args.server}/get_items?start={args.chunk_start}&end={args.chunk_end}'
    with urllib.request.urlopen(url) as resp:
        items = json.loads(resp.read().decode())

    classifier = SmartClassifier()
    results = {}
    for item in items:
        res = classifier.classify(item['title'], item.get('content', ''))
        results[item['id']] = res['model_name'] if res['confidence'] >= 0.5 else '미분류'

    out_file = f'classify_result_{args.chunk_start}_{args.chunk_end}.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False)

if __name__ == '__main__':
    main()
