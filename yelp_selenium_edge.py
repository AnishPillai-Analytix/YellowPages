from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from time import sleep
import re
import csv
import os

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


class Yelp():
    def __init__(self, start_date=None, end_date=None):
        self.cwd = os.getcwd()
        self.gui_queue = None
        self.file_name = 'output.csv'
        self.driver = None
        # important urls
        self._base_url = 'https://www.yelp.com/'

    # start chrome with pdf download enabled
    def start_chrome(self, download_pdf=True, download_prompt=False, headless=False):
        print('Yelp: Launching Edge')
        self.driver = webdriver.Edge(executable_path='msedgedriver.exe')
        # self._download_path = os.path.join(os.getcwd(), 'Downloads')
        # if not os.path.isdir(self._download_path):
        #     os.makedirs(self._download_path)
        # options = Options()
        # if headless:
        #     options.add_argument('--headless')
        # options.add_argument('--log_level=3')
        # # options.add_argument('--no-sandbox')
        # # options.add_argument("--remote-debugging-port=9200")
        # options.add_experimental_option(
        #     "prefs", {
        #         "behavior": "allow",
        #         "download.prompt_for_download": download_prompt,
        #         "plugins.always_open_pdf_externally": download_pdf,
        #         # "download.default_directory": self._download_path,
        #         "safebrowsing.enabled": False,
        #         "safebrowsing.disable_download_protection": True
        #     }
        # )
        # options.add_experimental_option('excludeSwitches', ['enable-logging'])
        # self.driver = webdriver.Chrome(options=options,
        #                                executable_path=os.path.join(self.cwd,
        #                                                             # 'Files',
        #                                                             'chromedriver.exe'),
        #                                service_log_path='log.txt')
        # if headless:
        #     # self.enable_download_in_headless_chrome(self.driver, self._download_path)
        #     self.enable_download_in_headless_chrome(self.driver)
        # self.driver.maximize_window()
        return self.driver

    def enable_download_in_headless_chrome(self, driver, download_dir):
        """
        there is currently a "feature" in chrome where
        headless does not allow file download: https://bugs.chromium.org/p/chromium/issues/detail?id=696481
        This method is a hacky work-around until the official chromedriver support for this.
        Requires chrome version 62.0.3196.0 or above.
        """

        # add missing support for chrome "send_command"  to selenium webdriver
        driver.command_executor._commands["send_command"] = ("POST", '/session/$sessionId/chromium/send_command')
        params = {'cmd': 'Page.setDownloadBehavior', 'params': {'behavior': 'allow', 'downloadPath': download_dir}}
        command_result = driver.execute("send_command", params)
        # print("response from browser:")
        # for key in command_result:
        #     print("result:" + key + ":" + str(command_result[key]))

    def search_task(self, locations, categories):
        if not self.driver:
            self.start_chrome(headless=False)
        output = []
        thread_message = thread_message_init.copy()
        list_element_xpath = '//li[@class="lemon--li__373c0__1r9wz border-color--default__373c0__3-ifU"]'
        href_element_xpath = '//a[@class="lemon--a__373c0__IEZFH link__373c0__1G70M link-color--inherit__373c0__3dzpk link-size--inherit__373c0__1VFlE"]'
        next_page_element_xpath = '//span[@class="lemon--span__373c0__3997G icon__373c0__ehCWV icon--24-chevron-right-v2 icon--currentColor__373c0__x-sG2 icon--v2__373c0__1yp8c navigation-button-icon__373c0__1WyUh"]'
        for location in locations:
            for category in categories:
                print(f'Yelp: Downloading data for {category["title"]} in {location["title"]}')
                url_list = []
                endpoint = f'search?find_desc={category["title"]}&find_loc={location["title"]}&ns=1'
                self.driver.get(f'{self._base_url}{endpoint}')
                next_page = self.driver.find_elements_by_xpath(next_page_element_xpath)
                page = 1
                empty_pages = 0
                while next_page and empty_pages < 5:
                    print(f'Yelp: Collecting urls from {page}')
                    sleep(5)
                    href_elements = self.driver.find_elements_by_xpath(href_element_xpath)
                    for number, href_element in enumerate(href_elements):
                        href_link = href_element.get_attribute("href")
                        if r'/adredir?' not in href_link and 'https://www.yelp.com/biz' in href_link:
                            url_list.append(href_link)
                            empty_pages = 0
                            thread_message['total_search_results'] += 1
                            self.gui_queue.put(thread_message) if self.gui_queue else None
                    else:
                        empty_pages += 1
                    current_url = self.driver.current_url
                    next_page[0].click()  # go to next page and collect more results
                    sleep(3)
                    while self.driver.current_url == current_url:  # wait for next page to load
                        sleep(5)
                    next_page = self.driver.find_elements_by_xpath(next_page_element_xpath)
                    page += 1
                    thread_message['completed_pages'] += 1
                    thread_message['total_pages'] += 1
                    self.gui_queue.put(thread_message) if self.gui_queue else None

                if url_list:
                    for index, url in enumerate(url_list):
                        print(f'Yelp: Collecting data from result # {index+1} of {len(url_list)}: {category["title"]}, '
                              f'{location["title"]}')
                        self.driver.get(url)
                        sleep(5)
                        output += self.parse_listing(location, category, url)
                        thread_message['completed_search_results'] += 1
                        self.gui_queue.put(thread_message) if self.gui_queue else None

                thread_message['categories'] += 1
                self.gui_queue.put(thread_message) if self.gui_queue else None

            thread_message['locations'] += 1
            self.gui_queue.put(thread_message) if self.gui_queue else None

        thread_message['%'] = 100
        self.gui_queue.put(thread_message) if self.gui_queue else None

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
                print('Yelp: Data saved to file: output.csv')

        return output

    def parse_listing(self, location, category, url):
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
            'source': url
        }

        # get business name
        business_name_element = self.driver.find_elements_by_class_name(
            'lemon--h1__373c0__2ZHSL heading--h1__373c0__dvYgw undefined heading--inline__373c0__10ozy'
        )
        if business_name_element:
            listing['business_name'] = business_name_element[0].text

        # get address
        address_element = self.driver.find_elements_by_class_name('lemon--address__373c0__2sPac')
        if address_element:
            listing['address'] = address_element[0].text

        # get website
        website_element = self.driver.find_elements_by_xpath(
            '//*[@class="lemon--p__373c0__3Qnnj text__373c0__2Kxyz text-color--normal__373c0__3xep9 '
            'text-align--left__373c0__2XGa- text--offscreen__373c0__2NIm_" and text()="Business website"]'
            '/following-sibling::p/a')
        if website_element:
            listing['dir_website'] = website_element[0].get_attribute("href")

        # get phone number
        phone_element = self.driver.find_elements_by_xpath(
            '//*[@class="lemon--p__373c0__3Qnnj text__373c0__2Kxyz text-color--normal__373c0__3xep9 '
            'text-align--left__373c0__2XGa- text--offscreen__373c0__2NIm_" and text()="Phone number"]'
            '/following-sibling::p'
        )
        if phone_element:
            listing['dir_phone_number'] = phone_element[0].text

        listing['dir_emails'] = self.extract_emails(self.driver.page_source)

        return listing

    def extract_emails(self, response):
        new_emails = set(re.findall(r"mailto:[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\..+?\b", response, re.I))
        if not new_emails:
            new_emails = set(re.findall(r"[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\.com", response, re.I))  # re.I: (ignore case)
        if not new_emails:
            new_emails = set(re.findall(r'/([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)/', response))
        for email in new_emails:
            if 'mailto:' in email:
                new_emails.remove(email)
                new_emails.add(email.replace('mailto:', '', 1))
        return ';'.join(new_emails)


if __name__ == "__main__":
    yelp = Yelp()
    yelp.search_task(categories=[{'title': 'Accountants'}], locations=[{'title': 'San Francisco, CA'}])
