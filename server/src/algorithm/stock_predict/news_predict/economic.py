# 데이터 처리 및 분석 관련 라이브러리
import faiss
import numpy as np
import pandas as pd
import networkx as nx

# 웹 관련 라이브러리
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

# 자연어 처리 및 텍스트 분석 라이브러리
import nltk
from nltk.tokenize import sent_tokenize
from nltk.cluster.util import cosine_distance
from sentence_transformers import SentenceTransformer

nltk.download('punkt')

# Transformer 기반 언어 모델 관련 라이브러리
import torch
from transformers import GPT2LMHeadModel, PreTrainedTokenizerFast

# 시간 및 정규 표현식 관련 라이브러리
from datetime import datetime
import re
import time
import json

# 경고 및 로그 관리
import warnings
import logging
from transformers import logging as hf_logging
hf_logging.set_verbosity_error()
logging.getLogger("faiss").setLevel(logging.ERROR)
warnings.filterwarnings('ignore', category=FutureWarning)
logging.getLogger("transformers").setLevel(logging.ERROR)
warnings.filterwarnings('ignore', category=MarkupResemblesLocatorWarning)

# 네이버 API 클라이언트 ID와 시크릿
client_id     = "4aM0BLbwSKf5jwggWUmb"
client_secret = "VG12t6mFAJ"


def getRequestUrl(url):
  req = urllib.request.Request(url)
  req.add_header("X-Naver-Client-Id", client_id)
  req.add_header("X-Naver-Client-Secret", client_secret)
  try:
    response = urllib.request.urlopen(req)
    if response.getcode() == 200:
      return response.read().decode('utf-8')
    else:
      print(f"HTTP Error {response.getcode()}: {response.reason}")
      return None
  except Exception as e:
    print(e)
    return None

def searchNaverNews(query, display=10, start=1):
  base_url = 'https://openapi.naver.com/v1/search/news.json'
  query    = urllib.parse.quote(query)
  url      = f"{base_url}?query={query}&display={display}&start={start}&sort=date"

  response = getRequestUrl(url)
  if response is None:
    return None

  return json.loads(response)

def sentence_similarity(sent1, sent2, stopwords=None):
  if stopwords is None:
    stopwords = []

  sent1 = [word.lower() for word in sent1 if word not in stopwords]
  sent2 = [word.lower() for word in sent2 if word not in stopwords]

  all_words = list(set(sent1 + sent2))

  vector1 = [0] * len(all_words)
  vector2 = [0] * len(all_words)

  for word in sent1:
    if word in stopwords:
      continue
    vector1[all_words.index(word)] +=1

  for word in sent2:
    if word in stopwords:
      continue
    vector2[all_words  .index(word)] +=1

  return 1 - cosine_distance(vector1, vector2)

def build_similarity_matrix(sentences, stop_words):

	# 문장 간 유사도 행렬 초기화
	similarity_matrix = np.zeros((len(sentences), len(sentences)))
	
	# 모든 문장 쌍에 대해 유사도 계산
	for idx1 in range(len(sentences)):
		for idx2 in range(len(sentences)):
			# 같은 문장인 경우 계산하지 않음
			if idx1 == idx2:
				continue
				
			# 문장 간 유사도 게산하여 행렬에 할당
			similarity_matrix[idx1][idx2] = sentence_similarity(sentences[idx1], sentences[idx2], stop_words)
			
	return similarity_matrix

def textrank_summary(content,  num_sentences=3):
    # 입력 텍스트를 문장 단위로 구분
    sentences = sent_tokenize(content)

    stop_words = ['을', '를', '이', '가', '은', '는', '에', '의', '과', '와', '한', '들', '의']
    sentences = [word for word in sentences if word not in stop_words]
    
    # 문장 간 유사도 행렬 생성
    similarity_matrix = build_similarity_matrix(sentences, stop_words)
    
    # 페이지랭크 알고리즘을 사용하여 각 문장의 점수 계산
    scores = nx.pagerank(nx.from_numpy_array(similarity_matrix))
    
    # 문장을 페이지랭크 점수에 따라 내림차순으로 정렬
    ranked_sentences = sorted(((scores[i], s) for i, s in enumerate(sentences)), reverse=True)
    
    # 상위 num_sentences 만큼의 문장을 선택하여 요약 생성
    summary = ' '.join([sentence for score, sentence in ranked_sentences[:num_sentences]])
    comparison_texts = [content]
    for comp_text in comparison_texts:
        sim = sentence_similarity(summary, comp_text)
        if sim >= 0.95:
            return None
    return summary

