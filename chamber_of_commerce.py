import aiohttp
import asyncio
import json
from bs4 import BeautifulSoup
from random import randint
import re
import csv
import os
# from website_extract import extract_info


base_url = 'https://www.chamberofcommerce.com/'
limit = 10  # connection limit
thread_message_init = {
    'Page URL': '',
    'Stock (Lot#)': '',
    'Heading': '',
    'VIN': '',
    'Year': '',
    'MakeName': '',
    'ModelName': '',
    'Engine_Description': '',
    'Engine_No.': '',
    'Exterior Color': '',
    'Interior Color': '',
    'Speed': '',
    'Transmission': '',
    'Status': '',
    'Mileage': '',
    'Listing Description': '',
    'Image_name': '',
}


async def search_location(sema, search_text):
    endpoint = f'search/citystatesearch?where={search_text.split(" ")[0]}'
    async with aiohttp.ClientSession() as session:
        async with sema:
            async with session.get(f'{base_url}{endpoint}') as request:
                response = await request.read()
                result = json.loads(response.decode('utf-8'))
                locations = result['result']['result']
                return [loc for loc in locations if search_text in loc['name']]


async def search_categories(sema, search_text):
    endpoint = f'search/businesssearch?what={search_text}'
    async with aiohttp.ClientSession() as session:
        async with sema:
            async with session.get(f'{base_url}{endpoint}') as request:
                response = await request.read()
                result = json.loads(response.decode('utf-8'))
                categories = result['result']['result']
                return categories


async def search_task(locations, categories, gui_queue):
    sema = asyncio.Semaphore(limit)
    output = []
    thread_message = thread_message_init.copy()
    async with aiohttp.ClientSession() as session:
        for location in locations:
            location_endpoint = location['slug']
            for category in categories:
                business_urls = []
                tasks = []
                print(f'CoC: Downloading data for {category["name"]} in {location["name"]}')
                category_endpoint = category['slug']
                endpoint = f'united-states/{location_endpoint}/{category_endpoint}'
                response = await get_response(sema, session, endpoint)
                total_pages = get_total_pages(response)
                thread_message['total_pages'] += total_pages
                gui_queue.put(thread_message) if gui_queue else None
                business_urls += parse_search_result(response)
                thread_message['total_search_results'] = len(business_urls)
                thread_message['completed_pages'] += 1
                print(f'CoC: Collecting urls from page 1')
                gui_queue.put(thread_message) if gui_queue else None

                # get additional pages
                current_page = 2
                while current_page <= total_pages:
                    print(f'CoC: Collecting urls from page {current_page}')
                    next_page_endpoint = f'{endpoint}/?pg={current_page}'
                    response = await get_response(sema, session, next_page_endpoint)
                    results = parse_search_result(response)
                    business_urls += results
                    current_page += 1

                    thread_message['total_search_results'] += len(results)
                    thread_message['completed_pages'] += 1
                    gui_queue.put(thread_message) if gui_queue else None

                if business_urls:
                    print(f'CoC: Collecting data from {len(business_urls)} urls')
                    for business_endpoint in business_urls:
                        task = asyncio.ensure_future(get_response(sema, session, business_endpoint, thread_message, gui_queue))
                        tasks.append(task)
                    if tasks:
                        business_htmls = await asyncio.gather(*tasks)
                        if business_htmls:
                            for index, html in enumerate(business_htmls):
                                print(f'CoC: {int(index/len(business_urls)*100)}% completed\r', end='')
                                output.append(parse_listing(html, category, location, business_urls[index][1:]))

                thread_message['categories'] += 1
                thread_message['%'] = int(thread_message['categories'] / len(categories))
                gui_queue.put(thread_message) if gui_queue else None

            thread_message['locations'] += 1
            thread_message['%'] = int(thread_message['locations']/len(locations))
            gui_queue.put(thread_message) if gui_queue else None

    thread_message['%'] = 67
    gui_queue.put(thread_message) if gui_queue else None

    # if output:
    #     print('Extracting emails and phone numbers from client websites')
    #     for index, i in enumerate(output):
    #         if i['dir_website'] != '' and i['dir_website'] != ' ' and i['dir_website']:
    #             output[index]['phone'], output[index]['email'] = extract_info(i['dir_website'])

    thread_message['%'] = 100
    gui_queue.put(thread_message) if gui_queue else None

    return output


async def get_response(sema, session, endpoint, thread_message=None, gui_queue=None):
    if endpoint.startswith('/'):
        endpoint = endpoint[1:]
    async with sema:
        await asyncio.sleep(randint(1, 3))
        async with session.get(url=f'{base_url}{endpoint}') as request:
            response = await request.read()
            if gui_queue:
                thread_message['completed_search_results'] += 1
                gui_queue.put(thread_message)
            return response.decode('utf-8')


