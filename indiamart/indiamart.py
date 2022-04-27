import aiohttp
import asyncio
import json
from bs4 import BeautifulSoup
from random import randint
import re
import csv
import os

base_url = 'https://www.chamberofcommerce.com/'
limit = 1  # connection limit
thread_message_init = {
    'Category': '',
    'State': '',
    'City': '',
    'Company Name': '',
    'Contact No.': '',
    'Name': '',
    'Address': '',
    'Product URL': '',
    'Company URL': '',
}


async def identify(sema, session, username):
    url = 'https://login.indiamart.com/user/identify/'
    headers = {
        'authority': 'login.indiamart.com',
        'accept': '*/*',
        'dnt': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://www.indiamart.com',
        'sec-fetch-site': 'same-site',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': 'https://www.indiamart.com/',
        'accept-language': 'en-US,en;q=0.9,pa;q=0.8',
    }

    data = {
        'username': username,
        'iso': 'IN',
        'modid': 'IMHOME',
        'format': 'JSON',
        'create_user': '1',
        'originalreferer': 'https://www.indiamart.com/',
        'GEOIP_COUNTRY_ISO': 'IN',
        # 'ip': '103.238.106.10',
        'screen_name': 'Sign IN Form Desktop',
        'Lat_val': '',
        'Long_val': '',
        'country': 'India'
    }
    async with sema:
        await asyncio.sleep(randint(1, 3))
        async with session.post(
                url=url,
                data=data,
                headers=headers,
        ) as request:
            response = await request.read()
            print(response)


async def login(sema, session, username, password, gui_queue=None):
    status = None
    headers = {
        'authority': 'login.indiamart.com',
        'accept': '*/*',
        'dnt': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://my.indiamart.com',
        'sec-fetch-site': 'same-site',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': 'https://my.indiamart.com/userprofile/contactprofile/',
        'accept-language': 'en-US,en;q=0.9,pa;q=0.8',
    }

    data = {
        'token': 'imobile@15061981',
        'username': username,
        'modid': 'MY',
        'format': 'JSON',
        'password': password,
        'country_iso': 'IN',
        'ip': '103.249.233.22',
        'gacookie': 'GA1.2.905863830.1591721416'
    }

    async with sema:
        await asyncio.sleep(randint(1, 3))
        async with session.post(
                url=f'https://login.indiamart.com/user/authenticate/',
                data=data,
                headers=headers,
        ) as request:
            response = await request.read()
            if 'message' in response.decode('utf-8'):
                message = json.loads(response.decode('utf-8'))['message']
                status = False
            else:
                message = 'Logged in successfully!'
                status = True
            if gui_queue:
                gui_queue.put(message)
    if status:
        async with session.get('https://my.indiamart.com/userprofile/contactprofile/') as request:
            response = await request.read()
            print(response.decode('utf-8'))
    return status, session


async def search_location(sema, location_text):
    url = f'https://suggest.imimg.com/suggest/suggest.php?q={location_text}&tag=suggestions&limit=40&type=city&fields=state%2Cid%2Cstateid%2Cflname%2Calias&display_fields=value%2C%3Dstate&display_separator=%2C+&match=fuzzy&v=357'
    async with aiohttp.ClientSession() as session:
        async with sema:
            async with session.get(url) as request:
                response = await request.read()
                result = json.loads(response.decode('utf-8'))
                locations = result['city']
                return locations


async def search_categories(sema, search_text):
    url = f'https://suggest.imimg.com/suggest/suggester.php?q={search_text}&tag=suggestions&limit=40&type=product&fields=type_data%2Csort_order&match=fuzzy&catid=197&mcatid=1454&v=357'
    async with aiohttp.ClientSession() as session:
        async with sema:
            async with session.get(url) as request:
                response = await request.read()
                result = json.loads(response.decode('utf-8'))
                categories = result['product']
                return categories


async def search_task(locations, categories, username, password, gui_queue):
    sema = asyncio.Semaphore(limit)
    output = []
    async with aiohttp.ClientSession() as session:
        await identify(sema, session, username)
        login_status, _session = await login(sema, session, username, password, gui_queue)
        if login_status:
            for location in locations:
                for category in categories:
                    page_num = 2
                    tasks = []
                    print(f'Downloading data for {category["value"]} in {location["value"]}')
                    await get_response(sema, session, 'https://dir.indiamart.com/search.mp?ss=bitumen&src=as-popular%3Akwd%3Dbitumen%3Apos%3D1%3Acat%3D-2%3Amcat%3D-2&cq=doda&cq_src=')
                    url = f'https://dir.indiamart.com/search.mp/next?glid=24608882&ss={category["value"]}&c=IN&scroll=1&language=en&city_only=&pr=0&cq={location["value"]}&pg={page_num}&frsc={(page_num-1)*14}&video='
                    response_html = await get_response(sema, session, url)
                    response_json = json.loads(response_html)
                    total_pages = get_total_pages(response_json["page_var"])  # 14 results per page
                    if total_pages:
                        while page_num < total_pages:
                            print(f'Downloading data from page {page_num}')
                            url = f'https://dir.indiamart.com/search.mp/next?glid=24608882&ss={category["value"]}&c=IN&scroll=1&language=en&city_only=&pr=0&cq={location["value"]}&pg={page_num}&frsc={page_num*14}&video='
                            response_html = await get_response(sema, session, url)
                            # if 'authentication token is missing' in response_html.lower():
                            #
                            #     login_status, session = await login(sema, session, username, password, gui_queue)
                            #     response_html = await get_response(sema, session, url)
                            response_json = json.loads(response_html)
                            result_list = parse_result(
                                response_json["content"],
                                category=category["value"],
                                city=location["value"],
                                state=location["data"]["state"],
                            )
                            for result_json in result_list:
                                if result_json["Company URL"] and result_json["Company URL"] != '' and 'indiamart.com' in result_json["Company URL"]:
                                    company_details_response = await get_response(sema, session,  result_json["Company URL"])
                                    result_json["Name"] = get_contact_name(company_details_response)
                                print(result_json)
                                output += result_json
                            page_num += 1
    return output


