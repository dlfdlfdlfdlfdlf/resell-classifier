import re
import json
import os
from typing import Dict, List, Optional

# ========== 설정 ==========
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

def save_master(master: dict):
    with open(MASTER_FILE, 'w', encoding='utf-8') as f:
        json.dump(master, f, ensure_ascii=False, indent=2)

def normalize(text: str) -> str:
    """소문자, 특수문자 제거, 공백 정리"""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

class SmartClassifier:
    def __init__(self):
        self.master = load_master()

    def classify(self, title: str, content: str = '') -> dict:
        """
        반환: {
            'category': str,
            'model_name': str,
            'confidence': float,
            'method': str   # 'pattern', 'exact', 'synonym', 'similarity', 'category', 'fail'
        }
        """
        full = normalize(title + ' ' + content)
        
        # 1. 품번 패턴 매칭
        res = self._match_pattern(full)
        if res:
            return res
        
        # 2. 정확한 모델명 매칭
        res = self._match_exact(full)
        if res:
            return res
        
        # 3. 동의어 매칭
        res = self._match_synonym(full)
        if res:
            return res
        
        # 4. 유사도 매칭 (BM25 간소화)
        res = self._match_similarity(full)
        if res:
            return res
        
        # 5. 카테고리 키워드 매칭 (최후의 보루)
        for cat, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in full:
                    return {'category': cat, 'model_name': '기타', 'confidence': 0.5, 'method': 'category'}
        
        return {'category': '미분류', 'model_name': '미분류', 'confidence': 0.0, 'method': 'fail'}

    def _match_pattern(self, text: str) -> Optional[dict]:
        for brand, info in self.master.items():
            for pattern in info.get('patterns', []):
                if re.search(pattern, text):
                    return {
                        'category': '기타',
                        'model_name': f'{brand} 품번매칭',
                        'confidence': 0.95,
                        'method': 'pattern'
                    }
        return None

    def _match_exact(self, text: str) -> Optional[dict]:
        for brand, info in self.master.items():
            for model, model_info in info.get('models', {}).items():
                if model in text:
                    return {
                        'category': model_info.get('category', '기타'),
                        'model_name': model,
                        'confidence': 1.0,
                        'method': 'exact'
                    }
        return None

    def _match_synonym(self, text: str) -> Optional[dict]:
        for brand, info in self.master.items():
            for model, model_info in info.get('models', {}).items():
                for syn in model_info.get('synonyms', []):
                    if syn in text:
                        return {
                            'category': model_info.get('category', '기타'),
                            'model_name': model,
                            'confidence': 0.9,
                            'method': 'synonym'
                        }
        return None

    def _match_similarity(self, text: str) -> Optional[dict]:
        tokens = set(text.split())
        best_model = None
        best_cat = None
        best_score = 0.0
        for brand, info in self.master.items():
            for model, model_info in info.get('models', {}).items():
                model_tokens = set(normalize(model).split())
                if not model_tokens:
                    continue
                common = len(tokens & model_tokens)
                score = common / len(model_tokens)
                if score > best_score:
                    best_score = score
                    best_model = model
                    best_cat = model_info.get('category', '기타')
        if best_score >= 0.6:
            return {
                'category': best_cat,
                'model_name': best_model,
                'confidence': best_score,
                'method': 'similarity'
            }
        return None

# ========== 마스터 사전 생성 도우미 (번개장터 모델 리스트로부터) ==========
def build_master_from_bunjang_models(models: list, brand_name: str) -> dict:
    """
    models: 번개장터 모델 리스트 (get_bunjang_models 결과)
    brand_name: 브랜드명 (예: '루이비통')
    """
    master = {}
    master[brand_name] = {'models': {}, 'patterns': []}
    for m in models:
        name_kor = m.get('nameKor', '')
        name_eng = m.get('nameEng', '')
        category = m.get('categoryName', '기타')
        if not name_kor:
            continue
        master[brand_name]['models'][name_kor] = {
            'category': category,
            'synonyms': []
        }
        # 영문명 동의어 추가
        if name_eng:
            master[brand_name]['models'][name_kor]['synonyms'].append(name_eng.lower())
        # 품번 패턴 추출 (숫자/영문 조합 4자 이상)
        pattern = re.findall(r'[A-Z0-9]{4,}', name_kor + ' ' + name_eng)
        for p in pattern:
            if p not in master[brand_name]['patterns']:
                master[brand_name]['patterns'].append(p)
    return master

# 전역 분류기 인스턴스 (app.py에서 사용)
classifier = SmartClassifier()