def parse_search_result(html_response):
    results = []
    soup = BeautifulSoup(html_response, 'html.parser')
    business_listings = soup.find_all('div', attrs={'class': 'bussiness_name'})  # class name is spelled incorrectly in website
    for business in business_listings:
        results.append(business.a["href"])
    return results


def parse_listing(html_response, category, location, endpoint):
    listing = {
        'directory': 'Chamber of Commerce',
        'category': category['name'],
        'location': location['name'],
        'business_name': None,
        'address': None,
        'dir_phone_number': None,
        'contact_person': None,
        'dir_emails': None,
        'dir_website': None,
        'website_email': None,
        'website_phone_number': None,
        'source': f'{base_url}{endpoint}'
    }

    soup = BeautifulSoup(html_response, 'html.parser')
    # soup = soup.prettify(formatter=lambda s: s.replace(u'\xa0', ' '))

    # business name
    name_div = soup.find('div', attrs={'class': 'profile_business_name'})
    if name_div:
        listing['business_name'] = name_div.text.strip()

    # address and phone number
    profile_div = soup.find('div', attrs={'class': 'profile_right_details'})
    if profile_div:
        address_div = profile_div.find_all('div', 'detail_text')
        if address_div:
            listing['address'] = address_div[0].text.strip(' ')
    phone_div = soup.find('span', attrs={'class': 'd-block d-sm-none phone-align'})
    if phone_div:
        listing['dir_phone_number'] = phone_div.text.strip()

    # contact person
    contact_div = soup.find('div', attrs={'class': 'key_notest_list'})
    if contact_div:
        listing['contact_person'] = contact_div.text.replace('PHONE:', '').strip()

    # emails
    listing['dir_emails'] = extract_emails(html_response)

    return listing


def extract_emails(response):
    new_emails = set(re.findall(r"mailto:[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\..+?\b", response, re.I))
    if not new_emails:
        new_emails = set(re.findall(r"[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\.com", response, re.I)) # re.I: (ignore case)
    if not new_emails:
        new_emails = set(re.findall(r'/([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)/', response))
    for email in new_emails:
        if 'mailto:' in email:
            new_emails.remove(email)
            new_emails.add(email.replace('mailto:', '', 1))
    new_emails.discard('membership@chamberofcommerce.com')
    return ';'.join(new_emails)


def get_total_pages(html_response):
    last_page_num = 1
    soup = BeautifulSoup(html_response, 'html.parser')
    pages_div = soup.find('div', attrs={'class': 'paging'})
    if pages_div:
        pages = pages_div.find_all('a')
        for page in pages:
            if str(page.text).isdigit():
                if int(page.text) > last_page_num:
                    last_page_num = int(page.text)
    return last_page_num


class ChamberOfCommerce:
    def __init__(self):
        self.sema = asyncio.Semaphore(limit)
        self.gui_queue = None
        self.file_name = 'output.csv'

    def get_location(self, location_text):
        loop = asyncio.get_event_loop()
        future = asyncio.ensure_future(search_location(self.sema, location_text))
        output = loop.run_until_complete(future)
        return output

    def get_categories(self, category_text):
        loop = asyncio.get_event_loop()
        future = asyncio.ensure_future(search_categories(self.sema, category_text))
        return loop.run_until_complete(future)

    def get_results(self, locations, categories):
        loop = asyncio.new_event_loop()
        future = asyncio.ensure_future(search_task(locations, categories, self.gui_queue), loop=loop)
        output = loop.run_until_complete(future)
        if output:
            if os.path.isfile(self.file_name):
                headers_required = False
            else:
                headers_required = True

            headers = output[0].keys()
            with open(self.file_name, 'a', newline='') as output_file:
                writer = csv.DictWriter(output_file, fieldnames=headers, dialect='excel')
                if headers_required:
                    writer.writeheader()
                writer.writerows(output)
                print('CoC: Data saved to file: output.csv')
        return output


if __name__ == "__main__":
    loop = asyncio.new_event_loop()

    coc = ChamberOfCommerce()
    locations = coc.get_location(location_text='Los Angeles')
    categories = coc.get_categories(category_text='Accountants')

    location = [location for location in locations if location['name'] == 'Los Angeles, California']
    category = [category for category in categories if category['name'] == 'Accountants']
    listings = coc.get_results(locations=location, categories=category)
    if listings:
        headers = listings[0].keys()
        with open('output.csv', 'a', newline='') as output_file:
            writer = csv.DictWriter(output_file, fieldnames=headers, dialect='excel')
            writer.writeheader()
            writer.writerows(listings)
