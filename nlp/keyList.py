import json
import jieba
import jieba.analyse
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy import text

class JobDataProcessor:
    def __init__(self):
        self.tfidf_vectorizer = TfidfVectorizer(max_features=10000)

    def load_all_job_data(self):
        engine = create_engine(
            'mysql+pymysql://root:123456@localhost:3306/zhaopin',
            echo=False,
            pool_pre_ping=True
        )
        query = """
                SELECT href, tagList, content, company, keyList
                FROM job
                """
        jobs_df = pd.read_sql(query, engine)
        engine.dispose()
        return jobs_df

    def extract_keywords_from_jobs(self, jobs_df, top_n=5000):
        all_contents = []
        for _, job in jobs_df.iterrows():
            content = job.get('content', '')
            if content and isinstance(content, str):
                processed_content = self._preprocess_text(content)
                all_contents.append(processed_content)
        if not all_contents:
            return {}
        # 合并所有content
        combined_text = ' '.join(all_contents)
        self.tfidf_vectorizer.fit(all_contents)
        feature_names = self.tfidf_vectorizer.get_feature_names_out()
        tfidf_matrix = self.tfidf_vectorizer.transform(all_contents)
        word_scores = np.asarray(tfidf_matrix.mean(axis=0)).ravel()
        top_indices = np.argsort(word_scores)[-top_n:][::-1]
        top_words = [(feature_names[i], word_scores[i]) for i in top_indices]
        return top_words

    def _preprocess_text(self, text):  # 预处理文本，去除数字、日期等
        text = re.sub(r'\b\d+\.?\d*\b', '', text)
        text = re.sub(r'\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b', '', text)
        text = re.sub(r'\b\d{1,2}:\d{2}\b', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        remove_patterns = [
            r'任职要求', r'岗位职责', r'职位描述', r'工作内容', r'任职资格',
            r'岗位描述', r'职位职责', r'任职条件', r'工作职责', r'岗位要求',
            r'基本要求', r'职位要求', r'任职标准', r'工作描述', r'原标题',
            r'岗位内容', r'工作时间', r'工作地点', r'要求', r'工作经验', r'职位福利',
            r'薪资待遇', r'职位亮点', r'专业', r'底薪'
        ]
        for pattern in remove_patterns:
            text = re.sub(pattern, '', text)
        return text

    def _extract_skills_from_job(self, job_data):
        skills = set()
        content = job_data.get('content', '')
        if not content:
            return list(skills)
        # 方法1: 使用jieba的TextRank提取关键词
        textrank_keywords = jieba.analyse.textrank(content, topK=30, withWeight=False)
        skills.update(textrank_keywords)
        # 方法2: 使用TF-IDF提取关键词
        tfidf_keywords = jieba.analyse.extract_tags(content, topK=30, withWeight=False)
        skills.update(tfidf_keywords)
        # 方法3: 提取英文技术词汇
        english_tech_pattern = r'\b[A-Z][a-z]+[A-Z][a-z]+\b|\b[A-Z]{2,}\b'
        english_matches = re.findall(english_tech_pattern, content)
        skills.update([match.lower() for match in english_matches])
        # 方法4: 从tagList中提取
        tag_list = job_data.get('tagList', '')
        if tag_list:
            tags = tag_list.split(',')
            skills.update(tags)
        return list(skills)


jobObj = JobDataProcessor()
jobs_df = jobObj.load_all_job_data()
engine = create_engine(
            'mysql+pymysql://root:123456@localhost:3306/zhaopin',
            echo=False,
            pool_pre_ping=True
        )
with engine.connect() as conn:
    batch_size = 0
    total_rows = len(jobs_df)

    for start_idx in range(0, total_rows, batch_size):
        trans = conn.begin()
        try:
            end_idx = min(start_idx + batch_size, total_rows)
            batch_df = jobs_df.iloc[start_idx:end_idx]
            updated_count = 0
            for index, row in batch_df.iterrows():
                if row['keyList']:
                    continue
                skill_weights = json.dumps(jobObj._extract_skills_from_job(row), ensure_ascii=False)
                if not skill_weights:
                    continue
                update_query = text("""
                                    UPDATE job
                                    SET keyList = :keyList
                                    WHERE href = :href
                                    """)
                result = conn.execute(update_query, {'keyList': skill_weights, 'href': row['href']})
            trans.commit()
            print(f"✅ 批次 {start_idx // batch_size + 1}: 成功更新 (范围: {start_idx}-{end_idx - 1})")
        except Exception as e:
            trans.rollback()
            print(f"❌ 批次 {start_idx // batch_size + 1} 失败: {e}")
            raise e

engine.dispose()

