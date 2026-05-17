import os
from pathlib import Path
import re
import jieba.analyse
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import pandas as pd
from sqlalchemy import create_engine
from sklearn.metrics.pairwise import cosine_similarity
import json
import pdfplumber
import docx


def extract_from_docx(file_path):
    doc = docx.Document(file_path)
    text = []
    for para in doc.paragraphs:
        text.append(para.text)
    return '\n'.join(text)


def extract_from_pdf(file_path):
    with pdfplumber.open(file_path) as pdf:
        text = []
        for page in pdf.pages:
            text.append(page.extract_text())
    return '\n'.join(text) if text else ''

class ContentBasedRecommender:
    def __init__(self, db_connection):
        self.db = db_connection
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=5000
        )
        self.job_features = None
        self.job_ids = None

    def prepare_job_features(self):
        query = """
                SELECT href,
                       name,
                       content,
                       keyList,
                       company,
                       location,
                       salaryMin,
                       salaryMax,
                       experience,
                       education
                FROM job
                WHERE deleteStatus = 0 
                """
        jobs_df = pd.read_sql(query, self.db)
        if jobs_df.empty:
            return False
        # 构建岗位特征文本
        job_texts = []
        self.job_ids = []
        for _, job in jobs_df.iterrows():
            features = []
            features.append(job.get('name', ''))
            key_list = job.get('keyList', '[]')
            try:
                if key_list and key_list != '[]':
                    keywords = json.loads(key_list)
                    features.append(' '.join(keywords))
                    features.append(' '.join(keywords))
                    features.append(' '.join(keywords))
                    features.append(' '.join(keywords))
            except:
                pass
            features.append(job.get('company', ''))
            features.append(job.get('location', ''))
            features.append(job.get('experience', ''))
            features.append(job.get('education', ''))
            job_text = ' '.join(filter(lambda x: x is not None and x != '', features))
            job_texts.append(job_text)
            self.job_ids.append(job['href'])
        # 计算TF-IDF特征
        self.job_features = self.tfidf_vectorizer.fit_transform(job_texts)
        return True

    def recommend_for_resume(self, user_resume, top_n=200):
        if self.job_features is None:
            if not self.prepare_job_features():
                return []
        resume_vector = self.tfidf_vectorizer.transform([user_resume])
        # 计算相似度
        similarities = cosine_similarity(resume_vector, self.job_features).flatten()
        # 获取相似度最高的岗位索引
        top_indices = np.argsort(similarities)[::-1]
        # 获取推荐结果
        recommendations = []
        for idx in top_indices[:top_n]:  # 多取一些用于过滤
            job_id = self.job_ids[idx]
            similarity = similarities[idx]
            # 获取岗位详细信息
            job_query = f"""
            SELECT href, name, company, location, salaryMin, salaryMax, 
                   experience, education, content
            FROM job
            WHERE href = '{job_id}'
            """
            job_df = pd.read_sql(job_query, self.db)
            if not job_df.empty:
                job = job_df.iloc[0]
                recommendations.append({
                    'job_id': job['href'],
                    'title': job['name'],
                    'company': job['company'],
                    'location': job.get('location', ''),
                    'salary_range': f"{job.get('salaryMin', 0)}-{job.get('salaryMax', 0)}k",
                    'similarity': float(similarity),
                    'type': 'content_based'
                })
        return recommendations


engine = create_engine(
    'mysql+pymysql://root:123456@localhost:3306/zhaopin',
    echo=False,
    pool_pre_ping=True
)
recommender = ContentBasedRecommender(engine)
recommender.prepare_job_features()
user = 'a'
query = "select experience, education, city, work, resume from user where username = %s"
try:
    user_data = pd.read_sql(query, engine, params=(user,))
    if not user_data.empty:
        user_info = user_data.iloc[0]
    else:
        print("未找到用户数据")
except Exception as e:
    print(f"查询出错: {e}")

# 指定简历文件路径
resume_folder = "E:\project\python\djzhao\media"
resume_filename = user_info['resume']
resume_path = os.path.join(resume_folder, resume_filename)
# 提取简历文本
if os.path.exists(resume_path):
    file_extension = Path(resume_path).suffix.lower()
    if file_extension in ['.docx', '.doc']:
        resume_text = extract_from_docx(resume_path)
    elif file_extension == '.pdf':
        resume_text = extract_from_pdf(resume_path)
    else:
        print(f"不支持的文件格式: {file_extension}")
else:
    print(f"文件不存在: {resume_path}")
skills = set()
textrank_keywords = jieba.analyse.textrank(resume_text, topK=30, withWeight=False)
skills.update(textrank_keywords)
# 方法2: 使用TF-IDF提取关键词
tfidf_keywords = jieba.analyse.extract_tags(resume_text, topK=30, withWeight=False)
skills.update(tfidf_keywords)
# 方法3: 提取英文技术词汇
english_tech_pattern = r'\b[A-Z][a-z]+[A-Z][a-z]+\b|\b[A-Z]{2,}\b'
english_matches = re.findall(english_tech_pattern, resume_text)
skills.update([match.lower() for match in english_matches])

user_resume = []
user_resume.append(user_info.get('experience', ''))
user_resume.append(user_info.get('education', ''))
user_resume.append(user_info.get('city', ''))
user_resume.append(user_info.get('work', ''))
user_resume.append(str(skills))
user_text = ' '.join(filter(lambda x: x is not None and x != '', user_resume))
recommendations = recommender.recommend_for_resume(user_text)
print( recommendations)