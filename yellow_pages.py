import aiohttp
import asyncio
from bs4 import BeautifulSoup
from random import randint
import re
import csv
import os

# from website_extract import extract_info


base_url = 'https://www.yellowpages.com/'
limit = 10  # connection limit
thread_message_init = {
    'source': 'Yellow Pages',
    'categories': 0,
    'locations': 0,
    'total_pages': 0,
    'completed_pages': 0,
    'total_search_results': 0,
    'completed_search_results': 0,
    '%': 0,
}


async def get_response(sema, session, endpoint, thread_message=None, gui_queue=None):
    endpoint = endpoint[1:] if endpoint.startswith('/') else endpoint  # remove extra forward slash
    async with sema:
        await asyncio.sleep(randint(1, 3))
        async with session.get(f'{base_url}{endpoint}') as request:
            response = await request.read()
            if gui_queue:
                thread_message['completed_search_results'] += 1
                gui_queue.put(thread_message)
            return response.decode('utf-8')


async def search_location(sema, search_text):
    endpoint = f'autosuggest/location.html?location={search_text}'
    async with aiohttp.ClientSession() as session:
        response = await get_response(sema, session, endpoint)
        soup = BeautifulSoup(response, 'html.parser')
        locations_li = soup.find_all('li')
        return [location['data-value'] for location in locations_li]


async def search_categories(sema, search_text):
    endpoint = f'autosuggest/headings.html?text={search_text}'
    async with aiohttp.ClientSession() as session:
        response = await get_response(sema, session, endpoint)
        soup = BeautifulSoup(response, 'html.parser')
        categories_li = soup.find_all('li')
        return [category['data-value'] for category in categories_li]


async def search_task(locations, categories, gui_queue):
    sema = asyncio.Semaphore(limit)
    output = []
    thread_message = thread_message_init.copy()
    async with aiohttp.ClientSession() as session:
        for location in locations:
            for category in categories:
                business_urls = []
                tasks = []
                # get first page
                print(f'Yellow Pages: Downloading data for {category} in {location}')
                print('Yellow Pages: Collecting urls from page 1')
                endpoint = f'search?search_terms={category}&geo_location_terms={location}'
                response = await get_response(sema, session, endpoint)
                thread_message['completed_pages'] += 1
                thread_message['total_pages'] += 1
                gui_queue.put(thread_message) if gui_queue else None
                soup = BeautifulSoup(response, 'html.parser')
                business_urls += soup.find_all('a', attrs={'class': 'business-name'})
                thread_message['total_search_results'] = len(business_urls)
                # if next pages exist, add to list
                next_page = 2
                while is_next_page(response):
                    print(f'Yellow Pages: Collecting urls from page {next_page}')
                    next_page_endpoint = f'{endpoint}&page={next_page}'
                    response = await get_response(sema, session, next_page_endpoint)
                    soup = BeautifulSoup(response, 'html.parser')
                    results = soup.find_all('a', attrs={'class': 'business-name'})
                    business_urls += results
                    next_page += 1

                    # update status in ui
                    thread_message['total_search_results'] += len(results)
                    thread_message['completed_pages'] += 1
                    thread_message['total_pages'] += 1
                    gui_queue.put(thread_message) if gui_queue else None

                # get data from urls
                print(f'Yellow Pages: Downloading data from {len(business_urls)} urls')
                for business_url in business_urls:
                    task = asyncio.ensure_future(
                        get_response(sema, session, business_url["href"], thread_message, gui_queue))
                    tasks.append(task)
                if tasks:
                    business_details_htmls = await asyncio.gather(*tasks)
                    for index, business_html in enumerate(business_details_htmls):
                        print(f'Yellow Pages: {int(index / len(business_urls) * 100)}% completed\r', end='')
                        output.append(
                            parse_business_html(business_html, category, location, business_urls[index]["href"]))

                thread_message['categories'] += 1
                thread_message['%'] = int(thread_message['categories'] / len(categories))
                gui_queue.put(thread_message) if gui_queue else None

            thread_message['locations'] += 1
            thread_message['%'] = int(thread_message['locations'] / len(locations))
            gui_queue.put(thread_message) if gui_queue else None

    # thread_message['%'] = 67
    # gui_queue.put(thread_message) if gui_queue else None
    # #
    # if output:
    #     print('Extracting emails and phone numbers from client websites')
    #     for index, i in enumerate(output):
    #         if i['dir_website'] != '' and i['dir_website'] != ' ' and i['dir_website']:
    #             output[index]['phone'], output[index]['email'] = extract_info(i['dir_website'])

    thread_message['%'] = 100
    gui_queue.put(thread_message) if gui_queue else None

    return output


def is_next_page(html_response):
    if '<a class="next ajax-page"' in html_response:
        return True
    else:
        return False


def parse_business_html(business_html, category, location, url):
    listing = {
        'directory': 'Yellow Pages',
        'category': category,
        'location': location,
        'business_name': None,
        'address': None,
        'dir_phone_number': None,
        'contact_person': None,
        'dir_emails': None,
        'dir_website': None,
        'website_email': None,
        'website_phone_number': None,
        'source': url
    }

    soup = BeautifulSoup(business_html, 'html.parser')

    # name of business
    business_name_element = soup.find('h1')
    if business_name_element:
        listing['business_name'] = business_name_element.text

    # address
    address_element = soup.find('h2', attrs={'class': 'address'})
    if address_element:
        listing['address'] = address_element.text

    # phone
    phone_element = soup.find('p', attrs={'class': 'phone'})
    if phone_element:
        listing['dir_phone_number'] = phone_element.text

    # email
    listing['dir_emails'] = extract_emails(business_html)

    # website
    website_element = soup.find('a', attrs={'class': 'primary-btn website-link'})
    if website_element:
        listing['dir_website'] = website_element["href"]

    return listing


def extract_emails(response):
    new_emails = set(re.findall(r"mailto:[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\..+?\b", response, re.I))
    if not new_emails:
        new_emails = set(re.findall(r"[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\.com", response, re.I))  # re.I: (ignore case)
    if not new_emails:
        new_emails = set(re.findall(r'/([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)/', response))
    for email in new_emails:
        if 'mailto:' in email:
            new_emails.remove(email)
            new_emails.add(email.replace('mailto:', '', 1))
    # new_emails.discard('membership@chamberofcommerce.com')
    return ';'.join(new_emails)


class YellowPages:
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
        output = loop.run_until_complete(future)
        return output

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
                print('Data saved to file: output.csv')
        return output


if __name__ == "__main__":
    yp = YellowPages()
    locations = yp.get_location(location_text='San Francisco')
    categories = yp.get_categories(category_text='Accountant')

    location = [location for location in locations if location == 'San Francisco, CA']
    category = [category for category in categories if category == 'Accountants-Certified Public']
    listings = yp.get_results(locations=location, categories=category)
    if listings:
        headers = listings[0].keys()
        with open('output.csv', 'a', newline='') as output_file:
            writer = csv.DictWriter(output_file, fieldnames=headers, dialect='excel')
            writer.writeheader()
            writer.writerows(listings)
