import PySimpleGUI as sg
from yelp_selenium import Yelp as YelpSelenium
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from datetime import datetime


sg.theme('DarkBlue3')  # Add a touch of color

# All the stuff inside your window.

# empty rows for tables
empty_gui_table = [[' ' * 20, ' ' * 40, '']]
all_locations = empty_gui_table.copy()
selected_locations = empty_gui_table.copy()
all_categories = empty_gui_table.copy()
selected_categories = empty_gui_table.copy()

# global variables
gui_queue = queue.Queue()
coc = ChamberOfCommerce()
yp = YellowPages()
yelp = Yelp()
yelp_selenium = YelpSelenium()
coc.gui_queue = gui_queue
yp.gui_queue = gui_queue
yelp.gui_queue = gui_queue
yelp_selenium.gui_queue = gui_queue
sources = ['Indiamart']


def generate_status_tree():
    status_dict = {
        'categories': 0,
        'locations': 0,
        'total_pages': 0,
        'completed_pages': 0,
        'total_search_results': 0,
        'completed_search_results': 0,
    }
    status_tree = sg.TreeData()
    for source in sources:
        status_tree.Insert(parent='', key=source, text=source, values=[f'0%'])
        for key, value in status_dict.items():
            status_tree.Insert(parent=source, key=source+key, text=key, values=[value])
    return status_tree


def get_all_categories(category_text):

    categories = {
        'Chamber of Commerce': [],
        'Yellow Pages': [],
        'Yelp': []
    }

    # get coc category suggestions
    for category in coc.get_categories(category_text):
        categories['Chamber of Commerce'].append([category['name'], category])

    # get yellow pages category suggestions
    for category in yp.get_categories(category_text):
        categories['Yellow Pages'].append([category, category])

    # get yelp category suggestions
    for category in yelp.get_categories(category_text):
        categories['Yelp'].append([category['title'], category])

    return categories


def get_all_locations(location_text):
    locations = {
        'Chamber of Commerce': [],
        'Yellow Pages': [],
        'Yelp': []
    }

    # get coc location suggestions
    # event_loop = asyncio.new_event_loop()
    for location in coc.get_location(location_text):
        locations['Chamber of Commerce'].append([location['name'], location])

    # get yellow pages location suggestions
    for location in yp.get_location(location_text):
        locations['Yellow Pages'].append([location, location])

    # get yelp location suggestions
    for location in yelp.get_location(location_text):
        locations['Yelp'].append([location['title'], location])

    return locations


def get_search_results(datetime_now):
    coc_locations = []
    coc_categories = []
    yp_locations = []
    yp_categories = []
    yelp_locations = []
    yelp_categories = []

    for row in selected_locations:
        if row[0] == 'Chamber of Commerce':
            if row[2] != '' and row[2]:
                coc_locations.append(row[2])

        if row[0] == 'Yellow Pages':
            if row[2] != '' and row[2]:
                yp_locations.append(row[2])
        if row[0] == 'Yelp':
            if row[2] != '' and row[2]:
                yelp_locations.append(row[2])

    for row in selected_categories:
        if row[0] == 'Chamber of Commerce':
            if row[2] != '' and row[2]:
                coc_categories.append(row[2])

        if row[0] == 'Yellow Pages':
            if row[2] != '' and row[2]:
                yp_categories.append(row[2])

        if row[0] == 'Yelp':
            if row[2] != '' and row[2]:
                yelp_categories.append(row[2])

    with ThreadPoolExecutor(max_workers=3) as executor:
        if coc_locations and coc_categories:
            coc.file_name = f'Output_{datetime_now.strftime("%Y_%m_%d_%H_%M_%S")}.csv'
            thread_1 = executor.submit(coc.get_results, coc_locations, coc_categories)

        if yp_locations and yp_categories:
            yp.file_name = f'Output_{datetime_now.strftime("%Y_%m_%d_%H_%M_%S")}.csv'
            thread_2 = executor.submit(yp.get_results, yp_locations, yp_categories)

        if yelp_locations and yelp_categories:
            yelp_selenium.file_name = f'Output_{datetime_now.strftime("%Y_%m_%d_%H_%M_%S")}.csv'
            thread_3 = executor.submit(yelp_selenium.search_task, yelp_locations, yelp_categories)

    return thread_1.result(), thread_2.result(), thread_3.result()


