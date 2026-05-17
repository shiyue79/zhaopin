from myApp.models import User
import os

educations = ["不限", "初中", "高中", "中专/中技", "大专", "本科", "硕士", "MBA/EMBA", "博士"]
WorkExperiences = ["不限", "无经验", "1年以下", "1-3年", "3-5年", "5-10年", "10年以上"]


def getPageData():
    return educations, WorkExperiences


def changeSelfInfo(newInfo, fileInfo):
    user = User.objects.get(username=newInfo.get('username'))
    old_avatar_path = user.avatar.path if user.avatar and hasattr(user.avatar, 'path') else None
    old_resume_path = user.resume.path if user.resume and hasattr(user.resume, 'path') else None
    user.realName = newInfo.get('realName')
    user.sex = newInfo.get('sex')
    user.age = newInfo.get('age')
    user.mobile = newInfo.get('mobile')
    user.email = newInfo.get('email')
    user.edu = newInfo.get('education')
    user.exp = newInfo.get('experience')
    user.city = newInfo.get('city')
    user.work = newInfo.get('work')
    if fileInfo.get('resume'):
        allowed_extensions = ['.pdf', '.doc', '.docx']
        file_extension = os.path.splitext(fileInfo.get('resume').name)[1].lower()
        if file_extension in allowed_extensions:
            user.resume = fileInfo.get('resume')
            if old_resume_path and os.path.exists(old_resume_path):
                try:
                    os.remove(old_resume_path)
                except Exception as e:
                    print(f"删除旧简历失败: {e}")
    try:
        if fileInfo.get('avatar'):
            user.avatar = fileInfo.get('avatar')
            if old_avatar_path and os.path.exists(old_avatar_path) and not old_avatar_path.endswith('avatar\\cat.jpg'):
                try:
                    os.remove(old_avatar_path)
                except Exception as e:
                    print(f"删除旧头像失败: {e}")
    except:
        pass
    user.save()
