import time
from bs4 import BeautifulSoup
import csv
import re
from datetime import datetime
from random import randint
import aiohttp
import asyncio


_base_url = 'https://www.exportersindia.com'
LIMIT = 10  # connection limit
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


async def login(session, username='info@neptunetradelink.com', password='Neptune@321'):
    """Login into website"""
    endpoint = '/signin.htm'
    headers = {
        'authority': 'www.exportersindia.com',
        'cache-control': 'max-age=0',
        'origin': _base_url,
        'upgrade-insecure-requests': '1',
        'dnt': '1',
        'content-type': 'application/x-www-form-urlencoded',
        'user-agent': USER_AGENT,
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document',
        'referer': f'{_base_url}{endpoint}',
        'accept-language': 'en-US,en;q=0.9,pa;q=0.8',
    }

    data = {
        'email_login': username,
        'mobile_login': '',
        'pass_word': password,
        'mobile_cont_code': 'IN^91',
        'login_by': 'email',
        'id1': '',
        'id5': '',
        'baseurl': _base_url
    }

    async with session.post(f'{_base_url}{endpoint}', headers=headers, data=data) as request:
        response = await request.content.read()
    if 'Incorrect username or password' in response.decode('utf-8'):
        return False
    else:
        return True


async def search_keywords(sema, keyword):
    headers = {
        'authority': 'www.exportersindia.com',
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'dnt': '1',
        'x-requested-with': 'XMLHttpRequest',
        'user-agent': USER_AGENT,
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': 'https://www.exportersindia.com/',
        'accept-language': 'en-US,en;q=0.9,pa;q=0.8',
    }

    params = (
        ('action', 'get_main_serch_kword'),
        ('term', keyword),
    )

    async with sema:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://www.exportersindia.com/catg_search.php', headers=headers, params=params) as response:
                return await response.read()


async def get_total_pages(sema, session, product):
    headers = {
        'authority': 'www.exportersindia.com',
        'upgrade-insecure-requests': '1',
        'dnt': '1',
        'user-agent': USER_AGENT,
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document',
        'referer': 'https://www.exportersindia.com',
        'accept-language': 'en-US,en;q=0.9,pa;q=0.8',
    }

    params = (
        ('srch_catg_ty', 'prod'),
        ('term', product),
        ('cont', 'IN'),
    )
    total_pages = 1
    async with sema:
        # await asyncio.sleep(randint(1, 5))
        async with session.get('https://www.exportersindia.com/search.php', headers=headers, params=params) as request:
            response = await request.content.read()
            soup = BeautifulSoup(response, 'html.parser')
            script_tags = soup.find_all('script')
            pattern = re.compile("var ttl_pages = (\d+);", re.MULTILINE)
            for tag in script_tags:
                total_page_regex = pattern.search(str(tag.string))
                if total_page_regex:
                    total_pages = total_page_regex[1]
                    break
    return int(total_pages)


async def search_result(sema, session, product, page_num):
    headers = {
        'authority': 'www.exportersindia.com',
        'accept': '*/*',
        'dnt': '1',
        'x-requested-with': 'XMLHttpRequest',
        'user-agent': USER_AGENT,
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': f'https://www.exportersindia.com',
        'accept-language': 'en-US,en;q=0.9,pa;q=0.8',
    }

    params = (
        ('term', f'{product}'),
        ('srch_catg_ty', 'prod'),
        ('busty', ''),
        ('cont2', ''),
        ('city', ''),
        ('state_code', ''),
        ('pageno', f'{page_num}'),
        # ('solr_rand_no', '1192371949^'),
        ('action', 'ajax_load_classified'),
    )
    async with sema:
        # await asyncio.sleep(randint(1, 5))
        async with session.get('https://www.exportersindia.com/search.php', headers=headers, params=params) as response:
            return await response.read()


async def get_contact_details(sema, session, member_id):
    headers = {
        'authority': 'www.exportersindia.com',
        'accept': 'text/html, */*; q=0.01',
        'dnt': '1',
        'user-agent': USER_AGENT,
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://www.exportersindia.com',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
        'referer': 'https://www.exportersindia.com/search.php?term=bitumen&srch_catg_ty=prod',
        'accept-language': 'en-US,en;q=0.9,pa;q=0.8',
    }

    params = (
        ('mem_id', f'{member_id}'),
        # ('sid', '0.8610157149425441'),
    )

    data = {
        'action_id': 'action_view_mobile_number',
        'ref_url': 'www.exportersindia.com/search.php?term=bitumen&srch_catg_ty=prod'
    }

    async with sema:
        # await asyncio.sleep(randint(1, 3))
        async with session.post(
                'https://www.exportersindia.com/view_free_member_mobile.php', headers=headers, params=params, data=data
        ) as request:
            response = await request.content.read()
            soup = BeautifulSoup(response, 'html.parser')
            contact_elements = soup.find_all('li', attrs={'class': 'black xlarge'})
            if contact_elements:
                return [contact_elements[1].text.strip(), contact_elements[2].text.strip()]  # name and number


