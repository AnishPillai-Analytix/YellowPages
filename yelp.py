import aiohttp
import asyncio
import json
from bs4 import BeautifulSoup
from random import randint
import re
import csv
from time import perf_counter

base_url = 'http://www.yelp.com/'
limit = 10  # connection limit
proxies = []
thread_message_init = {
    'source': 'Yelp',
    'categories': 0,
    'locations': 0,
    'total_pages': 0,
    'completed_pages': 0,
    'total_search_results': 0,
    'completed_search_results': 0,
    '%': 0,
}


# async def get_proxies():
#     url = 'https://free-proxy-list.net/'
#     async with aiohttp.ClientSession() as session:
#         async with session.get(url) as request:
#             response = await request.text()
#             soup = BeautifulSoup(response, 'html.parser')
#             table = soup.find('table', attrs={'id': 'proxylisttable'})
#             rows = table.tbody.find_all('tr')
#             for row in rows:
#                 cells = row.find_all('td')
#                 if cells[6].text == 'no' and cells[3].text == 'India':
#                     proxies.append(f'{cells[0].text}:{cells[1].text}')
#     return proxies


async def get_response(sema, session, endpoint):
    endpoint = endpoint[1:] if endpoint.startswith('/') else endpoint  # remove extra forward slash
    async with sema:
        await asyncio.sleep(randint(3, 5))
        async with session.get(f'{base_url}{endpoint}') as request:
            response = await request.read()
            # print(request.headers)
            return response.decode('utf-8')


async def search_location(sema, search_text):
    endpoint = f'location_suggest/v2?prefix={search_text}'
    async with aiohttp.ClientSession() as session:
        response = await get_response(sema, session, endpoint)
        locations = json.loads(response)
        return locations["suggestions"]


async def search_categories(sema, search_text):
    endpoint = f'search_suggest/v2/prefetch?prefix={search_text}'
    async with aiohttp.ClientSession() as session:
        response = await get_response(sema, session, endpoint)
        categories = json.loads(response)
        return categories["response"][0]["suggestions"]


async def search_task(locations, categories, gui_queue):
    output = []
    thread_message = thread_message_init.copy()
    sema = asyncio.Semaphore(limit)
    headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'}
    async with aiohttp.ClientSession(headers=headers) as session:
        for location in locations:
            for category in categories:
                business_urls = []
                tasks = []
                count = 0
                page = 0

                endpoint = f'search/snippet?find_desc={category["title"]}&find_loc={location["title"]}'
                endpoint += f'&start=1'
                search_response = await get_response(sema, session, endpoint)
                search_results_json = json.loads(search_response)

                # total results
                total_results = search_results_json['searchPageProps']['searchResultsProps']['paginationInfo'][
                    'totalResults']
                thread_message['total_search_results'] = total_results
                thread_message['total_pages'] = int(total_results/10)  # estimated number of pages(10 results per page)
                thread_message['total_pages'] += 1 if total_results % 10 == 0 else 0  # rounding up
                gui_queue.put(thread_message) if gui_queue else None

                # extract all urls
                while count < total_results:
                    print(f'Collecting urls from page {page+1}')

                    if page > 0:  # ignore first page as it is already fetched
                        endpoint = f'search/snippet?find_desc={category["title"]}&find_loc={location["title"]}'
                        endpoint += f'&start={1 if page == 0 else page * 10}'
                        search_response = await get_response(sema, session, endpoint)
                        search_results_json = json.loads(search_response)
                    search_results = search_results_json['searchPageProps']['searchResultsProps']['searchResults']
                    for result in search_results:
                        try:
                            if type(result['markerKey']) == int:
                                business_urls.append(result['searchResultBusiness']['businessUrl'])
                                count += 1
                        except KeyError:
                            continue
                    page += 1
                    thread_message['completed_pages'] += 1
                    gui_queue.put(thread_message) if gui_queue else None

                # go to each url and extract data
                print(f'Downloading data from {len(business_urls)} urls')
                for index, business_url in enumerate(business_urls):
                    business_responses = await get_response(sema, session, business_url)
                    thread_message['completed_search_results'] += 1
                    if business_responses:
                        output.append(
                            parse_business_data(
                                business_responses,
                                category["title"],
                                location["title"],
                                f'{base_url}{business_url[1:]}'
                            )
                        )
                        print(f'{int(index / len(business_urls) * 100)}% completed\r', end='')

                thread_message['categories'] += 1
                thread_message['%'] = int(thread_message['categories'] / len(categories))
                gui_queue.put(thread_message) if gui_queue else None

            thread_message['locations'] += 1
            thread_message['%'] = int(thread_message['locations']/len(locations))
            gui_queue.put(thread_message) if gui_queue else None

    thread_message['%'] = 100
    gui_queue.put(thread_message) if gui_queue else None
    return output


def parse_business_data(html_response, category, location, endpoint):
    listing = {
        'directory': 'Yelp',
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
        'source': f'{base_url}{endpoint}'
    }

    soup = BeautifulSoup(html_response, 'html.parser')

    business_element_name = soup.find('h1')
    if business_element_name:
        listing['business_name'] = business_element_name.text

    address_element = soup.find('address', attrs={'itemprop': 'address'})
    if address_element:
        listing['address'] = address_element.text

    phone_element = soup.find('span', attrs={'itemprop': 'telephone'})
    if phone_element:
        listing['dir_phone_number'] = phone_element.text

    website_element = soup.find('p', text='Business website')
    if website_element:
        listing['dir_website'] = website_element.next_sibling.text

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
    return ';'.join(new_emails)


class Yelp:
    def __init__(self):
        self.sema = asyncio.Semaphore(limit)
        self.gui_queue = None
        self.file_name = 'output.csv'

    def get_location(self, location_text):
        loop = asyncio.get_event_loop()
        future = asyncio.ensure_future(search_location(self.sema, location_text))
        return loop.run_until_complete(future)

    def get_categories(self, category_text):
        loop = asyncio.get_event_loop()
        future = asyncio.ensure_future(search_categories(self.sema, category_text))
        return loop.run_until_complete(future)

    def get_results(self, locations, categories):
        loop = asyncio.new_event_loop()
        future = asyncio.ensure_future(search_task(locations, categories, self.gui_queue), loop=loop)
        output = loop.run_until_complete(future)
        if output:
            headers = output[0].keys()
            with open(self.file_name, 'a', newline='') as output_file:
                writer = csv.DictWriter(output_file, fieldnames=headers, dialect='excel')
                writer.writeheader()
                writer.writerows(output)
                print('Data saved to file: output.csv')
        return output

    # def get_proxy_list(self):
    #     loop = asyncio.get_event_loop()
    #     future = asyncio.ensure_future(get_proxies())
    #     return loop.run_until_complete(future)


if __name__ == "__main__":
    start_time = perf_counter()

    yelp = Yelp()
    # print(yelp.get_proxy_list())
    locations = yelp.get_location(location_text='San Francisco')
    categories = yelp.get_categories(category_text='Accountant')

    location = [location for location in locations if location['title'] == 'San Francisco, CA']
    category = [category for category in categories if category['title'] == 'Accountants']
    listings = yelp.get_results(locations=location, categories=category)
    if listings:
        headers = listings[0].keys()
        with open('output.csv', 'a', newline='') as output_file:
            writer = csv.DictWriter(output_file, fieldnames=headers, dialect='excel')
            writer.writeheader()
            writer.writerows(listings)
    end_time = perf_counter()
    print(f'Time Taken {end_time-start_time} seconds')