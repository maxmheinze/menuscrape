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


def get_baschly_menu():
    # Fetch the webpage
    url = 'https://baschly.com/home/baschly-1020/'
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the PDF link containing "Lunch Special"
    link = soup.find('a', string=re.compile(
        r'\s*Lunch\s*Special\s*', re.IGNORECASE))
    pdf_url = link['href']

    # If the link isn't a PDF, assume it's image-based and return the message.
    if not pdf_url.lower().endswith('.pdf'):
        df_image_pdf = pd.DataFrame({
            'foodtype': ['Meat', 'Veggie'] * 5,
            'menu': ['Baschly decided to upload an image-based menu this week. So please follow the link to your right if you want to access their menu.'] * 10,
            'language': ['english'] * 10,
            'location': ['Baschly'] * 10,
            'day': [1, 2, 3, 4, 5] * 2,
            'source': [pdf_url] * 10
        })
        return df_image_pdf

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
    df_subset = df_table.iloc[1:6, [0, 2]]
    df_split = df_subset.replace('\n', ' ', regex=True)

    days_to_remove = ['Montag', 'Dienstag',
                      'Mittwoch', 'Donnerstag', 'Freitag']
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


get_baschly_menu()
