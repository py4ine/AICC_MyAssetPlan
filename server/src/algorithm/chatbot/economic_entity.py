import re
import pytz

import nltk
from nltk import word_tokenize, pos_tag, ne_chunk

import spacy
from konlpy.tag import Okt, Kkma
from spacy.tokens import Span
from pykospacing import Spacing
from soynlp.normalizer import repeat_normalize

okt = Okt()
kkma = Kkma()
spacing = Spacing()
kst = pytz.timezone('Asia/Seoul')


def extract_finance_entities(text):
    patterns = {
        "지출": r"지출|소비|쓴|사용|결제|카드",
        "소득": r"수입|소득|월급|급여",
        "BUDGET": r"예산",
        "LOAN": r"대출",
        "저축": r"적금|예금|저축",
        "입출금": r"입출금|입금|출금|이체|송금|인출|납부|입금내역",
        "ASSET" : r"보유|자산|재정|재무|자본|재산|잔고",
        "STOCK" : r"주식|삼성|삼전|애플|코인|비트코인|samsung|apple|coin|bitcoin",
        "buy" : r"구매|구입|매입|매수|투자|\b산\b",
        "sell" : r"판매|매도|\b판\b|처분",
        "ALL": r"가계부|가계|금전",
    }
    patterns2 = {
        "stats" : r"비교|통계|보고|정리|분석|현황",  # 내역+합계
        "simple" : r"내역|상황|항목|목록|기록|출처|조회|정보|사항|이력|내용",  # 내역
        "sum" : r"합계|총액|잔액|잔고|총합|누적|합산|총계|전체금액|최종금액",  # 합계
        "average" : r"평균",  # 평균
        "date" : r"언제",  # 날짜
        "sort" : r"가장|큰|작은|제일|많이|적게|높은|낮은|순위|순서|자주|반복|빈번|주요|적은|많은",  # 정렬
    }

    # 패턴에 맞는 주요 키워드 추출 함수
    def extract_main_keyword(text, pattern):
        match = re.search(pattern, text)
        if match:
            return match.group(0)
        return None

    # 텍스트에서 조사를 제거하는 함수
    def clean_text(text):
        cleaned_text = re.sub(r'(과|와|의|가|이|을|를|은|는|에서|으로|고|까지|부터|도|만|조차|뿐|에|와|에서|로)$', '', text)
        return cleaned_text

    # 사용자 정의 spaCy 파이프라인 컴포넌트
    @spacy.Language.component("custom_finance_entity_adder")
    def custom_finance_entity_adder(doc):
        ents = []
        seen_tokens = set()

        for token in doc:
            text_cleaned = clean_text(token.text)
            # patterns1 검사
            for label, pattern in patterns.items():
                main_keyword = extract_main_keyword(text_cleaned, pattern)
                if main_keyword and token.i not in seen_tokens:
                    ent = Span(doc, token.i, token.i + 1, label=f"{label}_pattern1")
                    ent._.set("cleaned_text", text_cleaned)
                    ents.append(ent)
                    seen_tokens.add(token.i)
                    break

            for label, pattern in patterns2.items():
                main_keyword = extract_main_keyword(text_cleaned, pattern)
                if main_keyword and token.i not in seen_tokens:
                    ent = Span(doc, token.i, token.i + 1, label=f"{label}_pattern2")
                    ent._.set("cleaned_text", text_cleaned)
                    ents.append(ent)
                    seen_tokens.add(token.i)
                    
        doc.ents = ents
        return doc
    
    # spaCy 모델 로드
    nlp = spacy.load("ko_core_news_sm")
    Span.set_extension("cleaned_text", default=None, force=True)

    # custom_finance_entity_adder가 이미 파이프라인에 존재하면 제거
    if "custom_finance_entity_adder" in nlp.pipe_names:
        nlp.remove_pipe("custom_finance_entity_adder")
    nlp.add_pipe("custom_finance_entity_adder", after="ner")
    doc = nlp(text)
    
    # 엔티티 결과 수집
    entities = {f"pattern{i}": [(ent._.get("cleaned_text"), ent.label_.replace(f"_pattern{i}", "")) 
                             for ent in doc.ents if f"_pattern{i}" in ent.label_] for i in (1, 2)}
    if not entities['pattern2']:
        entities['pattern2'].append(('기본값', 'simple'))

    return entities


from konlpy.tag import Komoran
import re
import spacy
from spacy.tokens import Span

# Komoran 형태소 분석기 사용
komoran = Komoran()

