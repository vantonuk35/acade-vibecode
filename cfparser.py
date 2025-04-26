import cloudscraper
from bs4 import BeautifulSoup
import re
import html

ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "sub", "sup", "code", "pre"}

LABELS = {
    'ru': {
        'time': 'ограничение по времени на тест',
        'memory': 'ограничение по памяти на тест',
        'input': 'ввод',
        'output': 'вывод',
        'standard': 'стандартный',
        'input_section': 'входные данные',
        'output_section': 'выходные данные',
        'note_section': 'примечание'
    },
    'en': {
        'time': 'time limit per test',
        'memory': 'memory limit per test',
        'input': 'input',
        'output': 'output',
        'standard': 'standard',
        'input_section': 'input',
        'output_section': 'output',
        'note_section': 'note'
    }
}

def convert_latex_blocks(html_text):
    def span_replacer(match):
        inner = html.unescape(match.group(1))
        return f"\\({inner}\\)"

    html_text = re.sub(r'<span class="tex-math">(.*?)</span>', span_replacer, html_text)

    def dollar_replacer(match):
        latex = html.unescape(match.group(1))
        return f"\\({latex}\\)"

    html_text = re.sub(r'\$\$\$(.*?)\$\$\$', dollar_replacer, html_text, flags=re.DOTALL)
    html_text = re.sub(r'\$\$(.*?)\$\$', dollar_replacer, html_text, flags=re.DOTALL)

    return html_text

def convert_formatting_tags(soup):
    for tag in soup.find_all("span"):
        classes = tag.get("class", [])
        if 'tex-font-style-bf' in classes:
            tag.name = 'b'
            tag.attrs = {}
        elif 'tex-font-style-it' in classes:
            tag.name = 'i'
            tag.attrs = {}
        elif 'tex-font-style-tt' in classes:
            tag.name = 'code'
            tag.attrs = {}
        else:
            tag.unwrap()

def process_lists(soup):
    for ul in soup.find_all("ul"):
        items = []
        for li in ul.find_all("li"):
            text = li.decode_contents().strip()
            items.append(f"\\(\\quad\\bullet\\) {text}")
        ul.replace_with('\n'.join(items) + '\n')

    for ol in soup.find_all("ol"):
        items = []
        for idx, li in enumerate(ol.find_all("li"), 1):
            text = li.decode_contents().strip()
            items.append(f"\\(\\quad{idx}.\\) {text}")
        ol.replace_with('\n'.join(items) + '\n')

def remove_sample_tests(soup):
    st = soup.find('div', class_='sample-tests')
    if st:
        st.decompose()

def unwrap_unwanted_tags(soup):
    for tag in soup.find_all(True):
        if tag.name == 'span':
            tag.unwrap()
        elif tag.name in ALLOWED_TAGS:
            tag.attrs = {}
        else:
            if tag.name in ['p', 'div', 'section', 'article', 'center']:
                tag.insert_before('\n')
                tag.insert_after('\n')
            tag.unwrap()

def detect_language(statement):
    if statement.find(string=re.compile(r'ввод', re.IGNORECASE)) or \
       statement.find(string=re.compile(r'входные данные', re.IGNORECASE)):
        return 'ru'
    return 'en'

def fetch_statement_with_language(scraper, problem_url, language):
    url = problem_url
    if f'locale={language}' not in url:
        url += ('&' if '?' in url else '?') + f'locale={language}'
    response = scraper.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to load: {response.status_code}")
    soup = BeautifulSoup(convert_latex_blocks(response.text), 'html.parser')
    return soup

def extract_limit_text(soup, class_name, label):
    div = soup.find('div', class_=class_name)
    if not div:
        return ''
    title_div = div.find('div', class_='property-title')
    if not title_div or not title_div.next_sibling:
        return ''
    value = title_div.next_sibling.strip() if isinstance(title_div.next_sibling, str) else title_div.next_sibling.get_text(strip=True)
    return f"<b>{label}: {value}</b>"

def extract_file_info(soup, class_name, label, standard):
    div = soup.find('div', class_=class_name)
    if not div:
        return ''
    title_div = div.find('div', class_='property-title')
    if not title_div or not title_div.next_sibling:
        return ''
    value = title_div.next_sibling.strip() if isinstance(title_div.next_sibling, str) else title_div.next_sibling.get_text(strip=True)
    if standard.lower() in value.lower():
        return ''
    return f"<b>{label}: {value}</b>"

def bolden_sections(content, labels):
    for section in [labels['input_section'], labels['output_section'], labels['note_section']]:
        pattern = rf'(^|\n)(\s*{section}\s*)(\n|$)'
        replacement = rf'\1\n<b>{section.capitalize()}</b>\3'
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
    return content

def extract_problem_text(problem_url, language='ru'):
    scraper = cloudscraper.create_scraper()
    soup = fetch_statement_with_language(scraper, problem_url, language)
    statement = soup.find('div', class_='problem-statement')
    if not statement:
        raise Exception("Problem statement not found.")

    actual_language = detect_language(statement)
    if actual_language != language:
        soup = fetch_statement_with_language(scraper, problem_url, actual_language)
        statement = soup.find('div', class_='problem-statement')
        language = actual_language

    labels = LABELS[language]
    title_div = statement.find('div', class_='title')
    title = title_div.get_text(strip=True) if title_div else ''

    time_limit = extract_limit_text(statement, 'time-limit', labels['time'])
    memory_limit = extract_limit_text(statement, 'memory-limit', labels['memory'])
    input_file = extract_file_info(statement, 'input-file', labels['input'], labels['standard'])
    output_file = extract_file_info(statement, 'output-file', labels['output'], labels['standard'])

    for cls in ['title', 'time-limit', 'memory-limit', 'input-file', 'output-file']:
        tag = statement.find('div', class_=cls)
        if tag:
            tag.decompose()

    inner_html = ''.join(str(child) for child in statement.contents)
    content_soup = BeautifulSoup(inner_html, 'html.parser')

    convert_formatting_tags(content_soup)
    process_lists(content_soup)
    remove_sample_tests(content_soup)
    unwrap_unwanted_tags(content_soup)

    content = str(content_soup)
    content = bolden_sections(content, labels)
    content = html.unescape(html.unescape(content)).replace('\xa0', ' ').strip()
    content = re.sub(r'(\n\s*){3,}', '\n\n', content)

    blocks = []
    if title:
        blocks.append(f"<b>{title}</b>")
    meta = "\n".join(filter(None, [time_limit, memory_limit, input_file, output_file]))
    if meta:
        blocks.append(meta)
    blocks.append(content)

    final_text = "\n\n".join(blocks).strip()
    return {
        'title': title,
        'content': final_text
    }

if __name__ == "__main__":
    url = "https://codeforces.com/gym/102586/problem/A"
    result = extract_problem_text(url, language='ru')
    print(result['content'])
