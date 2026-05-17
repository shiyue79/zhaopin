import csv
import os
import random
import time
import re
from selenium import webdriver
import chromedriver_autoinstaller
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import django
import pandas as pd
import pymysql
from pymysql.cursors import DictCursor
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djzhao.settings')
django.setup()


def parse_salary_advanced(salary_text):
    if not salary_text or salary_text in ['面议', '薪资面议', '']:
        return None, None, None
    patterns = [
        # 模式1: xxx-xxxx元·xx薪 (如: 6000-12000元·13薪)
        r'(\d+(?:\.\d+)?)(?:-|~)?(\d+(?:\.\d+)?)?元[·•]?(\d+)?薪?',
        # 模式2: xxk-xxk·xx薪 或 xx-xxk·xx薪 (如: 6k-8k·13薪 或 6-8k·13薪)
        r'(\d+(?:\.\d+)?)(?:k|K)?(?:-|~)(\d+(?:\.\d+)?)(?:k|K)[·•]?(\d+)?薪?',
        # 模式3: xx-xx万·xx薪 (如: 6-12万·13薪)
        r'(\d+(?:\.\d+)?)(?:-|~)?(\d+(?:\.\d+)?)?万[·•]?(\d+)?薪?',
    ]
    for pattern in patterns:
        match = re.search(pattern, salary_text)
        if match:
            groups = match.groups()
            break
    else:
        return None, None, None
    # 解析各组
    if len(groups) >= 2 and groups[1] is not None:
        # 有范围的情况
        min_val = groups[0]
        max_val = groups[1]
        bonus = groups[2] if len(groups) > 2 else None
    else:
        # 单个值的情况
        min_val = groups[0]
        max_val = groups[0]
        bonus = groups[1] if len(groups) > 1 else None

    # 转换为千元单位
    def convert_to_k(value_str, is_wan=False):
        if not value_str:
            return None
        value = float(value_str)
        if is_wan or '万' in salary_text:  # 如果是"万"单位
            return round(value * 10, 1)  # 万->千元 (*10)
        elif 'k' in salary_text.lower():  # 如果是"k"单位
            return value
        else:  # 如果是"元"单位
            return round(value / 1000, 1)

    is_wan_unit = '万' in salary_text
    min_k = convert_to_k(min_val, is_wan_unit)
    max_k = convert_to_k(max_val, is_wan_unit) if max_val else min_k
    bonus_months = int(bonus) if bonus else None
    return min_k, max_k, bonus_months


