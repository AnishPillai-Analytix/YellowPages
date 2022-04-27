import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import json
import os
import csv
from time import sleep
from random import randint


_base_url = 'https://www.tradeindia.com'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Safari/537.36'
output_dict = {
    'Category': '',
    'State': '',
    'City': '',
    'Company Name': '',
    'Contact No.': '',
    'Name': '',
    'Address': '',
    'Product Name': '',
    'Product URL': '',
    'Company URL': '',
}


def new_session(session):
    endpoint = '/login/login.html'
    headers = {
        'authority': 'www.tradeindia.com',
        'dnt': '1',
        'upgrade-insecure-requests': '1',
        'user-agent': USER_AGENT,
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'sec-fetch-site': 'none',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document',
        'accept-language': 'en-US,en;q=0.9,pa;q=0.8',
    }
    session.get(f'{_base_url}{endpoint}', headers=headers)


def get_session_csrf_token(session):
    headers = {
        'authority': 'www.tradeindia.com',
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'dnt': '1',
        'x-requested-with': 'XMLHttpRequest',
        'user-agent': USER_AGENT,
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': 'https://www.tradeindia.com/',
        'accept-language': 'en-US,en;q=0.9,pa;q=0.8',
    }
    response = session.get('https://www.tradeindia.com/ti_forms/components/get_session_details.html', headers=headers)
    response_json = json.loads(response.content.decode('utf-8'))
    return response_json['csrf_token']


def login_with_email(session, username='info@neptunetradelink.com'):
    endpoint = '/login/email_mobile_ajax.html'
    data = {
        'email_mobile': username,
    }
    csrf_token = get_session_csrf_token(session)
    headers = {
        'authority': 'www.tradeindia.com',
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'dnt': '1',
        'x-csrftoken': csrf_token,
        'x-requested-with': 'XMLHttpRequest',
        'user-agent': USER_AGENT,
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://www.tradeindia.com',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': 'https://www.tradeindia.com/',
        'accept-language': 'en-US,en;q=0.9,pa;q=0.8',
    }
    login_request = session.post(url=f'{_base_url}{endpoint}', data=data, headers=headers)
    if 'SUCCESS' in login_request.content.decode('utf-8'):
        return True
    else:
        return False


def login_with_password(session, username='info@neptunetradelink.com', user_id='7075417', password='Neptune123'):
    csrf_token = get_session_csrf_token(session)
    endpoint = '/login/login_action_ajax.html'
    headers = {
        'authority': 'www.tradeindia.com',
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'dnt': '1',
        'x-csrftoken': csrf_token,
        'x-requested-with': 'XMLHttpRequest',
        'user-agent': USER_AGENT,
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://www.tradeindia.com',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': 'https://www.tradeindia.com/',
        'accept-language': 'en-US,en;q=0.9,pa;q=0.8',
    }
    data = {
        'password': password,
        'userid': user_id,
        'username': username,
        'section': '1',
        'came_from': '/'
    }
    login_request = session.post(url=f'{_base_url}{endpoint}', data=data, headers=headers)
    if 'SUCCESS' in login_request.content.decode('utf-8'):
        return True
    else:
        return False


def get_total_results(session, category):
    headers = {
        'authority': 'www.tradeindia.com',
        'upgrade-insecure-requests': '1',
        'dnt': '1',
        'user-agent': USER_AGENT,
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document',
        'referer': 'https://www.tradeindia.com/',
        'accept-language': 'en-US,en;q=0.9,pa;q=0.8',
    }

    params = (
        ('keyword', category),
        ('search_return_url',
         '/search.html?keyword=bitumen&search_return_url=%2Fsearch.html%3Fkeyword%3Dbitumen%2Bplant%26search_return_url%3D%252F%26search_form_id%3D18&search_form_id=18'),
        ('search_form_id', '18'),
    )

    response = session.get('https://www.tradeindia.com/search.html', headers=headers, params=params)
    soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
    total_results_element = soup.find('input', attrs={'id': 'totalData'})
    if total_results_element:
        return int(total_results_element['value'])
    else:
        return 0


def search_products(session, category, page_num):
    headers = {
        'authority': 'www.tradeindia.com',
        'accept': 'text/html, */*; q=0.01',
        'dnt': '1',
        'x-requested-with': 'XMLHttpRequest',
        'user-agent': USER_AGENT,
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': 'https://www.tradeindia.com/',
        'accept-language': 'en-US,en;q=0.9,pa;q=0.8',
    }

    params = (
        ('loggedin_sellers', '0'),
        ('loggedin_profiles_list', '0'),
        ('keyword', f'{category}'),
        ('search_form_id', 'None'),
        ('list_type', 'search'),
        ('paginate', '1'),
        ('page_no', f'{page_num}'),
        ('_', f'{time.time() * 1000}'),
    )
    search_response = session.get('https://www.tradeindia.com/search.html', headers=headers, params=params)
    return search_response.content.decode('utf-8')


