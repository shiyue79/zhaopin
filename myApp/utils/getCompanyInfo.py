from myApp.models import Company, Employer
import os


def getCompanyInfo(username):
    try:
        employer = Employer.objects.get(username=username)
        company_id = employer.company_id

        if not company_id:
            return {
                'isCertified': False,
                'message': '未关联公司'
            }

        company = Company.objects.get(id=company_id)

        company_data = {
            'companyId': company.id,
            'companyName': company.name,
            'companyIntro': company.content,
            'logo': company.logo.url if company.logo else '',
            'location': company.location,
            'size': company.size,
            'tag': company.tag,
            'isCertified': company.vfbool == 1,
            'certificationStatus': company.vfstatus == 1,
            'license': company.verification.url if company.verification else '',
            'position': employer.position,
        }

        return company_data

    except Employer.DoesNotExist:
        return {
            'isCertified': False,
            'message': '用户不存在'
        }
    except Company.DoesNotExist:
        return {
            'isCertified': False,
            'message': '公司信息不存在'
        }


def saveCompanyInfo(username, data, files=None):
    try:
        employer = Employer.objects.get(username=username)
        company_id = employer.company_id

        if not company_id:
            return {'success': False, 'message': '未关联公司'}

        company = Company.objects.get(id=company_id)

        old_logo_path = company.logo.path if company.logo and hasattr(company.logo, 'path') else None
        company.name = data.get('name', company.name)
        company.content = data.get('content', company.content)
        company.location = data.get('location', company.location)
        company.size = data.get('size', company.size)
        company.tag = data.get('tag', company.tag)

        if files and files.get('logo'):
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']
            file_extension = os.path.splitext(files.get('logo').name)[1].lower()
            if file_extension in allowed_extensions:
                company.logo = files.get('logo')
                if old_logo_path and os.path.exists(old_logo_path):
                    try:
                        os.remove(old_logo_path)
                    except Exception as e:
                        print(f"删除旧Logo失败: {e}")

        company.save()

        return {'success': True, 'message': '企业信息保存成功'}

    except Employer.DoesNotExist:
        return {'success': False, 'message': '用户不存在'}
    except Company.DoesNotExist:
        return {'success': False, 'message': '公司信息不存在'}
    except Exception as e:
        return {'success': False, 'message': f'保存失败: {str(e)}'}


def submitCertification(username, files):
    try:
        if not files or not files.get('license'):
            return {'success': False, 'message': '请上传营业执照'}

        employer = Employer.objects.get(username=username)
        company_id = employer.company_id

        if not company_id:
            return {'success': False, 'message': '未关联公司'}

        company = Company.objects.get(id=company_id)

        old_verification_path = company.verification.path if company.verification and hasattr(company.verification,
                                                                                              'path') else None

        allowed_extensions = ['.jpg', '.jpeg', '.png']
        file_extension = os.path.splitext(files.get('license').name)[1].lower()
        if file_extension not in allowed_extensions:
            return {'success': False, 'message': '只支持JPG、PNG格式'}

        company.verification = files.get('license')
        company.vfstatus = 0
        company.vfbool = 0

        company.save()

        if old_verification_path and os.path.exists(old_verification_path):
            try:
                os.remove(old_verification_path)
            except Exception as e:
                print(f"删除旧认证文件失败: {e}")

        return {'success': True, 'message': '认证资料已提交，等待审核'}

    except Employer.DoesNotExist:
        return {'success': False, 'message': '用户不存在'}
    except Company.DoesNotExist:
        return {'success': False, 'message': '公司信息不存在'}
    except Exception as e:
        return {'success': False, 'message': f'提交失败: {str(e)}'}