def economic_news_search(num_days=30, display=100):
  all_filtered_news = []
  collected_data    = set()

  # 확장된 증시 관련 키워드 목록
  keywords = [
      '증시', '코스피', '코스닥', '주식', '상장', '상장폐지', '배당', '배당금', '주가', '시가총액',
      'PER', 'PBR', 'EPS', '매출', '순이익', '상승', '하락', '변동성', '투자', '매수', '매도', '공매도',
      '기관투자자', '개인투자자', 'ETF', '선물', '옵션', '지수', '거래량', '상한가', '하한가', '상승장',
      '하락장', '공시', '기업공개', 'IPO', '시장동향', '경제지표', '금리', '인플레이션', '디플레이션',
      '유동성', '재무제표', '주주총회', '배당수익률', '채권', '펀드', '헤지펀드', '알고리즘', '기술적분석',
      '기본적분석', '리스크', '포트폴리오', '다각화', '시장점유율', '신규상장', '기업실적', '경영전략',
      '재무상태', '부채비율', '유보율', '자본금', '배당정책', '주식시장', '금융시장', '경제성장', '국제금융',
      '환율', '원화', '달러', '유로', '엔화', '금', '은', '원자재', '에너지', '반도체', 'IT', '바이오',
      '헬스케어', '제약', '자동차', '건설', '부동산', '소비재', '필수소비재', '이차전지', '전기차', '친환경',
      '재생에너지', '스마트폰', '디지털', '블록체인', '암호화폐', '비트코인', '이더리움', '금융정책', '경제정책',
      '금융위기', '코로나19', '백신', '금리인상', '금리인하', '채권시장', '부동산시장', '인플레이션율',
      '디플레이션율', '경제성장률', 'GDP', '실업률', '소비자물가지수', '생산자물가지수', '수출', '수입',
      '경상수지', '자본수지', '무역수지', '금융수지', '경기순환', '거시경제', '미시경제', '금융기관', '은행',
      '증권사', '자산관리', '재테크', '부동산투자', '주식투자', '펀드투자', '채권투자', 'ETF투자', '리츠',
      '벤처캐피탈', '스타트업', '핀테크', '모바일뱅킹', '온라인증권', '로보어드바이저', '디지털자산', '가상자산',
      '스마트컨트랙트', '탈중앙화', '디파이', 'NFT', '메타버스', 'AI투자', '빅데이터', '클라우드컴퓨팅',
      'IoT', '5G', '자율주행', '친환경차', '스마트시티', '헬스케어기술', '바이오테크', '제로에너지건축',
      '그린에너지', '재생가능에너지', '탄소중립', 'ESG투자', '사회책임투자', '지속가능투자', '투자전략'
  ]

  exclude_keywords = ['기자', '?', "앵커", '투자', '운용사', '괜찮아요', 'http', '신진대사', '체질', '날씨', '기온']
  today = datetime.today()
  formatted_date = f"{today.month}월 {today.day}일" 
  # 쿼리 리스트 정의 (내부에서 고정된 쿼리 목록 사용, 증시 대표 키워드로 추가)
  queries = [
  '증시', '미국증시', '한국증시', '나스닥', '다우지수', 'S&P500', '니케이', '상해종합', 'FTSE100', 'DAX30', '항셍지수',
  '유가', '천연가스', '미국채', '유럽경제', '기술주', '헬스케어', '핀테크', 'ESG', '인공지능', '비트코인',
  '블록체인', '암호화폐', '달러', '원유', '금', '은', '구리', '철광석', '리튬', '배터리', '전기차', '테슬라',
  '애플', '마이크로소프트', '아마존', '구글', '페이스북', '메타버스', '코로나19', '백신', '반도체', '5G',
  'AI', '로봇공학', '양자 컴퓨팅', '사이버 보안', '자율주행', '클라우드컴퓨팅', '대선', '재생에너지',
  '친환경차', '삼성전자', "HBM", "BDSPN", "파운드리"
  ]
  queries_with_date = [f"{formatted_date} {query}" for query in queries]

  for query in queries_with_date:
    filtered_news = searchNaverNews(query, display=display)
    if filtered_news and 'items' in filtered_news:
      for item in filtered_news['items']:
        title = BeautifulSoup(item['title'], 'html.parser').get_text()
        description = BeautifulSoup(item['description'], 'html.parser').get_text()
        content = description

        # 제외할 키워드가 포함된 뉴스는 건너뛰기
        if any(exclude in title for exclude in exclude_keywords) or any(exclude in content for exclude in exclude_keywords):
          continue

        # 제목, 설명, 본문 중 하나라도 중복된 경우 건너뛰기
        if title in collected_data or description in collected_data or content in collected_data:
          continue

        if not '증시' in content:
          continue

        # 키워드와 겹치는 단어 수 계산
        matched_keywords = [keyword for keyword in keywords if keyword in title or keyword in content]
        if len(matched_keywords) < 3:  # 키워드가 N개 이상 겹치는 경우에만 가져옴
          continue

        link = item['link']
        news_data = {
            'title': title,
            'description': description,
            'link': link,
            'Date': datetime.strptime(item['pubDate'], '%a, %d %b %Y %H:%M:%S +0900').strftime('%Y-%m-%d'),
            'content': description,
        }

        news_data['summary'] = textrank_summary(news_data['description'])
        all_filtered_news.append(news_data)
        collected_data.update([title, description, content])

  return None if not all_filtered_news else pd.DataFrame(all_filtered_news)

