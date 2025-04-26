import requests
from bs4 import BeautifulSoup
import re
import json

# --- Перевод через LM Studio ---
def translate_with_lm_studio(text: str) -> str:
    url = "http://127.0.0.1:1234/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    prompt = (
        "Переведи следующий китайский текст на русский язык. "
        "Сохрани формулы LaTeX, которые находятся в \\(...\\). "
        "Не добавляй никаких HTML тегов, кроме уже имеющихся.\n\n" + text
    )
    data = {
        "model": "local-model",
        "messages": [
            {"role": "system", "content": "Ты — переводчик с китайского на русский."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    result = response.json()
    return result["choices"][0]["message"]["content"].strip()

# --- LaTeX: $...$ и $$$...$$$ → \( ... \)
def normalize_latex(text: str) -> str:
    text = re.sub(r'\${3}([^$]+?)\${3}', r'\\(\1\\)', text)
    text = re.sub(r'\$([^$]+?)\$', r'\\(\1\\)', text)
    return text

# --- Очистка HTML
def clean_html(html: str) -> str:
    html = html.replace("&nbsp;", " ")
    soup = BeautifulSoup(html, "html.parser")
    for br in soup.find_all("br"):
        br.decompose()  # удаляем <br> вообще
    return soup.get_text()

# --- Основной парсер ---
def parse_acwing_problem(url: str) -> str:
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Название
    title = soup.select_one(".problem-content-title")
    title_text = title.text.strip() if title else "Без названия"
    title_ru = translate_with_lm_studio(normalize_latex(title_text))

    # Ограничения: ищем td с "时/空限制"
    time_limit = "неизвестно"
    memory_limit = "неизвестно"
    for td in soup.find_all("td"):
        if "时/空限制" in td.get_text():
            span = td.find("span")
            if span:
                match = re.match(r"([\d.]+)s\s*/\s*([\d.]+)MB", span.text.strip())
                if match:
                    time_limit = f"{match.group(1)} сек."
                    memory_limit = f"{match.group(2)} мегабайт"
            break

    # Условие задачи
    main = soup.select_one(".main-martor")
    if not main:
        raise Exception("Не найден блок с условием задачи (.main-martor)")

    html_raw = str(main)
    text = clean_html(html_raw)
    text = normalize_latex(text)
    translated = translate_with_lm_studio(text.strip())

    # Финальный HTML
    result = f"<b>Название:</b> {title_ru}\n"
    result += f"<b>Ограничение времени:</b> {time_limit}\n"
    result += f"<b>Ограничение памяти:</b> {memory_limit}\n\n"
    result += f"<p>{translated}</p>"

    return result

# --- Пример запуска ---
if __name__ == "__main__":
    url = "https://www.acwing.com/problem/content/4266/"
    print(parse_acwing_problem(url))
