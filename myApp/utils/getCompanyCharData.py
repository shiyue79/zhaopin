from myApp.models import Job
companySizes = ["20人以下","20-99人","100-299人","300-499人","500-999人","1000-9999人","10000人以上"]

def getCompanyPie():
    jobs = Job.objects.all()
    addressData = {}
    for job in jobs:
        city = job.city
        if '-' in city:
            address = city.split('-')[0]
        else:
            address = city
        if address not in addressData:
            addressData[address] = 1
        else:
            addressData[address] += 1
    result = []
    for k, v in addressData.items():
        result.append({
            'name': k,
            'value': v
        })
    result.sort(key=lambda x: x['value'], reverse=True)
    return result[:31]

def getCompanyPeople():
    jobs = Job.objects.all()
    data = [0 for x in range(len(companySizes))]
    for i in jobs:
        size = i.comSize
        if size in companySizes:
            index = companySizes.index(size)
            data[index] += 1
    return  companySizes,data