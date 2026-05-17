from myApp.models import Job

educations = ["初中及以下", "高中", "中专/中技", "大专", "本科", "硕士", "MBA/EMBA", "博士"]
WorkExperiences = ["无经验", "1年以下", "1-3年", "3-5年", "5-10年", "10年以上"]


def getEduForEpx():
    jobs = Job.objects.all()
    result = {}
    for edu in educations:
        result[edu] = {}
        for exp in WorkExperiences:
            result[edu][exp] = {
                'count': 0,
                'avg': 0,
                'salarySum': 0,
                'minSalaries': 0,
                'maxSalaries': 0
            }
    for job in jobs:
        education = job.edu
        experience = job.exp
        salaryMin = job.salaryMin
        salaryMax = job.salaryMax
        if education in educations and experience in WorkExperiences:
            if salaryMin is None:
                continue
            salaryMin = salaryMin * 1000
            salaryMax = salaryMax * 1000
            category = result[education][experience]
            category['count'] += 1
            category['salarySum'] += (salaryMin + salaryMax) / 2
            category['minSalaries'] += salaryMin
            category['maxSalaries'] += salaryMax
    for edu in educations:
        for exp in WorkExperiences:
            if result[edu][exp]['count'] > 0:
                result[edu][exp]['avg'] = round(result[edu][exp]['salarySum'] / result[edu][exp]['count'], 2)
                result[edu][exp]['minSalaries'] = round(result[edu][exp]['minSalaries'] / result[edu][exp]['count'], 2)
                result[edu][exp]['maxSalaries'] = round(result[edu][exp]['maxSalaries'] / result[edu][exp]['count'], 2)
    return educations, WorkExperiences, result


def getBonusData():
    jobs = Job.objects.filter(salaryBonus__isnull=False)
    data = {}
    for job in jobs:
        bonus = str(job.salaryBonus) + '薪'
        if bonus in data:
            data[bonus] += 1
        else:
            data[bonus] = 1
    result = []
    for k, v in data.items():
        result.append({
            'name': k,
            'value': v
        })
    return result
