"""
基于内容的岗位推荐系统
功能：
1. 从 Joblist 表加载岗位数据并提取特征
2. 从 User 表加载求职者数据
3. 使用 History（浏览历史）划分训练集和测试集
4. 基于 TF-IDF + 余弦相似度进行推荐
5. 计算推荐准确率、召回率等指标
"""

import os
import json
import re
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import train_test_split
from collections import defaultdict
from django.conf import settings
import jieba
import jieba.analyse
from pathlib import Path
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
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return '\n'.join(text) if text else ''

class ContentBasedRecommender:
    """基于内容的推荐系统"""
    
    def __init__(self, top_k=20):
        self.top_k = top_k
        self.tfidf_vectorizer = TfidfVectorizer(max_features=5000)
        self.job_features = None
        self.job_ids = None
        self.jobs_df = None
        
    def extract_job_features(self, job):
        """从岗位数据中提取特征文本"""
        features = []
        
        # 岗位名称（权重较高，重复4次）
        features.append(job.get('name', '') * 4)
        
        # 关键词列表（从 keyList 字段）
        key_list = job.get('keyList', '[]')
        try:
            if key_list and key_list != '[]':
                keywords = json.loads(key_list)
                if isinstance(keywords, dict):
                    features.append(' '.join(keywords.keys()) * 4)
                elif isinstance(keywords, list):
                    features.append(' '.join(keywords) * 4)
        except:
            pass
        
        # 经验要求
        features.append(job.get('exp', '') * 2)
        
        # 学历要求
        features.append(job.get('edu', '') * 2)
        
        # 公司规模
        features.append(job.get('comSize', '') * 2)
        
        # 薪资范围
        features.append(str(job.get('salaryMin', '')))
        features.append(str(job.get('salaryMax', '')))
        features.append(str(job.get('salaryBonus', '')))
        
        # 职位描述
        features.append(job.get('content', '') * 2)
        
        # 行业
        features.append(job.get('industry', '') * 2)
        
        # 城市
        features.append(job.get('city', '') * 2)
        
        # 过滤空值并拼接
        job_text = ' '.join([str(item) for item in features if item and item != 'None'])
        return job_text
    
    def prepare_job_features(self, jobs_df):
        """准备所有岗位的特征向量"""
        if jobs_df.empty:
            print(" 岗位数据为空")
            return False
            
        print(f"📊 正在处理 {len(jobs_df)} 个岗位...")
        
        job_texts = []
        self.job_ids = []
        
        for _, job in jobs_df.iterrows():
            job_text = self.extract_job_features(job.to_dict())
            job_texts.append(job_text)
            self.job_ids.append(job['id'])
        
        # 计算 TF-IDF 特征矩阵
        self.job_features = self.tfidf_vectorizer.fit_transform(job_texts)
        self.jobs_df = jobs_df
        
        print(f"✅ 岗位特征提取完成，特征维度: {self.job_features.shape}")
        return True
    
    def extract_user_features(self, user):
        """从求职者数据中提取特征文本"""
        features = []
        
        # 意向岗位（权重较高）
        features.append(user.get('work', '') * 4)
        
        # 学历
        features.append(user.get('edu', '') * 2)
        
        # 工作经验
        features.append(user.get('exp', '') * 2)
        
        # 意向城市
        features.append(user.get('city', '') * 2)
        
        # 如果有简历文本，提取关键词
        resume_folder = "E:\project\python\djzhao\media"
        resume_filename = user.get('resume', '')
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
        try:
            if resume_text:
                # 使用 TextRank 提取关键词
                textrank_keywords = jieba.analyse.textrank(resume_text, topK=30, withWeight=False)
                features.append(' '.join(textrank_keywords) * 2)

                # 使用 TF-IDF 提取关键词
                tfidf_keywords = jieba.analyse.extract_tags(resume_text, topK=30, withWeight=False)
                features.append(' '.join(tfidf_keywords) * 2)

                # 提取英文技术术语
                english_pattern = r'\b[A-Z][a-z]+[A-Z][a-z]+\b|\b[A-Z]{2,}\b'
                english_matches = re.findall(english_pattern, resume_text)
                features.append(' '.join([m.lower() for m in english_matches]) * 2)
        except:
            pass
        user_text = ' '.join([str(item) for item in features if item and item != 'None'])
        return user_text
    
    def recommend_for_user(self, user_features_dict, top_n=None):
        """为单个用户推荐岗位"""
        if top_n is None:
            top_n = self.top_k
            
        if self.job_features is None:
            print("❌ 请先调用 prepare_job_features() 初始化岗位特征")
            return []
        
        # 提取用户特征向量
        user_text = self.extract_user_features(user_features_dict)
        user_vector = self.tfidf_vectorizer.transform([user_text])
        
        # 计算余弦相似度
        similarities = cosine_similarity(user_vector, self.job_features).flatten()
        
        # 获取 Top-N 推荐
        top_indices = np.argsort(similarities)[::-1][:top_n]
        
        recommendations = []
        for idx in top_indices:
            job_id = self.job_ids[idx]
            job = self.jobs_df[self.jobs_df['id'] == job_id]
            if not job.empty:
                recommendations.append({
                    'job_id': int(job_id),
                    'job_name': job.iloc[0]['name'],
                    'score': float(similarities[idx]),
                    'city': job.iloc[0].get('city', ''),
                    'salary': f"{job.iloc[0].get('salaryMin', 0)}-{job.iloc[0].get('salaryMax', 0)}k"
                })
        
        return recommendations
    
    def split_train_test(self, history_df, test_size=0.2, random_state=42):
        """
        根据浏览历史划分训练集和测试集
        按用户分组，每个用户的历史浏览记录划分为 train/test
        """
        print(f"\n📈 正在划分训练集/测试集 (测试集比例: {test_size})...")
        
        train_data = []
        test_data = []
        
        # 按用户分组
        for user_id, user_histories in history_df.groupby('user_id'):
            if len(user_histories) < 2:
                # 浏览记录少于2条的用户全部放入训练集
                train_data.extend(user_histories.to_dict('records'))
                continue
            
            # 按时间排序（如果有时间字段）
            if 'time' in user_histories.columns:
                user_histories = user_histories.sort_values('time')
            
            # 划分训练集和测试集
            train_subset, test_subset = train_test_split(
                user_histories, 
                test_size=test_size, 
                random_state=random_state,
                shuffle=False  # 保持时间顺序
            )
            
            train_data.extend(train_subset.to_dict('records'))
            test_data.extend(test_subset.to_dict('records'))
        
        train_df = pd.DataFrame(train_data)
        test_df = pd.DataFrame(test_data)
        
        print(f"✅ 划分完成:")
        print(f"   训练集: {len(train_df)} 条记录")
        print(f"   测试集: {len(test_df)} 条记录")
        print(f"   用户数: {history_df['user_id'].nunique()}")
        
        return train_df, test_df
    
    def evaluate(self, test_df, users_df, jobs_df, top_n=None):
        """
        评估推荐系统性能
        计算指标：
        - 命中率 (Hit Rate): 测试集中的岗位有多少被推荐出来
        - 准确率 (Precision): 推荐的岗位有多少在测试集中
        - 召回率 (Recall): 测试集中的岗位有多少被推荐出来
        - F1 Score: 准确率和召回率的调和平均
        """
        if top_n is None:
            top_n = self.top_k
            
        print(f"\n🎯 开始评估推荐系统 (Top-{top_n})...")
        
        precisions = []
        recalls = []
        f1_scores = []
        hit_rates = []
        
        # 统计每个用户的测试集岗位
        user_test_jobs = defaultdict(set)
        for _, row in test_df.iterrows():
            user_test_jobs[row['user_id']].add(row['job_id'])
        
        total_users = len(user_test_jobs)
        evaluated_users = 0
        
        for user_id, test_jobs in user_test_jobs.items():
            # 获取用户信息
            user_data = users_df[users_df['id'] == user_id]
            if user_data.empty:
                continue
            
            user_dict = user_data.iloc[0].to_dict()
            
            # 生成推荐列表
            recommendations = self.recommend_for_user(user_dict, top_n=top_n)
            recommended_job_ids = set([rec['job_id'] for rec in recommendations])
            
            if not recommended_job_ids:
                continue
            
            evaluated_users += 1
            
            # 计算指标
            hits = len(test_jobs & recommended_job_ids)
            
            # Precision: 推荐列表中有多少是用户实际浏览过的
            precision = hits / len(recommended_job_ids) if recommended_job_ids else 0
            
            # Recall: 用户实际浏览过的岗位有多少被推荐出来了
            recall = hits / len(test_jobs) if test_jobs else 0
            
            # F1 Score
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
            
            # Hit Rate: 是否至少命中一个
            hit_rate = 1 if hits > 0 else 0
            
            precisions.append(precision)
            recalls.append(recall)
            f1_scores.append(f1)
            hit_rates.append(hit_rate)
        
        # 计算平均指标
        avg_precision = np.mean(precisions) if precisions else 0
        avg_recall = np.mean(recalls) if recalls else 0
        avg_f1 = np.mean(f1_scores) if f1_scores else 0
        avg_hit_rate = np.mean(hit_rates) if hit_rates else 0
        
        print(f"\n📊 评估结果:")
        print(f"   评估用户数: {evaluated_users}/{total_users}")
        print(f"   平均准确率 (Precision@{top_n}): {avg_precision:.4f} ({avg_precision*100:.2f}%)")
        print(f"   平均召回率 (Recall@{top_n}): {avg_recall:.4f} ({avg_recall*100:.2f}%)")
        print(f"   平均 F1 Score: {avg_f1:.4f}")
        print(f"   命中率 (Hit Rate@{top_n}): {avg_hit_rate:.4f} ({avg_hit_rate*100:.2f}%)")
        
        return {
            'precision': avg_precision,
            'recall': avg_recall,
            'f1': avg_f1,
            'hit_rate': avg_hit_rate,
            'evaluated_users': evaluated_users,
            'total_users': total_users
        }


    def evaluate_by_similarity(self, test_df, users_df, jobs_df, top_n=None):
        """
        基于相似度阈值的评估
        只要推荐岗位与用户画像相似度 > 阈值，就算推荐成功
        """
        if top_n is None:
            top_n = self.top_k

        print(f"\n🎯 开始评估推荐系统 (Top-{top_n})...")

        similarity_scores = []
        high_quality_recs = 0
        total_recs = 0

        for _, user in users_df.iterrows():
            user_dict = user.to_dict()
            recommendations = self.recommend_for_user(user_dict, top_n=top_n)

            if not recommendations:
                continue

            # 计算推荐岗位的平均相似度
            user_scores = [rec['score'] for rec in recommendations]
            similarity_scores.extend(user_scores)

            # 统计高质量推荐（相似度 > 0.5）
            high_quality_recs += sum([1 for s in user_scores if s > 0.2])
            total_recs += len(user_scores)

        avg_similarity = np.mean(similarity_scores) if similarity_scores else 0
        quality_rate = high_quality_recs / total_recs if total_recs > 0 else 0

        print(f"\n📊 评估结果:")
        print(f"   平均相似度: {avg_similarity:.4f}")
        print(f"   高质量推荐率: {quality_rate:.4f} ({quality_rate*100:.2f}%)")
        print(f"   总推荐数: {total_recs}")

        return {
            'avg_similarity': avg_similarity,
            'quality_rate': quality_rate,
            'total_recommendations': total_recs
        }