def insert_job(href, name, salaryMin, salaryMax, salaryBonus,
               location, experience, education, jobType, num,
               tagList, content, company, companySize, companyTag, staff):
    try:
        conn = pymysql.connect(
            host='localhost',
            user='root',
            password='123456',
            database='zhaopin',
            charset='utf8mb4',
            cursorclass=DictCursor,
            connect_timeout=10
        )
        cursor = conn.cursor()
        # SQL语句
        insert_stmt = """INSERT INTO job_copy1 (
            href, name, salaryMin, salaryMax, salaryBonus,
            location, experience, education, jobType, num,
            tagList, content, company, companySize, companyTag, staff
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        data = (href, name, salaryMin, salaryMax, salaryBonus,
                location, experience, education, jobType, num,
                tagList, content, company, companySize, companyTag, staff)
        # print(build_sql_statement(insert_stmt, data))
        cursor.execute(insert_stmt, data)
        print(f"✅ 数据库插入成功")
        conn.commit()
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        return None
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def build_sql_statement(insert_stmt, data):
    params = []
    for i, value in enumerate(data):
        if value is None:
            params.append("NULL")
        elif isinstance(value, str):
            escaped = value.replace("'", "''")
            params.append(f"'{escaped}'")
        elif isinstance(value, (int, float)):
            params.append(str(value))
        elif isinstance(value, bool):
            params.append("1" if value else "0")
        else:
            str_value = str(value)
            escaped_value = str_value.replace("'", "''")
            params.append(f"'{escaped_value}'")
    full_sql = insert_stmt.replace("%s", "{}").format(*params)
    return full_sql

class spider(object):
    def __init__(self, page, work, ind):
        self.page = page
        self.work = work
        self.ind = ind
        # self.spiderUrl='https://www.liepin.com/zhaopin/?city=410&dq=410&currentPage=%s&pageSize=40&workYearCode=%s&industry=%s&compScale=%s&sfrom=search_job_pc&ckId=tfi7gdd7h1gcuz1uv358c8cv5ieztvga&scene=condition&skId=h37dc1sq9oxcabyvf9srp837r6dw8wwb&fkId=tfi7gdd7h1gcuz1uv358c8cv5ieztvga&suggestId='
        self.spiderUrl = 'https://www.liepin.com/zhaopin/?city=410&dq=410&pubTime=&currentPage=%s&pageSize=40&key=&suggestTag=&workYearCode=%s&compId=&compName=&compTag=&industry=%s&salaryCode=&jobKind=&compScale=&compKind=&compStage=&eduLevel=&otherCity=&scene=condition&ckId=8sxprnli59mb0z6c3r98fk34tlzxywv8&skId=edoper6olfluyf09igc6dez8fa1fk5ra&fkId=8sxprnli59mb0z6c3r98fk34tlzxywv8&sfrom=search_job_pc&suggestId='

    def startBrowser(self):
        chromedriver_path = chromedriver_autoinstaller.install()
        service = Service(chromedriver_path)
        options = Options()
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--disable-blink-features=AutomationControlled')
        import random
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{}.0.0.0 Safari/537.36'.format(
            random.randint(110, 120)
        )
        options.add_argument(f'user-agent={user_agent}')
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver, service

    def main(self, page):
        if self.page > 9: return
        href_list = []
        browser, service = self.startBrowser()
        print('开始爬取第' + str(self.page) + '页' + self.spiderUrl % (self.page, self.work, self.ind))
        browser.get(self.spiderUrl % (self.page, self.work, self.ind))
        wait_time = random.uniform(15, 20)
        time.sleep(wait_time)
        divs = browser.find_elements(By.CSS_SELECTOR, "._40108yn42Q")
        y_val = 430
        for index in range(len(divs)):
            if index >= len(divs) - 2:
                break
            real_url = self.get_real_job_url_selenium(browser, y_val)
            y_val += 135
            if real_url:
                href_list.append(real_url)
        browser.quit()
        service.stop()
        if len(href_list) < 35:
            return
        self.page += 1
        self.main(page)

    def get_real_job_url_selenium(self, browser, y_val):
        try:
            original_window = browser.current_window_handle
            time.sleep(3)
            browser.execute_script(f"window.scrollTo(0, {y_val});")
            time.sleep(5)
            x=400
            y=160
            browser.execute_script(f"""
                    var clickEvent = new MouseEvent('click', {{
                        view: window,
                        bubbles: true,
                        cancelable: true,
                        clientX: {x},
                        clientY: {y}
                    }});

                    var element = document.elementFromPoint({x}, {y});
                    if (element) {{
                        element.dispatchEvent(clickEvent);
                    }}
                """)
            WebDriverWait(browser, 10).until(EC.number_of_windows_to_be(2))
            for window_handle in browser.window_handles:
                if window_handle != original_window:
                    browser.switch_to.window(window_handle)
                    break
            href = browser.current_url
            try:
                name = browser.find_element(By.CSS_SELECTOR, ".job-title.ellipsis-2").text.strip()
                salary = browser.find_element(By.CSS_SELECTOR, ".salary").text.strip()
                if salary:
                    salaryMin, salaryMax, salaryBonus = parse_salary_advanced(salary)
                else:
                    salaryMin = salaryMax = salaryBonus = None
                job_properties_div = browser.find_element(By.CSS_SELECTOR, ".job-properties")
                spans = job_properties_div.find_elements(By.CSS_SELECTOR, "span")
                if len(spans) >= 3:
                    location = spans[0].text.strip()
                    experience = spans[2].text.strip()
                    education = spans[4].text.strip()
                else:
                    location = experience = education = None
                jobType = '全职'
                num = None
                try:
                    labels_div = browser.find_element(By.CSS_SELECTOR, ".labels")
                    span_elements = labels_div.find_elements(By.CSS_SELECTOR, "span")
                    job_tags_list = [span.text.strip() for span in span_elements if span.text.strip()]
                except Exception as e:
                    job_tags_list = None
                job_tags = json.dumps(job_tags_list, ensure_ascii=False) if job_tags_list else None
                content = browser.find_element(By.CSS_SELECTOR, "[data-selector='job-intro-content']").get_attribute("textContent")
                try:
                    company = browser.find_element(By.CSS_SELECTOR, ".name.ellipsis-1").text.strip()
                    label_boxes = browser.find_elements(By.CSS_SELECTOR, ".label-box")
                    for box in label_boxes:
                        text = box.text.strip()
                        if "企业行业：" in text:
                            companyTag = text.split("：", 1)[1].strip()
                        elif "人数规模：" in text:
                            companySize = text.split("：", 1)[1].strip()
                except:
                    company = companySize = companyTag = None
                staff = browser.find_element(By.CSS_SELECTOR, ".recruiter-container").find_element(By.CSS_SELECTOR, ".name").text.strip()
                insert_job(href, name, salaryMin, salaryMax, salaryBonus,
                      location, experience, education, jobType, num,
                      job_tags, content, company, companySize, companyTag, staff)
                wait_time = random.uniform(20, 25)
                time.sleep(wait_time)
            except:
                print("获取职位信息失败")
            browser.close()
            browser.switch_to.window(original_window)
            return href
        except Exception as e:
            print(f"获取真实URL失败: {e}")
            return None


if __name__ == '__main__':
    pa=0
    workyear = ['0$1', '1$3', '3$5', '5$10', '10$999']
    industy = [  'H06', 'H07', 'H08', 'H09', 'H10', 'H11', 'H12', 'H13', 'H14', 'H15']
    for work in workyear:
        for ind in industy:
                print(work, ind)
                spiderObj = spider(pa, work, ind + '$' + ind)
                spiderObj.main(pa)
                pa=0