async def get_response(sema, session, url, gui_queue=None):
    headers = {
        'authority': 'login.indiamart.com',
        'accept': '*/*',
        'dnt': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://my.indiamart.com',
        'sec-fetch-site': 'same-site',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': 'https://my.indiamart.com/userprofile/contactprofile/',
        'accept-language': 'en-US,en;q=0.9,pa;q=0.8',
    }
    async with sema:
        await asyncio.sleep(randint(1, 3))
        async with session.get(url=url) as request:
            response = await request.read()
            return response.decode('utf-8')


def get_total_pages(html_string):
    regex = re.search(r"ims.r = '(\d+)'", html_string)
    if regex:
        return int(regex[1])/14
    else:
        return 0


def parse_result(html_response, category, city, state):
    parsed_results = []
    soup = BeautifulSoup(html_response, 'html.parser')
    result_divs = soup.find_all('div', attrs={'class': 'f-div r-e-h ft bdr1'})
    for result_div in result_divs:
        thread_message = thread_message_init.copy()
        thread_message['Category'] = category
        thread_message['City'] = city
        thread_message['State'] = state
        #  company details
        company_div = result_div.find('div', attrs={'class': 'r-cl b-gry'})
        if company_div:
            thread_message['Company Name'] = company_div.a.h4.text.strip()
            thread_message['Company URL'] = company_div.a['href']
            city_div = company_div.find('p', attrs={'class': 'sm clg'})
            if city_div:
                thread_message['Address'] = city_div.text.strip()
        # product_link
        product_link_div = result_div.find('span', attrs={'class': 'lg elps'})
        if product_link_div:
            thread_message['Product URL'] = product_link_div.a['href']
        # phone
        phone_div = result_div.find('span', attrs={'class': 'pns_h duet'})
        if phone_div:
            thread_message['Contact No.'] = phone_div.text.strip()
        parsed_results.append(thread_message)
    return parsed_results


def get_contact_name(html_response):
    soup = BeautifulSoup(html_response, 'html.parser')
    name_divs = soup.find_all('p', attrs={'class': 'FM_Lsp4 FM_f18 Fm_lh10 FM_wrd FM_fl FM_w350'})
    if name_divs:
        return name_divs[0].text.strip()
    return None


class Indiamart:
    def __init__(self):
        self.sema = asyncio.Semaphore(limit)
        self.gui_queue = None
        self.file_name = 'output.csv'
        self.credentials_file = 'credentials.json'

        with open('credentials.json', 'r') as credentials_file:
            credentials = json.load(credentials_file)
            self.username = credentials['username']
            self.password = credentials['password']

    def get_location(self, location_text):
        loop = asyncio.get_event_loop()
        future = asyncio.ensure_future(search_location(self.sema, location_text))
        output = loop.run_until_complete(future)
        return output

    def get_categories(self, category_text):
        loop = asyncio.get_event_loop()
        future = asyncio.ensure_future(search_categories(self.sema, category_text))
        return loop.run_until_complete(future)

    def search_results(self, locations, categories):
        loop = asyncio.get_event_loop()
        future = asyncio.ensure_future(search_task(locations, categories, self.username, self.password, self.gui_queue))
        output = loop.run_until_complete(future)
        return output

    def save_output(self, output):
        headers_needed = False
        headers = output[0]
        if not os.path.isfile(self.file_name):
            headers_needed = True
        with open(self.file_name, 'a', newline='') as output_file:
            writer = csv.DictWriter(output_file, fieldnames=headers)
            if headers_needed:
                writer.writeheader()
            writer.writerows(output)


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    indiamart = Indiamart()
    locations = indiamart.get_location(location_text='Doda')
    categories = indiamart.get_categories(category_text='bitumen')

    location = [location for location in locations if location['value'] == 'Dodamarg']
    category = [category for category in categories if category['value'] == 'bitumen']
    output = indiamart.search_results(location, category)
    if output:
        indiamart.save_output(output)

    print(locations)
    print(categories)
