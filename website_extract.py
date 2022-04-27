import aiohttp
import asyncio
from bs4 import BeautifulSoup, NavigableString
import re
import html2text
from urllib.parse import urlparse, urljoin

limit = 10


async def scrape_page(session, url, sema):
    try:
        async with sema:
            async with session.get(url) as request:
                if request.status == 200:
                    response = await request.read()
                    return response.decode('utf-8')
                else:
                    return None
    except Exception as e:
        print(f'error in {url}', str(e))
        return f'error in {url}: {str(e)}'


async def scrap_link(response):
    soup = BeautifulSoup(response, 'html.parser')
    if soup.body:
        links = soup.body.find_all('a')
        if links:
            for link in links:
                if isinstance(link, NavigableString):
                    continue
                if "href" in link.attrs and 'contact' in str(link.text).lower():
                    return link.attrs['href']
        else:
            return None
    else:
        return None


def extract_emails(response):
    new_emails = set(re.findall(r"mailto:[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\..+?\b", response, re.I))
    if not new_emails:
        new_emails = set(re.findall(r"[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\.com", response, re.I)) # re.I: (ignore case)
        if not new_emails:
            new_emails = set(re.findall(r'/([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)/', response))
    return new_emails


def extract_phones(response):
    phones = set(re.findall("[\(]*?\d{3}[\)\.\s-]+?\d{3}[-\.\s]+?\d{4}", response, re.DOTALL))
    if phones:
        return phones
    return None


async def run_task(url, session, sema):
    emails = None
    phones = None

    if url != '' and url:
        try:
            response = await scrape_page(session, url, sema)
            if not str(response).startswith('error in ') and response:
                response_text = html2text.html2text(response)
                emails = extract_emails(response_text)
                phones = extract_phones(response_text)
                if not emails or not phones:
                    link = await scrap_link(response)
                    if link:
                        base_url = urlparse(url)
                        print('Going to: ', urljoin(f'{base_url.scheme}://{base_url.netloc}', link))
                        contact_page_response = await scrape_page(session, urljoin(f'{base_url.scheme}://{base_url.netloc}', link))
                        if contact_page_response:
                            contact_page_text = html2text.html2text(contact_page_response)
                            if not emails:
                                emails = extract_emails(contact_page_text)
                                if not emails:
                                    emails = extract_emails(contact_page_response)
                            if not phones:
                                phones = extract_phones(contact_page_text)
            if phones:
                phones = '; '.join(phones).replace('\n', '')
                print(f'\tPhone number found in website: {url}\n', phones)
            if emails:
                emails = '; '.join(emails).replace('mailto:', '')
                print(f'Email id found in website:{url}', emails)
        except Exception:
            pass
    return phones, emails


async def main(sema, websites):
    connector = aiohttp.TCPConnector(limit=25, limit_per_host=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for url in websites:
            tasks.append(run_task(url, session, sema))
        output = await asyncio.gather(*tasks)
    return output


def extract_info(websites):
    sema = asyncio.Semaphore(limit)
    try:
        loop = asyncio.get_event_loop()
    except Exception:
        loop = asyncio.new_event_loop
    future = asyncio.ensure_future(main(sema, websites), loop=loop)
    output = loop.run_until_complete(future)
    return output
