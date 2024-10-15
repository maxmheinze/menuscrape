import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import camelot
import numpy as np
from googletrans import Translator
import pdfplumber
import io
import pytesseract
import cv2
from PIL import Image
import difflib
import string
import os
from datetime import datetime

# Function to scrape Baschly menu


def get_baschly_menu():
    # Fetch the webpage
    url = 'https://baschly.com/home/baschly-1020/'
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the PDF link containing "Lunch Special"
    link = soup.find('a', string=re.compile(
        r'\s*Lunch\s*Special\s*', re.IGNORECASE))
    pdf_url = link['href']

    # Try to extract tables from the PDF
    tables = camelot.read_pdf(pdf_url, pages='all')

    # Check if the PDF is image-based
    if len(tables) == 0 or ('warnings' in tables[0].parsing_report and 'error' in tables[0].parsing_report['warnings']):
        # If image-based, return a DataFrame with rows for each day (1, 2, 3, 4, 5)
        df_image_pdf = pd.DataFrame({
            'foodtype': ['Meat', 'Veggie'] * 5,
            'menu': ['Baschly decided to upload an image-based menu PDF this week. So please follow the link to your right if you want to access their menu.'] * 10,
            'language': ['english'] * 10,
            'location': ['Baschly'] * 10,
            'day': [1, 2, 3, 4, 5] * 2,
            'source': [pdf_url] * 10
        })
        return df_image_pdf

    # Extract tables if the PDF is not image-based
    df_table = tables[0].df

    # Select relevant rows and columns
    df_subset = df_table.iloc[1:6, [0,2]]
    df_split = df_subset.replace('\n', ' ', regex=True)

    days_to_remove = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag']
    df_split = df_split.replace(days_to_remove, '', regex=True)

    df_melted = df_split.melt(ignore_index=False).assign(
        day=lambda x: x.index,
        foodtype=lambda x: x['variable'].map({0: 'Meat', 2: 'Veggie'})
    ).drop(columns='variable').rename(columns={'value': 'menu'}).reset_index(drop=True)

    df_melted['language'] = 'german'

    # Translate 'menu' column to English
    translator = Translator()

    def translate_menu(text):
        if pd.isnull(text) or text.strip() == '':
            return text
        return translator.translate(text, src='de', dest='en').text

    df_translated = df_melted.copy()
    df_translated['menu'] = df_translated['menu'].apply(translate_menu)
    df_translated['language'] = 'english'

    # Combine German and English DataFrames
    df_combined = pd.concat([df_melted, df_translated], ignore_index=True)
    df_combined['location'] = 'Baschly'

    # Add 'day' and 'source' columns
    df_combined['day'] = np.tile(np.arange(1, 6), len(
        df_combined) // 5 + 1)[:len(df_combined)]
    df_combined['source'] = pdf_url

    return df_combined
    
    
# Function to scrape Mensa menu


def get_mensa_menu():
    # URL of the PDF
    pdf_url = 'https://www.wumensa.at/menuplan-deutsch'
    response = requests.get(pdf_url)
    pdf_bytes = io.BytesIO(response.content)

    # Extract table using pdfplumber
    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                df_table = pd.DataFrame(table)
                df_cleaned = df_table.ffill()

    # Clean and restructure the DataFrame
    df_cleaned = df_cleaned.replace(r'\n', ' ', regex=True)
    df_cleaned = df_cleaned.iloc[:, [0, 2, 4, 6, 8, 10]]
    df_cleaned.columns = df_cleaned.iloc[0]
    df_cleaned = df_cleaned.drop(0).reset_index(drop=True)
    df_melted = pd.melt(df_cleaned, id_vars=[
                        df_cleaned.columns[0]], var_name='day', value_name='menu')
    df_melted['language'] = 'german'

    # Map day names to numbers
    day_map = {
        'montag': 1,
        'dienstag': 2,
        'mittwoch': 3,
        'donnerstag': 4,
        'freitag': 5
    }
    df_melted['day'] = df_melted['day'].str.lower().map(day_map)

    # Translate 'menu' column to English
    translator = Translator()

    def translate_menu(text):
        if pd.isnull(text) or text.strip() == '':
            return text
        return translator.translate(text, src='de', dest='en').text

    df_translated = df_melted.copy()
    df_translated['menu'] = df_translated['menu'].apply(translate_menu)
    df_translated['language'] = 'english'

    # Combine German and English DataFrames
    df_combined = pd.concat([df_melted, df_translated], ignore_index=True)
    df_combined['location'] = 'Mensa'
    df_combined.columns.values[0] = 'foodtype'
    df_combined['source'] = pdf_url
    return df_combined

# Function to scrape library menu


def get_library_menu():
    # Fetch the webpage
    library_url = 'https://lia.coffee'
    html = requests.get(library_url)
    soup = BeautifulSoup(html.content, 'html.parser')
    soup = soup.find('div', id='menu')

    # Initialize lists to store data
    places = []
    days = []
    menu_items = []
    types = []
    prices = []

    # Find all place headers and extract menu information
    place_headers = soup.find_all('h3')
    for place in place_headers:
        plc = place.get_text(strip=True)
        day_headers = place.find_next('div').find_all('h4')
        for header in day_headers:
            day = header.get_text(strip=True)
            menu_list = header.find_next('ul')
            for item in menu_list.find_all('li'):
                menu_item = item.get_text(strip=True)
                if '€' in menu_item:
                    item_parts = menu_item.split('€')
                    name = item_parts[0].strip()
                    price = item_parts[1].strip().replace(',', '.')
                    if 'VEGGIE' in menu_item.upper():
                        foodtype = 'Veggie'
                    elif 'MEAT' in menu_item.upper():
                        foodtype = 'Meat'
                    elif 'VEGAN' in menu_item.upper():
                        foodtype = 'Vegan'
                    else:
                        foodtype = 'Unspecified'
                    places.append(plc)
                    days.append(day)
                    menu_items.append(name)
                    types.append(foodtype)
                    prices.append(price)
                else:
                    places.append(plc)
                    days.append(day)
                    menu_items.append(menu_item)
                    types.append('UNKNOWN')
                    prices.append('N/A')

    # Create DataFrame and split menus into German and English
    df = pd.DataFrame({
        'Place': places,
        'Day': days,
        'menu': menu_items,
        'foodtype': types,
        'price': prices,
        'location': 'Library',
        'source': library_url
    })
    df[['menu', 'menu_eng']] = df['menu'].str.split('/', expand=True)
    df = df[df['Place'] == 'Tagesmenü Lia Coffee am WU Campus']

    # Separate German and English menus
    df_german = df[['Place', 'Day', 'menu', 'foodtype',
                    'price', 'location', 'source']].copy()
    df_german['language'] = 'german'
    df_english = df[['Place', 'Day', 'menu_eng',
                     'foodtype', 'price', 'location', 'source']].copy()
    df_english.rename(columns={'menu_eng': 'menu'}, inplace=True)
    df_english['language'] = 'english'

    # Combine DataFrames and map days to numbers
    df_combined = pd.concat([df_german, df_english], ignore_index=True)
    day_mapping = {
        'montag': 1,
        'dienstag': 2,
        'mittwoch': 3,
        'donnerstag': 4,
        'freitag': 5,
        'samstag': 6,
        'sonntag': 7
    }
    df_combined['day'] = df_combined['Day'].str.split(',').str[0].str.lower()
    df_combined['day'] = df_combined['day'].map(day_mapping)
    df_combined.drop(columns=['Day', 'Place'], inplace=True)
    return df_combined

# Function to scrape Finn menu


def get_finn_menu():
    # Step 1: Fetch the webpage
    page_url = 'https://finn.wien/collections/mittagsmenu'
    response = requests.get(page_url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Step 2: Find the div that contains the image
    div_tag = soup.find(
        'div', class_='collection__header-info__text rte rte--header')
    if div_tag:
        # Step 3: Find the img tag within the div
        image_tag = div_tag.find('img')
        if image_tag:
            image_url = image_tag['src']
            if not image_url.startswith('http'):
                image_url = 'https://finn.wien' + image_url
        else:
            print("Error: No image found inside the specified div.")
            return pd.DataFrame()
    else:
        print("Error: Specified div not found.")
        return pd.DataFrame()

    # Step 4: Download and preprocess the image for OCR (only thresholding)
    image_response = requests.get(image_url)
    img_data = image_response.content
    img_array = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    # img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # manual_threshold_value = 200
    # _, img_thresh = cv2.threshold(img_gray, manual_threshold_value, 255, cv2.THRESH_BINARY)
    # img_for_ocr = Image.fromarray(img_thresh)

    # Step 5: Extract text from the image
    imagetext = pytesseract.image_to_string(img, lang='deu')

    # Step 6: Define helper functions

    # Clean dish name
    def clean_dish(dish):
        allowed_chars = 'a-zA-Z0-9äöüÄÖÜß'
        dish = re.sub(r'^[^{}]+'.format(allowed_chars), '', dish)
        dish = re.sub(r'[^{}]+$'.format(allowed_chars), '', dish)
        words = dish.split()
        words = [word for word in words if not re.match(
            r'^[^{}]'.format(allowed_chars), word)]
        dish = ' '.join(words)
        if len(dish) > 3:
            prefix = dish[:3]
            rest = dish[3:]
            unwanted_chars = string.digits + \
                ''.join([c for c in string.punctuation if c not in "-'"])
            pattern = r'[{}]'.format(re.escape(unwanted_chars))
            match = re.search(pattern, rest)
            if match:
                index = match.start()
                rest = rest[:index]
            dish = prefix + rest
        dish = dish.strip()
        words = dish.split()
        if words and words[-1][0].islower():
            words = words[:-1]
        words = [word.capitalize() if word.isupper()
                 else word for word in words]
        dish = ' '.join(words)
        return dish

    # Get day number
    def get_day_number(day_str):
        day_str = day_str.upper()
        day_names = ['MONTAG', 'DIENSTAG', 'MITTWOCH', 'DONNERSTAG', 'FREITAG']
        day_numbers = [1, 2, 3, 4, 5]
        match = difflib.get_close_matches(day_str, day_names, n=1, cutoff=0.6)
        if match:
            day_name = match[0]
            index = day_names.index(day_name)
            return day_numbers[index]
        else:
            return None

    # Process price
    def process_price(price_str):
        # Replace comma with period if present
        price_str = price_str.replace(',', '.')

        # If no decimal point, insert it before the last two digits
        if '.' not in price_str and len(price_str) > 2:
            price_str = price_str[:-2] + '.' + price_str[-2:]

        # Replace "4" at the beginning followed by a digit with "1" (OCR correction)
        if price_str.startswith('4') and len(price_str) > 1 and price_str[1].isdigit():
            price_str = '1' + price_str[1:]

        # Check if the price is in the range 4 to 15, otherwise return an empty value
        try:
            price_value = float(price_str)
            if 4 <= price_value <= 15:
                return price_value
            else:
                return None
        except ValueError:
            return None

    # Step 7: Process the extracted text
    lines = imagetext.split('\n')
    dish_list = []
    current_day = None
    day_pattern = re.compile(
        r'^(MONTAG|DIENSTAG|MITTWOCH|DONNERSTAG|FREITAG)[:\s]*(.*)', re.IGNORECASE)
    menu_pattern = re.compile(r'^(M[0-9]+|MS)\s*:?\s*(.*)', re.IGNORECASE)
    asia_pattern = re.compile(
        r'^AS[A-Z]A BOX TO GO[:_]?\s*(.*)', re.IGNORECASE)
    # Pattern to find price at the end of a line
    price_pattern = re.compile(r'(\d+[.,]?\d*)$')
    sushi_bar = False
    translator = Translator()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Extract price at the end of the line (if available)
        price_match = price_pattern.search(line)
        price = None
        if price_match:
            price_str = price_match.group(1)
            price = process_price(price_str)
            # Remove the price from the line for further dish processing
            line = line[:price_match.start()].strip()

        day_match = day_pattern.match(line)
        if day_match:
            day_str = day_match.group(1)
            soup_dish = day_match.group(2).strip()
            day_number = get_day_number(day_str)
            if day_number:
                current_day = day_number
                dish = clean_dish(soup_dish)
                dish_list.append(
                    {'day': current_day, 'foodtype': 'Soup', 'menu': dish, 'price': price})
            continue
        menu_match = menu_pattern.match(line)
        if menu_match:
            type_ = menu_match.group(1).upper()
            dish = menu_match.group(2).strip()
            dish = clean_dish(dish)
            if type_ == 'MS':
                type_ = 'M5'
            if type_ in ['M1', 'M4', 'M5']:
                for day_number in [1, 2, 3, 4, 5]:
                    dish_list.append(
                        {'day': day_number, 'foodtype': type_, 'menu': dish, 'price': price})
            else:
                day = current_day
                if day is not None:
                    dish_list.append(
                        {'day': day, 'foodtype': type_, 'menu': dish, 'price': price})
            continue
        asia_match = asia_pattern.match(line)
        if asia_match:
            dish = asia_match.group(1).strip()
            dish = clean_dish(dish)
            for day_number in [1, 2, 3, 4, 5]:
                dish_list.append(
                    {'day': day_number, 'foodtype': 'ASIA BOX TO GO', 'menu': dish, 'price': price})
            continue
        if 'SUSHI BAR' in line.upper():
            sushi_bar = True
            continue
        if sushi_bar:
            menu_match = menu_pattern.match(line)
            if menu_match:
                type_ = menu_match.group(1).upper()
                dish = menu_match.group(2).strip()
                dish = clean_dish(dish)
                if type_ == 'MS':
                    type_ = 'M5'
                for day_number in [1, 2, 3, 4, 5]:
                    dish_list.append(
                        {'day': day_number, 'foodtype': type_, 'menu': dish, 'price': price})
                continue
            else:
                sushi_bar = False

    # Step 8: Create DataFrame
    df = pd.DataFrame(dish_list)

    # Step 9: Translate 'menu' column to English
    df['menu'] = df['menu'].str.replace(
        'dazu', 'mit', case=False)
    df['language'] = 'german'
    df_translated = df.copy()
    df_translated['menu'] = df_translated['menu'].apply(
        lambda x: translator.translate(x, src='de', dest='en').text)
    df_translated['language'] = 'english'

    # Step 10: Combine DataFrames and add location and source
    df_combined = pd.concat([df, df_translated], ignore_index=True)
    df_combined['location'] = 'Finn'
    df_combined['source'] = page_url

    print(imagetext)
    return df_combined


def get_glashaus_menu():
    import requests
    from bs4 import BeautifulSoup
    import pandas as pd
    from googletrans import Translator

    # Fetch the webpage
    glashaus_url = 'https://www.dasglashaus.at/menues'
    html = requests.get(glashaus_url)
    soup = BeautifulSoup(html.content, 'html.parser')

    # Initialize lists to store data
    days = []
    menu_items = []
    types = []
    prices = []
    locations = []
    sources = []
    languages = []

    location = 'Glashaus'
    source = glashaus_url

    # Map for day names to numbers
    day_mapping = {
        'montag': 1,
        'dienstag': 2,
        'mittwoch': 3,
        'donnerstag': 4,
        'freitag': 5,
        'samstag': 6,
        'sonntag': 7
    }

    # Find all h2 elements that represent days
    day_sections = soup.find_all('h2', class_='font_2 wixui-rich-text__text')
    for day_header in day_sections:
        day_text = day_header.get_text(strip=True).lower()
        if day_text in day_mapping:
            day_number = day_mapping[day_text]
            # Get the menu items following the day header
            menu_div = day_header.find_parent('div').find_next_sibling(
                'div', class_='wixui-rich-text')
            if menu_div:
                # Get all 'p' tags within menu_div
                menu_paragraphs = menu_div.find_all('p')
                # For each menu item, assign food type based on position
                for idx, p in enumerate(menu_paragraphs):
                    menu_item_text = p.get_text(strip=True)
                    if idx == 0:
                        foodtype = 'Vegetarisch'
                        price = '13.90'
                    elif idx == 1:
                        foodtype = 'Fisch & Fleisch'
                        price = '14.90'
                    else:
                        # If there are more than 2 items
                        foodtype = 'Unspecified'
                        price = 'N/A'
                    days.append(day_number)
                    menu_items.append(menu_item_text)
                    types.append(foodtype)
                    prices.append(price)
                    locations.append(location)
                    sources.append(source)
                    languages.append('german')
            else:
                continue

    # Create DataFrame
    df = pd.DataFrame({
        'menu': menu_items,
        'foodtype': types,
        'price': prices,
        'location': locations,
        'source': sources,
        'language': languages,
        'day': days
    })

    # Replace 'dazu' with 'mit' in 'menu' column
    df['menu'] = df['menu'].str.replace('dazu', 'mit', case=False)

    # Translate 'menu' column to English
    translator = Translator()
    df_translated = df.copy()
    df_translated['menu'] = df_translated['menu'].apply(
        lambda x: translator.translate(x, src='de', dest='en').text)
    df_translated['language'] = 'english'

    # Combine DataFrames
    df_combined = pd.concat([df, df_translated], ignore_index=True)

    return df_combined


def get_campus_menu():

    days = [1, 2, 3, 4, 5]

    data = {
        'menu': [
            "Das Campus Hot Stuff only posts their lunch options on Facebook, so please follow the link to your right if you want to access their menu."
        ] * len(days),
        'foodtype': [None] * len(days),
        'price': [None] * len(days),
        'location': ['Das Campus Hot Stuff'] * len(days),
        'source': ['https://www.facebook.com/dchotstuff'] * len(days),
        'language': [None] * len(days),
        'day': days
    }

    # Create DataFrame
    df = pd.DataFrame(data)

    return df


# Main Execution
if __name__ == '__main__':
    df_baschly = get_baschly_menu()
    df_mensa = get_mensa_menu()
    df_library = get_library_menu()
    df_finn = get_finn_menu()
    df_glashaus = get_glashaus_menu()
    df_campus = get_campus_menu()

    # Combine all DataFrames
    df_all = pd.concat([df_baschly, df_mensa, df_library,
                       df_finn, df_glashaus, df_campus], ignore_index=True)

    # Export the combined DataFrame to CSV in the current folder
    df_all.to_csv('menu_data.csv', index=False)

    # Check if today is Thursday
    if datetime.now().weekday() == 3:
        # Export the combined DataFrame to CSV in the "archive" folder
        current_date = datetime.now().strftime('%Y%m%d')

        archive_folder = 'archive'
        if not os.path.exists(archive_folder):
            os.makedirs(archive_folder)

        file_path = os.path.join(
            archive_folder, f'menu_data_{current_date}.csv')

        df_all.to_csv(file_path, index=False)

# Map day numbers to weekday names
day_names = {
    1: 'Monday',
    2: 'Tuesday',
    3: 'Wednesday',
    4: 'Thursday',
    5: 'Friday',
    6: 'Saturday',
    7: 'Sunday'
}

# Ensure 'day' column is of integer type
df_all['day'] = df_all['day'].astype(int)

# Markdown
current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

md_content = f"""---
layout: default
title: Max Heinze
description: Economics PhD Student @ WU Vienna
---

# This Week's Scraped Lunch Menus

_Last Update: {current_time}_

**Note:** English text is (mostly) Google-translated from German menus and may therefore be inaccurate (or bad, or funny, or all of the above). **Click** (or tap) on a weekday to expand that day's menu.
"""


# Iterate over each unique day
for day_num in sorted(df_all['day'].dropna().unique()):
    # Get the weekday name
    day_name = day_names.get(day_num, f'Day{day_num}')

    # Filter the dataframe for the current day
    df_day = df_all[df_all['day'] == day_num].copy()

    # Sort by 'location', 'foodtype', and reverse 'language'
    df_day.sort_values(['location', 'foodtype', 'language'],
                       ascending=[True, True, False], inplace=True)

    # Drop the 'language' and 'day' columns
    df_day.drop(columns=['language', 'day'], inplace=True)

    # Modify the 'source' column to display 'Link' with the URL
    df_day['source'] = df_day['source'].apply(
        lambda x: f'<a href="{x}">Link</a>')

    # Reorder columns if necessary
    df_day = df_day[['location', 'foodtype', 'menu', 'price', 'source']]

    # Replace NaN with empty strings
    df_day.fillna('', inplace=True)

    # Convert the dataframe to an HTML table without escaping HTML characters
    html_table = df_day.to_html(
        index=False, border=0, header=False, classes='menu-table', escape=False)

    # Add the collapsible section for the current day
    md_content += f"""
<details>
  <summary><h2>{day_name}</h2></summary>
  {html_table}
</details>
"""

# Write the entire Markdown content to a file
with open('menu.md', 'w', encoding='utf-8') as f:
    f.write(md_content)

print("menu.md has been created.")