def extract_stock_entities(text):
    """주어진 텍스트에서 주식 관련 엔티티를 추출하는 통합 함수입니다."""
    
    # 주식 관련 패턴 정의
    patterns1 = {
        "주가": r"주가|주식|종가|가격|값",
        "증시": r"증시|뉴스",
        "예상": r"예상|예측|전망|앞으로",
        "삼성전자": r"삼성전자|삼성|삼전|samsung",
        "애플": r"애플|apple",
        "비트코인": r"비트코인|bitcoin|비트|코인|coin",
        "PER": r"PER|per|주가수익비율|Price Earning Ratio",
        "PBR": r"PBR|pbr|주가순자산비율|Price Book-value Ratio",
        "ROE": r"ROE|roe|자기자본이익률|Return on Equity",
        "MC": r"MC|mc|시가총액|총액|시총|Market Cap",
        "경제지표":r"경제지표|국내총생산|GDP|기준금리|IR|수입물가지수|IPI|생산자물가지수|PPI|소비자물가지수|CPI|외환보유액"
    }

    # 패턴 통합
    combined_patterns = {**patterns1}

    # 텍스트에서 패턴에 맞는 주요 키워드 추출
    def extract_main_keyword(text, pattern):
        match = re.search(pattern, text)
        if match:
            return match.group(0)  # 매칭된 주요 키워드 반환
        return None  # 매칭되지 않으면 None 반환

    def clean_text(text):
        # Komoran으로 형태소 분석을 수행
        token_pos = komoran.pos(text)
        cleaned_tokens = [word for word, pos in token_pos if not pos.startswith('J')]
        cleaned_text = ''.join(cleaned_tokens)

        return cleaned_text

    # 사용자 정의 spaCy 파이프라인 컴포넌트
    @spacy.Language.component("custom_stock_entity_adder")
    def custom_stock_entity_adder(doc):
        new_ents = []

        for token in doc:
            # 형태소 분석을 통해 명사와 동사/형용사 추출
            token_pos = komoran.pos(token.text)
            
            # 품사별로 나눠서 명사 및 동사 추출
            noun_phrase = ''.join([word for word, tag in token_pos if tag in ['NNG', 'NNP', 'SL']])  # 명사
            verb_phrase = ''.join([word for word, tag in token_pos if tag in ['VV', 'VA']])  # 동사/형용사

            # 형태소 분석 결과와 원래 텍스트 보정
            noun_phrase_cleaned = clean_text(noun_phrase)  # 형태소 분석된 명사에서 조사를 제거
            original_text_cleaned = clean_text(token.text)  # 원래 텍스트에서 조사를 제거

            found = False  # 해당 단어가 패턴과 매칭되는지 확인
            for label, pattern in combined_patterns.items():
                if noun_phrase_cleaned and len(noun_phrase_cleaned) > 1:  # 명사가 있으면
                    main_keyword = extract_main_keyword(noun_phrase_cleaned, pattern)
                    if main_keyword:
                        found = True
                        new_ent = Span(doc, token.i, token.i + 1, label=label)
                        new_ent._.set("cleaned_text", noun_phrase_cleaned)
                        new_ents.append(new_ent)
                        break

                if verb_phrase:  # 동사/형용사가 있으면
                    main_keyword = extract_main_keyword(verb_phrase, pattern)
                    if main_keyword:
                        found = True
                        new_ent = Span(doc, token.i, token.i + 1, label=label)
                        new_ent._.set("cleaned_text", verb_phrase)
                        new_ents.append(new_ent)
                        break

            if not found:
                # 원래 텍스트에 기반해 패턴 매칭 시도
                main_keyword = extract_main_keyword(original_text_cleaned, pattern)
                if main_keyword:
                    new_ent = Span(doc, token.i, token.i + 1, label=label)
                    new_ent._.set("cleaned_text", original_text_cleaned)
                    new_ents.append(new_ent)
                    break

        # 최종 엔티티 설정
        doc.ents = new_ents

        return doc

    # spaCy 모델 로드
    nlp = spacy.load("ko_core_news_sm")

    # 확장 속성 등록
    Span.set_extension("cleaned_text", default=None, force=True)

    # 기존 파이프라인에서 custom_stock_entity_adder 제거
    if "custom_stock_entity_adder" in nlp.pipe_names:
        nlp.remove_pipe("custom_stock_entity_adder")

    # custom_stock_entity_adder 추가
    nlp.add_pipe("custom_stock_entity_adder", after="ner")

    # 텍스트 처리
    doc = nlp(text)

    # 결과 출력
    entities = [ent._.get("cleaned_text") for ent in doc.ents] + [ent.label_ for ent in doc.ents]
    return list(set(entities))
