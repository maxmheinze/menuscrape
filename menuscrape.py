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

    # Extract tables from the PDF
    tables = camelot.read_pdf(pdf_url, pages='all')
    if len(tables) > 0:
        df_table = tables[0].df
    else:
        return pd.DataFrame()

    # Select relevant rows and columns
    df_subset = df_table.iloc[1:6, 1]
    df_split = df_subset.str.split('\n', expand=True)

    # Concatenate columns to create 'Meat' and 'Veggie' dishes
    df_concat = pd.DataFrame({
        'Meat': df_split[0].fillna('') + ' ' + df_split[2].fillna(''),
        'Veggie': df_split[1].fillna('') + ' ' + df_split[3].fillna('')
    })

    # Reshape DataFrame and add language information
    df_melted = pd.melt(df_concat, var_name='foodtype', value_name='menu')
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
    df_combined['location'] = 'baschly'

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
    df_combined['location'] = 'mensa'
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
        'location': 'library',
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
    # Fetch the webpage
    page_url = 'https://www.dasfinn.at/mittagsmen%C3%BC'
    response = requests.get(page_url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the image URL containing the menu
    image_tag = soup.find('img', {'alt': ''})
    if image_tag:
        image_url = image_tag['src']
        if not image_url.startswith('http'):
            image_url = 'https://www.dasfinn.at' + image_url

        # Download and preprocess the image for OCR
        image_response = requests.get(image_url)
        img_data = image_response.content
        img_array = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        scale_factor = 5
        width = int(img_gray.shape[1] * scale_factor)
        height = int(img_gray.shape[0] * scale_factor)
        img_resized = cv2.resize(
            img_gray, (width, height), interpolation=cv2.INTER_LINEAR)
        manual_threshold_value = 200
        _, img_thresh = cv2.threshold(
            img_resized, manual_threshold_value, 255, cv2.THRESH_BINARY)
        img_for_ocr = Image.fromarray(img_thresh)
        imagetext = pytesseract.image_to_string(img_for_ocr, lang='deu')
    else:
        return pd.DataFrame()

    # Functions for cleaning and translating
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
            unwanted_chars = string.digits + string.punctuation
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

    # Process the text extracted from the image
    lines = imagetext.split('\n')
    dish_list = []
    current_day = None
    day_pattern = re.compile(r'^([A-ZÄÖÜa-zäöüß]+):\s*(.*)', re.IGNORECASE)
    menu_pattern = re.compile(r'^(M[0-9]+|MS):\s*(.*)', re.IGNORECASE)
    asia_pattern = re.compile(
        r'^AS[A-Z]A BOX TO GO[:_]?\s*(.*)', re.IGNORECASE)
    sushi_bar = False
    translator = Translator()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        day_match = day_pattern.match(line)
        if day_match:
            day_str = day_match.group(1)
            soup_dish = day_match.group(2).strip()
            day_number = get_day_number(day_str)
            if day_number:
                current_day = day_number
                dish = clean_dish(soup_dish)
                dish_list.append(
                    {'day': current_day, 'foodtype': 'Soup', 'menu': dish})
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
                        {'day': day_number, 'foodtype': type_, 'menu': dish})
            else:
                day = current_day
                if day is not None:
                    dish_list.append(
                        {'day': day, 'foodtype': type_, 'menu': dish})
            continue
        asia_match = asia_pattern.match(line)
        if asia_match:
            dish = asia_match.group(1).strip()
            dish = clean_dish(dish)
            for day_number in [1, 2, 3, 4, 5]:
                dish_list.append(
                    {'day': day_number, 'foodtype': 'ASIA BOX TO GO', 'menu': dish})
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
                        {'day': day_number, 'foodtype': type_, 'menu': dish})
                continue
            else:
                sushi_bar = False

    # Create DataFrame and translate 'menu' column to English
    df = pd.DataFrame(dish_list)
    df['language'] = 'german'
    df_translated = df.copy()
    df_translated['menu'] = df_translated['menu'].apply(
        lambda x: translator.translate(x, src='de', dest='en').text)
    df_translated['language'] = 'english'

    # Combine DataFrames and add location and source
    df_combined = pd.concat([df, df_translated], ignore_index=True)
    df_combined['location'] = 'finn'
    df_combined['source'] = page_url
    return df_combined


# Main Execution
if __name__ == '__main__':
    df_baschly = get_baschly_menu()
    df_mensa = get_mensa_menu()
    df_library = get_library_menu()
    df_finn = get_finn_menu()

    # Combine all DataFrames
    df_all = pd.concat([df_baschly, df_mensa, df_library,
                       df_finn], ignore_index=True)

    # Export the combined DataFrame to CSV in the current folder
    df_all.to_csv('menu_data.csv', index=False)

    # Export the combined DataFrame to CSV in the "archive" folder
    current_date = datetime.now().strftime('%Y%m%d')

    archive_folder = 'archive'
    if not os.path.exists(archive_folder):
        os.makedirs(archive_folder)

    file_path = os.path.join(archive_folder, f'menu_data_{current_date}.csv')

    df_all.to_csv(file_path, index=False)
