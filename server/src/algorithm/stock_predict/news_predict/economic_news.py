# 표준 라이브러리
import json
import urllib.parse
import urllib.request
from datetime import datetime

# 외부 라이브러리
import requests
import numpy as np
import pandas as pd
import networkx as nx
from bs4 import BeautifulSoup

# NLTK 관련 다운로드
import nltk
nltk.download('punkt')
nltk.download('stopwords')

# NLTK 모듈
from nltk.cluster.util import cosine_distance
from nltk.tokenize import sent_tokenize

import logging
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)

# 네이버 API 클라이언트 ID와 시크릿
client_id = "4aM0BLbwSKf5jwggWUmb"
client_secret = "VG12t6mFAJ"

# URL 요청 함수: API에 요청을 보내고 응답을 반환
def getRequestUrl(url):
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", client_id)
    req.add_header("X-Naver-Client-Secret", client_secret)
    try:
        response = urllib.request.urlopen(req)
        if response.getcode() == 200:
            return response.read().decode('utf-8')
        else:
            return None
    except Exception as e:
        print(e)
        return None

# 네이버 뉴스 검색 API를 사용하여 뉴스를 검색하는 함수
def searchNaverNews(query, from_date, to_date, display=10, start=1):
    base_url = "https://openapi.naver.com/v1/search/news.json"
    query = urllib.parse.quote(query)
    url = f"{base_url}?query={query}&display={display}&start={start}&sort=date&startDate={from_date}&endDate={to_date}"
    
    response = getRequestUrl(url)
    if response is None:
        return None
    
    return json.loads(response)

# 네이버 뉴스 본문을 크롤링하는 함수
def fetchNaverNewsContent(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 네이버 뉴스 본문 추출 (주어진 HTML 구조에 맞게 수정)
            article_body = soup.find('article', {'id': 'dic_area', 'class': 'go_trans _article_content'})
            
            if article_body:
                # 불필요한 태그 제거 (예: 스크립트, 스타일 등)
                for unwanted in article_body(['script', 'style']):
                    unwanted.extract()
                return article_body.get_text(strip=True)
            else:
                return ""
        else:
            return ""
    except Exception as e:
        return str(e)



def getFilteredNews(query, date, keywords=None, display=500):
    # keywords가 주어지지 않으면 빈 리스트로 설정
    if keywords is None:
        keywords = []
    
    news_items = searchNaverNews(query, 20200917, date, display)
    
    if news_items:
        parsed_news = []
        for item in news_items['items']:
            try:
                title = BeautifulSoup(item['title'], 'html.parser').get_text()
                link = item['link']
                description = BeautifulSoup(item['description'], 'html.parser').get_text()
                
                # 원문 기사 크롤링
                content = fetchNaverNewsContent(link)
                
                # 'HTTPSConnectionPool' 문자열이 포함된 경우 필터링
                if "HTTPSConnectionPool" in content:
                    continue
                
                summary_content = textrank_summary(content)
                
                # title, link, description, content 중 하나라도 비어 있으면 해당 기사를 넘기기
                if not title or not link or not description or not content:
                    continue
                
                # 키워드 리스트가 비어 있지 않으면 필터링
                if keywords and not any(keyword in content for keyword in keywords):
                    continue
                
                parsed_news.append({
                    'title': title,
                    'link': link,
                    'description': description,
                    'content': content,
                    'summary_content': summary_content
                })
            
            except Exception as e:
                continue
        
        return parsed_news
    else:
        return []

def sentence_similarity(sent1, sent2, stopwords=None):
	# 불용어가 주어지지 않으면 빈 리스트로 초기화
	if stopwords is None:
		stopwords = []
		
	# 문장을 모두 소문자로 변환
	sent1 = [word.lower() for word in sent1 if word not in stopwords]
	sent2 = [word.lower() for word in sent2 if word not in stopwords]
	
	# 두 문장에서 모든 단어를 모두 중복을 제거한 집합 생성
	all_words = list(set(sent1 + sent2))
	
	# 각 문장의 단어 등장 횟수를 기록할 벡터 초기화
	vector1 = [0] * len(all_words)
	vector2 = [0] * len(all_words)
	
	# 첫 번째 문장의 단어 등장 횟수 기록
	for word in sent1:
		if word in stopwords:
			continue # 불용어 무시
		vector1[all_words.index(word)] += 1
	
	# 두 번째 문장의 단어 등장 횟수 기록
	for word in sent2:
		if word in stopwords:
			continue
		vector2[all_words.index(word)] += 1
		
		# 코사인 유사도 계산을 위해 벡터를 이용하여 측정
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

def textrank_summary(text, num_sentences=3):
    # 입력 텍스트를 문장 단위로 구분
    sentences = sent_tokenize(text)
    
    # 불용어 제거
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
    
    return summary

today = datetime.today().strftime("%Y-%m-%d")

queries = ['증시', '한국증시', '미국증시', "한국은행", "연준", "기준금리"]

filtered_summaries = []
for query in queries:
    df = getFilteredNews(query, today, display=100)
    for news_item in df:
        news = news_item['summary_content']
        if "기자" not in news and "?" not in news and "투자증권" not in news and "증시" in news and "앵커" not in news and "운용사" not in news:
            filtered_summaries.append(news)
            break
    if filtered_summaries[0]:
        break

    # 필터링된 결과 확인
filtered_summaries[0]

def main():
    today = datetime.today().strftime("%Y-%m-%d")
    queries = ['증시', '한국증시', '미국증시', "한국은행", "연준", "기준금리"]
    
    filtered_summaries = []
    for query in queries:
        df = getFilteredNews(query, today, display=100)
        for news_item in df:
            news = news_item['summary_content']
            if ("기자" not in news and "?" not in news and "투자증권" not in news and 
                "증시" in news and "앵커" not in news and "운용사" not in news):
                filtered_summaries.append(news)
                break
        if filtered_summaries[0]:
            break
    
    # 필터링된 결과 확인
    print(filtered_summaries[0])

# main 함수 실행
if __name__ == "__main__":
    main()