from django.db.models import Q
from djzhao import settings
from myApp.models import Job, User
import os
from pathlib import Path
import re
import jieba.analyse
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import json
import pdfplumber
import docx

educations = ["不限", "初中及以下", "高中", "中专/中技", "大专", "本科", "硕士", "MBA/EMBA", "博士"]
WorkExperiences = ["不限", "无经验", "1年以下", "1-3年", "3-5年", "5-10年", "10年以上"]


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


def job_data(job):
    if job.salaryMin is not None:
        def format_salary(sal):
            if sal is None:
                return 0
            formatted = float(sal)
            if formatted == int(formatted):
                return str(int(formatted))
            else:
                return f"{formatted:.1f}"

        min_sal = format_salary(job.salaryMin)
        max_sal = format_salary(job.salaryMax)
        salary = f"{min_sal}-{max_sal}k"
        if job.salaryBonus:
            bounds_formatted = format_salary(job.salaryBonus)
            salary += f'*{bounds_formatted}薪'
    else:
        salary = "薪资面议"
    return {
        'href': job.href,
        'title': job.name,
        'location': job.city,
        'salary': salary,
        'exp': job.exp,
        'edu': job.edu,
        'tags': job.tags,
        'keyList': job.keyList,
        'company': job.com,
        'comSize': job.comSize,
        'comTag': job.comTag.split(',')
    }


class ContentBasedRecommender:
    def __init__(self):
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=5000
        )
        self.job_features = None
        self.job_ids = None

    def prepare_job_features(self, jobs_df):
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
            features.append(job.get('exp', ''))
            features.append(job.get('edu', ''))
            features.append(job.get('comSize', ''))
            features.append(job.get('salaryMin', ''))
            features.append(job.get('salaryMax', ''))
            features.append(job.get('salaryBonus', ''))
            job_text = ' '.join(filter(lambda x: x is not None and x != '', [str(item) for item in features]))
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
        similarities = cosine_similarity(resume_vector, self.job_features).flatten()
        top_indices = np.argsort(similarities)[::-1]
        recommendations = []
        for idx in top_indices[:top_n]:
            job_id = self.job_ids[idx]
            job = Job.objects.filter(href=job_id).first()
            if job:
                recommendations.append(job_data(job))
        return recommendations


def getDefaultData(uname, request):
    if request.method == 'POST':
        defaultWork = request.POST.get('work', '')
        defaultCity = request.POST.get('city', '')
        defaultEdu = request.POST.get('education', '不限')
        defaultExp = request.POST.get('experience', '不限')
        defaultSalary = request.POST.get('salary', '')
    elif request.GET:
        defaultWork = request.GET.get('work', '')
        defaultCity = request.GET.get('city', '')
        defaultEdu = request.GET.get('education', '不限')
        defaultExp = request.GET.get('experience', '不限')
        defaultSalary = request.GET.get('salary', '')
    else:
        user = User.objects.get(username=uname)
        if user.work:
            defaultWork = user.work
        else:
            defaultWork = ""
        if user.city:
            defaultCity = user.city
        else:
            defaultCity = ""
        if user.edu:
            defaultEdu = user.edu
        else:
            defaultEdu = "不限"
        if user.exp:
            defaultExp = user.exp
        else:
            defaultExp = "不限"
        defaultSalary = ""
    return {
        'educations': educations,
        'workEx': WorkExperiences,
        'defaultWork': defaultWork,
        'defaultCity': defaultCity,
        'defaultEdu': defaultEdu,
        'defaultExp': defaultExp,
        'defaultSalary': defaultSalary
    }


def getTableData(uname, pageData):
    work = pageData.get('defaultWork', '')
    city = pageData.get('defaultCity', '')
    education = pageData.get('defaultEdu', '不限')
    experience = pageData.get('defaultExp', '不限')
    salary = pageData.get('defaultSalary', '')
    filters = Q()
    if work != "":
        filters &= Q(name__icontains=str(work)) | Q(keyList__icontains=str(work))
    if city != "":
        filters &= Q(city__icontains=str(city))
    if education != "不限":
        filters &= Q(edu=education)
    if experience != "不限":
        filters &= Q(exp=experience)
    if salary != '' and salary is not None:
        try:
            salary = int(salary)
            filters &= Q(salaryMin__gte=salary)
        except ValueError:
            pass
    jobs = Job.objects.filter(filters)
    jobs_df = pd.DataFrame(list(jobs.values()))
    recommender = ContentBasedRecommender()
    recommender.prepare_job_features(jobs_df)
    user = User.objects.get(username=uname)
    if user:
        resume_filename = user.resume
        resume_path = os.path.join(settings.MEDIA_ROOT, str(resume_filename))
        if os.path.exists(resume_path):
            file_extension = Path(resume_path).suffix.lower()
            resume_text = None
            if file_extension in ['.docx', '.doc']:
                resume_text = extract_from_docx(resume_path)
            elif file_extension == '.pdf':
                resume_text = extract_from_pdf(resume_path)
            else:
                print(f"不支持的文件格式: {file_extension}")
        else:
            print(f"文件不存在: {resume_path}")
        user_resume = []
        user_resume.append(work)
        user_resume.append(user.edu)
        user_resume.append(user.exp)
        user_resume.append(user.work)
        if resume_text:
            skills = set()
            textrank_keywords = jieba.analyse.textrank(resume_text, topK=30, withWeight=False)
            skills.update(textrank_keywords)
            tfidf_keywords = jieba.analyse.extract_tags(resume_text, topK=30, withWeight=False)
            skills.update(tfidf_keywords)
            english_tech_pattern = r'\b[A-Z][a-z]+[A-Z][a-z]+\b|\b[A-Z]{2,}\b'
            english_matches = re.findall(english_tech_pattern, resume_text)
            skills.update([match.lower() for match in english_matches])
            user_resume.append(str(skills))
        user_text = ' '.join(filter(lambda x: x is not None and x != '', user_resume))
        recommendations = recommender.recommend_for_resume(user_text)
    if recommendations:
        return recommendations
    else:
        return [job_data(job) for job in jobs]


def calculate_recommendation_accuracy(name, recommendations):
    if not recommendations:
        return 0.0, {"total": 0, "matched": 0}
    user_keywords = jieba.analyse.extract_tags(name, topK=10, withWeight=False)
    matched_count = 0
    count = 0
    total_recommendations = len(recommendations)
    for job in recommendations:
        job_title = (job.get('title', '') or '').lower()
        job_tags = ' '.join(job.get('keyList', [])).lower()
        full_text = f"{job_title} {job_tags}"
        if any(keyword in full_text for keyword in user_keywords):
            matched_count += 1
    accuracy1 = matched_count / total_recommendations if total_recommendations > 0 else 0.0
    accuracy2 = count / total_recommendations if total_recommendations > 0 else 0.0
    return accuracy1, {
        "total": total_recommendations,
        "matched": matched_count,
        "accuracy_rate": f"{accuracy1 * 100:.2f}%",
        "accuracy_rate2": f"{accuracy2 * 100:.2f}%"
    }
