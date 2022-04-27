from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from time import sleep
import re
import csv
import json
import os
from bs4 import BeautifulSoup


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


class Indiamart():
    def __init__(self, start_date=None, end_date=None):
        self.cwd = os.getcwd()
        self.gui_queue = None
        self.file_name = 'output.csv'
        self.driver = None
        self.credentials_file = 'Files/credentials.json'

        with open(self.credentials_file, 'r') as credentials_file:
            credentials = json.load(credentials_file)
            self.username = credentials['username']
            self.password = credentials['password']

    # start chrome with pdf download enabled
    def start_chrome(self, download_pdf=True, download_prompt=False, headless=False):
        print('Launching Google Chrome')
        # self._download_path = os.path.join(os.getcwd(), 'Downloads')
        # if not os.path.isdir(self._download_path):
        #     os.makedirs(self._download_path)
        options = Options()
        if headless:
            options.add_argument('--headless')
        options.add_argument('--log_level=3')
        # options.add_argument('--no-sandbox')
        # options.add_argument("--remote-debugging-port=9200")
        options.add_experimental_option(
            "prefs", {
                "behavior": "allow",
                "download.prompt_for_download": download_prompt,
                "plugins.always_open_pdf_externally": download_pdf,
                # "download.default_directory": self._download_path,
                "safebrowsing.enabled": False,
                "safebrowsing.disable_download_protection": True
            }
        )
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        self.driver = webdriver.Chrome(options=options,
                                       executable_path=os.path.join(self.cwd,
                                                                    # 'Files',
                                                                    'chromedriver.exe'),
                                       service_log_path='log.txt')
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

        # login
        self.driver.get('https://my.indiamart.com/userprofile/contactprofile/')
        sleep(5)
        username_input_element = self.driver.find_element_by_id('email')
        if username_input_element:
            username_input_element.send_keys(self.username)
            submit_button_element = self.driver.find_element_by_id('submtbtn')
            if submit_button_element:
                submit_button_element.click()
                sleep(2)
                login_with_password_buttons = self.driver.find_elements_by_id('passwordbtn1')
                for button in login_with_password_buttons:
                    if button.get_attribute('value') == 'Login with Password':
                        button.click()
                        sleep(1)
                        password_input_element = self.driver.find_element_by_id('usr_pass')
                        if password_input_element:
                            password_input_element.send_keys(self.password)
                            submit_buttons = self.driver.find_elements_by_id('submtbtn')
                            for button in submit_buttons:
                                if button.get_attribute('value') == 'Login with Password':
                                    button.click()
                                    break
        sleep(5)
        if self.driver.find_element_by_id('primary_email'):
            print('Logged in successfully!')

        for location in locations:
            for category in categories:
                print(f'Collecting data for product: {category[0]} in location: {location[0]}')
                url = f'https://dir.indiamart.com/search.mp?ss={category[0]}&cq={location[0]}&cq_src=city-search&city_only=true'
                self.driver.get(url)
                sleep(5)
                try:
                    self.driver.find_element_by_class_name('nres')
                    print('\t No result')
                    continue
                except Exception as e:
                    pass
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                sleep(3)
                while True:
                    try:
                        loadMoreButton = self.driver.find_element_by_xpath('//*[contains(text(), "Show More Results")]')
                        sleep(2)
                        loadMoreButton.click()
                        sleep(5)
                    except Exception:
                        break

                results = self.parse_result(self.driver.page_source, category[0], location[0], location[1])
                for result_json in results:
                    try:
                        if result_json["Product URL"] and result_json["Product URL"] != '':
                            self.driver.get(result_json["Product URL"])
                            sleep(3)
                            # self.driver.get(result_json["Product URL"])
                            result_json["Name"] = self.get_contact_name(self.driver.page_source)
                    except Exception as e:
                        print(e)
                    output.append(result_json)
                    print('\t', result_json)
        return output

    def get_total_pages(self, html_string):
        regex = re.search(r"ims.r = '(\d+)'", html_string)
        if regex:
            return int(regex[1]) / 14
        else:
            return 0

    def get_contact_name(self, html_response):
        soup = BeautifulSoup(html_response, 'html.parser')
        name_divs = soup.find_all('div', attrs={'id': 'supp_nm'})
        if name_divs:
            return name_divs[0].text.strip()
        return None

    def save_output(self, output):
        headers_needed = False
        headers = output[0].keys()
        if not os.path.isfile(self.file_name):
            headers_needed = True
        with open(self.file_name, 'w', newline='', encoding='utf-8') as output_file:
            writer = csv.DictWriter(output_file, fieldnames=headers)
            if headers_needed:
                writer.writeheader()
            writer.writerows(output)

    def parse_result(self, html_response, category, city, state):
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
                city_div = company_div.find('span', attrs={'id': re.compile('citytt')})
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


if __name__ == '__main__':
    indiamart = Indiamart()
    locations = []
    categories = []
    with open('Files/location.csv') as location_file:
        reader = csv.reader(location_file)
        for location in reader:
            locations.append(location)
    with open('Files/categories.csv') as category_file:
        reader = csv.reader(category_file)
        for category in reader:
            categories.append(category)
    output = indiamart.search_task(categories=categories[1:], locations=locations[1:])
    indiamart.save_output(output)
