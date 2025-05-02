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
from pytesseract import Output
import cv2
from PIL import Image
import difflib
import string
import os
from datetime import datetime


def _ocr_rows(img, lang='deu'):
    data = pytesseract.image_to_data(
        img,
        lang=lang,
        config='--oem 3 --psm 4',          # “single column” keeps long lines together
        output_type=Output.DATAFRAME
    )
    data = data[data.conf.astype(int) > 60]   # keep only high-confidence words
    bin_size = int(data.height.median() * 1.2) or 25
    data['row'] = ((data.top + data.height / 2) // bin_size).astype(int)
    rows = (
        data.sort_values(['row', 'left'])
        .groupby('row', observed=True)['text']
        .agg(' '.join)
        .tolist()
    )
    return rows


def _merge_wrapped(lines):
    """
    Join lines that were hard-wrapped by the PDF/image
    (start with lowercase letter, a price, or 'mit / dazu').
    """
    merged, buf = [], ''
    cont = re.compile(r'^[a-zäöü]|^[€\d]|^(mit|dazu)\b', re.I)

    for ln in lines:
        if buf and cont.match(ln):
            buf += ' ' + ln
        else:
            if buf:
                merged.append(buf.strip())
            buf = ln
    if buf:
        merged.append(buf.strip())
    return merged


def preprocess(img, upscale=2):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)                  # grayscale
    h, w = g.shape
    g = cv2.resize(g, (w*upscale, h*upscale),                  # 2× upscale
                   interpolation=cv2.INTER_CUBIC)
    # denoise + sharpen
    g = cv2.bilateralFilter(g, 9, 75, 75)
    th = cv2.adaptiveThreshold(g, 255,
                               cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY, 31, 11)      # binarise
    return th


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
    # imagetext = pytesseract.image_to_string(img, lang='deu')

    # upscale + denoise + binarise
    img_proc = preprocess(img)

    # 1) OCR → rows  2) glue hard-wraps  3) force line-breaks before markers
    lines_raw = _ocr_rows(img_proc)
    lines_merged = _merge_wrapped(lines_raw)

    # collapse to a single string first …
    imagetext_flat = ' '.join(lines_merged)

    # remove “LUNCH DRINK …” or “ZUSÄTZLICH …” tails
    imagetext_flat = re.sub(r'\b(LUNCH\s+DRINK|ZUSÄTZLICH)\b.*',
                            '', imagetext_flat, flags=re.I)

    # insert a line-break before every weekday / menu marker
    marker_re = re.compile(
        r'\b('
        r'MONTAG|DIENSTAG|MITTWOCH|DONNERSTAG|FREITAG|'
        r'SUSHI\s+BAR|AS[A-Z]A\s+BOX\s+TO\s+GO|'
        r'M[0-9]+|MS'
        r')\b',
        re.I,
    )
    imagetext_norm = marker_re.sub(r'\n\1', imagetext_flat)

    # final list of “clean” lines
    lines = [ln.strip() for ln in imagetext_norm.split('\n') if ln.strip()]

    # keep for printing/debug
    imagetext = '\n'.join(lines)

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
    dish_list = []
    current_day = None
    day_pattern = re.compile(
        r'^(MONTAG|DIENSTAG|MITTWOCH|DONNERSTAG|FREITAG)[:\s]*(.*)', re.IGNORECASE)
    menu_pattern = re.compile(r'(M[0-9]+|MS)\s*[:\-]?\s*(.*)', re.IGNORECASE)
    asia_pattern = re.compile(
        r'AS[A-Z]A\s+BOX\s+TO\s+GO[:_]?\s*(.*)', re.IGNORECASE)
    # Pattern to find price at the end of a line
    price_pattern = re.compile(r'€?\s*(\d+[.,]?\d*)')
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
            # remove price token but keep text before/after
            line = (line[:price_match.start()] + ' ' +
                    line[price_match.end():]).strip()

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
        menu_match = menu_pattern.search(line)
        if menu_match:
            type_ = menu_match.group(1).upper()
            dish = menu_match.group(2).strip()
            dish = clean_dish(dish)
            if type_ == 'MS':
                type_ = 'M5'
            if type_ in ['M3', 'M4']:
                for day_number in [1, 2, 3, 4, 5]:
                    dish_list.append(
                        {'day': day_number, 'foodtype': type_, 'menu': dish, 'price': price})
            else:
                day = current_day
                if day is not None:
                    dish_list.append(
                        {'day': day, 'foodtype': type_, 'menu': dish, 'price': price})
            continue
        asia_match = asia_pattern.search(line)
        if asia_match:
            dish = clean_dish(asia_match.group(1).strip())
            # if the OCR put the price first (“…: €5,90 Frühlingsrollen …”)
            if not dish and price is None:
                # dish sits after the first price token we already stripped above
                # so split once more on ':' to grab it
                tail = line.split(':', 1)[-1].strip()
                dish = clean_dish(tail)
            for d in range(1, 6):
                dish_list.append(
                    {'day': d, 'foodtype': 'ASIA BOX TO GO', 'menu': dish, 'price': price})
            continue
        if re.match(r'^(LUNCH\s+DRINK|ZUSÄTZLICH)\b', line, re.I):
            # ignore drink- or extra-sections entirely
            continue

        if 'SUSHI BAR' in line.upper():
            sushi_bar = True
            continue
        if sushi_bar:
            menu_match = menu_pattern.search(line)
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
    df_translated['menu'] = df_translated['menu'].apply(lambda x: translator.translate(
        x, src='de', dest='en').text if pd.notnull(x) and x != '' else x)
    df_translated['language'] = 'english'

    # Step 10: Combine DataFrames and add location and source
    df_combined = pd.concat([df, df_translated], ignore_index=True)
    df_combined['location'] = 'Finn'
    df_combined['source'] = page_url

    print(imagetext)
    print(df_combined)

    return df_combined


get_finn_menu()