def run_gui():
    global all_categories, all_locations, selected_categories, selected_locations
    frame_layout = [
        [sg.Button('Select Categories', key='button_add_categories', size=(20, 1)),
         sg.Button('Select Locations', key='button_add_locations', size=(20, 1))]
    ]
    status = generate_status_tree()

    main_layout = [
        [sg.Text('Directory Data Download', font=('Helvatica', 18), text_color='DarkBlue', justification='center')],
        [sg.Frame(layout=frame_layout, title='Title')],
        [sg.Text('')],
        [sg.Button('Download', size=(15, 1), key='Download', font=('Helvatica', 14)),
         sg.Button('Exit', size=(15, 1), font=('Helvatica', 14))],
        [sg.Text('')],
        [sg.Text('Download Status:', visible=True, key='status_heading')],
        [sg.Tree(data=status, headings=['   Status   '], key='status', visible=False, col0_width=25, def_col_width=20,
                 show_expanded=True, num_rows=50)],
    ]

    # Create the Window
    window = sg.Window('Directory Data Download', main_layout, text_justification='center',
                       element_justification='center',
                       size=(400, 200))
    # Event Loop to process "events" and get the "values" of the inputs
    while True:
        event, values = window.read(timeout=100)
        if event in (None, 'Exit'):  # if user closes window or clicks cancel
            break

        if event == 'Download':
            if len(selected_locations) > 1 and len(selected_categories)>1:
                datetime_now = datetime.now()
                window['status'].Update(generate_status_tree(), visible=True)
                window.size = (400, 600)
                window.current_location = (0, 0)
                window.refresh()
                thread = threading.Thread(target=get_search_results, args=(datetime_now,), daemon=True)
                thread.start()
            else:
                sg.popup('Categories or Locations are missing.\nPlease select categories and locations first',
                         title='Selection Error!',)

        if event == 'button_add_locations':
            location_table = sg.Table(headings=['Source', 'Location', 'key'],
                                      values=all_locations,
                                      visible_column_map=[True, True, False],
                                      vertical_scroll_only=False,
                                      key='location_list',
                                      display_row_numbers=True,
                                      justification='left',
                                      )
            selection_table = sg.Table(headings=['Source', 'Location', 'key'],
                                       values=selected_locations,
                                       visible_column_map=[True, True, False],
                                       key='selected_locations',
                                       display_row_numbers=True,
                                       justification='left',
                                       )
            location_layout = [
                [sg.Text('Enter a Location:')],
                [sg.Input(default_text='San Francisco'), sg.Button('Search', key='button_search', size=(10, 1))],
                [sg.Text('Location search result:')],
                [location_table, sg.Button('Add', key='button_add', size=(10, 1))],
                [sg.Text('Locations selected for downloading:')],
                [selection_table, sg.Button('Remove', key='button_remove', size=(10, 1))],
                [sg.Text('')],
                [sg.Button('Done', key='Done', size=(10, 1))],
            ]
            location_window = sg.Window(
                'Select Locations',
                location_layout,
                element_justification='left',
                text_justification='left',
            )

            def update_location_tables():
                location_window['location_list'].Update(values=all_locations)
                location_window['selected_locations'].Update(values=selected_locations)

            while True:
                event, values = location_window.read()
                if event in (None, 'Done'):  # if user closes window or clicks cancel
                    location_window.close()
                    if len(selected_locations) > 1:
                        window['button_add_locations'].Update(
                            text=f'Selected Locations ({len(selected_locations) - 1})')
                    break

                # when search button is pressed
                if event == 'button_search' and values[0]:
                    all_locations = empty_gui_table.copy()
                    locations_list = get_all_locations(values[0])
                    for source, locations in locations_list.items():
                        for location in locations:
                            all_locations.append([source, location[0], location[1]])
                    update_location_tables()

                # when add button is pressed
                if event == 'button_add':
                    for row_num in values['location_list'][::-1]:
                        selected_locations.append(all_locations[row_num])
                        all_locations.pop(row_num)
                    update_location_tables()

                # when remove button is pressed
                if event == 'button_remove':
                    for row_num in values['selected_locations'][::-1]:
                        all_locations.append(selected_locations[row_num])
                        selected_locations.pop(row_num)
                    update_location_tables()

        # category selection
        if event == 'button_add_categories':

            all_category_table = sg.Table(headings=['Source', 'Categories', 'key'],
                                          values=all_categories,
                                          visible_column_map=[True, True, False],
                                          vertical_scroll_only=False,
                                          key='all_categories',
                                          auto_size_columns=True,
                                          display_row_numbers=True,
                                          justification='left',
                                          )

            selected_category_table = sg.Table(headings=['Source', 'Categories', 'key'],
                                               values=selected_categories,
                                               visible_column_map=[True, True, False],
                                               key='selected_categories',
                                               auto_size_columns=True,
                                               display_row_numbers=True,
                                               justification='left',
                                               )
            category_layout = [
                [sg.Text('Enter a search categories:')],
                [sg.Input(default_text='Accountants'), sg.Button('Search', key='button_search', size=(10, 1))],
                [sg.Text('Category search result:')],
                [all_category_table, sg.Button('Add', key='button_add', size=(10, 1))],
                [sg.Text('Categories selected for downloading:')],
                [selected_category_table, sg.Button('Remove', key='button_remove', size=(10, 1))],
                [sg.Text('')],
                [sg.Button('Done', key='Done', size=(10, 1))],
                [sg.Text('')]
            ]
            category_window = sg.Window(
                'Select Categories',
                category_layout,
                element_justification='left',
                text_justification='left',
            )

            def update_category_tables():
                category_window['all_categories'].Update(values=all_categories)
                category_window['selected_categories'].Update(values=selected_categories)

            while True:
                event, values = category_window.read(timeout=100)
                if event in (None, 'Done'):  # if user closes window or clicks cancel
                    category_window.close()
                    window['button_add_categories'].Update(text=f'Selected Categories ({len(selected_categories) - 1})')
                    break

                # when search button is pressed
                if event == 'button_search' and values[0]:
                    all_categories = empty_gui_table.copy()
                    category_list = get_all_categories(values[0])
                    for source, categories in category_list.items():
                        for category in categories:
                            all_categories.append([source, category[0], category[1]])
                    update_category_tables()

                # when add button is pressed
                if event == 'button_add':
                    for row_num in values['all_categories'][::-1]:
                        selected_categories.append(all_categories[row_num])
                        all_categories.pop(row_num)
                    update_category_tables()

                # when remove button is pressed
                if event == 'button_remove':
                    for row_num in values['selected_categories'][::-1]:
                        all_categories.append(selected_categories[row_num])
                        selected_categories.pop(row_num)
                    update_category_tables()

        try:
            message = gui_queue.get_nowait()
        except queue.Empty:
            message = None
        if message is not None:
            parent = None
            for key, value in message.items():
                if key == 'source':
                    parent = value
                elif key == '%':
                    window['status'].Update(value=f'{value}%', key=parent)
                else:
                    window['status'].Update(value=value, key=parent+key)
    window.close()


if __name__ == '__main__':
    run_gui()
    # try:
    #     run_gui()
    # except Exception as e:
    #     print(str(e))
    #     if gui_queue:
    #         gui_queue.put(str(e))
