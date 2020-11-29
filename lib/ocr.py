import re
from io import BytesIO

import PIL.ImageOps
import pytesseract
from PIL import Image, ImageDraw, ImageEnhance

UNKNOWN_NAME = '<unknown name>'
UNKNOWN_LEGACY = '<unknown legacy>'

KEY_TABLE_TOP = 'table_top'
KEY_TABLE_LEFT = 'table_left'
KEY_TABLE_RIGHT = 'table_right'
KEY_COLUMN_WIDTH = 'column_width'
KEY_ROW_HEIGHT = 'row_height'
KEY_NUMBER_OF_ROWS = 'number_of_rows'

DEFAULT_BOUNDS = {
    KEY_TABLE_TOP: 330,
    KEY_TABLE_LEFT: 328,
    KEY_TABLE_RIGHT: 1530,
    KEY_COLUMN_WIDTH: 220,
    KEY_ROW_HEIGHT: 23.33,
    KEY_NUMBER_OF_ROWS: 24,
}


# Enhances the image to make it more easily readable for OCR.
def enhance_image(image):
    image = ImageEnhance.Color(image).enhance(0)
    image = ImageEnhance.Sharpness(image).enhance(8)

    # Invert the colors of the image.
    if image.mode == 'RGBA':
        r, g, b, a = image.split()
        rgb_image = Image.merge('RGB', (r, g, b))
        inverted_image = PIL.ImageOps.invert(rgb_image)
        r2, g2, b2 = inverted_image.split()
        return Image.merge('RGBA', (r2, g2, b2, a))
    else:
        return PIL.ImageOps.invert(image)


# Returns the cleaned-up text extracted from the specified section of the row image.
def extract_column_text(row_image, left, right):
    cropped_image = row_image.crop((left, 0, right, row_image.size[1]))
    text = pytesseract.image_to_string(cropped_image)
    return ' '.join(text.split()).strip('*‘:._').replace(',', '')


# Returns a tuple containing the character name, legacy name, and conquest points.
def process_row_image(row_image, column_width):
    name = extract_column_text(row_image, 0, column_width) or UNKNOWN_NAME
    legacy = extract_column_text(row_image, column_width, column_width * 2) or UNKNOWN_LEGACY

    row_width = row_image.size[0]
    conquest_text = extract_column_text(row_image, row_width - column_width, row_width)
    conquest = 0 if not conquest_text else int(re.sub('[^0-9]', '', conquest_text))

    return name, legacy, conquest


# Returns a list of tuples corresponding to the sections of text recognized in the given image.
def process_screenshot(file: BytesIO, bounds: dict = DEFAULT_BOUNDS):
    image = Image.open(file)
    rows = []

    for i in range(bounds[KEY_NUMBER_OF_ROWS]):
        row_top = bounds[KEY_TABLE_TOP] + (bounds[KEY_ROW_HEIGHT] * i)
        row_bottom = row_top + bounds[KEY_ROW_HEIGHT]
        row_image = image.crop((bounds[KEY_TABLE_LEFT], row_top, bounds[KEY_TABLE_RIGHT], row_bottom))
        row_image = enhance_image(row_image)
        row_data = process_row_image(row_image, bounds[KEY_COLUMN_WIDTH])
        rows.append(row_data)

    return rows


# Draws the specified (or default) bounds on top of the given image, and saves the result to the specified filename.
def draw_bounds(input_file: BytesIO, output_filename: str, bounds: dict = DEFAULT_BOUNDS):
    image = Image.open(input_file)
    draw = ImageDraw.Draw(image)

    first_column_right = bounds[KEY_TABLE_LEFT] + bounds[KEY_COLUMN_WIDTH]
    second_column_right = bounds[KEY_TABLE_LEFT] + (bounds[KEY_COLUMN_WIDTH] * 2)
    last_column_left = bounds[KEY_TABLE_RIGHT] - bounds[KEY_COLUMN_WIDTH]

    for i in range(bounds[KEY_NUMBER_OF_ROWS]):
        row_top = bounds[KEY_TABLE_TOP] + (bounds[KEY_ROW_HEIGHT] * i)
        row_bottom = row_top + bounds[KEY_ROW_HEIGHT]
        draw.rectangle([bounds[KEY_TABLE_LEFT], row_top, first_column_right, row_bottom], outline='red')
        draw.rectangle([bounds[KEY_TABLE_LEFT], row_top, second_column_right, row_bottom], outline='red')
        draw.rectangle([last_column_left, row_top, bounds[KEY_TABLE_RIGHT], row_bottom], outline='red')

    image.save(output_filename)