def run_recommendation_system():
    """运行完整的推荐系统评估流程"""
    import django
    import sys
    
    # 设置 Django 环境
    sys.path.append(r'E:\project\python\djzhao')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djzhao.settings')
    django.setup()
    
    from myApp.models import Joblist, User, History
    from django.db.models import Q
    
    print("="*60)
    print("🚀 基于内容的岗位推荐系统")
    print("="*60)
    
    # 1. 加载岗位数据
    print("\n📥 正在加载岗位数据...")
    jobs_df = pd.DataFrame(list(Joblist.objects.filter(delete=0).values()))
    print(f"✅ 加载了 {len(jobs_df)} 个岗位")
    
    # 2. 加载用户数据
    print("\n📥 正在加载用户数据...")
    users_df = pd.DataFrame(list(User.objects.values()))
    print(f"✅ 加载了 {len(users_df)} 个用户")
    
    # 3. 加载浏览历史
    print("\n📥 正在加载浏览历史...")
    history_df = pd.DataFrame(list(History.objects.values()))
    print(f"✅ 加载了 {len(history_df)} 条浏览记录")
    
    if history_df.empty:
        print("❌ 没有浏览历史数据，无法进行评估")
        return
    
    # 4. 初始化推荐系统
    recommender = ContentBasedRecommender(top_k=20)
    
    # 5. 准备岗位特征
    if not recommender.prepare_job_features(jobs_df):
        print("❌ 岗位特征提取失败")
        return
    
    # 6. 划分训练集和测试集
    train_df, test_df = recommender.split_train_test(
        history_df, 
        test_size=0.2, 
        random_state=42
    )
    
    # 7. 评估推荐系统
    results = recommender.evaluate(test_df, users_df, jobs_df, top_n=20)
    res = recommender.evaluate_by_similarity(test_df, users_df, jobs_df, top_n=20)
    # 8. 示例：为某个用户推荐
    print(f"\n 示例推荐:")
    if len(users_df) > 0:
        sample_user = users_df.iloc[35].to_dict()
        recommendations = recommender.recommend_for_user(sample_user, top_n=10)
        print(f"\n为用户 '{sample_user.get('username', 'Unknown')}' 推荐:")
        for i, rec in enumerate(recommendations[:5], 1):
            print(f"   {i}. {rec['job_name']} (城市: {rec['city']}, 薪资: {rec['salary']}, 得分: {rec['score']:.4f})")
    
    print("\n" + "="*60)
    print("✅ 推荐系统评估完成")
    print("="*60)
    
    return results


if __name__ == '__main__':
    results = run_recommendation_system()