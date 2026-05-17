import hashlib
from myApp.models import User, Employer

def checkPwd(username, account, password_data):
    oldPwd = password_data.get('oldPwd')
    newPwd = password_data.get('newPwd')
    checkPwd_value = password_data.get('checkPwd')
    
    if not oldPwd or not newPwd or not checkPwd_value:
        return "密码不能为空"
    
    if newPwd != checkPwd_value:
        return "新密码两次不一致"
    
    # 根据 account 类型查询不同的表
    if account == 'user':
        user = User.objects.get(username=username)
    elif account == 'admin':
        user = Employer.objects.get(username=username)
    else:
        return "无效的账户类型"
    
    # 验证旧密码
    md5 = hashlib.md5()
    md5.update(oldPwd.encode())
    oldPwdHash = md5.hexdigest()
    
    if oldPwdHash != user.password:
        return "原始密码错误"
    
    # 更新为新密码
    md5 = hashlib.md5()
    md5.update(newPwd.encode())
    user.password = md5.hexdigest()
    user.save()
    
    return None