async def search_task(sema, products, gui_queue):
    results = []
    async with sema:
        async with aiohttp.ClientSession() as session:
            await login(session)
            for product in products:
                listings = []
                print(f'Collecting results for product {product}:')
                total_pages = await get_total_pages(sema, session, product)
                current_page = 1
                while current_page <= total_pages:
                    print(f'\tPage {current_page} of {total_pages}')
                    business_listings = await search_result(sema, session, product, current_page)
                    if business_listings:
                        listings.append(business_listings)
                    current_page += 1
                print('Extracting data and contact information:')
                for index, listing in enumerate(listings):
                    print(f'\tPage {index+1} of {len(listings)}')
                    parsed_results = await parse_results(sema, session, listing, product)
                    results += parsed_results
    return results


async def parse_results(sema, session, html_response, category):
    parsed_output = []
    soup = BeautifulSoup(html_response, 'html.parser')
    result_elements = soup.find_all('li', attrs={'class': 'fo classified with_thumb big_text'})
    for element in result_elements:
        output_dict = {
            'Category': category,
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
        try:
            # company name and url
            company_name_element = element.find('p', attrs={'class': re.compile('mb5px ffos xlarge graydark b')})
            if company_name_element:
                output_dict['Company Name'] = company_name_element.a.text.strip()
                company_url_text = company_name_element.a.get('onclick')
                if company_url_text:
                    output_dict['Company URL'] = company_url_text.replace("window.open('", '').replace("', '_blank')", "")

            # address
            address_element = element.find('p', attrs={'class': 'address gray ffos large'})
            if address_element:
                output_dict['City'] = str(address_element.text.replace(' | More...', '')).strip()
                output_dict['Address'] = str(address_element.span.get('data-tooltip')).strip()

            # product
            product_element = element.find('p', attrs={'class': 'ffrc blue xxxxlarge sc lh11em'})
            if product_element:
                output_dict['Product Name'] = product_element.a.text.strip()
                output_dict['Product URL'] = product_element.a.get('href')

            # contact details:
            contact_element = element.find('div', attrs={'class': 'fo contact_bt'})
            if contact_element:
                member_id_url_string = contact_element.a["onclick"]
                member_id_url_pattern = re.compile("ViewMobileNumber\('https://www.exportersindia.com/view_free_member_mobile.php\?mem_id=(\d+)',")
                member_id_regex = member_id_url_pattern.search(member_id_url_string)
                if member_id_regex:
                    member_id = member_id_regex.groups()[0]
                    if member_id:
                        contact_name_number = await get_contact_details(sema, session, member_id)
                        if contact_name_number:
                            output_dict['Name'] = contact_name_number[0]
                            output_dict['Contact No.'] = contact_name_number[1]
        except Exception as e:
            print('\tSkipping because of error:', str(e))
        parsed_output.append(output_dict)

    return parsed_output


class ExporterIndia:
    def __init__(self):
        self.sema = asyncio.Semaphore(LIMIT)
        self.gui_queue = None
        self.file_name = f'exporter_india_{datetime.now().strftime("%Y%m%d%H%M")}.csv'

    def get_categories(self, category_text):
        loop = asyncio.get_event_loop()
        future = asyncio.ensure_future(search_keywords(self.sema, category_text))
        return loop.run_until_complete(future)

    def get_results(self, products):
        loop = asyncio.new_event_loop()
        future = asyncio.ensure_future(search_task(self.sema, products, self.gui_queue), loop=loop)
        output = loop.run_until_complete(future)
        return output

    def save_output(self, output):
        headers = output[0].keys()
        with open(self.file_name, 'w', newline='', encoding='utf-8') as output_file:
            writer = csv.DictWriter(output_file, fieldnames=headers, dialect='excel')
            writer.writeheader()
            writer.writerows(output)
            print(f'Data saved to file: {self.file_name}')


if __name__ == '__main__':
    products = []

    # read categories/products file
    with open('categories.csv', 'r', encoding='utf-8-sig') as input_file:
        reader = csv.reader(input_file)
        next(reader)
        for row in reader:
            if row[0] and row[0] != '':
                products.append(row[0])

    # scrape data
    exporter_india = ExporterIndia()
    results = exporter_india.get_results(products)

    # save output to file
    if results:
        exporter_india.save_output(results)