def get_contact_details(session, contact_profile_json):
    csrf_token = get_session_csrf_token(session)
    headers = {
        'authority': 'www.tradeindia.com',
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'dnt': '1',
        'x-csrftoken': csrf_token,
        'x-requested-with': 'XMLHttpRequest',
        'user-agent': USER_AGENT,
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://www.tradeindia.com',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': 'https://www.tradeindia.com/',
        'accept-language': 'en-US,en;q=0.9,pa;q=0.8',
    }

    data = {
        'receiver_profile_contact_data': contact_profile_json
    }

    response = session.post(
        'https://www.tradeindia.com/ti_forms/view_contact_details/view_contact_details_action.html', headers=headers,
        data=data
    )
    return response.content.decode('utf-8')


def parse_results(html_response, category):
    parsed_search_result = []
    soup = BeautifulSoup(html_response, 'html.parser')
    product_elements = soup.find_all(
        'div', {'class': 'prod-list relative block wd100 super-list product-list-bg clearfix mb10'}
    )
    for element in product_elements:
        result = output_dict.copy()
        result['Category'] = category

        # company name and url
        company_name_element = element.find('div', attrs={'class': 'company-name'})
        if company_name_element:
            result['Company Name'] = company_name_element.a.text.strip()
            result['Company URL'] = f'{_base_url}{company_name_element.a["href"]}'

        # location and address
        location_element = element.find('div', attrs={'class': 'location'})
        if location_element:
            result['City'] = location_element.find(
                'span', attrs={'class': 'inline-block vertical-align-mid'}
            ).text.strip()
            result['Address'] = location_element.a.div.text.strip()

        # product name and url
        product_name_element = element.find('div', attrs={'class': 'title'})
        if product_name_element:
            result['Product Name'] = product_name_element.a.text.strip()
            result['Product URL'] = f'{_base_url}{product_name_element.a["href"]}'

        # contact details:
        contact_element = element.find('span', attrs={'class': 'phone'})
        if contact_element:
            if contact_element.find('i'):
                result['Contact No.'] = contact_element.i.text
            else:
                profile_element = contact_element.find('span', attrs={'class': 'phone-txt'})
                if profile_element:
                    # extract json from string
                    profile_json = profile_element['onclick'].replace("view_contact_details_popup(", "")
                    profile_json = profile_json.replace(",'view_contact_details')", "")
                    time.sleep(randint(1, 3))
                    contact_details = get_contact_details(session, profile_json)
                    if 'limit exceeded' not in contact_details:
                        contact_details_json = json.loads(get_contact_details(session, profile_json))
                        result['Contact No.'] = f'{contact_details_json.get("mobile")} / {contact_details_json.get("phone")}'
                        result['Name'] = f'{contact_details_json.get("username")} ({contact_details_json.get("desg")})'

        parsed_search_result.append(result)
    return parsed_search_result


def save_output(parsed_results, output_file_path='output.csv'):
    file_name = f'trade_india_{datetime.now().strftime("%Y%m%d%H%M")}.csv'
    headers = parsed_results[0].keys()
    headers_required = False
    if not os.path.isfile(output_file_path):
       headers_required = True
    with open(file_name, 'a', encoding='utf-8', newline='') as output_file:
        writer = csv.DictWriter(output_file, fieldnames=headers, dialect='excel')
        if headers_required:
            writer.writeheader()
        writer.writerows(parsed_results)
        print(f'Data saved to file:{file_name}')


if __name__ == '__main__':
    products = []

    # read categories/products file
    with open('categories.csv', 'r', encoding='utf-8') as input_file:
        reader = csv.reader(input_file)
        next(reader)
        for row in reader:
            if row[0] and row[0] != '':
                products.append(row[0])
    if products:
        output = []
        session = requests.Session()
        sleep(randint(1, 5))
        new_session(session)
        sleep(randint(1, 5))
        if not login_with_email(session):
            print(f'Could not login. Check username and password.')
            exit()
        sleep(randint(1, 5))
        if not login_with_password(session):
            print(f'Could not login. Check username and password.')
            exit()
        sleep(randint(1, 5))

        for product in products:
            # get first page
            print(f'Collecting data from product: {product}')
            total_results = get_total_results(session, category=product)
            print(f'Total results is {total_results}')
            # get additional pages
            current_result_count = 0
            page_num = 1
            while current_result_count < total_results:
                search_response = search_products(session, category=product, page_num=page_num)
                sleep(randint(1, 5))
                page_results = parse_results(search_response, category=product)
                output += page_results
                current_result_count += len(page_results)
                print(f'\tCollected {current_result_count} results of {total_results} from page {page_num}')
                page_num += 1
            else:
                print('\tNo Results')
        if output:
            save_output(output)