def get_response(user_query_pre, top_k=3, max_new_tokens=150, try_count=False):
    today = datetime.today()
    formatted_date = f"{today.month}월 {today.day}일"

    user_query =  formatted_date + user_query_pre

    # 1. 뉴스 데이터 불러오기 및 전처리
    df = economic_news_search()  # 뉴스 데이터를 가져오는 함수
    df = df.dropna(subset=['summary'])  # 요약이 없는 데이터는 제거
    texts = df['summary'].tolist()  # 요약 부분만 리스트로 변환
    def remove_urls(text):
      url_pattern = r'https?://\S+|www\.\S+'
      return re.sub(url_pattern, '', text)

    texts = [remove_urls(text) for text in texts]
    # 2. 한국어 GPT 모델 설정
    generator_model = GPT2LMHeadModel.from_pretrained('gpt2')
    tokenizer = PreTrainedTokenizerFast.from_pretrained('gpt2')

    # padding 토큰 설정 (GPT 모델에서는 eos_token을 padding으로 사용)
    tokenizer.pad_token = tokenizer.eos_token
    generator_model.config.pad_token_id = tokenizer.eos_token_id

    # pad_token이 없는 경우, 새로운 pad_token 추가
    if tokenizer.pad_token is None:
        tokenizer.add_special_tokens({'pad_token': '[PAD]'})
        generator_model.resize_token_embeddings(len(tokenizer))

    # 3. SentenceTransformer 모델을 사용한 임베딩 모델 설정
    embedding_model = SentenceTransformer('jhgan/ko-sroberta-multitask')

    # 4. FAISS 인덱스 생성 및 추가
    document_embeddings = embedding_model.encode(texts, convert_to_tensor=False, show_progress_bar=False)
    document_embeddings = np.array(document_embeddings).astype('float32')
    dimension = document_embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(document_embeddings)

    # 5. 질의에 맞는 관련 뉴스를 검색하는 함수
    def get_relevant_summaries(query, top_k=3):
        query_embedding = embedding_model.encode([query], convert_to_tensor=False)
        query_embedding = np.array(query_embedding).astype('float32')
        distances, indices = index.search(query_embedding, top_k)
        relevant_summaries = [texts[idx] for idx in indices[0]]
        return relevant_summaries

    # 6. 무조건 CPU 장치 설정
    device = torch.device('cpu')
    generator_model.to(device)

    # 7. 답변 생성
    relevant_summaries = get_relevant_summaries(user_query, top_k)
    context = " ".join(relevant_summaries)
    prompt = f"뉴스 요약: {context}\n질문: {user_query}\n답변: "
    
    inputs = tokenizer(prompt, return_tensors='pt', padding=True).to(device)
    attention_mask = inputs['attention_mask']
    outputs = generator_model.generate(
        inputs['input_ids'],
        attention_mask=attention_mask,
        max_new_tokens=max_new_tokens,
        num_beams=5,
        no_repeat_ngram_size=2,
        early_stopping=True
    )

    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    answer = generated_text.split('답변:')[-1].strip()
    def process_response(answer):
        # "괜찮아요." 제거 및 세 번째 "다."에서 자르기
        answer = answer.replace("괜찮아요.\n", "")
        split_response = answer.split("다.")[:3]
        final_response = "다.".join(split_response) + "다."
        
        # 첫 번째 한글이 등장하는 위치를 찾고 그 이후의 텍스트 반환
        korean_text_match = re.search(r'[가-힣]', final_response)
        if korean_text_match:
            korean_text_start = korean_text_match.start()
            return final_response[korean_text_start:]  # 한글 이후 부분 반환
        else:
            return final_response  # 한글이 없으면 전체 텍스트 반환
    final_response = process_response(answer)


    print("상세 응답:", final_response)

    # 반환값이 http로 시작하는 경우 다시 실행
    if (final_response in ("", None) or user_query_pre not in final_response) and not try_count:
        time.sleep(100)
        return get_response(user_query, top_k, max_new_tokens, try_count=True)
    if (final_response in ("", None) or user_query_pre not in final_response) and try_count:
        return process_response(context)

    return final_response

# 사용 예시
user_query_pre = " 증시"
response = get_response(user_query_pre)
print(f'response {response}')
