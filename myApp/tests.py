"""
educations, workEx = getSelfInfo.getPageDate()
defaultEdu = "不限"
defaultEpx = "不限"
if request.GET.get('education'):
    defaultEdu = request.GET.get('education')
if request.GET.get('experience'):
    defaultEpx = request.GET.get('experience')
educations, workEx = getSalaryCharData.getEduForEpx()
return render(request, 'salaryChar.html', {
    'userInfo': userInfo,
    'pageDate': {
        'educations': educations,
        'workEx': workEx,
        'defaultEdu': defaultEdu,
        'defaultEpx': defaultEpx
    }
})
< div


class ="row" >

< div


class ="col-md-12" >

< div


class ="panel panel-default" data-collapsed="0" >

< div


class ="panel-heading" >

< div


class ="panel-title" > 查询条件 < / div >

< div


class ="panel-options" >

< a
href = "#"
data - rel = "collapse" > < i


class ="entypo-down-open" > < / i > < / a >

< a
href = "#"
data - rel = "reload" > < i


class ="entypo-arrows-ccw" > < / i > < / a >

< / div >
< / div >
< div


class ="panel-body" >

< form
action = "/myApp/salary/"
method = "GET" >
< div


class ="row" >

< div


class ="form-group" style="display: flex; align-items: center; margin-right: 30px;" >

< label


class ="control-label"


style = "margin-left: 20px; margin-top:5px" > 意向岗位 < / label >
< div


class ="col-sm-2" >

< input
type = "text"
name = "work"


class ="form-control"


placeholder = "请输入意向岗位名称" >
< / div >
< label


class ="control-label" style="margin-left: 20px; margin-top:5px" > 学历 < / label >

< div


class ="col-sm-2" >

< select
name = "education"


class ="form-control" >


{ % if pageDate.defaultEdu == "不限" %}
< option
value = "不限"
selected > 不限 < / option >
{ % else %}
< option
value = "不限" > 不限 < / option >
{ % endif %}
{ %
for item in pageDate.educations %}
{ % if item == pageDate.defaultEdu %}
< option
value = "{{ item }}"
selected > {{item}} < / option >
{ % else %}
< option
value = "{{ item }}" > {{item}} < / option >
{ % endif %}
{ % endfor %}
< / select >
< / div >
< label


class ="control-label"


style = "margin-left: 20px; margin-top:5px" > 工作经验 < / label >
< div


class ="col-sm-2" >

< select
name = "experience"


class ="form-control" >


{ % if pageDate.defaultEpx == "不限" %}
< option
value = "不限"
selected > 不限 < / option >
{ % else %}
< option
value = "不限" > 不限 < / option >
{ % endif %}
{ %
for item in pageDate.workEx %}
{ % if item == pageDate.defaultEpx %}
< option
value = "{{ item }}"
selected > {{item}} < / option >
{ % else %}
< option
value = "{{ item }}" > {{item}} < / option >
{ % endif %}
{ % endfor %}
< / select >
< / div >
< button
type = "submit"


class ="btn btn-primary" style="margin-left: auto;" > 查询

< / button >
< / div >
< / div >
< / form >
< / div >
< / div >
< / div >
< / div >
"""